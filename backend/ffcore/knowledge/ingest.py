"""Ingest: raw → silver → gold for one document (brief 04 pipeline steps 1-9, D1-D3, D5).

Adapted from PayCore `ingest/sync.py` (run_silver/run_gold: Kapı 0-2, attachments with
`Ek: <file>` breadcrumbs, `_reuse_vectors`, `flag_truncated`) for the Postgres model:
  raw    data/storage/raw/{project}/{kb}/{source}/{document}/original.<ext>  (never user paths)
  silver data/storage/silver/{project}/{kb}/{source}/{document}.md + YAML frontmatter
  gold   chunks (text + vector) in Postgres and the selected vector store
Every elimination is a gate status with a reason; nothing is dropped silently (ARCH-06).
The worker never loads the embedding model: it asks the API (`POST /internal/embed`, C10).
"""

import asyncio
import atexit
import hashlib
import logging
import re
import time
import uuid
from collections import Counter
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO, Protocol

import yaml
from sqlalchemy import select

from ffcore.core import db
from ffcore.core.config import Settings
from ffcore.knowledge import gates, ingest_mask, raw_staging, scope
from ffcore.knowledge.chunking import (
    BREADCRUMB_SEPARATOR,
    ChunkingError,
    ChunkSettings,
    chunk_markdown,
)
from ffcore.knowledge.convert import pipeline as convert_pipeline
from ffcore.knowledge.convert.types import CONVERTED, TIMEOUT, ConversionResult
from ffcore.knowledge.convert.workers import Limits, PersistentPool
from ffcore.knowledge.embed import Embeddings, get_embedder, token_counter
from ffcore.knowledge.normalize import NORMALIZER_CONFIG_ID, clean_markdown
from ffcore.knowledge.store import NewChunk, PgKnowledgeStore, text_hash
from ffcore.knowledge.vectorstore.base import VectorRecord, VectorStore, VectorStoreError
from ffcore.models.knowledge import Attachment, Chunk, Document, KnowledgeBase

log = logging.getLogger("ffcore.knowledge.ingest")

UPLOAD_SOURCE = "upload"
_EXT = re.compile(r"^[a-z0-9]{1,10}$")


# --- embedding clients: the API embeds in process, the worker asks the API ---


class EmbedClient(Protocol):
    model: str

    async def embed(self, texts: list[str]) -> Embeddings: ...


class LocalEmbedClient:
    """In the API process (and tests): the process-wide embedder behind its model lock."""

    def __init__(self, settings: Settings, embedder=None):
        self._embedder = embedder or get_embedder(settings)
        self.model = self._embedder.model

    async def embed(self, texts: list[str]) -> Embeddings:
        return await asyncio.to_thread(self._embedder.encode, texts)


class HttpEmbedClient:
    """In the ingest worker: POST /internal/embed with the service token (SafeOutboundClient)."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self.model = settings.embed_model

    async def embed(self, texts: list[str]) -> Embeddings:
        from ffcore.core.auth import service_authorization
        from ffcore.core.egress import EgressTimeout, SafeOutboundClient

        timeout = EgressTimeout(connect=5, read=600, total=900)
        async with SafeOutboundClient(timeout=timeout, settings=self._settings) as client:
            response = await client.request(
                "POST",
                f"{self._settings.internal_api_url.rstrip('/')}/internal/embed",
                headers=service_authorization(self._settings),
                json={"texts": texts},
            )
        if response.status_code != 200:
            raise RuntimeError(f"internal embed failed: {response.status_code}")
        body = response.json()
        if body["model"] != self.model:
            raise RuntimeError(f"API embeds with {body['model']}, worker expects {self.model}")
        sparse = [{int(k): v for k, v in w.items()} for w in body["sparse"]]
        return Embeddings(body["dense"], sparse, body["truncated"])


# --- conversion: in a bounded worker process (timeout kill) or inline ---

Converter = Callable[[Path, str, Settings], ConversionResult]


_pools: dict[tuple[int, int, Limits], PersistentPool] = {}


def close_pools() -> None:
    """Stop the long-lived converter processes (registered at exit: they are not daemons, so
    an exiting interpreter would otherwise wait for them forever)."""
    for pool in list(_pools.values()):
        pool.close()
    _pools.clear()


atexit.register(close_pools)


def convert_bounded(path: Path, filename: str, settings: Settings) -> ConversionResult:
    """Convert in this process's long-lived worker (timeout kill, models loaded once)."""
    timeout = settings.convert_timeout_seconds
    start_timeout = settings.convert_worker_start_timeout_seconds
    limits = Limits(settings.convert_memory_limit_mb, settings.convert_cpu_limit_seconds)
    key = (timeout, start_timeout, limits)
    pool = _pools.get(key)
    if pool is None:
        pool = _pools[key] = PersistentPool(
            timeout=timeout,
            name="ingest",
            target=convert_pipeline.CONVERT_TARGET,
            limits=limits,
            start_timeout=start_timeout,
        )
    return pool.convert(path)


