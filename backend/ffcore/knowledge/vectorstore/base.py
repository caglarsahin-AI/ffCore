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
MetadataValue = str | int | bool | tuple[str, ...]


def metadata_items(mapping: dict) -> tuple[tuple[str, MetadataValue], ...]:
    """Metadata filters as a hashable, ordered tuple; a list value becomes an IN tuple.
    An empty list would match nothing (or, ignored, everything): refused."""
    items = []
    for key, value in sorted(mapping.items()):
        if isinstance(value, list | tuple):
            if not value:
                raise ValueError(f"metadata filter {key!r} has an empty list")
            value = tuple(str(v) for v in value)
        items.append((key, value))
    return tuple(items)


def metadata_sql(metadata, params: dict) -> list[str]:
    """The metadata filters as SQL on `d` (documents), for pgvector and the lexical leg."""
    clauses = []
    for index, (key, value) in enumerate(metadata):
        params[f"mk{index}"] = key
        if isinstance(value, tuple):
            clauses.append(f"d.metadata ->> :mk{index} = ANY(CAST(:mv{index} AS text[]))")
            params[f"mv{index}"] = list(value)
        else:
            clauses.append(f"d.metadata ->> :mk{index} = :mv{index}")
            params[f"mv{index}"] = str(value).lower() if isinstance(value, bool) else str(value)
    return clauses


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
    # A tuple value is an IN filter (04b-2 D6, C5 additive): any of the values matches.
    metadata: tuple[tuple[str, MetadataValue], ...] = ()

    @classmethod
    def from_mapping(cls, filters: dict) -> "VectorFilters":
        unknown = set(filters) - FILTER_KEYS
        if unknown:
            raise ValueError(f"unknown filter keys: {sorted(unknown)}")
        return cls(
            document_ids=tuple(filters.get("document_ids", ())),
            acl_roles=tuple(filters.get("acl_roles", ())),
            acl_users=tuple(str(u) for u in filters.get("acl_users", ())),
            metadata=metadata_items(filters.get("metadata", {})),
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


async def _unsupported_update_acl(self, kb_id, document_id, acl_roles, acl_users) -> None:
    raise VectorStoreError("unsupported", f"{self.name} cannot update a document's ACL")


# Optional, additive to C5 (default: unsupported). An ACL change of an already indexed document
# must reach the store before the change is answered (review 04a r1 MAJOR-1).
VectorStore.update_acl = _unsupported_update_acl


async def _unsupported_count(self, kb_id) -> int:
    raise VectorStoreError("unsupported", f"{self.name} cannot count a collection")


async def _unsupported_fetch_vectors(self, kb_id, chunk_ids) -> dict:
    raise VectorStoreError("unsupported", f"{self.name} cannot return stored vectors")


# Optional, additive to C5 (04b `migrate-vectors`, default: unsupported).
# count(kb_id) -> int: the vectors the store holds for the KB (searchable chunks for pgvector,
# every point of the collection for Qdrant; a missing collection is 0).
# fetch_vectors(kb_id, chunk_ids) -> {chunk_id: (dense, sparse or None)} for the ids it holds.
VectorStore.count = _unsupported_count
VectorStore.fetch_vectors = _unsupported_fetch_vectors
