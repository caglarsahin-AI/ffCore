"""`migrate-vectors`: copy a knowledge base's vectors between pgvector and Qdrant (04b D1).

Postgres `chunks` is the source of truth on both roads (chunk text, dense vector, sparse
weights, the document's ACL). Embeddings are never recomputed (brief 04): pgvector → Qdrant
upserts the stored dense vector, its sparse weights and the ACL payload read now; Qdrant →
pgvector fills `chunks.embedding` of rows that lack it from the Qdrant points. A row written
before 04b has no sparse weights; only those are computed (`sparse_computed`), and counted
(K-04B-0002 S2 A). Dry run counts, writes nothing (`sparse_missing`).

The check is per knowledge base: the vectors the target holds equal the vectors the source
holds, otherwise the run is not ok (CLI exit 1, fail-loud). A target collection with points of
its own (an earlier run, another installation) is never cleaned silently: `drop_target` drops
the Qdrant collection first, on request. The switch itself is the operator's `VECTOR_BACKEND`;
going back is setting it back, the source is never changed.
"""

import json
import logging
import uuid
from dataclasses import dataclass, field

from sqlalchemy import bindparam, select, text

from ffcore.core import db
from ffcore.core.config import Settings
from ffcore.knowledge.store import sparse_to_json
from ffcore.knowledge.vectorstore.base import VectorRecord, VectorStore
from ffcore.models.knowledge import SEARCHABLE_CHUNK_STATUSES, KnowledgeBase

log = logging.getLogger("ffcore.knowledge.migrate")

DRIVERS = ("pgvector", "qdrant")
BATCH = 256

_SEARCHABLE = (
    "c.kb_id = :kb_id AND c.chunk_status IN :searchable AND d.deleted_at IS NULL"
    " AND d.status = 'indexed'"
)


