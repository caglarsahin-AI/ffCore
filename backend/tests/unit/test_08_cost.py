"""08-lite: bounded cost on the real evaluate path (review r2 MAJOR-1).

Budgets are upper bounds, not P95: a run over budget fails, and a run that never ends fails at the
same bound (the evaluation runs in a daemon thread, so a quadratic regression cannot hang CI).
The privacy guarantees of review r1 are checked on the same inputs.
"""

import asyncio
import threading
import time

import pytest

from ffcore.guardrails.builtin import BUILTIN_DEFAULT
from ffcore.guardrails.engine import EvalContext, evaluate
from ffcore.guardrails.quality import latency_text

EMAIL = "a.b@example.org"


def timed_evaluate(text: str, budget_s: float):
    result: dict = {}

    def target():
        started = time.perf_counter()
        result["decision"] = asyncio.run(
            evaluate(text, "input.pre", BUILTIN_DEFAULT, ctx=EvalContext(egress_enabled=True))
        )
        result["seconds"] = time.perf_counter() - started

    worker = threading.Thread(target=target, daemon=True)
    worker.start()
    worker.join(budget_s)
    assert not worker.is_alive(), f"evaluate did not finish within {budget_s} s"
    assert result["seconds"] < budget_s, result["seconds"]
    return result["decision"], result["seconds"]


@pytest.mark.parametrize(("repeats", "budget_s"), [(320, 0.5), (640, 0.5), (10_000, 1.0)])
def test_08_9_repeated_value_bounded_and_masked(repeats, budget_s):
    text = (EMAIL + " ") * repeats
    decision, _ = timed_evaluate(text, budget_s)
    pii = next(e for e in decision.events if e.rule.startswith("pii"))
    assert len(pii.matches) == repeats  # no finding skipped
    for event in decision.events:
        assert EMAIL not in event.input_preview
        assert len(event.input_preview) <= 60
        assert "example.org" not in event.input_preview or "[EMAIL_ADDRESS]" in event.input_preview


def test_08_9_largest_allowed_mixed_text_bounded_and_masked():
    text = latency_text(200_000)
    decision, _ = timed_evaluate(text, 1.0)
    for event in decision.events:
        assert "10000000146" not in event.input_preview
        assert "ayse@ornek.com" not in event.input_preview
        assert "4111 1111 1111 1111" not in event.input_preview


def test_08_9_latency_includes_the_preview():
    text = (EMAIL + " ") * 2000
    decision, seconds = timed_evaluate(text, 1.0)
    recorded = sum(e.latency_ms for e in decision.events) / 1000
    # The recorded rule latencies cover the whole evaluation except loop overhead.
    assert recorded >= seconds * 0.5, (recorded, seconds)


def test_08_20_preview_window_edge_never_shows_a_cut_value():
    # A long high-entropy secret runs past the scanned window: only its label may appear, and
    # nothing after the window edge is shown in clear.
    import random

    rng = random.Random(8)
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    secret = "".join(rng.choice(alphabet) for _ in range(6000))
    text = f"key {secret} then {EMAIL}"
    decision, _ = timed_evaluate(text, 1.0)
    for event in decision.events:
        assert event.input_preview.startswith("key [API_TOKEN]"), event.input_preview
        for i in range(0, len(secret) - 8, 97):
            assert secret[i : i + 8] not in event.input_preview
        assert EMAIL not in event.input_preview
