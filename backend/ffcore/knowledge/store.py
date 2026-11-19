"""`KnowledgeStore`: document and chunk persistence behind one interface (KARARLAR "04a").

FFCore ships the Postgres implementation. A consumer may register another one (PayCore wraps
its DuckDB document store in its own repository; ffcore never imports it, C14).

Adapted from PayCore `ingest/store.py` (hash ownership, indexed chunk statuses) for the
Postgres data model: keys and indexes come back (DuckDB had none on purpose), chunks are
replaced inside one transaction, and ownership of a duplicate text never moves (brief D1).
"""

import hashlib
import uuid
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.ext.asyncio import AsyncSession

from ffcore.models.knowledge import Chunk, Document, KnowledgeBase


# Defined here, not in the API schemas: the knowledge core does not import the API package
# (that import closed a cycle store → api → ingest → store). No docstring: it would become the
# OpenAPI schema description.
class UploadOutcome(StrEnum):
    created = "created"
    new_version = "new_version"
    unchanged = "unchanged"


@dataclass(frozen=True)
class NewChunk:
    ordinal: int
    text: str
    breadcrumb: str
    token_count: int
    page: int | None = None
    section_path: str | None = None
    chunk_status: str = "ok"
    chunk_reason: str | None = None

    @property
    def text_hash(self) -> str:
        return text_hash(self.text)


def text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sparse_to_json(weights: dict[int, float] | None) -> dict[str, float] | None:
    """jsonb keys are strings; token ids go back to int on the way out (sparse_from_json)."""
    if weights is None:
        return None
    return {str(int(k)): float(v) for k, v in weights.items()}


def sparse_from_json(value: dict | None) -> dict[int, float] | None:
    if value is None:
        return None
    return {int(k): float(v) for k, v in value.items()}


class KnowledgeStore(Protocol):
    async def register_upload(
        self,
        kb: KnowledgeBase,
        *,
        filename: str,
        sha256: str,
        size: int,
        raw_path: str,
        acl_roles: list[str],
        acl_users: list[uuid.UUID],
        created_by: str,
    ) -> tuple[Document, UploadOutcome]: ...

    async def text_hash_owner(
        self, kb_id: uuid.UUID, document_text_hash: str, document_id: uuid.UUID
    ) -> uuid.UUID | None: ...

    async def replace_chunks(
        self, document: Document, chunks: list[NewChunk], embedding_model: str
    ) -> list[Chunk]: ...

    async def reusable_vectors(
        self, kb_id: uuid.UUID, hashes: list[str], embedding_model: str
    ) -> dict[str, list[float]]: ...


class PgKnowledgeStore:
    """Every method works inside the caller's session; the caller commits (one unit of work)."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def register_upload(
        self,
        kb: KnowledgeBase,
        *,
        filename: str,
        sha256: str,
        size: int,
        raw_path: str,
        acl_roles: list[str],
        acl_users: list[uuid.UUID],
        created_by: str,
    ) -> tuple[Document, UploadOutcome]:
        """Same file name in the KB: the same record (brief 04 acceptance 4); new bytes are
        version + 1. Identical bytes (sha256) keep the version and the converted layers and
        queue nothing (FOLLOWUP-157); only an ACL change is applied."""
        current = await self.session.scalar(
            select(Document)
            .where(
                Document.kb_id == kb.id,
                Document.filename == filename,
                Document.deleted_at.is_(None),
            )
            .with_for_update()
        )
        if current is None:
            document = Document(
                id=uuid.uuid4(),
                project_id=kb.project_id,
                kb_id=kb.id,
                filename=filename,
                sha256=sha256,
                size=size,
                raw_path=raw_path,
                status="pending",
                acl_roles=acl_roles,
                acl_users=acl_users,
                meta={},
                version=1,
                created_by=created_by,
            )
            self.session.add(document)
            await self.session.flush()
            return document, UploadOutcome.created
        current.acl_roles = acl_roles
        current.acl_users = acl_users
        if current.sha256 == sha256:
            # FOLLOWUP-157: identical bytes are not a new version (nothing is reprocessed).
            await self.session.flush()
            return current, UploadOutcome.unchanged
        current.version += 1
        current.sha256 = sha256
        current.size = size
        current.raw_path = raw_path
        current.status = "pending"
        current.error = None
        for gate in ("gate0", "gate1", "gate2"):
            setattr(current, f"{gate}_status", None)
            setattr(current, f"{gate}_reason", None)
        await self.session.flush()
        return current, UploadOutcome.new_version

    async def text_hash_owner(
        self, kb_id: uuid.UUID, document_text_hash: str, document_id: uuid.UUID
    ) -> uuid.UUID | None:
        """The live document that first held this normalized text (oldest wins, stable)."""
        return await self.session.scalar(
            select(Document.id)
            .where(
                Document.kb_id == kb_id,
                Document.text_hash == document_text_hash,
                Document.id != document_id,
                Document.duplicate_of.is_(None),
                Document.deleted_at.is_(None),
            )
            .order_by(Document.created_at, Document.id)
            .limit(1)
        )

    async def reusable_vectors(
        self, kb_id: uuid.UUID, hashes: list[str], embedding_model: str
    ) -> dict[str, list[float]]:
        """Vectors of chunks with the same text and model (brief D3): taken over, not re-embedded.
        Call before replace_chunks, which deletes the document's previous chunks."""
        reusable = await self.reusable_embeddings(kb_id, hashes, embedding_model)
        return {h: dense for h, (dense, _) in reusable.items()}

    async def reusable_embeddings(
        self, kb_id: uuid.UUID, hashes: list[str], embedding_model: str
    ) -> dict[str, tuple[list[float], dict[int, float] | None]]:
        """Dense vector and sparse weights per text hash (04b S2): a row that has sparse weights
        is preferred; a row written before 04b gives None (the caller decides, never silently)."""
        if not hashes:
            return {}
        rows = await self.session.execute(
            select(Chunk.text_hash, Chunk.embedding, Chunk.sparse)
            .where(
                Chunk.kb_id == kb_id,
                Chunk.text_hash.in_(hashes),
                Chunk.embedding_model == embedding_model,
                Chunk.embedding.is_not(None),
            )
            .order_by(Chunk.text_hash, Chunk.sparse.is_(None))
            .ext(distinct_on(Chunk.text_hash))
        )
        return {h: ([float(x) for x in vec], sparse_from_json(sparse)) for h, vec, sparse in rows}

    async def replace_chunks(
        self, document: Document, chunks: list[NewChunk], embedding_model: str
    ) -> list[Chunk]:
        await self.session.execute(delete(Chunk).where(Chunk.document_id == document.id))
        rows = [
            Chunk(
                id=uuid.uuid4(),
                document_id=document.id,
                kb_id=document.kb_id,
                ordinal=c.ordinal,
                text=c.text,
                token_count=c.token_count,
                char_count=len(c.text),
                page=c.page,
                section_path=c.section_path,
                breadcrumb=c.breadcrumb,
                embedding_model=embedding_model,
                chunk_status=c.chunk_status,
                chunk_reason=c.chunk_reason,
                text_hash=c.text_hash,
            )
            for c in chunks
        ]
        self.session.add_all(rows)
        await self.session.flush()
        return rows

    async def chunk_count(self, document_id: uuid.UUID) -> int:
        return await self.session.scalar(
            select(func.count()).select_from(Chunk).where(Chunk.document_id == document_id)
        )

    async def set_status(self, document_id: uuid.UUID, status: str, error: str | None = None):
        await self.session.execute(
            update(Document).where(Document.id == document_id).values(status=status, error=error)
        )
