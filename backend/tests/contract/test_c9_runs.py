"""C9 and C10 freeze with 06a: run statuses, run event types, SSE event names, queue names.

Values may only be added (CONTRACTS additive rule). These sets are the frozen ones; a removal or
rename fails here, an addition needs this file and CONTRACTS.md updated in the same PR.
"""

import importlib.util
from pathlib import Path

from ffcore.models import Run, RunEvent
from ffcore.runtime import contracts

FROZEN_STATUSES = {
    "queued",
    "running",
    "waiting_approval",
    "waiting_user",
    "completed",
    "failed",
    "cancelled",
    "abandoned",
}
FROZEN_EVENT_TYPES = {
    "queued",
    "llm_call",
    "tool_call",
    "tool_result",
    "approval_requested",
    "approval_resolved",
    "question",
    "user_answer",
    "guardrail_hook",
    "budget",
    "progress",
    "memory_used",
    "sources",
    "answer",
    "fallback",
    "error",
    # 07 (K-06a-0016): an approval reused within its TTL, and one that expired unanswered.
    "approval_reused",
    "approval_expired",
}
FROZEN_SSE = {
    "token",
    "tool_call",
    "tool_result",
    "approval_required",
    "question",
    "sources",
    "done",
    "error",
    "progress",
    "fallback",
}
FROZEN_QUEUES = ("ingest", "llm-interactive", "llm-background", "sync")
MIGRATION = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "06a_0001_agents_runs.py"


def _migration():
    spec = importlib.util.spec_from_file_location("m06a", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _check_values(table, name: str) -> str:
    for constraint in table.constraints:
        # The naming convention renders "type" as ck_<table>_type.
        if getattr(constraint, "name", None) in (name, f"ck_{table.name}_{name}"):
            return str(constraint.sqltext)
    raise AssertionError(f"no check constraint {name} on {table.name}")


def test_c9_run_statuses_frozen():
    assert {s.value for s in contracts.RunStatus} == FROZEN_STATUSES
    assert set(_migration().RUN_STATUSES) == FROZEN_STATUSES
    for status in FROZEN_STATUSES:
        assert f"'{status}'" in _check_values(Run.__table__, "status")


def test_c9_run_event_types_frozen():
    assert {t.value for t in contracts.RunEventType} == FROZEN_EVENT_TYPES
    assert set(_migration().RUN_EVENT_TYPES) == FROZEN_EVENT_TYPES
    for kind in FROZEN_EVENT_TYPES:
        assert f"'{kind}'" in _check_values(RunEvent.__table__, "type")


def test_c9_sse_event_names_frozen():
    assert {e.value for e in contracts.SseEvent} == FROZEN_SSE
    assert contracts.TERMINAL_SSE <= FROZEN_SSE


def test_c9_facade_channels_present_from_the_start():
    # 06b, 11 and 15 add no enum value (N8).
    assert {c.value for c in contracts.Channel} >= {
        "chat",
        "api",
        "test",
        "slack",
        "teams",
        "mattermost",
        "widget",
    }
    assert set(_migration().RUN_CHANNELS) == {c.value for c in contracts.Channel}


def test_c10_queue_names_frozen():
    assert contracts.QUEUES == FROZEN_QUEUES
