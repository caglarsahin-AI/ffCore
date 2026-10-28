"""`QdrantStore`: dense + bge-m3 sparse vectors, fused with RRF inside Qdrant (C5).

PayCore's primary driver (PLAN 2d). Adapted from PayCore `rag/retrieve.py` (named vectors
`dense` (cosine) and `sparse`, two prefetches fused with `rrf`), with FFCore's model: one
collection per knowledge base (`kb_<uuid hex>`), the ACL in the payload and in every query.
Calls go over Qdrant's REST API through SafeOutboundClient (C5: every HTTP call FFCore makes;
the compose service name must be in ALLOWED_INTERNAL_HOSTS), not through a second HTTP stack.
Qdrant down is a 503-class error (`vector_store_unavailable`); there is no fallback to pgvector.
"""

from uuid import UUID

from ffcore.core.config import Settings
from ffcore.core.egress import EgressError, EgressTimeout, SafeOutboundClient
from ffcore.knowledge.vectorstore.base import (
    VectorFilters,
    VectorHit,
    VectorQuery,
    VectorRecord,
    VectorStore,
    VectorStoreError,
)

TIMEOUT = EgressTimeout(connect=5, read=30, total=60)
COLLECTION_PREFIX = "kb_"
# Exact search for the R3.5 parity test; approximate (HNSW) otherwise.
_KEYWORD_FIELDS = ("kb_id", "document_id", "acl_roles", "acl_users")


def collection_name(kb_id: UUID) -> str:
    return f"{COLLECTION_PREFIX}{kb_id.hex}"


def _sparse(weights: dict[int, float]) -> dict:
    items = sorted(weights.items())
    return {"indices": [k for k, _ in items], "values": [v for _, v in items]}


def qdrant_filter(kb_id: UUID, filters: VectorFilters) -> dict:
    """KB isolation and ACL in the query (C15: empty ACL is open to the project's members)."""
    acl: list[dict] = [{"key": "acl_open", "match": {"value": True}}]
    if filters.acl_roles:
        acl.append({"key": "acl_roles", "match": {"any": list(filters.acl_roles)}})
    if filters.acl_users:
        acl.append({"key": "acl_users", "match": {"any": list(filters.acl_users)}})
    must: list[dict] = [
        {"key": "kb_id", "match": {"value": str(kb_id)}},
        {"should": acl},
    ]
    if filters.document_ids:
        must.append(
            {"key": "document_id", "match": {"any": [str(d) for d in filters.document_ids]}}
        )
    for key, value in filters.metadata:
        must.append({"key": f"metadata.{key}", "match": {"value": value}})
    return {"must": must}


class QdrantStore(VectorStore):
    name = "qdrant"

    def __init__(self, settings: Settings):
        if not settings.qdrant_url:
            raise VectorStoreError("vector_store_unconfigured", "QDRANT_URL is not set.")
        self._base = settings.qdrant_url.rstrip("/")
        self._settings = settings
        key = settings.qdrant_api_key
        self._headers = {"api-key": key.get_secret_value()} if key else {}

    async def _call(self, method: str, path: str, json: dict | None = None, ok=(200,)):
        try:
            async with SafeOutboundClient(timeout=TIMEOUT, settings=self._settings) as client:
                response = await client.request(
                    method, f"{self._base}{path}", headers=self._headers, json=json
                )
        except EgressError as exc:
            raise VectorStoreError("vector_store_unavailable", f"Qdrant: {exc.code}") from None
        if response.status_code not in ok:
            # Qdrant's error body names the problem; it carries no secret.
            raise VectorStoreError(
                "vector_store_error", f"Qdrant {method} {path}: {response.status_code}"
            )
        return response.json() if response.content else {}

    async def ensure_collection(self, kb_id: UUID, dim: int) -> None:
        name = collection_name(kb_id)
        existing = await self._call("GET", f"/collections/{name}", ok=(200, 404))
        if existing.get("result"):
            size = existing["result"]["config"]["params"]["vectors"]["dense"]["size"]
            if size != dim:
                raise VectorStoreError(
                    "embed_dim_mismatch", f"Collection {name} has size {size}, EMBED_DIM is {dim}."
                )
            return
        await self._call(
            "PUT",
            f"/collections/{name}",
            {
                "vectors": {"dense": {"size": dim, "distance": "Cosine"}},
                "sparse_vectors": {"sparse": {}},
            },
        )
        for field in _KEYWORD_FIELDS:
            await self._call(
                "PUT",
                f"/collections/{name}/index?wait=true",
                {"field_name": field, "field_schema": "keyword"},
            )

    async def upsert(self, chunks: list[VectorRecord]) -> None:
        by_kb: dict[UUID, list[dict]] = {}
        for record in chunks:
            vector: dict = {"dense": record.dense}
            if record.sparse:
                vector["sparse"] = _sparse(record.sparse)
            by_kb.setdefault(record.kb_id, []).append(
                {
                    "id": str(record.chunk_id),
                    "vector": vector,
                    "payload": {
                        "kb_id": str(record.kb_id),
                        "document_id": str(record.document_id),
                        "acl_roles": list(record.acl_roles),
                        "acl_users": [str(u) for u in record.acl_users],
                        "acl_open": not record.acl_roles and not record.acl_users,
                        "page": record.page,
                        "section_path": record.section_path,
                        "metadata": record.metadata,
                    },
                }
            )
        for kb_id, points in by_kb.items():
            await self._call(
                "PUT", f"/collections/{collection_name(kb_id)}/points?wait=true", {"points": points}
            )

    async def search(
        self, kb_id: UUID, query: VectorQuery, filters: VectorFilters, top_k: int
    ) -> list[VectorHit]:
        flt = qdrant_filter(kb_id, filters)
        params = {"exact": True} if query.exact else {}
        if query.sparse:
            body = {
                "prefetch": [
                    {"query": query.dense, "using": "dense", "limit": top_k, "filter": flt},
                    {
                        "query": _sparse(query.sparse),
                        "using": "sparse",
                        "limit": top_k,
                        "filter": flt,
                    },
                ],
                "query": {"fusion": "rrf"},
                "limit": top_k,
                "with_payload": ["document_id"],
            }
        else:
            body = {
                "query": query.dense,
                "using": "dense",
                "filter": flt,
                "limit": top_k,
                "params": params,
                "with_payload": ["document_id"],
            }
        result = await self._call(
            "POST", f"/collections/{collection_name(kb_id)}/points/query", body
        )
        return [
            VectorHit(
                chunk_id=UUID(point["id"]),
                document_id=UUID(point["payload"]["document_id"]),
                score=float(point["score"]),
            )
            for point in result["result"]["points"]
        ]

    async def delete_by_document(self, document_id: UUID) -> None:
        collections = await self._call("GET", "/collections")
        flt = {"must": [{"key": "document_id", "match": {"value": str(document_id)}}]}
        for item in collections["result"]["collections"]:
            if item["name"].startswith(COLLECTION_PREFIX):
                await self._call(
                    "POST", f"/collections/{item['name']}/points/delete?wait=true", {"filter": flt}
                )

    async def drop_collection(self, kb_id: UUID) -> None:
        await self._call("DELETE", f"/collections/{collection_name(kb_id)}", ok=(200, 404))
