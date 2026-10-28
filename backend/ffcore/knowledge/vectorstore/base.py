"""`VectorStore` (CONTRACTS C5): the one interface every vector driver implements.

Signatures are frozen at M3; new optional methods are additive with an "unsupported" default.
Chunk text and the tsvector always live in Postgres `chunks`; a driver holds vectors and the
filter payload. A query carries `dense` and optionally `sparse`: the Qdrant driver fuses them
inside Qdrant (bge-m3 sparse), the pgvector driver ignores `sparse` (its lexical leg is
Postgres BM25 in search.py). ACL and KB filters are applied in the query, never afterwards.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from uuid import UUID

# Filter keys (C5). Unknown keys are refused, never ignored.
FILTER_KEYS = frozenset({"document_ids", "acl_roles", "acl_users", "metadata"})


class VectorStoreError(RuntimeError):
    """The store could not serve the call (unreachable, wrong dimension). Never swallowed."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class VectorRecord:
    chunk_id: UUID
    kb_id: UUID
    document_id: UUID
    dense: list[float]
    sparse: dict[int, float] | None = None
    acl_roles: tuple[str, ...] = ()
    acl_users: tuple[str, ...] = ()
    page: int | None = None
    section_path: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class VectorQuery:
    dense: list[float]
    sparse: dict[int, float] | None = None
    # Exact (brute-force) search: hnsw.ef_search raised / Qdrant exact=true (R3.5 parity test).
    exact: bool = False


@dataclass(frozen=True)
class VectorFilters:
    """ACL semantics (C15): a chunk matches when its document has no ACL at all, or one of
    `acl_roles` is in the document's roles, or one of `acl_users` is in its users."""

    document_ids: tuple[UUID, ...] = ()
    acl_roles: tuple[str, ...] = ()
    acl_users: tuple[str, ...] = ()
    metadata: tuple[tuple[str, str | int | bool], ...] = ()

    @classmethod
    def from_mapping(cls, filters: dict) -> "VectorFilters":
        unknown = set(filters) - FILTER_KEYS
        if unknown:
            raise ValueError(f"unknown filter keys: {sorted(unknown)}")
        return cls(
            document_ids=tuple(filters.get("document_ids", ())),
            acl_roles=tuple(filters.get("acl_roles", ())),
            acl_users=tuple(str(u) for u in filters.get("acl_users", ())),
            metadata=tuple(sorted(filters.get("metadata", {}).items())),
        )


@dataclass(frozen=True)
class VectorHit:
    chunk_id: UUID
    document_id: UUID
    score: float


class VectorStore(ABC):
    name: str

    @abstractmethod
    async def ensure_collection(self, kb_id: UUID, dim: int) -> None: ...

    @abstractmethod
    async def upsert(self, chunks: list[VectorRecord]) -> None: ...

    @abstractmethod
    async def search(
        self, kb_id: UUID, query: VectorQuery, filters: VectorFilters, top_k: int
    ) -> list[VectorHit]: ...

    @abstractmethod
    async def delete_by_document(self, document_id: UUID) -> None: ...

    @abstractmethod
    async def drop_collection(self, kb_id: UUID) -> None: ...
