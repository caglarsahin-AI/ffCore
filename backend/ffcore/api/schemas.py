"""Request and response bodies of the 03a API (identity, projects, providers, models, audit).

These models are the source of `backend/openapi/03a.yaml`; the console (10a-binding) generates
its types from that file. Changes after the draft are additive only.
"""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# Project key: global, unique and immutable. No ".", "/" or ":" so that "<project_key>.<model_key>"
# and "agent:<project_key>/<agent_key>" always split one way (CONTRACTS C1).
PROJECT_KEY_PATTERN = r"^[a-z][a-z0-9-]{1,31}$"
MODEL_KEY_PATTERN = r"^[a-z][a-z0-9-]{1,63}$"
PROVIDER_KEY_PATTERN = r"^[a-z][a-z0-9-]{1,63}$"

ProjectKey = Annotated[
    str, Field(pattern=PROJECT_KEY_PATTERN, description="Global, unique, immutable project key.")
]
ModelKey = Annotated[
    str, Field(pattern=MODEL_KEY_PATTERN, description="Model key, unique within the project.")
]


class Role(StrEnum):
    """Fixed roles, ordered user < analyst < developer < admin. `developer` and `user` are
    reserved in the PoC and cannot be assigned yet."""

    user = "user"
    analyst = "analyst"
    developer = "developer"
    admin = "admin"


class AccessMode(StrEnum):
    """`read` sees the same screens and data as `edit` but every mutation returns 403."""

    edit = "edit"
    read = "read"


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _omitted_is_not_a_default(schema: dict[str, Any]) -> None:
    for prop in schema.get("properties", {}).values():
        prop.pop("default", None)


class Patch(Strict):
    """PATCH body: every field may be omitted and is then left as it is. Only fields typed
    `T | None` accept an explicit null (it clears the value); for the others null fails the type
    check with a 422, never a database error. Endpoints apply `model_dump(exclude_unset=True)`.

    Fields are declared `name: T = Field(default=None)`: the None default only marks omission
    (Pydantic does not validate defaults) and is removed from the JSON schema."""

    model_config = ConfigDict(extra="forbid", json_schema_extra=_omitted_is_not_a_default)


class ErrorDetail(BaseModel):
    message: str = Field(description="English, actionable, never contains secrets.")
    type: str = Field(description="authentication_error, permission_error, not_found_error, ...")
    code: str = Field(description="Stable machine-readable code, e.g. read_only_access.")


class ErrorBody(BaseModel):
    """OpenAI-shaped error body used by every 4xx response."""

    error: ErrorDetail


# --- Auth ---


class LoginRequest(Strict):
    email: str = Field(max_length=320)
    password: str = Field(min_length=1, max_length=1024)


class PasswordChangeRequest(Strict):
    current_password: str = Field(min_length=1, max_length=1024)
    new_password: str = Field(min_length=12, max_length=1024)


class Membership(BaseModel):
    project_id: UUID
    project_key: str
    role: Role
    access: AccessMode


class CurrentUser(BaseModel):
    id: UUID
    email: str
    full_name: str
    is_superadmin: bool


class MeResponse(BaseModel):
    """`role`/`access`: the superadmin's own values, otherwise the highest membership role and
    that membership's access; null without memberships. The API re-checks per project."""

    user: CurrentUser
    role: Role | None
    access: AccessMode | None
    memberships: list[Membership]


# --- Users (superadmin) ---


class UserOut(BaseModel):
    id: UUID
    email: str
    full_name: str
    is_active: bool
    is_superadmin: bool
    superadmin_access: AccessMode | None
    created_at: datetime
    updated_at: datetime


class UserCreate(Strict):
    email: str = Field(max_length=320)
    full_name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=12, max_length=1024)
    is_superadmin: bool = False
    superadmin_access: AccessMode | None = Field(
        default=None, description="Required when is_superadmin is true."
    )


class UserUpdate(Patch):
    full_name: str = Field(default=None, min_length=1, max_length=200)
    is_active: bool = Field(default=None)
    is_superadmin: bool = Field(default=None)
    superadmin_access: AccessMode | None = Field(default=None)


class UserList(BaseModel):
    data: list[UserOut]


