"""What a run carries: the checkpointed state, the per-attempt context, and the ports.

`RunState` is checkpointed by LangGraph (Postgres, `checkpoints` schema): plain JSON-like values
only. `RunContext` is passed as LangGraph's runtime context: never checkpointed, rebuilt by the
worker on every attempt (a resumed run gets fresh clients). Nodes reach the outside world only
through the ports, so tests run the real graph with scripted ports.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol, TypedDict

from ffcore.runtime.definition import AgentDefinition
from ffcore.runtime.events import RunEventWriter
from ffcore.runtime.prompting import Budget, Source


class RunState(TypedDict, total=False):
    question: str
    # Model conversation of this run (system + history + this turn), OpenAI message dicts.
    messages: list[dict[str, Any]]
    iteration: int
    tool_calls_used: int
    sources: list[dict[str, Any]]
    pending_tool: dict[str, Any] | None
    answer: str
    outcome: str
    confidence: float | None
    # Milliseconds spent per kind, for the "where did the time go" fields (B1).
    timing: dict[str, int]
    usage: dict[str, int]


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ModelTurn:
    content: str
    tool_calls: list[ToolCall]
    finish_reason: str | None
    usage: dict[str, Any] | None
    fallback: dict[str, str] | None
    model: str
    ms: int
    queue_ms: int = 0
    # LiteLLM's call id (x-litellm-call-id); None when LiteLLM did not send it (K-06a-0007).
    call_id: str | None = None


@dataclass
class ToolOutcome:
    text: str
    truncated: bool
    total_chars: int
    is_error: bool
    latency_ms: int


@dataclass
class GuardResult:
    action: str  # allow or an action_taken value (C4)
    text: str
    message: str | None
    reference_id: str | None
    events: int


class ModelCaller(Protocol):
    async def call(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]],
        max_tokens: int,
        on_token: Callable[[str], Awaitable[None]] | None,
    ) -> ModelTurn: ...


class Retriever(Protocol):
    async def search(
        self, kb_key: str, query: str, top_k: int | None, scope: list[str]
    ) -> tuple[list[Source], dict[str, Any]]: ...


class ToolRunner(Protocol):
    def schemas(self) -> list[dict[str, Any]]: ...

    def needs_approval(self, name: str) -> bool: ...

    async def call(self, name: str, arguments: dict[str, Any]) -> ToolOutcome: ...


class Guard(Protocol):
    async def check(self, stage: str, text: str, *, tool: str | None = None) -> GuardResult: ...


class StopRun(Exception):
    """Ends a run at a step boundary with a final status and code (never a silent stop)."""

    def __init__(self, status: str, code: str | None, message: str | None = None, **extra):
        super().__init__(code or status)
        self.status = status
        self.code = code
        self.message = message
        self.extra = extra


@dataclass
class RunContext:
    run_id: str
    project_id: str
    user_id: str | None
    definition: AgentDefinition
    events: RunEventWriter
    model: ModelCaller
    retriever: Retriever
    tools: ToolRunner
    guard: Guard
    # Checked before every node: cancel, abandon, run timeout (raises StopRun).
    boundary: Callable[[str], Awaitable[None]]
    system: dict[str, str] = field(default_factory=dict)
    history: list[dict[str, str]] = field(default_factory=list)
    budget: Budget | None = None
    # Tokens go to the client while the model writes, unless an enforce-mode policy checks
    # output first (then the answer is shown after output.pre).
    stream_live: bool = True