def convert_inline(path: Path, filename: str, settings: Settings) -> ConversionResult:
    """Same converters in this process, without the kill guarantee: tests and CLI only."""
    return convert_pipeline.convert_one(path, time.time() + settings.convert_timeout_seconds)


# --- storage layout ---


def _root(settings: Settings) -> Path:
    return Path(settings.knowledge_storage_dir)


def raw_dir(settings: Settings, document: Document, source: str = UPLOAD_SOURCE) -> Path:
    return (
        _root(settings)
        / "raw"
        / str(document.project_id)
        / str(document.kb_id)
        / source
        / str(document.id)
    )


def silver_path(settings: Settings, document: Document, source: str = UPLOAD_SOURCE) -> Path:
    return (
        _root(settings)
        / "silver"
        / str(document.project_id)
        / str(document.kb_id)
        / source
        / f"{document.id}.md"
    )


def _raw_name(filename: str) -> str:
    # The stored name is ours; only a sane extension survives from the user's name, so the
    # router can still see it.
    ext = scope.extension(filename)
    return f"original.{ext}" if _EXT.match(ext) else "original"


@dataclass
class IngestReport:
    document_id: uuid.UUID
    status: str
    reused: int = 0
    embedded: int = 0


STAGE_CHUNK_BYTES = 1024 * 1024


@dataclass(frozen=True)
class StagedUpload:
    """One uploaded file streamed to disk: hash and size of every byte; `path` is None when
    the file passed Kapı 0's size limit (nothing of it is kept)."""

    sha256: str
    size: int
    path: Path | None


def stage_upload(source: BinaryIO, filename: str, settings: Settings) -> StagedUpload:
    """Copy an upload in 1 MiB pieces (review r1 MAJOR-5): memory stays bounded and bytes
    past the size limit are hashed and counted, never written."""
    limit = scope.max_bytes(filename)
    staging = Path(settings.knowledge_storage_dir) / "staging"
    staging.mkdir(parents=True, exist_ok=True)
    path = staging / uuid.uuid4().hex
    digest, size = hashlib.sha256(), 0
    with path.open("wb") as out:
        while chunk := source.read(STAGE_CHUNK_BYTES):
            digest.update(chunk)
            size += len(chunk)
            if size <= limit:
                out.write(chunk)
    if size > limit:
        path.unlink()
        return StagedUpload(digest.hexdigest(), size, None)
    return StagedUpload(digest.hexdigest(), size, path)


