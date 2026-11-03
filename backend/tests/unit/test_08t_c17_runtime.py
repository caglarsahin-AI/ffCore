"""08-tam-1a, C17 on the writing side: a run's live `token` entries never end inside a
placeholder, so the readers (console stream, facade agent path) can reverse entry by entry."""

import asyncio
from types import SimpleNamespace

from ffcore.guardrails.masking import PLACEHOLDER
from ffcore.runtime.definition import parse_definition
from ffcore.runtime.graph import model
from ffcore.runtime.state import ModelTurn
from tests.integration.runtime_support import definition
from tests.unit.test_134_egress_all_messages import MaskingGuard

run = asyncio.run
DELTAS = ["Sayın <<PII", "_1>>, ", "başvurunuz <", "<PII_23>> ile", " eşleşti <<PII_"]
ANSWER = "".join(DELTAS)


class StreamingModel:
    def __init__(self):
        self.published = []

    async def call(self, messages, *, tools, max_tokens, on_token):
        for delta in DELTAS:
            if on_token is not None:
                await on_token(delta)
        return ModelTurn(
            content=ANSWER,
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
        return None

    async def live(self, event, data):
        self.published.append(data["text"])


def _ctx(stream_live):
    rec = StreamingModel()
    ctx = SimpleNamespace(
        definition=parse_definition(definition(knowledge=[])),
        model=rec,
        events=rec,
        guard=MaskingGuard(),
        egress_cache={},
        tools=SimpleNamespace(schemas=lambda: []),
        stream_live=stream_live,
    )

    async def boundary(_):
        return None

    ctx.boundary = boundary
    return ctx, rec


def _state():
    return {
        "messages": [{"role": "user", "content": "x"}],
        "iteration": 0,
        "usage": {},
        "timing": {},
        "sources": [],
    }


def test_08t_8_live_tokens_carry_whole_placeholders():
    ctx, rec = _ctx(stream_live=True)
    out = run(model(_state(), SimpleNamespace(context=ctx)))
    assert "".join(rec.published) == ANSWER  # nothing dropped, the open tail comes at the end
    bounds, at = [], 0
    for piece in rec.published:
        bounds.append((at, at + len(piece)))
        at += len(piece)
    for match in PLACEHOLDER.finditer(ANSWER):
        assert any(a <= match.start() and match.end() <= b for a, b in bounds), rec.published
    assert rec.published[-1] == "<<PII_"  # an unfinished placeholder is given as it is at the end
    assert out["answer"] == ANSWER  # stored text unchanged (tokenized)


def test_08t_8_no_live_tokens_when_output_is_buffered():
    ctx, rec = _ctx(stream_live=False)
    run(model(_state(), SimpleNamespace(context=ctx)))
    assert rec.published == []
