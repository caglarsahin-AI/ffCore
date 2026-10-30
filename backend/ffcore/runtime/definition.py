"""Agent definition (`agent_versions.definition`), contract C8, schema_version 1.

The definition is data: the console fills a form, LangGraph's graph is built from it (brief 06).
Frozen with 06a: an existing field is never removed and never changes meaning; a new field comes
with a default; a document without `schema_version` is version 1.

Unknown fields are rejected (422), not ignored: a typo would otherwise silently do nothing.
Options the runtime does not run yet fail at save time with a coded error, never at run time:
`answer_rules.verify` (off on CPU, brief 06 PayCore note) and `sentence_max` confidence.
"""

import re
from typing import Annotated, Any, Literal

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION = 1
# The runtime does not import the API package (it imports the runtime); test_06a_definition
# checks this equals ffcore.api.schemas.MODEL_KEY_PATTERN.
MODEL_KEY_PATTERN = r"^[a-z][a-z0-9-]{1,63}$"
KEY_PATTERN = r"^[a-z][a-z0-9_-]{0,63}$"
TOOL_KEY_PATTERN = r"^[a-z][a-z0-9-]{0,63}$"
ACTION_PATTERN = r"^[A-Za-z_][A-Za-z0-9_.-]{0,127}$"
DEFAULT_APPROVER = "analyst"
# The model sees an MCP action as `<tool_key>__<action>` (function names take no dot); approval
# lists keep `<tool_key>.<action>`. A tool key has no underscore, so the split is unambiguous.
TOOL_NAME_SEPARATOR = "__"
MODEL_TOOL_NAME_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"
# Variables in instructions: `{{key}}`, the Langfuse prompt syntax (KARARLAR, K-06a-0021).
PLACEHOLDER = re.compile(r"\{\{\s*([a-z][a-z0-9_-]{0,63})\s*\}\}")


def model_tool_name(tool_key: str, action: str) -> str:
    return f"{tool_key}{TOOL_NAME_SEPARATOR}{action}"


def approval_name(model_name: str) -> str | None:
    """`mcp-sql__run_sql` -> `mcp-sql.run_sql`; None for a built-in tool."""
    tool_key, separator, action = model_name.partition(TOOL_NAME_SEPARATOR)
    return f"{tool_key}.{action}" if separator else None


