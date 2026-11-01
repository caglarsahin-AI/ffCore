"""BLOCKERS 134: every message that goes to the model passes egress on every call."""

import asyncio
import re
from types import SimpleNamespace

import pytest

from ffcore.runtime.contracts import RunStatus
from ffcore.runtime.definition import parse_definition
from ffcore.runtime.graph import model
from ffcore.runtime.state import GuardResult, ModelTurn, StopRun
from tests.integration.runtime_support import ScriptedGuard, definition

run = asyncio.run
EMAIL = re.compile(r"[\w.]+@[\w.]+")


class MaskingGuard(ScriptedGuard):
    """Tokenizes e-mail and phone like the built-in egress rule; idempotent on placeholders."""

    def __init__(self, egress=True, block_word=None):
        super().__init__()
        self.egress, self.block_word, self.tokens = egress, block_word, {}

    async def check(self, stage, text, *, tool=None):
        self.seen.append((stage, text))
        if stage != "egress" or not self.egress:
            return GuardResult("allow", text, None, None, 0)
        if self.block_word and self.block_word in text:
            return GuardResult("block", "", "Blocked.", "ref-1", 1)

        def token(m):
            return self.tokens.setdefault(m.group(0), f"<<PII_{len(self.tokens) + 1}>>")

        masked = re.sub(r"\+90\d{10}", token, EMAIL.sub(token, text))
        return GuardResult("tokenize" if masked != text else "allow", masked, None, None, 0)


class Recorder:
    def __init__(self):
        self.sent, self.events = [], []

    async def call(self, messages, *, tools, max_tokens, on_token):
        self.sent.append(messages)
        return ModelTurn(
            content="ok",
            tool_calls=[],
            model="m",
            call_id="c",
            finish_reason="stop",
            usage={},
            ms=1,
            queue_ms=0,
            fallback=None,
        )

    async def record(self, kind, payload, **kw):
        self.events.append((kind, payload))


def _ctx(guard):
    rec = Recorder()
    ctx = SimpleNamespace(
        definition=parse_definition(definition(knowledge=[])),
        model=rec,
        events=rec,
        guard=guard,
        egress_cache={},
        tools=SimpleNamespace(schemas=lambda: []),
        stream_live=False,
    )

    async def boundary(_):
        return None

    ctx.boundary = boundary
    return ctx, rec


def _state(messages):
    return {"messages": messages, "iteration": 0, "usage": {}, "timing": {}, "sources": []}


MESSAGES = [
    {"role": "system", "content": "Contact admin@corp.test for help."},
    {"role": "user", "content": "my mail is ali@example.com"},
    {"role": "assistant", "content": "noted ali@example.com"},
    {"role": "tool", "tool_call_id": "t1", "content": "row: +905321234567"},
    {"role": "user", "content": "<<PII_9>> and more"},
]


def test_134_all_messages_masked_before_model_call():
    ctx, rec = _ctx(MaskingGuard())
    run(model(_state(MESSAGES), SimpleNamespace(context=ctx)))
    sent = "\n".join(m["content"] for m in rec.sent[0])
    assert not re.search(r"@|\+90\d", sent)
    assert "<<PII_9>> and more" in sent  # an existing placeholder is not matched again
    logged = next(p for k, p in rec.events if k.value == "llm_call")["request_messages"]
    assert logged == rec.sent[0]


def test_134_idempotent_and_cached_per_run():
    guard = MaskingGuard()
    ctx, rec = _ctx(guard)
    run(model(_state(MESSAGES), SimpleNamespace(context=ctx)))
    first = rec.sent[0]
    calls = len([1 for s, _ in guard.seen if s == "egress"])
    run(model(_state(MESSAGES), SimpleNamespace(context=ctx)))
    assert rec.sent[1] == first
    assert len([1 for s, _ in guard.seen if s == "egress"]) == calls  # cache hit, no re-check
    ctx2, rec2 = _ctx(guard)  # a fresh cache (resume): same tokens, same text
    run(model(_state(first), SimpleNamespace(context=ctx2)))
    assert rec2.sent[0] == first


def test_134_block_fails_run_loud():
    ctx, rec = _ctx(MaskingGuard(block_word="row:"))
    with pytest.raises(StopRun) as raised:
        run(model(_state(MESSAGES), SimpleNamespace(context=ctx)))
    assert raised.value.status == RunStatus.failed and raised.value.code == "guardrail_block"
    assert rec.sent == []


def test_134_airgap_egress_off_sends_unchanged():
    ctx, rec = _ctx(MaskingGuard(egress=False))
    run(model(_state(MESSAGES), SimpleNamespace(context=ctx)))
    assert rec.sent[0] == MESSAGES