# --- Projects and members ---


class ProjectOut(BaseModel):
    id: UUID
    key: str
    name: str
    description: str | None
    created_by: str
    created_at: datetime
    updated_at: datetime


class ProjectCreate(Strict):
    key: ProjectKey
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class ProjectUpdate(Patch):
    """The project key cannot be changed (it is part of every model name)."""

    name: str = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class ProjectList(BaseModel):
    data: list[ProjectOut]


class MemberOut(BaseModel):
    project_id: UUID
    user_id: UUID
    email: str
    full_name: str
    role: Role
    access: AccessMode


class MemberCreate(Strict):
    user_id: UUID
    role: Role
    access: AccessMode = AccessMode.edit


class MemberUpdate(Patch):
    role: Role = Field(default=None)
    access: AccessMode = Field(default=None)


class MemberList(BaseModel):
    data: list[MemberOut]


class ReadinessCheck(BaseModel):
    key: Literal["model_provider", "vector_provider", "project_admin", "limits", "alert_rules"]
    ok: bool
    detail: str


class ReadinessOut(BaseModel):
    project_id: UUID
    passed: int
    total: int
    checks: list[ReadinessCheck]


# --- Providers ---


class ProviderDriver(StrEnum):
    ollama = "ollama"
    vllm = "vllm"
    anthropic = "anthropic"
    openai = "openai"
    azure_openai = "azure_openai"
    bedrock = "bedrock"
    openai_compatible = "openai_compatible"
    local_flagembedding = "local_flagembedding"
    pgvector = "pgvector"
    qdrant = "qdrant"
    local_fs = "local_fs"


class ProviderDomain(StrEnum):
    model = "model"
    embedding = "embedding"
    vector = "vector"
    file = "file"


class DriverField(BaseModel):
    name: str
    required: bool
    secret: bool
    description: str


class DriverSpec(BaseModel):
    driver: ProviderDriver
    domains: list[ProviderDomain]
    supports_test: bool
    fields: list[DriverField]


class DriverList(BaseModel):
    data: list[DriverSpec]


class ProviderOut(BaseModel):
    id: UUID
    key: str
    label: str
    description: str | None
    driver: ProviderDriver
    domains: list[ProviderDomain]
    config: dict[str, Any] = Field(description='Secret fields are returned as "***".')
    supports_test: bool
    is_active: bool
    project_ids: list[UUID]
    created_by: str
    created_at: datetime
    updated_at: datetime


class ProviderCreate(Strict):
    key: str = Field(pattern=PROVIDER_KEY_PATTERN)
    label: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    driver: ProviderDriver
    domains: list[ProviderDomain] = Field(min_length=1)
    config: dict[str, Any] = Field(default_factory=dict)
    project_ids: list[UUID] = Field(
        min_length=1, description="A provider is always assigned to at least one project."
    )
    is_active: bool = True


class ProviderUpdate(Patch):
    label: str = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    domains: list[ProviderDomain] = Field(default=None, min_length=1)
    config: dict[str, Any] = Field(
        default=None, description='A secret field sent as "***" keeps its stored value.'
    )
    is_active: bool = Field(
        default=None,
        description="false is refused (409 provider_in_use) while an active model uses it.",
    )


class ProviderProjectsUpdate(Strict):
    project_ids: list[UUID] = Field(min_length=1)


class ProviderList(BaseModel):
    data: list[ProviderOut]


class ProviderTestRequest(Strict):
    """Test a configuration without saving it."""

    driver: ProviderDriver
    config: dict[str, Any] = Field(default_factory=dict)


class ProviderTestResult(BaseModel):
    supported: bool = Field(description="False: this driver has no connection test.")
    ok: bool
    code: str = Field(description="ok, connection_test_unsupported, egress_denied, ...")
    message: str
    latency_ms: int | None = None


# --- Model catalog and models ---


class ModelCategory(StrEnum):
    llm = "llm"
    embedding = "embedding"
    stt = "stt"
    tts = "tts"
    ocr = "ocr"
    moderation = "moderation"


class InputType(StrEnum):
    text = "text"
    image = "image"
    audio = "audio"
    file = "file"