Key = Annotated[str, Field(pattern=KEY_PATTERN)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LangfusePromptRef(_Strict):
    """A managed prompt in Langfuse (02) used instead of an inline system prompt."""

    name: str = Field(min_length=1, max_length=200)
    label: str = Field(default="production", min_length=1, max_length=64)


class Variable(_Strict):
    key: Key
    label: str = Field(min_length=1, max_length=200)
    default: str = Field(default="", max_length=2000)


class KnowledgeFilter(_Strict):
    # Source/area scope passed on to the search filter (v9 P7: PayCore profiles = filtered agents).
    scope: list[str] = Field(default_factory=list, max_length=50)


class KnowledgeRef(_Strict):
    kb_key: Key
    mode: Literal["always", "tool"]
    top_k: int | None = Field(default=None, ge=1, le=50, description="None: the KB default.")
    min_score: float | None = Field(
        default=None, description="Only with the reranker off (one threshold rule, K2)."
    )
    filter: KnowledgeFilter | None = None


class ToolRef(_Strict):
    tool_key: Annotated[str, Field(pattern=TOOL_KEY_PATTERN)]
    actions: list[Annotated[str, Field(pattern=ACTION_PATTERN)]] = Field(min_length=1)


class Approval(_Strict):
    actions: list[str] = Field(
        default_factory=list, description="'<tool_key>.<action>'; joined with needs_approval."
    )
    # The `user` role never approves (brief 06 R5.2); the default approver is analyst (brief 07).
    assign_to: Literal["analyst", "developer", "admin"] = DEFAULT_APPROVER


class Limits(_Strict):
    max_tool_calls: int = Field(default=6, ge=0, le=50)
    max_turns: int = Field(default=10, ge=1, le=50)
    run_timeout_s: int | None = Field(
        default=None, gt=0, description="None: the installation's RUN_TIMEOUT_S."
    )
    context_tokens: int = Field(default=16000, ge=1000)
    output_tokens: int = Field(default=800, ge=16)


class ContextPolicy(_Strict):
    history_turns: int = Field(default=6, ge=0)
    # The summary call is not in 06a (FOLLOWUP-88): past the share, the oldest turns drop and
    # the `budget` event says so.
    history_summarize: bool = True
    history_max_tokens: int = Field(default=3000, ge=0)
    memory_max_tokens: int = Field(default=300, ge=0)
    rag_max_tokens: int = Field(default=4000, ge=0)
    tools_schema_max_tokens: int = Field(default=1500, ge=0)
    output_reserve_tokens: int = Field(default=800, ge=0)
    trim_order: list[Literal["history", "rag", "memory"]] = Field(
        default_factory=lambda: ["history", "rag", "memory"], min_length=3, max_length=3
    )

    @field_validator("trim_order")
    @classmethod
    def _each_once(cls, value: list[str]) -> list[str]:
        if len(set(value)) != 3:
            raise ValueError("trim_order lists history, rag and memory once each")
        return value


class AnswerRules(_Strict):
    cite_sources: bool = True
    unknown_reply: str = Field(default="This information is not in the documents.", min_length=1)
    confidence_formula: Literal["cited", "max", "sentence_max"] = "cited"
    confidence_threshold: float | None = Field(default=None, ge=0, le=1)
    show_confidence: bool = False
    verify: bool = False
    max_answer_tokens: int = Field(default=400, ge=16)


class AgentDefinition(_Strict):
    schema_version: Literal[1] = SCHEMA_VERSION
    model: Annotated[str, Field(pattern=MODEL_KEY_PATTERN, description="Project model key.")]
    system_prompt: str | None = Field(default=None, max_length=20000)
    langfuse_prompt: LangfusePromptRef | None = None
    variables: list[Variable] = Field(default_factory=list)
    knowledge: list[KnowledgeRef] = Field(default_factory=list)
    tools: list[ToolRef] = Field(default_factory=list)
    approval: Approval | None = None
    ask_user: bool = False
    guardrail_policy_key: str = Field(default="default", min_length=1, max_length=64)
    structured_output: dict[str, Any] | None = None
    limits: Limits = Field(default_factory=Limits)
    context_policy: ContextPolicy = Field(default_factory=ContextPolicy)
    answer_rules: AnswerRules = Field(default_factory=AnswerRules)
    reasoning: Literal["none", "model_default"] = "none"
    # Reserved: one runtime profile in the first release (brief 06).
    runtime_profile: Literal["default"] = "default"

    @model_validator(mode="after")
    def _consistent(self) -> "AgentDefinition":
        check_definition(self)
        return self


def _fail(code: str, message: str) -> None:
    # Raised inside a Pydantic validator, so the 422 carries the code in its message.
    raise ValueError(f"{code}: {message}")


def check_definition(d: AgentDefinition) -> None:
    if (d.system_prompt is None) == (d.langfuse_prompt is None):
        _fail("prompt_source", "set exactly one of system_prompt and langfuse_prompt")
    keys = [v.key for v in d.variables]
    if len(keys) != len(set(keys)):
        _fail("variable_duplicate", "variable keys must be unique")
    if d.system_prompt is not None:
        undefined = sorted(set(PLACEHOLDER.findall(d.system_prompt)) - set(keys))
        if undefined:
            _fail("variable_undefined", f"system_prompt uses variables not defined: {undefined}")
    kbs = [k.kb_key for k in d.knowledge]
    if len(kbs) != len(set(kbs)):
        _fail("knowledge_duplicate", "a knowledge base is listed once")
    if any(k.filter and k.filter.scope for k in d.knowledge):
        # 04a search filters by metadata equality only; a scope list would be ignored there.
        _fail("knowledge_filter_not_supported", "knowledge[].filter.scope is not available yet")
    tools = [t.tool_key for t in d.tools]
    if len(tools) != len(set(tools)):
        _fail("tool_duplicate", "a tool is listed once")
    offered = {f"{t.tool_key}.{a}" for t in d.tools for a in t.actions}
    if d.approval is not None:
        unknown = sorted(set(d.approval.actions) - offered)
        if unknown:
            _fail("approval_action_unknown", f"approval lists actions not offered: {unknown}")
    if d.answer_rules.verify:
        _fail("verify_not_supported", "the verification step is not available yet")
    if d.answer_rules.confidence_formula == "sentence_max":
        _fail("confidence_formula_not_supported", "sentence_max is not available yet")
    reserve = d.context_policy.output_reserve_tokens
    if reserve < d.limits.output_tokens:
        _fail("output_reserve_too_small", "output_reserve_tokens must cover limits.output_tokens")
    if d.structured_output is not None:
        try:
            Draft202012Validator.check_schema(d.structured_output)
        except SchemaError as exc:
            _fail("structured_output_invalid", f"not a JSON schema: {exc.message}")


def parse_definition(data: dict[str, Any]) -> AgentDefinition:
    """A stored or submitted definition; a missing schema_version means version 1 (C8)."""
    return AgentDefinition.model_validate({"schema_version": SCHEMA_VERSION, **data})
