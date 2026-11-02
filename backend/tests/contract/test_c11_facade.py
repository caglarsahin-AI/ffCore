"""C11 (frozen with 06b): the OpenAI-compatible facade's routes, chunk vocabulary and the five
points the coordinator named (K-06b-0002): the refused-impersonation answer, the
`output_buffered` progress, the keepalive form, `tool_calls` deltas, and the external agent's
event subset. Values may be added (additive); nothing here may be removed or renamed."""

from pathlib import Path

from ffcore.api import facade_schemas as c11
from ffcore.main import app

CONTRACTS = Path(__file__).resolve().parents[3] / "handbook" / "CONTRACTS.md"

FROZEN = {
    "FINISH_REASONS": ("stop", "length", "tool_calls", "content_filter", "approval_required"),
    "X_PLATFORM_EVENTS": (
        "tool_call",
        "tool_result",
        "sources",
        "approval_required",
        "question",
        "progress",
        "fallback",
    ),
    "PROGRESS_KINDS": ("queued", "output_buffered", "keepalive"),
    "KEEPALIVE": ": keepalive\n\n",
    "STREAM_END": "data: [DONE]\n\n",
    "AGENT_EVENTS_HEADER": "X-Agent-Events",
    "CONVERSATION_HEADER": "X-Conversation-Id",
    "RESUME_HEADER": "X-Resume-Run-Id",
    "AGENT_PREFIX": "agent:",
}


def test_c11_frozen_values_keep_their_prefix():
    for name, frozen in FROZEN.items():
        current = getattr(c11, name)
        if isinstance(frozen, tuple):
            assert current[: len(frozen)] == frozen, name
        else:
            assert current == frozen, name


def test_c11_error_codes_include_the_frozen_ones():
    frozen = {
        "invalid_api_key",
        "impersonation_denied",
        "scope_missing",
        "model_not_found",
        "agent_not_published",
        "guardrail_blocked",
        "quota_exceeded",
        "output_buffer_exceeded",
        "external_agent_not_available",
        "unsupported_field",
    }
    assert frozen <= set(c11.FACADE_ERROR_CODES)


def test_c11_routes_exist():
    # FastAPI keeps included routers nested; the generated schema lists every route.
    paths = app.openapi()["paths"]
    assert "post" in paths["/v1/chat/completions"]
    assert "get" in paths["/v1/models"]


def test_c11_contracts_row_names_the_five_points():
    row = next(
        line for line in CONTRACTS.read_text(encoding="utf-8").splitlines() if "| C11 |" in line
    )
    for needle in (
        "impersonation_denied",
        "output_buffered",
        ": keepalive",
        "tool_calls",
        "kind: external",
        "x_platform",
        "annotations[]",
    ):
        assert needle in row, needle
