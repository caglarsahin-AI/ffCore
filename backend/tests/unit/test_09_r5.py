"""09-1 r5 review (state/reviews/09-1-r5.md, KARARLAR "09-1 r5 kararı", K-09-0034): unit tests.

MAJOR-r5-1 one usable-window constant TICK_PLAN_S (600 - 30 - 30 = 540): a plan up to it can
start in a tick, a longer one ends coded; nothing in between waits forever. MINOR-r5-1 a cut
counts only when the item started with at least min(LLM_CALL_TIMEOUT_S x calls, TICK_PLAN_S).
"""

import time

import anyio
import pytest
from pydantic import ValidationError

from ffcore.evaluation import ticks, worker_tick
from ffcore.evaluation.runner import Budget
from tests.unit.test_09_engine import _full, _ItemsApi, _StartSession, _suite, _version
from tests.unit.test_09_r2 import _window_settings


def test_09_r5_major1_one_usable_window_constant():
    assert ticks.TICK_PLAN_S == 540
    assert ticks.TICK_PLAN_S == ticks.TICK_TIMEOUT_S - ticks.TICK_MARGIN_S - ticks.TICK_OVERHEAD_S
    assert worker_tick.tick_budget(_window_settings(open_now=True)).total_s == ticks.TICK_PLAN_S


def test_09_r5_major1_judge_call_estimate_bounded_by_the_usable_window(monkeypatch):
    monkeypatch.setenv("EVAL_JUDGE_CALL_S", str(ticks.TICK_PLAN_S))
    assert _full().eval_judge_call_s == ticks.TICK_PLAN_S
    monkeypatch.setenv("EVAL_JUDGE_CALL_S", str(ticks.TICK_PLAN_S + 1))
    with pytest.raises(ValidationError):
        _full()


def test_09_r5_major1_every_plan_either_starts_or_ends_coded():
    # A tick spends less than TICK_OVERHEAD_S before its first item (lock, listen, load).
    spent = ticks.TICK_OVERHEAD_S - 1
    for call_s, calls in ((540, 1), (540 - 1e-3, 1), (570, 1), (285, 2), (190, 3), (541, 1),
                          (60, 9), (60, 10), (1, 0)):  # fmt: skip
        b = Budget(
            20,
            deadline=time.monotonic() + ticks.TICK_BUDGET_S - spent,
            call_s=float(call_s),
            total_s=float(ticks.TICK_PLAN_S),
        )
        starts, ends = b.may_judge(calls), b.exceeds_tick(calls)
        # advance_eval checks exceeds_tick first: a plan that ends coded never waits either.
        assert starts or ends, (call_s, calls, starts, ends)
        assert ends == (call_s * max(calls, 1) > ticks.TICK_PLAN_S), (call_s, calls)


def test_09_r5_minor1_a_cut_counts_only_after_a_full_window():
    b = Budget(20, call_s=10.0, hard_s=60.0, total_s=float(ticks.TICK_PLAN_S))
    assert b.full_window(1) == 60 and b.full_window(3) == 180 and b.full_window(0) == 60
    assert b.counts_cut(1, 59.9) is False and b.counts_cut(1, 60.0) is True
    # K-09-0034: a hard limit above the usable window: the full tick window is enough.
    slow = Budget(20, call_s=10.0, hard_s=600.0, total_s=float(ticks.TICK_PLAN_S))
    assert slow.full_window(1) == ticks.TICK_PLAN_S
    assert slow.counts_cut(1, ticks.TICK_PLAN_S - 1) is False
    assert slow.counts_cut(1, ticks.TICK_PLAN_S) is True
    assert Budget(20).counts_cut(1, 0.0) is True  # no hard limit known (tests): every cut counts


def test_09_r5_minor1_tick_budget_knows_the_hard_limit():
    settings = _window_settings(open_now=True)
    settings.llm_call_timeout_s = 600
    assert worker_tick.tick_budget(settings).hard_s == 600.0


def test_09_r5_major1_start_compares_with_the_usable_window(monkeypatch):
    from types import SimpleNamespace

    from ffcore.core.errors import ApiError
    from ffcore.evaluation import runner

    async def no_audit(session, entry):
        pass

    monkeypatch.setattr(runner, "write_event", no_audit)

    def start(call_s, repeat):
        settings = SimpleNamespace(eval_max_item_runs=500, eval_judge_call_s=call_s)
        return anyio.run(
            lambda: runner.start_eval(
                _StartSession(),
                settings,
                suite=_suite(scorers=[{"name": "llm_judge"}], repeat=repeat),
                version=_version(),
                starter=runner.Starter("u", "user", "u", "req", None),
                api=_ItemsApi(None),
            )
        )

    for call_s, repeat in ((285, 2), (271, 2), (540, 1), (60, 10)):  # 570, 542, -, 600
        if call_s * repeat > ticks.TICK_PLAN_S:
            with pytest.raises(ApiError) as err:
                start(call_s, repeat)
            assert err.value.code == "eval_plan_exceeds_tick"
        else:
            start(call_s, repeat)
