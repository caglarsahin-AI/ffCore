"""08-lite: bounded cost on the real evaluate path (review r2 MAJOR-1).

Cost is checked as a scaling ratio, never as an absolute time (K-SEN-0015; KARARLAR: a unit test
has no absolute wall-clock or CPU limit). The process CPU time (`time.process_time`: the event
loop and the `asyncio.to_thread` workers the rules run in) for N=10000 repeated values over N=1000,
each the best of REPEATS runs, stays under MAX_RATIO: linear cost gives about 10, quadratic about
100, and machine speed or host load affect both runs alike (FOLLOWUP-76). A run that never ends
fails at HANG_S of wall-clock time (the evaluation runs in a daemon thread, so it cannot hang CI).
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
HANG_S = 10
MAX_RATIO = 25
REPEATS = 3


def run_evaluate(text: str):
    """Decision, process CPU seconds and wall-clock seconds; fails only if it never ends."""
    result: dict = {}

    def target():
        started, cpu = time.perf_counter(), time.process_time()
        result["decision"] = asyncio.run(
            evaluate(text, "input.pre", BUILTIN_DEFAULT, ctx=EvalContext(egress_enabled=True))
        )
        result["cpu"] = time.process_time() - cpu
        result["seconds"] = time.perf_counter() - started

    worker = threading.Thread(target=target, daemon=True)
    worker.start()
    worker.join(HANG_S)
    assert not worker.is_alive(), f"evaluate did not finish within {HANG_S} s (hang guard)"
    return result["decision"], result["cpu"], result["seconds"]


def best_cpu(text: str) -> float:
    return min(run_evaluate(text)[1] for _ in range(REPEATS))


@pytest.mark.parametrize("repeats", [320, 640, 10_000])
def test_08_9_repeated_value_bounded_and_masked(repeats):
    text = (EMAIL + " ") * repeats
    decision, _, _ = run_evaluate(text)
    pii = next(e for e in decision.events if e.rule.startswith("pii"))
    assert len(pii.matches) == repeats  # no finding skipped
    for event in decision.events:
        assert EMAIL not in event.input_preview
        assert len(event.input_preview) <= 60
        assert "example.org" not in event.input_preview or "[EMAIL_ADDRESS]" in event.input_preview


def test_08_9_cost_scales_linearly():
    small = best_cpu((EMAIL + " ") * 1_000)
    large = best_cpu((EMAIL + " ") * 10_000)
    assert small > 0, small
    assert large / small < MAX_RATIO, (large / small, small, large)


def test_08_9_largest_allowed_mixed_text_bounded_and_masked():
    text = latency_text(200_000)
    decision, _, _ = run_evaluate(text)
    for event in decision.events:
        assert "10000000146" not in event.input_preview
        assert "ayse@ornek.com" not in event.input_preview
        assert "4111 1111 1111 1111" not in event.input_preview


def test_08_9_latency_includes_the_preview():
    text = (EMAIL + " ") * 2000
    decision, _, seconds = run_evaluate(text)
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
    decision, _, _ = run_evaluate(text)
    for event in decision.events:
        assert event.input_preview.startswith("key [API_TOKEN]"), event.input_preview
        for i in range(0, len(secret) - 8, 97):
            assert secret[i : i + 8] not in event.input_preview
        assert EMAIL not in event.input_preview
