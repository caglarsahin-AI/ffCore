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
from typing import Protocol

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.ext.asyncio import AsyncSession

from ffcore.api.knowledge_schemas import UploadOutcome
from ffcore.models.knowledge import Chunk, Document, KnowledgeBase


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
        """Same file name in the KB: the same record, version + 1 (brief 04 acceptance 4).
        Identical bytes (sha256) keep the converted layers and queue nothing."""
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
        current.version += 1
        current.acl_roles = acl_roles
        current.acl_users = acl_users
        if current.sha256 == sha256:
            await self.session.flush()
            return current, UploadOutcome.unchanged
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
        if not hashes:
            return {}
        rows = await self.session.execute(
            select(Chunk.text_hash, Chunk.embedding)
            .where(
                Chunk.kb_id == kb_id,
                Chunk.text_hash.in_(hashes),
                Chunk.embedding_model == embedding_model,
                Chunk.embedding.is_not(None),
            )
            .ext(distinct_on(Chunk.text_hash))
        )
        return {h: list(vec) for h, vec in rows}

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