async def register_upload(
    session,
    kb_id: uuid.UUID,
    *,
    filename: str,
    data: bytes | None = None,
    staged: StagedUpload | None = None,
    acl_roles: list[str],
    acl_users: list[uuid.UUID],
    created_by: str,
    settings: Settings,
    vector_store: VectorStore | None = None,
):
    """Pipeline step 1 for a manual upload: sha256, version, Kapı 0 (scope, size), raw file.

    The content is `data` (tests, small inputs) or a `staged` file (the API). Kapı 0 runs before
    the raw write: a refused file is recorded with its reason and never stored (r1 MAJOR-5).

    An ACL change of an existing document is pushed to `vector_store` before this returns,
    also when the bytes are unchanged and nothing is re-indexed (review r1 MAJOR-1). A store
    failure raises: the caller's transaction (and the ACL change) is rolled back, fail-loud.
    """
    try:
        return await _register(
            session,
            kb_id,
            filename,
            data,
            staged,
            acl_roles,
            acl_users,
            created_by,
            settings,
            vector_store,
        )
    finally:
        if staged is not None and staged.path is not None:
            staged.path.unlink(missing_ok=True)


async def _register(
    session,
    kb_id,
    filename,
    data,
    staged,
    acl_roles,
    acl_users,
    created_by,
    settings,
    vector_store,
):
    kb = await session.get(KnowledgeBase, kb_id)
    if data is not None:
        sha, size = hashlib.sha256(data).hexdigest(), len(data)
    else:
        sha, size = staged.sha256, staged.size
    previous = (
        await session.execute(
            select(Document.id, Document.acl_roles, Document.acl_users).where(
                Document.kb_id == kb_id,
                Document.filename == filename,
                Document.deleted_at.is_(None),
            )
        )
    ).first()
    document, outcome = await PgKnowledgeStore(session).register_upload(
        kb,
        filename=filename,
        sha256=sha,
        size=size,
        raw_path="",
        acl_roles=acl_roles,
        acl_users=acl_users,
        created_by=created_by,
    )
    if outcome != "unchanged":
        status, reason = scope.gate0_upload(filename, size)
        document.gate0_status, document.gate0_reason = status, reason
        document.status = "skipped" if status == "skipped" else "pending"
        if status != "skipped":
            target = raw_dir(settings, document) / _raw_name(filename)
            target.parent.mkdir(parents=True, exist_ok=True)
            if data is not None:
                target.write_bytes(data)
            else:
                staged.path.replace(target)
            document.raw_path = str(target)
    await session.flush()
    if previous is not None and vector_store is not None:
        before = (sorted(previous.acl_roles), sorted(map(str, previous.acl_users)))
        after = (sorted(acl_roles), sorted(map(str, acl_users)))
        if before != after:
            await vector_store.update_acl(kb_id, document.id, acl_roles, acl_users)
    # Server-side timestamps expire on flush; load them now, not lazily in sync code later.
    await session.refresh(document)
    return document, outcome


def _frontmatter(document: Document, kb: KnowledgeBase, convert_engine: str, breadcrumb: str):
    return {
        "document_id": str(document.id),
        "kb": kb.key,
        "breadcrumb": breadcrumb,
        "filename": document.filename,
        "acl_roles": list(document.acl_roles),
        "acl_users": [str(u) for u in document.acl_users],
        "gate0": [document.gate0_status, document.gate0_reason],
        "gate1": [document.gate1_status, document.gate1_reason],
        "gate2": [document.gate2_status, document.gate2_reason],
        "converter": convert_engine,
        "normalizer_config_id": NORMALIZER_CONFIG_ID,
    }


