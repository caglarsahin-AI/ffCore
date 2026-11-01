"""06b units: target names, the refused parameters, Redis-less quota (fail-closed, K-06b-0001
item 4), and the run-event → OpenAI chunk translation (masking, annotations, approval)."""

import asyncio

import pytest

from ffcore.api.facade import parse_target
from ffcore.api.facade_schemas import ChatCompletionRequest
from ffcore.core.config import Settings
from ffcore.core.errors import ApiError
from ffcore.services import facade_proxy
from ffcore.services.facade_agent import Translation
from ffcore.services.facade_identity import FacadeCaller
from tests.dummy import OBO_SECRET, SERVICE_TOKEN, SETTINGS_03A


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("hastane.chat-default", ("model", "chat-default")),
        ("chat-default", ("model", "chat-default")),
        ("baska.chat-default", ("model", None)),
        ("agent:hastane/asistan", ("agent", "asistan")),
        ("agent:baska/asistan", ("agent", None)),
        ("agent:hastane", ("agent", None)),
        ("agent:hastane/", ("agent", None)),
    ],
)
def test_06b_target_names(name, expected):
    assert parse_target(name, "hastane") == expected


def _body(**extra):
    return ChatCompletionRequest.model_validate(
        {"model": "chat-default", "messages": [{"role": "user", "content": "x"}], **extra}
    )


def test_06b_7_unknown_parameters_refused():
    with pytest.raises(ApiError) as exc:
        facade_proxy.call_params(_body(api_base="http://x", fallbacks=["y"]))
    assert exc.value.code == "parameter_not_supported"
    assert "api_base" in exc.value.message and "fallbacks" in exc.value.message
    with pytest.raises(ApiError):
        facade_proxy.call_params(_body(n=2))
    assert facade_proxy.call_params(_body(temperature=0.2, max_tokens=5)) == {
        "temperature": 0.2,
        "max_tokens": 5,
    }


def test_06b_6_redis_down_503():
    settings = Settings(
        deploy_profile="llmaas",
        service_token=SERVICE_TOKEN,
        obo_jwt_secret=OBO_SECRET,
        redis_url=None,
        **SETTINGS_03A,
    )
    caller = FacadeCaller(actor=None, key_id="k", project_id="p", scopes=frozenset({"chat_direct"}))

    class Target:
        key, name = "chat-default", "p.chat-default"

    with pytest.raises(ApiError) as exc:
        asyncio.run(facade_proxy.complete(None, caller, Target(), _body(), settings))
    assert (exc.value.status_code, exc.value.code) == (503, "quota_unavailable")


def _t(events_on=True) -> Translation:
    return Translation(cid="c", created=1, model="agent:p/a", run_id="r", events_on=events_on)


def test_06b_9_approval_without_events_carries_only_ids():
    data = {
        "action": "mcp-sql__run_sql",
        "arguments": {"sql": "[TR_NATIONAL_ID]"},
        "assign_to": "analyst",
        "approval_id": "ap",
        "expires_at": "2026-11-02T00:00:00Z",
    }
    quiet = _t(events_on=False)
    (chunk,) = quiet.on("approval_required", data)
    assert chunk["choices"][0]["finish_reason"] == "approval_required"
    assert chunk["x_platform"] == {
        "event": "approval_required",
        "run_id": "r",
        "approval_id": "ap",
        "expires_at": "2026-11-02T00:00:00Z",
    }
    (full,) = _t().on("approval_required", data)
    assert full["x_platform"]["arguments"] == {"sql": "[TR_NATIONAL_ID]"}


def test_06b_10_events_none_sends_text_only():
    quiet = _t(events_on=False)
    assert quiet.on("tool_call", {"name": "x", "arguments": {}}) == []
    assert quiet.on("progress", {"status": "queued"}) == []
    assert quiet.on("sources", {"sources": [{"n": 1, "document_name": "d"}]}) == []
    (token,) = quiet.on("token", {"text": "a [1]"})
    assert "x_platform" not in token and token["choices"][0]["delta"] == {"content": "a [1]"}
    assert quiet.annotations()[0]["url_citation"]["title"] == "d"


def test_06b_annotations_follow_markers():
    t = _t()
    t.on(
        "sources",
        {
            "sources": [
                {"n": 1, "kb_key": "kb", "document_id": "d1", "document_name": "a.pdf", "page": 3},
                {"n": 2, "kb_key": "kb", "document_id": "d2", "document_name": "b.pdf"},
            ]
        },
    )
    t.on("token", {"text": "Doksan gün [1]; yazılı [3]."})
    (citation,) = t.annotations()  # [3] names no known source: no annotation for it
    assert citation["url_citation"] == {
        "url": "ffcore://knowledge-bases/kb/documents/d1#page=3",
        "title": "a.pdf",
        "start_index": 11,
        "end_index": 14,
    }


def test_06b_error_codes_map_to_c11():
    t = _t()
    t.on("error", {"code": "guardrail_block", "message": "Blocked.", "reference_id": "ref"})
    assert (t.error.status_code, t.error.code) == (400, "guardrail_blocked")
    assert "ref" in t.error.message
    t2 = _t()
    t2.on("error", {"code": "quota_exceeded", "message": "q"})
    assert (t2.error.status_code, t2.error.code) == (429, "quota_exceeded")
    t3 = _t()
    t3.on("error", {"code": "limit_reached"})
    assert (t3.error.status_code, t3.error.code) == (502, "limit_reached")


def test_06b_unknown_event_ignored():
    assert _t().on("memory_used", {"x": 1}) == []
