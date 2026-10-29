"""`PgVectorStore`: dense vectors in `chunks.embedding` (product default, no extra service).

The chunk rows are written by the knowledge store; `upsert` only sets their vectors. `sparse`
is ignored by design (C5): this driver's lexical leg is Postgres BM25, fused in search.py.
"""

from uuid import UUID

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ffcore.knowledge.vectorstore.base import (
    VectorFilters,
    VectorHit,
    VectorQuery,
    VectorRecord,
    VectorStore,
    VectorStoreError,
)
from ffcore.models.knowledge import SEARCHABLE_CHUNK_STATUSES


def _literal(vector: list[float]) -> str:
    return "[" + ",".join(repr(float(x)) for x in vector) + "]"


class PgVectorStore(VectorStore):
    name = "pgvector"

    def __init__(self, sessions: async_sessionmaker[AsyncSession] | None = None):
        self._sessions = sessions

    def _session(self) -> AsyncSession:
        if self._sessions is not None:
            return self._sessions()
        from ffcore.core import db

        return db.session_scope()

    async def column_dim(self) -> int:
        async with self._session() as session:
            dim = await session.scalar(
                text(
                    "SELECT atttypmod FROM pg_attribute "
                    "WHERE attrelid = 'chunks'::regclass AND attname = 'embedding'"
                )
            )
        return int(dim)

    async def ensure_collection(self, kb_id: UUID, dim: int) -> None:
        # One column for every KB; the only thing to check is that it has the right size.
        actual = await self.column_dim()
        if actual != dim:
            raise VectorStoreError(
                "embed_dim_mismatch", f"chunks.embedding is vector({actual}), EMBED_DIM is {dim}."
            )

    async def upsert(self, chunks: list[VectorRecord]) -> None:
        if not chunks:
            return
        statement = text("UPDATE chunks SET embedding = CAST(:vec AS vector) WHERE id = :chunk_id")
        async with self._session() as session:
            for record in chunks:
                result = await session.execute(
                    statement, {"vec": _literal(record.dense), "chunk_id": record.chunk_id}
                )
                if result.rowcount != 1:
                    raise VectorStoreError(
                        "chunk_not_found", f"No chunk row {record.chunk_id} to attach a vector to."
                    )
            await session.commit()

    async def search(
        self, kb_id: UUID, query: VectorQuery, filters: VectorFilters, top_k: int
    ) -> list[VectorHit]:
        clauses = [
            "c.kb_id = :kb_id",
            "c.embedding IS NOT NULL",
            "c.chunk_status IN :searchable",
            "d.deleted_at IS NULL",
            # Searchable only once the whole publication succeeded (review r1 MAJOR-3).
            "d.status = 'indexed'",
        ]
        params: dict = {"kb_id": kb_id, "vec": _literal(query.dense), "top_k": top_k}
        binds = [bindparam("searchable", expanding=True)]
        params["searchable"] = list(SEARCHABLE_CHUNK_STATUSES)
        # ACL in the query (C15): no ACL, or a matching role, or a matching user.
        acl = ["(cardinality(d.acl_roles) = 0 AND cardinality(d.acl_users) = 0)"]
        if filters.acl_roles:
            acl.append("d.acl_roles && CAST(:acl_roles AS text[])")
            params["acl_roles"] = list(filters.acl_roles)
        if filters.acl_users:
            acl.append("d.acl_users && CAST(:acl_users AS uuid[])")
            params["acl_users"] = list(filters.acl_users)
        clauses.append("(" + " OR ".join(acl) + ")")
        if filters.document_ids:
            clauses.append("c.document_id IN :document_ids")
            binds.append(bindparam("document_ids", expanding=True))
            params["document_ids"] = list(filters.document_ids)
        for index, (key, value) in enumerate(filters.metadata):
            clauses.append(f"d.metadata ->> :mk{index} = :mv{index}")
            params[f"mk{index}"] = key
            params[f"mv{index}"] = str(value).lower() if isinstance(value, bool) else str(value)
        statement = text(
            "SELECT c.id, c.document_id, 1 - (c.embedding <=> CAST(:vec AS vector)) AS score "
            "FROM chunks c JOIN documents d ON d.id = c.document_id "
            f"WHERE {' AND '.join(clauses)} "
            "ORDER BY c.embedding <=> CAST(:vec AS vector), c.id LIMIT :top_k"
        ).bindparams(*binds)
        async with self._session() as session:
            if query.exact:
                # Brute force: no HNSW approximation (R3.5 exact mode).
                await session.execute(text("SET LOCAL enable_indexscan = off"))
            rows = (await session.execute(statement, params)).all()
        return [VectorHit(chunk_id=r[0], document_id=r[1], score=float(r[2])) for r in rows]

    async def update_acl(self, kb_id, document_id, acl_roles, acl_users) -> None:
        """Nothing to copy: this driver reads the ACL from `documents` in every query."""
        return None

    async def delete_by_document(self, document_id: UUID) -> None:
        async with self._session() as session:
            await session.execute(
                text("UPDATE chunks SET embedding = NULL WHERE document_id = :d"),
                {"d": document_id},
            )
            await session.commit()

    async def drop_collection(self, kb_id: UUID) -> None:
        async with self._session() as session:
            await session.execute(
                text("UPDATE chunks SET embedding = NULL WHERE kb_id = :k"), {"k": kb_id}
            )
            await session.commit()
