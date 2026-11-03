"""08-tam-1a, C17 on the facade's direct model path, live stream: a placeholder split over two
OpenAI chunks (content or tool call arguments) reaches the caller as its value, and nothing is
left behind the finish_reason."""

import asyncio
import json

from ffcore.guardrails.masking import StreamDetokenizer
from ffcore.services.facade_proxy import _LiveReveal
from tests.unit.test_08t_c17_masking import _store_with

run = asyncio.run


class Guard:
    scope = "facade-test"
    reveals = True

    def __init__(self, store):
        self.store = store

    def stream_reveal(self):
        return StreamDetokenizer(self.store, "run-1")


def _choice(content=None, args=None, finish=None, call=0):
    delta = {}
    if content is not None:
        delta["content"] = content
    if args is not None:
        delta["tool_calls"] = [{"index": call, "function": {"arguments": args}}]
    return {"index": 0, "delta": delta, "finish_reason": finish}


def _relay(chunks, store):
    async def go():
        revealer = _LiveReveal(Guard(store))
        out = [await revealer.choice(c) for c in chunks]
        rest = await revealer.rest()
        return out, rest, revealer.unresolved

    return run(go())


def test_08t_7c_live_content_split_placeholder_reversed():
    store, _ = _store_with(["Ayşe Kaya"])
    chunks = [_choice("Sayın <<PII"), _choice("_1>>, hoş"), _choice(" geldiniz", finish="stop")]
    out, rest, unresolved = _relay(chunks, store)
    texts = [c["delta"].get("content", "") for c in out]
    assert "".join(texts) == "Sayın Ayşe Kaya, hoş geldiniz"
    assert not any("<<" in t or "PII" in t for t in texts)
    assert rest == {} and unresolved == 0


def test_08t_7c_held_tail_goes_out_with_the_finish():
    store, _ = _store_with(["Ayşe Kaya"])
    out, rest, _ = _relay([_choice("Sonuç <<PII_1"), _choice(">>", finish="stop")], store)
    assert out[-1]["delta"]["content"] == "Ayşe Kaya"
    assert out[-1]["finish_reason"] == "stop" and rest == {}


def test_08t_7c_stream_without_finish_gives_the_rest():
    store, _ = _store_with(["Ayşe Kaya"])
    out, rest, unresolved = _relay([_choice("x <<PII_")], store)
    assert out[0]["delta"]["content"] == "x "
    assert rest == {"content": "<<PII_"}  # unfinished, not a placeholder: given as it is
    assert unresolved == 0


def test_08t_7c_tool_call_arguments_split_reversed():
    store, _ = _store_with(["Ayşe Kaya"])
    chunks = [_choice(args='{"to": "<<PI'), _choice(args='I_1>>"}', finish="tool_calls")]
    out, rest, _ = _relay(chunks, store)
    args = "".join(
        p["function"]["arguments"] for c in out for p in c["delta"].get("tool_calls", [])
    )
    assert json.loads(args) == {"to": "Ayşe Kaya"}
    assert rest == {}


def test_08t_9_unknown_placeholder_stays_and_is_counted():
    store, _ = _store_with(["Ayşe Kaya"])
    out, _, unresolved = _relay([_choice("<<PII_9>> geldi", finish="stop")], store)
    assert out[0]["delta"]["content"] == "<<PII_9>> geldi"
    assert unresolved == 1
