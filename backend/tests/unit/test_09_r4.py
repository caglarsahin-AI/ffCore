"""09-1 r4 review (state/reviews/09-1-r4.md, KARARLAR "09-1 r4 kararı", A + ek): unit tests.

MAJOR-r4-1 the tick's first item also needs the time it is planned at (a shared deadline used
up by earlier exams is not a cut); an item planned longer than a whole tick ends at once as
`judge_out_of_time` (`planned_exceeds_tick_budget`); NOTE-9 a judge NER outage is logged.
"""

import logging
import time

import anyio

from ffcore.evaluation import judge as judge_mod
from ffcore.evaluation import worker_tick
from ffcore.evaluation.runner import Budget
from tests.unit.test_09_judge_ner import TEXT, FakeSession, _egress_ner_on, _guard
from tests.unit.test_09_r2 import _window_settings
from tests.unit.test_09_r3 import _Ner503, _NeverCalled, _Rubric


def test_09_r4_major1_first_item_waits_when_the_shared_deadline_is_used_up():
    spent = Budget(20, deadline=time.monotonic() - 1.0, call_s=0.5)
    assert spent.started == 0
    assert spent.may_judge(1) is False and spent.may_judge(0) is False
    tight = Budget(20, deadline=time.monotonic() + 1.0, call_s=0.4)
    assert tight.may_judge(2) is True  # 0.8 s fits
    assert tight.may_judge(3) is False  # 1.2 s does not: wait for a later tick
    assert Budget(20).may_judge(50) is True  # no deadline (tests): no time rule


def test_09_r4_major1_plan_longer_than_a_whole_tick():
    b = Budget(20, deadline=time.monotonic() + 100, call_s=30.0, total_s=100.0)
    assert b.exceeds_tick(3) is False  # 90 s fits in a tick
    assert b.exceeds_tick(4) is True  # 120 s never fits: no tick can start it
    assert b.exceeds_tick(0) is False  # no judge: one call_s
    assert Budget(20).exceeds_tick(99) is False


def test_09_r4_major1_tick_budget_carries_the_whole_tick_length():
    b = worker_tick.tick_budget(_window_settings(open_now=True))
    assert b.total_s == worker_tick.TICK_TIMEOUT_S - worker_tick.TICK_MARGIN_S


def test_09_r4_note9_judge_ner_outage_is_logged_without_content(monkeypatch, caplog):
    policy = _egress_ner_on(monkeypatch)
    guard = _guard(FakeSession(), policy, _Ner503())
    with caplog.at_level(logging.WARNING, logger="ffcore.evaluation"):
        result = anyio.run(
            lambda: judge_mod.judge(
                question="q",
                expected="e",
                answer=TEXT,
                rubric=_Rubric(),
                guard=guard,
                model=_NeverCalled(),
                pass_min=4,
            )
        )
    assert result.score.comment == "ner_unavailable"
    (record,) = [r for r in caplog.records if "eval_judge_ner_unavailable" in r.getMessage()]
    assert record.levelno == logging.WARNING
    assert "Ayşe" not in record.getMessage() and TEXT not in record.getMessage()
