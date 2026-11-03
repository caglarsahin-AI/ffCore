"""08-tam-1a r1 MINOR-1, 2, 3, 11 (unit, fakes):

1. A stream that fails (or a model call that fails) after the reveal held a tail: the tail
   reaches the reader before the error, never dropped silently.
2. A direct stream without a finish_reason: the held tail goes out before the usage chunk and
   carries a finish_reason.
3. A value in tool call arguments is JSON-escaped (a `"` in it does not break the JSON).
11. The token store fails while a reader's stream is being prepared: the stream ends with a
    coded `error` event, not silently.
"""

import asyncio
import json
from contextlib import AsyncExitStack
from types import SimpleNamespace

import pytest

from ffcore.core.errors import ApiError
from ffcore.guardrails.masking import RevealUnavailable, StreamDetokenizer
from ffcore.runtime import events as run_events
from ffcore.runtime.graph import model
from ffcore.services import facade_proxy
from tests.unit.test_08t_c17_masking import _store_with
from tests.unit.test_08t_c17_runtime import _ctx, _state

run = asyncio.run
NAME = 'Ayşe "Kaya"'


class Guard:
    scope = "facade-test"
    reveals = True
    streams_live = True

    def __init__(self, store):
        self.store = store

    def stream_reveal(self, *, json_escape=False):
        return StreamDetokenizer(self.store, "run-1", json_escape=json_escape)

    async def text(self, stage, text):
        return text

    async def reveal(self, text, *, json_escape=False):
        return text


class Stream:
    def __init__(self, chunks, fail=None):
        self.chunks, self.fail = chunks, fail
        self.result = SimpleNamespace(fallback=None, call_id="c", usage={})

    def __aiter__(self):
        return self._gen()

    async def _gen(self):
        for chunk in self.chunks:
            yield chunk
        if self.fail is not None:
            raise self.fail


class Gate:
    async def commit(self, **kw):
        return None


def _delta(content=None, finish=None, args=None):
    delta = {}
    if content is not None:
        delta["content"] = content
    if args is not None:
        delta["tool_calls"] = [{"index": 0, "function": {"arguments": args}}]
    return {"choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}


def _relay(chunks, store, fail=None):
    async def go():
        model_row = SimpleNamespace(id="m", name="p.chat", fallback_id=None)
        out = []
        async for line in facade_proxy._relay(
            Stream(chunks, fail), AsyncExitStack(), Gate(), Guard(store), model_row, "p.chat"
        ):
            out.append(line)
        return out

    return run(go())


def _events(lines):
    return [json.loads(line[6:]) for line in lines if line.startswith("data: {")]


def test_08t_r1_minor1_failed_stream_sends_the_held_tail_first():
    store, _ = _store_with([NAME])
    fail = ApiError(502, "api_error", "provider_failed", "The provider failed.")
    lines = _relay([_delta("Sonuç <<PII_")], store, fail=fail)
    data = _events(lines)
    texts = [ch["delta"].get("content") for d in data for ch in d.get("choices") or []]
    assert texts == ["Sonuç ", "<<PII_"]  # the unfinished tail, as it is, before the error
    assert data[-1]["error"]["code"] == "provider_failed"
    assert lines[-1].strip() == "data: [DONE]"


def test_08t_r1_minor1_failed_model_call_publishes_the_tail():
    ctx, rec = _ctx(stream_live=True)

    async def failing(messages, *, tools, max_tokens, on_token):
        await on_token("Sayın <<PII")
        raise RuntimeError("provider gone")

    ctx.model = SimpleNamespace(call=failing)
    with pytest.raises(RuntimeError):
        run(model(_state(), SimpleNamespace(context=ctx)))
    assert rec.published == ["Sayın ", "<<PII"]


def test_08t_r1_minor2_rest_before_usage_with_a_finish_reason():
    store, _ = _store_with([NAME])
    usage = {"choices": [], "usage": {"prompt_tokens": 1, "completion_tokens": 1}}
    data = _events(_relay([_delta("x <<PII_1"), usage], store))
    kinds = ["usage" if d.get("usage") else "delta" for d in data]
    assert kinds == ["delta", "delta", "usage"]
    rest = data[1]["choices"][0]
    assert rest["delta"]["content"] == "<<PII_1"  # unfinished: as it is
    assert rest["finish_reason"] == "stop"


def test_08t_r1_minor3_tool_argument_values_are_json_escaped():
    store, _ = _store_with([NAME])
    chunks = [_delta(args='{"to": "<<PI'), _delta(args='I_1>>"}', finish="tool_calls")]
    data = _events(_relay(chunks, store))
    args = "".join(
        p["function"]["arguments"]
        for d in data
        for ch in d.get("choices") or []
        for p in ch["delta"].get("tool_calls") or []
    )
    assert json.loads(args) == {"to": NAME}


class _NoLiveStream:
    async def exists(self, key):
        return 0


def test_08t_r1_minor11_store_failure_ends_the_stream_with_an_error_event():
    async def replay(after_seq):
        raise RevealUnavailable("ConnectionError")
        yield  # pragma: no cover

    async def finished():
        return True

    async def go():
        return [
            chunk
            async for chunk in run_events.follow(
                _NoLiveStream(),
                "run-1",
                after=None,
                keepalive_s=0.1,
                grace_s=1,
                replay_rows=replay,
                finished=finished,
            )
        ]

    chunks = run(go())
    assert "event: error" in chunks[-1]
    assert '"code":"detokenize_unavailable"' in chunks[-1]
