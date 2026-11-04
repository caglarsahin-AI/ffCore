"""09: Langfuse REST client (fake transport). The live behaviour is measured in state/pr/09.md
(L1-L16) and checked again by the integration tests."""

import functools
import json

import anyio
import pytest
from pydantic import SecretStr

from ffcore.core.config import Settings
from ffcore.evaluation.langfuse_api import LangfuseApi, LangfuseApiError, score_id


def _sync(fn):
    """The suite has no async pytest plugin; tests run their coroutine with anyio (01 style)."""

    @functools.wraps(fn)
    def run():
        return anyio.run(fn)

    return run


class _Resp:
    def __init__(self, status: int, body) -> None:
        self.status_code = status
        self.content = json.dumps(body).encode() if body is not None else b""
        self._body = body

    def json(self):
        return self._body


class _Fake:
    def __init__(self, *responses) -> None:
        self.responses = list(responses)
        self.calls = []

    async def request(self, method, url, *, headers=None, params=None, json=None):
        self.calls.append((method, url, params, json, headers))
        return self.responses.pop(0)


def _settings(**kw):
    base = dict(
        langfuse_host="http://langfuse-web:3000",
        langfuse_public_key=SecretStr("pk-lf-test"),
        langfuse_secret_key=SecretStr("sk-lf-test"),
    )
    base.update(kw)
    return Settings.model_construct(**base)


def test_09_langfuse_not_configured_is_loud():
    with pytest.raises(LangfuseApiError) as e:
        LangfuseApi(_settings(langfuse_host=None))
    assert e.value.code == "langfuse_not_configured"


@_sync
async def test_09_upsert_item_maps_brief_schema():
    fake = _Fake(_Resp(200, {"id": "p.s-q01"}))
    api = LangfuseApi(_settings(), transport=fake)
    await api.upsert_item(
        "p.s",
        "p.s-q01",
        input={"message": "q", "variables": {}},
        expected_output={"must_contain": ["x"]},
        metadata={"style": "dogrudan", "answerable": True},
    )
    method, url, _, body, headers = fake.calls[0]
    assert (method, url) == ("POST", "http://langfuse-web:3000/api/public/dataset-items")
    assert body["datasetName"] == "p.s" and body["id"] == "p.s-q01"
    assert body["expectedOutput"] == {"must_contain": ["x"]} and body["status"] == "ACTIVE"
    assert headers["Authorization"].startswith("Basic ")


@_sync
async def test_09_g3_score_read_rejects_foreign_rows():
    # v2 ignores traceId (L12); if v1 ever did the same, a foreign row must fail loudly.
    rows = [{"id": "a", "traceId": "t1"}, {"id": "b", "traceId": "t2"}]
    api = LangfuseApi(
        _settings(), transport=_Fake(_Resp(200, {"data": rows, "meta": {"totalPages": 1}}))
    )
    with pytest.raises(LangfuseApiError) as e:
        await api.trace_scores("t1")
    assert e.value.code == "langfuse_filter_ignored"


@_sync
async def test_09_score_read_uses_v1_trace_filter_and_pages():
    page1 = {"data": [{"id": "a", "traceId": "t1"}], "meta": {"totalPages": 2}}
    page2 = {"data": [{"id": "b", "traceId": "t1"}], "meta": {"totalPages": 2}}
    fake = _Fake(_Resp(200, page1), _Resp(200, page2))
    rows = await LangfuseApi(_settings(), transport=fake).trace_scores("t1")
    assert [r["id"] for r in rows] == ["a", "b"]
    assert all(c[1].endswith("/api/public/scores") and c[2]["traceId"] == "t1" for c in fake.calls)


@_sync
async def test_09_http_error_is_loud_and_body_free():
    api = LangfuseApi(_settings(), transport=_Fake(_Resp(500, {"message": "secret item text"})))
    with pytest.raises(LangfuseApiError) as e:
        await api.upsert_dataset("p.s", description="d", metadata={})
    assert e.value.code == "langfuse_request_failed" and "secret" not in str(e.value)


@_sync
async def test_09_score_needs_exactly_one_target():
    api = LangfuseApi(_settings(), transport=_Fake())
    with pytest.raises(ValueError):
        await api.upsert_score("x", name="n", value=1, data_type="NUMERIC")


def test_09_score_id_is_deterministic():
    assert score_id("t1", "contains") == "t1-contains"