class ModelCapabilities(Strict):
    tool_calls: bool = False
    reasoning: bool = False
    structured_outputs: bool = False


class ModelPricing(Strict):
    """USD per 1M tokens. airgap: virtual prices entered by hand."""

    input_per_1m: Decimal | None = Field(default=None, ge=0)
    output_per_1m: Decimal | None = Field(default=None, ge=0)
    cached_per_1m: Decimal | None = Field(default=None, ge=0)


class ModelLimits(Strict):
    context_window: int | None = Field(default=None, gt=0)
    max_output: int | None = Field(default=None, gt=0)
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, gt=0)


class RequestPolicy(Strict):
    drop_unsupported_params: bool = False
    reject_params: list[str] = Field(default_factory=list)
    extra_body: dict[str, Any] = Field(
        default_factory=dict, description="JSON merged into every request body."
    )
    forward_unknown_params: bool = False


class CatalogEntryOut(BaseModel):
    id: UUID
    driver: ProviderDriver
    model_id: str
    category: ModelCategory
    capabilities: ModelCapabilities
    input_types: list[InputType]
    context_window: int | None
    max_output: int | None
    embed_dim: int | None
    pricing: ModelPricing
    source: str
    as_of: str
    updated_at: datetime


class CatalogList(BaseModel):
    data: list[CatalogEntryOut]


class ModelOut(BaseModel):
    id: UUID
    project_id: UUID
    key: str
    litellm_name: str = Field(description='"<project_key>.<model_key>" (CONTRACTS C1).')
    display_name: str
    provider_id: UUID
    category: ModelCategory
    model_id: str
    capabilities: ModelCapabilities
    input_types: list[InputType]
    pricing: ModelPricing
    limits: ModelLimits
    reasoning_default: Literal["none", "low", "medium", "high"] | None
    return_reasoning: bool
    upstream_api: Literal["chat", "responses"]
    request_policy: RequestPolicy
    embed_dim: int | None = Field(description="Measured at registration (embedding only).")
    is_active: bool
    created_by: str
    created_at: datetime
    updated_at: datetime


class ModelCreate(Strict):
    key: ModelKey
    display_name: str = Field(min_length=1, max_length=200)
    provider_id: UUID
    category: ModelCategory
    model_id: str = Field(min_length=1, max_length=300)
    capabilities: ModelCapabilities = Field(default_factory=ModelCapabilities)
    input_types: list[InputType] = Field(default_factory=lambda: [InputType.text])
    pricing: ModelPricing = Field(default_factory=ModelPricing)
    limits: ModelLimits = Field(default_factory=ModelLimits)
    reasoning_default: Literal["none", "low", "medium", "high"] | None = None
    return_reasoning: bool = False
    upstream_api: Literal["chat", "responses"] = Field(
        description="Chosen explicitly; never detected."
    )
    request_policy: RequestPolicy = Field(default_factory=RequestPolicy)
    is_active: bool = True


class ModelUpdate(Patch):
    display_name: str = Field(default=None, min_length=1, max_length=200)
    category: ModelCategory = Field(default=None)
    model_id: str = Field(default=None, min_length=1, max_length=300)
    capabilities: ModelCapabilities = Field(default=None)
    input_types: list[InputType] = Field(default=None)
    pricing: ModelPricing = Field(default=None)
    limits: ModelLimits = Field(default=None)
    reasoning_default: Literal["none", "low", "medium", "high"] | None = Field(default=None)
    return_reasoning: bool = Field(default=None)
    upstream_api: Literal["chat", "responses"] = Field(default=None)
    request_policy: RequestPolicy = Field(default=None)
    is_active: bool = Field(default=None)


class ModelList(BaseModel):
    data: list[ModelOut]


# --- Audit (read) ---


class AuditEventOut(BaseModel):
    id: UUID
    ts: datetime
    actor_type: Literal["user", "api_key", "system"]
    actor_id: str
    project_id: UUID | None
    action: str
    resource_type: str
    resource_id: str | None
    outcome: Literal["success", "denied", "error"]
    before: Any = None
    after: Any = None
    request_id: str | None
    ip: str | None


class AuditList(BaseModel):
    data: list[AuditEventOut]
    limit: int
    offset: int
