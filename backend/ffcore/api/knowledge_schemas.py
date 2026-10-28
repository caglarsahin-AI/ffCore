"""Request and response bodies of the 04a API (knowledge bases, documents, search, embedding).

These models are the source of `backend/openapi/04a.yaml`; 05a (mcp-search), 06a (runtime) and
10b (console) consume that file. Changes after the draft are additive only.
"""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from ffcore.api.schemas import Patch, Role, Strict

KB_KEY_PATTERN = r"^[a-z][a-z0-9-]{1,63}$"

KbKey = Annotated[
    str, Field(pattern=KB_KEY_PATTERN, description="Knowledge base key, unique within the project.")
]


class KnowledgeBaseStatus(StrEnum):
    active = "active"
    reindexing = "reindexing"


class DocumentStatus(StrEnum):
    """Derived from the gate decisions; `skipped` always carries a gate reason (fail-loud)."""

    pending = "pending"
    converting = "converting"
    gated = "gated"
    chunking = "chunking"
    embedding = "embedding"
    indexed = "indexed"
    skipped = "skipped"
    failed = "failed"
    timeout = "timeout"


class GateStatus(StrEnum):
    ok = "ok"
    flagged = "flagged"
    skipped = "skipped"


class ThresholdMode(StrEnum):
    """Single threshold rule (K2): with the reranker on only the rerank floor applies; with it
    off only `min_score` (embedding score) applies. Never both."""

    rerank_floor = "rerank_floor"
    min_score = "min_score"


# --- Knowledge bases ---


class KnowledgeBaseCreate(Strict):
    key: KbKey
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    embed_model: str | None = Field(
        default=None,
        description="Must equal the installation's EMBED_MODEL if given (one model per "
        "installation); a different value is refused with 400 embed_dim_mismatch or "
        "embed_model_mismatch.",
    )
    embed_dim: int | None = Field(default=None, gt=0, description="Must equal EMBED_DIM if given.")
    chunk_size: int = Field(
        default=400, ge=50, le=4000, description="Lower token target of a chunk (measured: 400)."
    )
    chunk_overlap: int = Field(default=0, ge=0, le=1000, description="Overlap in tokens.")
    hybrid: bool = Field(default=True, description="Vector plus lexical leg, fused with RRF.")
    rerank: bool = Field(default=True, description="Rerank candidates; see threshold_mode.")
    default_top_k: int = Field(default=5, ge=1, le=50)
    default_min_score: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Embedding score floor; applies only while rerank is false (K2).",
    )
    default_filter: dict[str, Any] = Field(default_factory=dict)


class KnowledgeBaseUpdate(Patch):
    name: str = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    chunk_size: int = Field(
        default=None, ge=50, le=4000, description="Takes effect with a gold reindex."
    )
    chunk_overlap: int = Field(
        default=None, ge=0, le=1000, description="Takes effect with a gold reindex."
    )
    hybrid: bool = Field(default=None)
    rerank: bool = Field(default=None)
    default_top_k: int = Field(default=None, ge=1, le=50)
    default_min_score: float | None = Field(default=None, ge=0, le=1)
    default_filter: dict[str, Any] = Field(default=None)


class KnowledgeBaseOut(BaseModel):
    id: UUID
    project_id: UUID
    key: str
    name: str
    description: str | None
    embed_model: str
    embed_dim: int
    chunk_strategy: Literal["heading"]
    chunk_size: int
    chunk_overlap: int
    chunk_max_tokens: int = Field(description="Derived upper bound of a chunk in tokens.")
    hybrid: bool
    rerank: bool
    rerank_model: str
    default_top_k: int
    default_min_score: float | None
    default_filter: dict[str, Any]
    normalizer_config_id: str
    status: KnowledgeBaseStatus
    document_count: int
    chunk_count: int
    created_at: datetime
    updated_at: datetime


class KnowledgeBaseList(BaseModel):
    items: list[KnowledgeBaseOut]


# --- Documents ---