def _write_silver(path: Path, front: dict, body: str, raw_text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = yaml.safe_dump(front, allow_unicode=True, sort_keys=False)
    path.write_bytes(f"---\n{header}---\n\n{body}\n".encode())
    # text_raw: the converter's output before normalization, so a normalizer change re-runs
    # from here without converting again (brief D3).
    path.with_suffix(".raw.md").write_bytes(raw_text.encode())


def read_silver(path: Path) -> str:
    text = path.read_bytes().decode("utf-8")
    if text.startswith("---\n"):
        text = text.split("\n---\n", 1)[1]
    return text.strip()


async def _attachment_texts(
    session,
    document: Document,
    names: list[str],
    raw: Path,
    settings,
    convert: Converter,
    text_filter: Callable[[str], Awaitable[str]] | None = None,
    personnel_data: bool = False,
) -> list[tuple[str, str]]:
    """Convert the document's attachments; data dumps and low quality are recorded, not used.

    The shown name (attachment row, silver heading, chunk breadcrumb) is inside the personnel-data
    boundary (r1 MAJOR-4): `Ek <n>` in a personnel-data source, otherwise the name through the
    text filter with `_`/`-` read as spaces. Gate 0 and the converter see the real file name;
    `raw_path` is the real file."""
    texts = []
    for n, name in enumerate(names, 1):
        path = raw / name
        if personnel_data:
            shown = f"Ek {n}"
        elif text_filter is not None:
            shown = await text_filter(re.sub(r"[_-]+", " ", name))
        else:
            shown = name
        attachment = Attachment(
            id=uuid.uuid4(),
            document_id=document.id,
            filename=shown,
            size=path.stat().st_size,
            raw_path=str(path),
        )
        session.add(attachment)
        attachment.gate0_status, attachment.gate0_reason = scope.gate0_upload(name, attachment.size)
        if attachment.gate0_status == "skipped":
            continue
        started = time.monotonic()
        result = convert(path, name, settings)
        attachment.convert_engine = result.method
        attachment.convert_seconds = round(time.monotonic() - started, 3)
        if result.status != CONVERTED:
            attachment.gate2_status, attachment.gate2_reason = "skipped", result.status
            continue
        text = clean_markdown(result.text_md)
        if text_filter is not None:
            text = await text_filter(text)
        dump = gates.data_dump(text)
        if dump:
            attachment.gate2_status, attachment.gate2_reason = "skipped", f"data_dump:{dump}"
            continue
        verdict = gates.text_quality(text, title=shown)
        attachment.gate2_status, attachment.gate2_reason = verdict
        if verdict[0] != "skipped":
            texts.append((shown, text))
    await session.flush()
    return texts


class _CountingFilter:
    """A named text filter with its per-category counts for this document (counts only)."""

    def __init__(self, name: str) -> None:
        self.filter = ingest_mask.resolve(name)
        self.counts: Counter = Counter()

    async def __call__(self, text: str) -> str:
        masked, found = await self.filter.mask(text)
        self.counts.update(found)
        return masked


def _text_filter(document: Document) -> _CountingFilter | None:
    """The filter the document was registered with (`<name>@<version>`, 19); a reindex from raw
    applies the same one. An unknown name fails the document loudly, never passes unmasked."""
    label = (document.meta or {}).get("text_filter")
    if label is None:
        return None
    return _CountingFilter(str(label).split("@", 1)[0])


def _fail(document: Document, status: str, result: ConversionResult) -> None:
    document.status = status
    message = (result.warnings or [result.status])[0]
    document.error = f"{result.error_code or result.status}: {message}"[:1000]


async def ingest_document(
    document_id: uuid.UUID,
    *,
    settings: Settings,
    store: VectorStore,
    embed_client: EmbedClient,
    convert: Converter = convert_bounded,
    attachments: list[str] | None = None,
) -> IngestReport:
    async with db.session_scope() as session:
        document = await session.get(Document, document_id, with_for_update=True)
        kb = await session.get(KnowledgeBase, document.kb_id)
        if document.gate0_status == "skipped":
            document.status = "skipped"
            await session.commit()
            return IngestReport(document_id, "skipped")
        raw = Path(document.raw_path)
        document.status, document.error = "converting", None
        started = time.monotonic()
        result = await asyncio.to_thread(convert, raw, document.filename, settings)
        document.convert_engine = result.method
        document.convert_seconds = round(time.monotonic() - started, 3)
        document.page_count = result.page_count
        if result.status == TIMEOUT:
            _fail(document, "timeout", result)
            await session.commit()
            return IngestReport(document_id, "timeout")
        if result.status.startswith("skipped_") and result.status != "skipped_empty":
            # Format refused by content sniffing (e.g. a zip under another name): Kapı 0.
            document.gate0_status = "skipped"
            document.gate0_reason = result.status.removeprefix("skipped_")
            document.status = "skipped"
            await session.commit()
            return IngestReport(document_id, "skipped")
        if result.status not in (CONVERTED, "skipped_empty"):
            _fail(document, "failed", result)
            await session.commit()
            return IngestReport(document_id, "failed")

        text_md, masking = result.text_md, _text_filter(document)
        if masking is not None:
            # 19: raw stays byte for byte; silver (and text_raw beside it) is masked before it
            # is written, so gold and the model only ever see the masked text (K-M3S-0003).
            text_md = await masking(text_md)
        body = clean_markdown(text_md)
        if masking is not None:
            body = await masking(body)
        source = (document.meta or {}).get("source")
        extra = await _attachment_texts(
            session,
            document,
            attachments or [],
            raw.parent,
            settings,
            convert,
            masking,
            # The staging rule (source or path), r2 MINOR-r2-1; filename is the tree relpath.
            personnel_data=raw_staging.personnel_data(str(source or ""), document.filename),
        )
        if masking is not None:
            document.meta = {**document.meta, "text_filter_counts": dict(masking.counts)}
        # A connector's breadcrumb (C6 metadata) wins over the file name (16, 19: D5).
        breadcrumb = document.meta.get("breadcrumb") or document.filename
        breadcrumb = f"{kb.name}{BREADCRUMB_SEPARATOR}{breadcrumb}"
        document.breadcrumb = breadcrumb
        document.normalizer_config_id = NORMALIZER_CONFIG_ID
        document.text_hash = text_hash(body)
        store_ = PgKnowledgeStore(session)
        owner = await store_.text_hash_owner(kb.id, document.text_hash, document.id)
        document.duplicate_of = owner
        document.gate1_status, document.gate1_reason = gates.gate1(
            body,
            title=document.filename,
            duplicate_of=str(owner) if owner else None,
            has_attachment_text=bool(extra),
            allowed_languages=tuple(settings.allowed_languages),
        )
        document.status = "gated"
        if document.gate1_status != "skipped":
            document.gate2_status, document.gate2_reason = gates.text_quality(
                body, title=document.filename, min_tokens=gates.DEFAULT.min_doc_tokens
            )
        full_text = body + "".join(f"\n\n# Ek: {name}\n\n{text}" for name, text in extra)
        silver = silver_path(settings, document)
        _write_silver(
            silver, _frontmatter(document, kb, result.method, breadcrumb), full_text, text_md
        )
        document.silver_path = str(silver)
        final = gates.combine(
            (document.gate1_status, document.gate1_reason),
            (document.gate2_status, document.gate2_reason) if document.gate2_status else None,
        )
        if final[0] == "skipped":
            # Vector store first: the pgvector driver updates chunks in its own session and would
            # wait forever on rows this transaction already deleted (review r1 MAJOR-2).
            await store.delete_by_document(document.id)
            await store_.replace_chunks(document, [], embed_client.model)
            document.status = "skipped"
            await session.commit()
            return IngestReport(document_id, "skipped")
        await session.commit()
    return await _gold(document_id, settings=settings, store=store, embed_client=embed_client)


def _chunks_for(kb: KnowledgeBase, document: Document, silver_text: str, count) -> list[NewChunk]:
    settings = ChunkSettings.from_kb(kb.chunk_size, kb.chunk_overlap, count)
    out, seen = [], set()
    pieces = silver_text.split("\n\n# Ek: ")
    sections = [(document.breadcrumb, pieces[0])]
    for piece in pieces[1:]:
        name, _, text = piece.partition("\n\n")
        sections.append((f"{document.breadcrumb}{BREADCRUMB_SEPARATOR}Ek: {name}", text))
    for crumb, text in sections:
        for chunk in chunk_markdown(text, breadcrumb=crumb, settings=settings):
            body_hash = text_hash(chunk.body)
            duplicate = "previous chunk" if body_hash in seen else None
            seen.add(body_hash)
            status, reason = gates.text_quality(chunk.body, title=None, duplicate_of=duplicate)
            if duplicate:
                reason = "duplicate_in_document"
            out.append(
                NewChunk(
                    ordinal=len(out),
                    text=chunk.text,
                    breadcrumb=chunk.breadcrumb,
                    token_count=chunk.token_count,
                    page=chunk.page,
                    section_path=chunk.section_path,
                    chunk_status=status,
                    chunk_reason=reason,
                )
            )
    return out


async def _gold(
    document_id: uuid.UUID, *, settings: Settings, store: VectorStore, embed_client: EmbedClient
) -> IngestReport:
    """Chunk the silver text, take over vectors of unchanged chunks, embed the rest (D3)."""
    async with db.session_scope() as session:
        document = await session.get(Document, document_id, with_for_update=True)
        kb = await session.get(KnowledgeBase, document.kb_id)
        document.status = "chunking"
        try:
            new_chunks = _chunks_for(
                kb, document, read_silver(Path(document.silver_path)), token_counter(settings)
            )
        except ChunkingError as exc:
            # Fail loud (review r1 MAJOR-4): no chunk over the limit, no silent cut.
            await session.rollback()
            await _set_status(document_id, "failed", str(exc)[:1000])
            log.error("gold document=%s chunking failed: %s", document_id, exc.code)
            return IngestReport(document_id, "failed")
        store_ = PgKnowledgeStore(session)
        indexable = [c for c in new_chunks if c.chunk_status != "skipped"]
        reusable = await store_.reusable_vectors(
            kb.id, [c.text_hash for c in indexable], embed_client.model
        )
        rows = await store_.replace_chunks(document, new_chunks, embed_client.model)
        document.status = "embedding"
        todo = [r for r in rows if r.chunk_status != "skipped" and r.text_hash not in reusable]
        vectors: dict[uuid.UUID, tuple[list[float], dict[int, float]]] = {}
        for start in range(0, len(todo), settings.embed_batch_size):
            batch = todo[start : start + settings.embed_batch_size]
            result = await embed_client.embed([r.text for r in batch])
            for row, dense, sparse, cut in zip(
                batch, result.dense, result.sparse, result.truncated, strict=True
            ):
                vectors[row.id] = (dense, sparse)
                if cut:
                    row.chunk_status, row.chunk_reason = "flagged", "embedding_truncated"
        records = []
        for row in rows:
            if row.chunk_status == "skipped":
                continue
            if row.id in vectors:
                dense, sparse = vectors[row.id]
            else:
                # Reused vectors carry no sparse weights; the Qdrant driver needs them, so a
                # reused chunk there is re-embedded below rather than indexed half.
                dense, sparse = reusable[row.text_hash], None
            row.embedding = dense
            records.append(
                VectorRecord(
                    chunk_id=row.id,
                    kb_id=kb.id,
                    document_id=document.id,
                    dense=dense,
                    sparse=sparse,
                    acl_roles=tuple(document.acl_roles),
                    acl_users=tuple(str(u) for u in document.acl_users),
                    page=row.page,
                    section_path=row.section_path,
                    metadata=dict(document.meta),
                )
            )
        if store.name == "qdrant":
            missing = [i for i, r in enumerate(records) if r.sparse is None]
            if missing:
                result = await embed_client.embed(
                    [next(x.text for x in rows if x.id == records[i].chunk_id) for i in missing]
                )
                for i, sparse in zip(missing, result.sparse, strict=True):
                    rec = records[i]
                    records[i] = VectorRecord(**{**rec.__dict__, "sparse": sparse})
        await session.flush()
        reused = sum(1 for row in rows if row.chunk_status != "skipped" and row.id not in vectors)
        # Not searchable yet: search reads only `indexed` documents (review r1 MAJOR-3).
        document.status = "embedding"
        await session.commit()
    try:
        await store.ensure_collection(kb.id, settings.embed_dim)
        if store.name == "qdrant":
            await store.delete_by_document(document_id)
        await store.upsert(records)
    except VectorStoreError as exc:
        # The rows stay (a retry re-publishes them idempotently); the status says what failed.
        await _set_status(document_id, "failed", f"{exc.code}: vector publication failed")
        log.error("gold document=%s publication failed: %s", document_id, exc.code)
        return IngestReport(document_id, "failed", reused=reused, embedded=len(vectors))
    await _set_status(document_id, "indexed", None)
    log.info("gold document=%s reused=%d embedded=%d", document_id, reused, len(vectors))
    return IngestReport(document_id, "indexed", reused=reused, embedded=len(vectors))


async def _set_status(document_id: uuid.UUID, status: str, error: str | None) -> None:
    async with db.session_scope() as session:
        document = await session.get(Document, document_id, with_for_update=True)
        document.status, document.error = status, error
        await session.commit()


def _source_date(value: str | datetime) -> datetime:
    """A connector's source date (ISO 8601; a bare date is midnight UTC). Not a date: ValueError,
    the document is not registered with a guessed date."""
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


async def ingest_from_raw(
    raw_path: str,
    metadata: dict,
    acl: dict,
    *,
    settings: Settings,
    store: VectorStore,
    embed_client: EmbedClient,
    convert: Converter = convert_bounded,
    text_filter: ingest_mask.TextFilterName | None = None,
) -> uuid.UUID:
    """C6 entry point for source connectors (16): content already in raw is converted and
    indexed. metadata: kb_id, filename, optional source, source_item_id, attachments (names next
    to raw_path), updated_at_source, breadcrumb; acl: roles, users. `text_filter` (19, additive):
    a named filter applied to silver and gold, never to raw; recorded as `<name>@<version>`."""
    label = ingest_mask.resolve(text_filter).label if text_filter is not None else None
    path = Path(raw_path)
    async with db.session_scope() as session:
        kb = await session.get(KnowledgeBase, uuid.UUID(str(metadata["kb_id"])))
        document, _ = await PgKnowledgeStore(session).register_upload(
            kb,
            filename=metadata.get("filename", path.name),
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            size=path.stat().st_size,
            raw_path=str(path),
            acl_roles=list(acl.get("roles", [])),
            acl_users=[uuid.UUID(str(u)) for u in acl.get("users", [])],
            created_by="ingest_from_raw",
        )
        document.raw_path = str(path)
        document.source_item_id = metadata.get("source_item_id")
        document.meta = {
            k: v for k, v in metadata.items() if k not in {"kb_id", "attachments", "filename"}
        }
        if label is not None:
            # Silver frontmatter, documents.breadcrumb and search results read these fields:
            # masked before they are stored, like the body (r1 MAJOR-2).
            document.meta, meta_counts = await ingest_mask.mask_metadata(
                ingest_mask.resolve(text_filter), document.meta
            )
            document.meta["text_filter"] = label
            document.meta["text_filter_meta_counts"] = dict(meta_counts)
        if metadata.get("updated_at_source") is not None:
            # The column orders search results (FOLLOWUP-101); the metadata copy stays as given.
            document.updated_at_source = _source_date(metadata["updated_at_source"])
        document.gate0_status, document.gate0_reason = scope.gate0_upload(
            document.filename, document.size
        )
        document_id = document.id
        await session.commit()
    await ingest_document(
        document_id,
        settings=settings,
        store=store,
        embed_client=embed_client,
        convert=convert,
        attachments=list(metadata.get("attachments", [])),
    )
    return document_id


@dataclass
class ReindexReport:
    documents: int = 0
    reused: int = 0
    embedded: int = 0


class ReindexRefused(Exception):
    """A reindex refused before it touched any document (code, path; never content)."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code


def _silver_scope(kb_id: uuid.UUID, full: bool):
    statement = select(Document.id, Document.filename, Document.meta).where(
        Document.kb_id == kb_id, Document.deleted_at.is_(None)
    )
    if not full:
        statement = statement.where(Document.status.in_(("failed", "timeout", "pending")))
    return statement


async def check_reindex_silver(
    kb_id: uuid.UUID, *, full: bool, accept_personnel_data: bool = False
) -> int:
    """r2 NOTE-5 (KARARLAR "08 tam 1b r2 ekleri"): a personnel-data record written with
    `pii_regex` (the M3 mode, names not masked) is reconverted only with
    `--accept-personnel-data`; otherwise the whole reindex is refused before any document is
    touched (`prsim_requires_ner`). The same personnel-data rule as staging (MINOR-r2-1).

    With the flag the reindex goes on and the number of such records in scope is returned and
    logged (FOLLOWUP-172 N2: the M3 mode is visible, as ingest-raw's is)."""
    async with db.session_scope() as session:
        rows = (await session.execute(_silver_scope(kb_id, full))).all()
    personnel = 0
    for _, filename, meta in rows:
        meta = meta or {}
        label = str(meta.get("text_filter") or "")
        if label.startswith("pii_regex@") and raw_staging.personnel_data(
            str(meta.get("source") or ""), filename
        ):
            if not accept_personnel_data:
                raise ReindexRefused(
                    "prsim_requires_ner",
                    f"{filename} is personnel data written with {label} (the M3 mode); reindex "
                    "it with --accept-personnel-data or ingest it again with pii_ner",
                )
            personnel += 1
    if accept_personnel_data:
        log.warning(
            "reindex accept_personnel_data is the M3 measurement mode (pii_regex, names not "
            "masked) kb=%s records=%d",
            kb_id,
            personnel,
        )
    return personnel


async def reindex_gold(
    kb_id: uuid.UUID,
    *,
    full: bool,
    settings: Settings,
    store: VectorStore,
    embed_client: EmbedClient,
) -> ReindexReport:
    """`make reindex LAYER=gold`: from silver only, never raw or the source (D3)."""
    async with db.session_scope() as session:
        statement = select(Document.id).where(
            Document.kb_id == kb_id,
            Document.deleted_at.is_(None),
            Document.silver_path.is_not(None),
            Document.status.in_(
                ("indexed",) if not full else ("indexed", "embedding", "chunking", "failed")
            ),
        )
        ids = list((await session.scalars(statement)).all())
    report = ReindexReport()
    for document_id in ids:
        result = await _gold(document_id, settings=settings, store=store, embed_client=embed_client)
        report.documents += 1
        report.reused += result.reused
        report.embedded += result.embedded
    log.info("reindex gold kb=%s reused=%d embedded=%d", kb_id, report.reused, report.embedded)
    return report


async def reindex_silver(
    kb_id: uuid.UUID,
    *,
    full: bool,
    settings: Settings,
    store: VectorStore,
    embed_client: EmbedClient,
    convert: Converter = convert_bounded,
    accept_personnel_data: bool = False,
) -> ReindexReport:
    """`make reindex LAYER=silver`: reconvert from raw (never the source); then gold. Refused
    as a whole when an M3 personnel-data record is in scope without the flag (r2 NOTE-5)."""
    await check_reindex_silver(kb_id, full=full, accept_personnel_data=accept_personnel_data)
    async with db.session_scope() as session:
        ids = [row[0] for row in (await session.execute(_silver_scope(kb_id, full))).all()]
    report = ReindexReport()
    for document_id in ids:
        result = await ingest_document(
            document_id, settings=settings, store=store, embed_client=embed_client, convert=convert
        )
        report.documents += 1
        report.reused += result.reused
        report.embedded += result.embedded
    return report


async def chunk_count(session, document_id: uuid.UUID) -> int:
    return await PgKnowledgeStore(session).chunk_count(document_id)


__all__ = [
    "Chunk",
    "HttpEmbedClient",
    "IngestReport",
    "LocalEmbedClient",
    "convert_bounded",
    "convert_inline",
    "ingest_document",
    "ingest_from_raw",
    "register_upload",
    "ReindexRefused",
    "check_reindex_silver",
    "reindex_gold",
    "reindex_silver",
]
