"""08-tam-1a r3 MINOR-r3-3 and MINOR-r3-6 (unit, fakes):

r3-3. The token store fails on the facade's other reveal paths (one-piece answer, tool call
      arguments, the buffered stream, the external agent): `FacadeGuard.reveal` turns it into
      502 `detokenize_unavailable`; the buffered stream ends with that error event and `[DONE]`.
r3-6. The live branch: a reader whose reveal failed reconnects with the error's id and gets the
      failed entry again, nothing lost, nothing repeated.
"""

import asyncio
import json

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from ffcore.core.errors import ApiError
from ffcore.guardrails.masking import RevealUnavailable
from ffcore.guardrails.schemas import ResolvedPolicy
from ffcore.guardrails.service import BUILTIN_DEFAULT
from ffcore.services.facade_guard import FacadeGuard
from tests.unit.test_08t_r1_minors import Guard, _delta, _events, _relay
from tests.unit.test_08t_r2_minors import _follow, _ids

run = asyncio.run


class _DownRedis:
    async def hget(self, *args):
        raise RedisConnectionError("down")

    async def hmget(self, *args):
        raise RedisConnectionError("down")

    async def expire(self, *args):
        raise RedisConnectionError("down")


def test_08t_r3_minor3_facade_reveal_maps_store_errors_to_502():
    policy = ResolvedPolicy(key="default", spec=BUILTIN_DEFAULT.spec, builtin=True)
    guard = FacadeGuard(None, _DownRedis(), policy, "p")
    with pytest.raises(ApiError) as caught:
        run(guard.reveal("Sahibi <<PII_1>>"))
    error = caught.value
    assert (error.status_code, error.error_type, error.code) == (
        502,
        "api_error",
        "detokenize_unavailable",
    )


class _BufferedGuard(Guard):
    streams_live = False

    async def reveal(self, text, *, json_escape=False):
        raise ApiError(502, "api_error", "detokenize_unavailable", "down")


def test_08t_r3_minor3_buffered_stream_ends_with_the_error_and_done():
    from tests.unit.test_08t_c17_masking import _store_with

    store, _ = _store_with(["Ayşe Kaya"])
    import tests.unit.test_08t_r1_minors as r1

    original = r1.Guard
    r1.Guard = _BufferedGuard
    try:
        lines = _relay([_delta("Sonuç <<PII_1>>", finish="stop")], store)
    finally:
        r1.Guard = original
    data = _events(lines)
    assert "Ayşe Kaya" not in json.dumps(data, ensure_ascii=False)
    assert data[-1]["error"]["code"] == "detokenize_unavailable"
    assert lines[-1].strip() == "data: [DONE]"


class _Stream:
    """Two token entries; xread honours the position it is given."""

    entries = [
        (b"1-0", {b"event": b"token", b"data": b'{"text": "a"}'}),
        (b"2-0", {b"event": b"token", b"data": b'{"text": "b"}'}),
        (b"3-0", {b"event": b"done", b"data": b"{}"}),
    ]

    async def exists(self, key):
        return 1

    async def set(self, *args, **kwargs):
        return True

    async def xread(self, streams, block, count):
        (last,) = streams.values()
        after = tuple(int(x) for x in last.split("-"))
        rest = [e for e in self.entries if tuple(int(x) for x in e[0].decode().split("-")) > after]
        return [(b"k", rest)] if rest else []


def test_08t_r3_minor6_reconnect_after_the_error_gets_the_failed_entry():
    calls = {"n": 0}

    async def transform(event, data):
        calls["n"] += 1
        if calls["n"] == 2:  # the store fails once, on entry 2-0
            raise RevealUnavailable("ConnectionError")
        return data

    async def replay(after_seq):
        return
        yield  # pragma: no cover

    first = _follow(_Stream(), "0-0", replay, transform)
    resume_at = _ids(first)[-1]
    second = _follow(_Stream(), resume_at, replay, transform)
    assert resume_at == "1-0"
    assert _ids(second) == ["2-0", "3-0"]  # the failed entry again, then the end
    texts = [c for c in first + second if "event: token" in c]
    assert [json.loads(c.split("data: ", 1)[1])["text"] for c in texts] == ["a", "b"]
