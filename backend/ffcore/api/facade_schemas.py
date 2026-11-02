"""OpenAI-compatible facade shapes (06b, CONTRACTS C11).

OpenAI fields keep OpenAI's meaning; everything FFCore adds lives under `x_platform` (one event
per chunk) or in `annotations[]` (OpenAI `url_citation`). The tuples below are frozen with C11:
values may be added, never removed or renamed (tests/contract/test_c11_facade.py).
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# Why a choice ended. `approval_required` is FFCore's: the run waits for a person in the
# console (C4: the client cannot approve); the chunk carries x_platform.approval_id and run_id.
FINISH_REASONS = ("stop", "length", "tool_calls", "content_filter", "approval_required")

# x_platform.event values on the agent path; OpenAI clients ignore the unknown field.
X_PLATFORM_EVENTS = (
    "tool_call",
    "tool_result",
    "sources",
    "approval_required",
    "question",
    "progress",
    "fallback",
)
# An external agent (agents.kind = external) is reserved: a request answers 501
# external_agent_not_available until 06b-2; its event subset is frozen when it exists (K-06b-0004).
# x_platform.kind of a progress event the facade itself adds (S4): the answer is held back until
# the output guardrail has checked it, so the first token comes later.
PROGRESS_KINDS = ("queued", "output_buffered", "keepalive")

# The SSE comment line sent while a run produces nothing; OpenAI clients skip comments (S6).
KEEPALIVE = ": keepalive\n\n"
STREAM_END = "data: [DONE]\n\n"

# Header switching the x_platform events off (text only).
AGENT_EVENTS_HEADER = "X-Agent-Events"
CONVERSATION_HEADER = "X-Conversation-Id"
RESUME_HEADER = "X-Resume-Run-Id"

# Error codes the facade answers with (OpenAI error schema, 03b). `impersonation_denied` is the
# one answer for every refused `user` mapping (S1: unknown e-mail and non-member look the same).
FACADE_ERROR_CODES = (
    "invalid_api_key",
    "impersonation_denied",
    "scope_missing",
    "model_not_found",
    "agent_not_published",
    "guardrail_blocked",
    "quota_exceeded",
    "output_buffer_exceeded",
    "model_unavailable",
    "run_not_found",
    "external_agent_not_available",
    # Review r1 MAJOR-1: a message field outside OpenAI's known ones is refused, not passed.
    "unsupported_field",
    # Review r2: a supported parameter with a wrong type or out of range (`param` names it).
    "invalid_parameter",
)

# The model name prefix of the agent path (C1: agent:<project_key>/<agent_key>).
AGENT_PREFIX = "agent:"


class ChatMessage(BaseModel):
    # Other fields are parsed so the facade can refuse them the OpenAI way, 400
    # `unsupported_field` (facade_guard.client_messages); a parse-time refusal would be the
    # app's 422 `validation_error`. Nothing outside MESSAGE_FIELDS is ever passed on.
    model_config = ConfigDict(extra="allow")

    role: Literal["system", "developer", "user", "assistant", "tool"]
    content: str | list[dict[str, Any]] | None = None
    name: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None


# The numeric request parameters and their OpenAI ranges (review r2): (type, minimum, maximum).
# A wrong type (text, bool) or a value out of range is 400 `invalid_parameter` with `param` set;
# the value never reaches LiteLLM. The model parses them loosely so that the facade, not the
# app's 422 handler, answers (as for message fields); the schema below still shows the types.
NUMERIC_PARAMS: dict[str, tuple[str, float | None, float | None]] = {
    "temperature": ("number", 0, 2),
    "top_p": ("number", 0, 1),
    "presence_penalty": ("number", -2, 2),
    "frequency_penalty": ("number", -2, 2),
    "max_tokens": ("integer", 1, None),
    "max_completion_tokens": ("integer", 1, None),
    "seed": ("integer", None, None),
    "n": ("integer", 1, 1),  # one choice only
}


def _numeric(name: str) -> Any:
    kind, low, high = NUMERIC_PARAMS[name]
    schema = {"type": kind}
    if low is not None:
        schema["minimum"] = low
    if high is not None:
        schema["maximum"] = high
    return Field(default=None, json_schema_extra={"anyOf": [schema, {"type": "null"}]})


class ChatCompletionRequest(BaseModel):
    # Other fields are parsed so the facade can refuse them the OpenAI way, 400
    # `unsupported_field` (facade_proxy.call_params); nothing outside the documented parameters
    # is passed on or dropped silently.
    model_config = ConfigDict(extra="allow")

    model: str = Field(min_length=1, max_length=300)
    messages: list[ChatMessage] = Field(min_length=1)
    stream: bool = False
    user: str | None = Field(default=None, max_length=320)
    max_tokens: Any = _numeric("max_tokens")
    max_completion_tokens: Any = _numeric("max_completion_tokens")
    temperature: Any = _numeric("temperature")
    top_p: Any = _numeric("top_p")
    presence_penalty: Any = _numeric("presence_penalty")
    frequency_penalty: Any = _numeric("frequency_penalty")
    seed: Any = _numeric("seed")
    tools: list[dict[str, Any]] | None = None
    tool_choice: str | dict[str, Any] | None = None
    n: Any = _numeric("n")


class ModelEntry(BaseModel):
    id: str
    object: Literal["model"] = "model"
    created: int
    owned_by: str


class ModelList(BaseModel):
    object: Literal["list"] = "list"
    data: list[ModelEntry]