class MigrateError(RuntimeError):
    """Refused before or while copying (code, message; never content)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


@dataclass
class KbMigration:
    kb_id: uuid.UUID
    kb_key: str
    source_count: int = 0
    target_count: int = 0
    written: int = 0
    sparse_computed: int = 0
    sparse_missing: int = 0

    @property
    def ok(self) -> bool:
        return self.source_count == self.target_count


@dataclass
class MigrationReport:
    source: str
    target: str
    dry_run: bool
    kbs: list[KbMigration] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """A dry run writes nothing, so only a real run is held to equal counts."""
        return self.dry_run or all(kb.ok for kb in self.kbs)

    def lines(self) -> list[str]:
        mode = " (dry run, nothing written)" if self.dry_run else ""
        out = [f"migrate-vectors {self.source} -> {self.target}{mode}"]
        for kb in self.kbs:
            line = (
                f"  {kb.kb_key} source={kb.source_count} target={kb.target_count}"
                f" written={kb.written} sparse_computed={kb.sparse_computed}"
                f" sparse_missing={kb.sparse_missing}"
            )
            if kb.ok:
                line += " ok"
            elif not self.dry_run:
                line += (
                    " mismatch: the target does not hold the source's vectors; if it has points"
                    " of its own, run again with --drop-target"
                )
            out.append(line)
        return out


def _rows_statement(extra: str):
    return text(
        "SELECT c.id, c.document_id, c.embedding::text, c.sparse, c.page, c.section_path,"
        " c.text, c.embedding_model, d.acl_roles, d.acl_users, d.metadata"
        " FROM chunks c JOIN documents d ON d.id = c.document_id"
        f" WHERE {_SEARCHABLE} AND c.id > :after {extra} ORDER BY c.id LIMIT :limit"
    ).bindparams(bindparam("searchable", expanding=True))


async def _batches(kb_id: uuid.UUID, extra: str):
    after = uuid.UUID(int=0)
    statement = _rows_statement(extra)
    while True:
        async with db.session_scope() as session:
            rows = (
                await session.execute(
                    statement,
                    {
                        "kb_id": kb_id,
                        "searchable": list(SEARCHABLE_CHUNK_STATUSES),
                        "after": after,
                        "limit": BATCH,
                    },
                )
            ).all()
        if not rows:
            return
        yield rows
        after = rows[-1][0]


def _dense(value: str) -> list[float]:
    return [float(x) for x in value.strip("[]").split(",")]


async def _store_sparse(weights: dict[uuid.UUID, dict[int, float]]) -> None:
    statement = text("UPDATE chunks SET sparse = CAST(:sparse AS jsonb) WHERE id = :id")
    async with db.session_scope() as session:
        for chunk_id, sparse in weights.items():
            await session.execute(
                statement, {"id": chunk_id, "sparse": json.dumps(sparse_to_json(sparse))}
            )
        await session.commit()


async def _to_qdrant(kb: KbMigration, target, settings, embed_client, dry_run, drop):
    if not dry_run:
        if drop:
            await target.drop_collection(kb.kb_id)
        await target.ensure_collection(kb.kb_id, settings.embed_dim)
    async for rows in _batches(kb.kb_id, "AND c.embedding IS NOT NULL"):
        legacy = [r for r in rows if r[3] is None]
        computed: dict[uuid.UUID, dict[int, float]] = {}
        if legacy and dry_run:
            kb.sparse_missing += len(legacy)
        elif legacy:
            models = {r[7] for r in legacy}
            if models != {embed_client.model}:
                raise MigrateError(
                    "embedding_model_mismatch",
                    f"rows of {sorted(map(str, models))} cannot get sparse weights from "
                    f"{embed_client.model}; reindex gold first",
                )
            result = await embed_client.embed([r[6] for r in legacy])
            computed = {r[0]: s for r, s in zip(legacy, result.sparse, strict=True)}
            await _store_sparse(computed)
            kb.sparse_computed += len(computed)
        if dry_run:
            continue
        records = []
        for r in rows:
            sparse = computed.get(r[0])
            if sparse is None and r[3] is not None:
                sparse = {int(k): float(v) for k, v in r[3].items()}
            records.append(
                VectorRecord(
                    chunk_id=r[0],
                    kb_id=kb.kb_id,
                    document_id=r[1],
                    dense=_dense(r[2]),
                    sparse=sparse,
                    acl_roles=tuple(r[8] or ()),
                    acl_users=tuple(str(u) for u in r[9] or ()),
                    page=r[4],
                    section_path=r[5],
                    metadata=dict(r[10] or {}),
                )
            )
        await target.upsert(records)
        kb.written += len(records)


async def _to_pgvector(kb: KbMigration, source, target, dry_run):
    async for rows in _batches(kb.kb_id, "AND c.embedding IS NULL"):
        if dry_run:
            continue
        found = await source.fetch_vectors(kb.kb_id, [r[0] for r in rows])
        records, sparse = [], {}
        for r in rows:
            if r[0] not in found:
                continue  # not in the source either: the counts tell (never invented here)
            dense, weights = found[r[0]]
            records.append(
                VectorRecord(chunk_id=r[0], kb_id=kb.kb_id, document_id=r[1], dense=dense)
            )
            if weights and r[3] is None:
                sparse[r[0]] = weights
        await target.upsert(records)
        if sparse:
            await _store_sparse(sparse)
        kb.written += len(records)


async def migrate_vectors(
    *,
    source: VectorStore,
    target: VectorStore,
    kb_ids: list[uuid.UUID],
    settings: Settings,
    embed_client=None,
    dry_run: bool = False,
    drop_target: bool = False,
) -> MigrationReport:
    if source.name == target.name:
        raise MigrateError("migrate_same_driver", f"source and target are both {source.name}")
    if drop_target and target.name == "pgvector":
        raise MigrateError(
            "drop_target_not_applicable",
            "the pgvector column is the source of truth; --drop-target applies to qdrant only",
        )
    report = MigrationReport(source=source.name, target=target.name, dry_run=dry_run)
    async with db.session_scope() as session:
        keys = dict(
            (
                await session.execute(
                    select(KnowledgeBase.id, KnowledgeBase.key).where(KnowledgeBase.id.in_(kb_ids))
                )
            ).all()
        )
    for kb_id in kb_ids:
        kb = KbMigration(kb_id=kb_id, kb_key=keys.get(kb_id, str(kb_id)))
        kb.source_count = await source.count(kb_id)
        if target.name == "qdrant":
            await _to_qdrant(kb, target, settings, embed_client, dry_run, drop_target)
        else:
            await _to_pgvector(kb, source, target, dry_run)
        kb.target_count = await target.count(kb_id)
        log.info(
            "migrate-vectors kb=%s %s->%s source=%d target=%d written=%d sparse_computed=%d"
            " sparse_missing=%d dry_run=%s",
            kb_id,
            source.name,
            target.name,
            kb.source_count,
            kb.target_count,
            kb.written,
            kb.sparse_computed,
            kb.sparse_missing,
            dry_run,
        )
        report.kbs.append(kb)
    return report


def store_for(name: str, settings: Settings) -> VectorStore:
    """The driver by explicit name (the CLI's --from/--to), not by VECTOR_BACKEND."""
    if name == "qdrant":
        from ffcore.knowledge.vectorstore.qdrant import QdrantStore

        return QdrantStore(settings)
    from ffcore.knowledge.vectorstore.pgvector import PgVectorStore

    return PgVectorStore()


async def run(
    *,
    project_key: str,
    kb_key: str | None,
    source: str,
    target: str,
    dry_run: bool,
    drop_target: bool,
    settings: Settings,
) -> MigrationReport:
    """The CLI road: every live KB of the project, or one; the API process embeds (C10)."""
    from ffcore.knowledge.ingest import HttpEmbedClient
    from ffcore.models.identity import Project

    async with db.session_scope() as session:
        statement = (
            select(KnowledgeBase.id)
            .join(Project, Project.id == KnowledgeBase.project_id)
            .where(Project.key == project_key, KnowledgeBase.deleted_at.is_(None))
            .order_by(KnowledgeBase.key)
        )
        if kb_key is not None:
            statement = statement.where(KnowledgeBase.key == kb_key)
        kb_ids = list((await session.scalars(statement)).all())
    if not kb_ids:
        raise MigrateError(
            "knowledge_base_not_found", f"no knowledge base {project_key}/{kb_key or '*'}"
        )
    return await migrate_vectors(
        source=store_for(source, settings),
        target=store_for(target, settings),
        kb_ids=kb_ids,
        settings=settings,
        embed_client=None if dry_run else HttpEmbedClient(settings),
        dry_run=dry_run,
        drop_target=drop_target,
    )
