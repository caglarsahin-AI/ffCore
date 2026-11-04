"""Request and response bodies of the 08 API; source of `backend/openapi/08.yaml`."""

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from ffcore.api.schemas import Patch, Strict
from ffcore.guardrails.categories import (
    ACTIONS,
    DECISION_ACTIONS,
    EVENT_SOURCES,
    LANGUAGES,
    MODES,
    NER_CATEGORIES,
    ON_ERROR,
    STAGES,
)
from ffcore.guardrails.schemas import BlockMessage, CustomPattern, PiiCategorySetting, Rule

PolicyKey = Annotated[
    str,
    Field(pattern=r"^[a-z][a-z0-9-]{1,63}$", description="Unique within the project, immutable."),
]
Locale = Literal[LANGUAGES]


# --- PII policies ---


class PiiPolicyCreate(Strict):
    key: PolicyKey
    name: str = Field(min_length=1, max_length=200)
    engine: Literal["regex", "ner"] = Field(
        default="regex",
        description="`ner`: the regex recognizers plus the NER model (PERSON, ORGANIZATION, "
        "LOCATION); needs NER_MODEL / NER_REVISION.",
    )
    default_action: Literal[ACTIONS] = "redact"
    languages: list[Locale] = Field(default_factory=lambda: list(LANGUAGES))
    min_confidence: float = Field(default=0.5, ge=0, le=1)
    context_boost: bool = True
    categories: dict[str, PiiCategorySetting] = Field(
        default_factory=dict, description="Canonical category code -> setting."
    )
    custom_patterns: list[CustomPattern] = Field(default_factory=list)
    is_default: bool = False


class PiiPolicyUpdate(Patch):
    name: str = Field(default=None, min_length=1, max_length=200)
    engine: Literal["regex", "ner"] = Field(default=None)
    default_action: Literal[ACTIONS] = Field(default=None)
    languages: list[Locale] = Field(default=None)
    min_confidence: float = Field(default=None, ge=0, le=1)
    context_boost: bool = Field(default=None)
    categories: dict[str, PiiCategorySetting] = Field(default=None)
    custom_patterns: list[CustomPattern] = Field(default=None)
    is_default: bool = Field(default=None)


class PiiPolicyOut(BaseModel):
    id: UUID | None = Field(description="Null for the built-in policy.")
    project_id: UUID
    key: str
    name: str
    engine: str
    default_action: str
    languages: list[str]
    min_confidence: float
    context_boost: bool
    categories: dict[str, PiiCategorySetting]
    custom_patterns: list[CustomPattern]
    is_default: bool
    builtin: bool = Field(description="True: the built-in `default`, not stored.")
    created_at: datetime | None
    updated_at: datetime | None


class PiiPolicyList(BaseModel):
    data: list[PiiPolicyOut]


# --- Guardrail policies ---


class GuardrailPolicyCreate(Strict):
    key: PolicyKey
    name: str = Field(min_length=1, max_length=200)
    rules: list[Rule] = Field(default_factory=list)
    mode: Literal[MODES] = Field(default="monitor", description="A new policy starts in monitor.")
    short_circuit: bool = Field(
        default=True, description="False: rules after a block still run (for the record)."
    )
    on_error: Literal[ON_ERROR] = Field(default="block", description="Fail-closed by default.")
    block_message: BlockMessage = Field(default_factory=BlockMessage)
    is_default: bool = False


class GuardrailPolicyUpdate(Patch):
    name: str = Field(default=None, min_length=1, max_length=200)
    rules: list[Rule] = Field(default=None)
    mode: Literal[MODES] = Field(default=None)
    short_circuit: bool = Field(default=None)
    on_error: Literal[ON_ERROR] = Field(default=None)
    block_message: BlockMessage = Field(default=None)
    is_default: bool = Field(default=None)


class GuardrailPolicyOut(BaseModel):
    id: UUID | None = Field(description="Null for the built-in policy.")
    project_id: UUID
    key: str
    name: str
    rules: list[Rule]
    mode: str
    short_circuit: bool
    on_error: str
    block_message: BlockMessage
    is_default: bool
    builtin: bool
    builtin_version: int | None = None
    created_at: datetime | None
    updated_at: datetime | None


class GuardrailPolicyList(BaseModel):
    data: list[GuardrailPolicyOut]


# --- Test panel and internal evaluation ---


class FindingOut(BaseModel):
    rule: str
    category: str
    start: int | None = None
    end: int | None = None
    masked_value: str | None = Field(
        default=None, description="Masked; never equal to the raw value, which is not returned."
    )
    score: float | None = None
    severity: str | None = None
    evidence: str = Field(description="Why it matched, e.g. 'checksum valid · context word'.")
    action: str | None = None


class GuardrailTestRequest(Strict):
    text: str = Field(min_length=1)
    stage: Literal[STAGES] = "input.pre"
    policy_key: PolicyKey = "default"
    action: Literal["detect", "redact", "mask", "tokenize"] | None = Field(
        default=None,
        description="Set: run the PII policy `policy_key` with this action (PII panel). "
        "Unset: run the guardrail policy `policy_key` as if it were in enforce mode.",
    )
    tool: str | None = Field(default=None, description="'<tool_key>.<action>' for tool.pre.")
    locale: Locale = "en"


class GuardrailTestResult(BaseModel):
    action: Literal[DECISION_ACTIONS]
    text_out: str
    message: str | None
    findings: list[FindingOut]
    policy_mode: str | None = Field(description="The stored mode; the test always enforces.")
    builtin: bool


class EvaluateRequest(Strict):
    project_id: UUID
    stage: Literal[STAGES]
    text: str
    policy_key: PolicyKey = "default"
    run_id: UUID | None = Field(default=None, description="Required for tokenize.")
    source: Literal[EVENT_SOURCES] = "api"
    tool: str | None = None
    locale: Locale = "en"


class EventOut(BaseModel):
    rule: str
    stage: str
    action_taken: str
    status: str
    mode: str
    input_preview: str
    findings: list[dict[str, Any]]
    severity: str | None
    latency_ms: float
    error: str | None


class DecisionOut(BaseModel):
    """CONTRACTS C4 decision as returned to internal callers (06a, 06b)."""

    action: Literal[DECISION_ACTIONS]
    text_out: str
    message: str | None
    reference_id: str | None
    policy_key: str
    builtin: bool
    events: list[EventOut]


# --- 08 tam 1b: internal NER (service account) ---


class NerRequest(Strict):
    text: str = Field(max_length=200_000)
    categories: list[Literal[NER_CATEGORIES]] = Field(min_length=1)


class NerFindingOut(BaseModel):
    """A span and its category; never the value (the caller holds the text)."""

    category: Literal[NER_CATEGORIES]
    start: int
    end: int
    score: float
    evidence: str


class NerResponse(BaseModel):
    model: str
    revision: str
    findings: list[NerFindingOut]