class GateDecision(BaseModel):
    status: GateStatus | None = Field(description="Null until the gate has run.")
    reason: str | None = Field(description="e.g. boilerplate, data_dump:log, duplicate_of:<id>.")


class DocumentOut(BaseModel):
    id: UUID
    kb_id: UUID
    filename: str
    mime_sniffed: str | None
    size: int
    sha256: str
    status: DocumentStatus
    error: str | None = Field(description="Error code and message when failed or timeout.")
    page_count: int | None
    acl_roles: list[Role] = Field(
        description="Roles that may read the document. Both lists empty: every project member."
    )
    acl_users: list[UUID]
    metadata: dict[str, Any]
    version: int
    breadcrumb: str | None
    language: str | None
    duplicate_of: UUID | None
    gate0: GateDecision
    gate1: GateDecision
    gate2: GateDecision
    convert_engine: str | None
    convert_seconds: float | None
    chunk_count: int
    created_at: datetime
    updated_at: datetime


class DocumentList(BaseModel):
    items: list[DocumentOut]


class UploadOutcome(StrEnum):
    created = "created"
    new_version = "new_version"
    unchanged = "unchanged"


class UploadedDocument(BaseModel):
    outcome: UploadOutcome = Field(
        description="unchanged: same sha256 as the current version, nothing is queued."
    )
    document: DocumentOut


class UploadResult(BaseModel):
    items: list[UploadedDocument]


class ReindexLayer(StrEnum):
    silver = "silver"
    gold = "gold"


class ReindexRequest(Strict):
    layer: ReindexLayer = Field(
        description="silver: reconvert from raw; gold: rechunk and re-embed from silver. "
        "Neither goes back to the source system."
    )
    full: bool = Field(default=False, description="Every document, not only changed ones.")


class ReindexAccepted(BaseModel):
    job_id: str
    layer: ReindexLayer
    full: bool
    documents: int


# --- Search ---


class SearchFilters(Strict):
    document_ids: list[UUID] = Field(default_factory=list)
    metadata: dict[str, str | int | bool] = Field(
        default_factory=dict, description="Equality filters on document metadata."
    )


class SearchRequest(Strict):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int | None = Field(default=None, ge=1, le=50, description="Default: the KB's.")
    filters: SearchFilters = Field(default_factory=SearchFilters)
    hybrid: bool | None = Field(default=None, description="Default: the KB's.")


class SearchHit(BaseModel):
    chunk_id: UUID
    document_id: UUID
    document_name: str
    page: int | None
    section_path: str | None
    breadcrumb: str
    text: str = Field(description="Chunk text as embedded, starting with the breadcrumb.")
    chunk_status: Literal["ok", "flagged"]
    updated_at_source: datetime | None
    age_days: int | None
    embed_score: float | None
    rerank_score: float | None


class SearchResponse(BaseModel):
    """Hits are ordered newest source first (recency is shown, not scored)."""

    query_id: UUID = Field(description="Row in kb_queries; candidates are logged there.")
    hits: list[SearchHit]
    threshold_mode: ThresholdMode
    filtered_by_rerank_floor: int
    filtered_by_min_score: int
    normalizer_config_id: str
    latency_ms: int


# --- Internal embedding (service account only) ---


class EmbedRequest(Strict):
    texts: list[str] = Field(min_length=1, max_length=64)


class EmbedResponse(BaseModel):
    model: str
    dim: int
    dense: list[list[float]]
    sparse: list[dict[str, float]] = Field(description="Token id → lexical weight per text.")
    truncated: list[bool] = Field(description="True where the text exceeded the model limit.")


# --- Readiness ---


class CheckStatus(StrEnum):
    ok = "ok"
    failed = "failed"
    skipped = "skipped"


class ReadinessCheck(BaseModel):
    name: str
    status: CheckStatus
    code: str | None = Field(description="e.g. warming, context_configuration_invalid.")
    detail: str | None


class ReadyzOut(BaseModel):
    status: Literal["ready", "warming", "not_ready"]
    checks: list[ReadinessCheck]
