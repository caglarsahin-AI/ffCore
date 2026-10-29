"""Frozen run vocabulary (C9) and queue names (C10), one place for code, schemas and tests.

C9 and C10 freeze with 06a: values are only added, never renamed or removed. Consumers (10, 11,
15) ignore an SSE event they do not know.
"""

from enum import StrEnum


class RunStatus(StrEnum):
    queued = "queued"
    running = "running"
    waiting_approval = "waiting_approval"
    waiting_user = "waiting_user"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"
    # No client listened past RUN_ABANDON_GRACE_S; stopped at the next step boundary (K-06a-0002).
    abandoned = "abandoned"


WAITING = frozenset({RunStatus.waiting_approval, RunStatus.waiting_user})
FINISHED = frozenset(
    {RunStatus.completed, RunStatus.failed, RunStatus.cancelled, RunStatus.abandoned}
)


class RunEventType(StrEnum):
    queued = "queued"
    llm_call = "llm_call"
    tool_call = "tool_call"
    tool_result = "tool_result"
    approval_requested = "approval_requested"
    approval_resolved = "approval_resolved"
    question = "question"
    user_answer = "user_answer"
    guardrail_hook = "guardrail_hook"
    budget = "budget"
    progress = "progress"
    memory_used = "memory_used"
    sources = "sources"
    answer = "answer"
    fallback = "fallback"
    error = "error"


class SseEvent(StrEnum):
    token = "token"
    tool_call = "tool_call"
    tool_result = "tool_result"
    approval_required = "approval_required"
    question = "question"
    sources = "sources"
    done = "done"
    error = "error"
    progress = "progress"
    fallback = "fallback"


# The stream of one run ends with one of these.
TERMINAL_SSE = frozenset(
    {SseEvent.done, SseEvent.error, SseEvent.approval_required, SseEvent.question}
)


class Channel(StrEnum):
    chat = "chat"
    api = "api"
    test = "test"
    slack = "slack"
    teams = "teams"
    mattermost = "mattermost"
    widget = "widget"


class TriggerType(StrEnum):
    chat = "chat"
    api = "api"
    schedule = "schedule"
    webhook = "webhook"


class OutcomeLabel(StrEnum):
    answered = "answered"
    declined = "declined"
    below_threshold = "below_threshold"


class AgentStatus(StrEnum):
    draft = "draft"
    published = "published"
    inactive = "inactive"


class AgentKind(StrEnum):
    native = "native"
    external = "external"


class JobClass(StrEnum):
    """Scheduling classes (C10): who goes first at the model slot."""

    interactive = "interactive"
    interactive_low = "interactive_low"
    background = "background"


# C10 queue names. `ingest` belongs to 04a, `sync` to 16; listed so the set is frozen in one place.
QUEUES = ("ingest", "llm-interactive", "llm-background", "sync")
