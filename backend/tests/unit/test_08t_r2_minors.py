"""08-tam-1a r2 MINOR-r2-2 and MINOR-r2-3 (unit, fakes):

r2-2. The token store fails while a reader's stream is prepared: the `error` event carries the
      id of the last entry the reader got (live and replay alike), so a reconnect with it as
      Last-Event-ID neither loses the failed entry nor repeats what was sent.
r2-3. The token store fails on the facade's direct live stream: the stream ends with a coded
      `detokenize_unavailable` error and `[DONE]`; what the reveal held goes out first as it is
      (placeholders, never a value), not dropped silently.
"""

import asyncio
import json

from redis.exceptions import ConnectionError as RedisConnectionError

from ffcore.guardrails.masking import RevealUnavailable
from ffcore.runtime import events as run_events
from tests.unit.test_08t_c17_masking import _store_with
from tests.unit.test_08t_r1_minors import _delta, _events, _relay

run = asyncio.run


class _Live:
    """A live stream with two token entries; the run is not over."""

    def __init__(self):
        self.reads = 0

    async def exists(self, key):
        return 1

    async def set(self, *args, **kwargs):
        return True

    async def xread(self, streams, block, count):
        self.reads += 1
        if self.reads > 1:
            return []
        entries = [
            (b"1-0", {b"event": b"token", b"data": b'{"text": "a"}'}),
            (b"2-0", {b"event": b"token", b"data": b'{"text": "b"}'}),
        ]
        return [(b"k", entries)]


def _follow(redis, after, replay_rows, transform=None):
    async def finished():
        return False

    async def go():
        return [
            chunk
            async for chunk in run_events.follow(
                redis,
                "run-1",
                after=after,
                keepalive_s=0.1,
                grace_s=1,
                replay_rows=replay_rows,
                finished=finished,
                transform=transform,
            )
        ]

    return run(go())


def _ids(chunks):
    return [c.split("\n")[0].removeprefix("id: ") for c in chunks if c.startswith("id: ")]


def test_08t_r2_minor2_live_error_carries_the_last_delivered_id():
    async def transform(event, data):
        if data["text"] == "b":
            raise RevealUnavailable("ConnectionError")
        return data

    async def replay(after_seq):
        return
        yield  # pragma: no cover

    chunks = _follow(_Live(), "0-0", replay, transform)
    assert "event: error" in chunks[-1]
    assert _ids(chunks) == ["1-0", "1-0"]  # the token it got, then the error with that id


def test_08t_r2_minor2_replay_error_carries_the_last_delivered_id():
    class _Gone:
        async def exists(self, key):
            return 0

    async def replay(after_seq):
        yield run_events.SseMessage("4-0", "token", {"text": "x"})
        yield run_events.SseMessage("5-0", "token", {"text": "y"})
        raise RevealUnavailable("ConnectionError")

    chunks = _follow(_Gone(), "3-0", replay)
    assert "event: error" in chunks[-1]
    assert _ids(chunks)[-1] == "5-0"


def test_08t_r2_minor3_direct_store_failure_ends_with_a_coded_error():
    store, _ = _store_with(["Ayşe Kaya"])

    async def down(scope, token):
        raise RedisConnectionError("down")

    store.lookup = down
    lines = _relay([_delta("Sonuç <<PII_1>> ve <<PII_")], store)
    data = _events(lines)
    texts = [ch["delta"].get("content") for d in data for ch in d.get("choices") or []]
    assert "Ayşe Kaya" not in json.dumps(data, ensure_ascii=False)
    assert texts == ["Sonuç <<PII_1>> ve <<PII_"]  # held as it is, before the error
    assert data[-1]["error"]["code"] == "detokenize_unavailable"
    assert lines[-1].strip() == "data: [DONE]"


class _DownRedis:
    async def hget(self, *args):
        raise RedisConnectionError("down")

    async def hmget(self, *args):
        raise RedisConnectionError("down")


def test_08t_r2_minor2_store_error_becomes_reveal_unavailable():
    import pytest

    from ffcore.api.runs import detokenizer

    hook = detokenizer(_DownRedis(), "run-1")
    with pytest.raises(RevealUnavailable):
        run(hook({"text": "<<PII_1>>"}, "token"))


def test_08t_r2_minor2_facade_agent_maps_the_error_to_502():
    from ffcore.services.facade_agent import Translation

    translation = Translation(cid="c", created=0, model="m", run_id="r", events_on=False)
    translation.on("error", {"code": "detokenize_unavailable", "message": "reconnect"})
    error = translation.error
    assert (error.status_code, error.error_type, error.code) == (
        502,
        "api_error",
        "detokenize_unavailable",
    )
