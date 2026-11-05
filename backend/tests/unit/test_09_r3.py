"""09-1 r3 review (state/reviews/09-1-r3.md, KARARLAR "09-1 r3 kararları"): unit tests.

MAJOR-r3-1 the failure count is reset only by a tick that committed an item; NOTE-6 / MINOR-r3-4
a NER outage on the judge's egress is the item's not_run (`ner_unavailable`), not an error;
MINOR-r3-1 the per-tick judge-call limit is strict after the tick's first item; MINOR-r3-2
active exams in a fixed order, the oldest progress first.
"""

from types import SimpleNamespace

import anyio
from sqlalchemy.dialects import postgresql

from ffcore.evaluation import judge as judge_mod
from ffcore.evaluation import worker_tick
from ffcore.evaluation.engine import item_result
from ffcore.evaluation.runner import Budget
from ffcore.evaluation.scorers import Score
from tests.unit.test_09_engine import _facts, _item
from tests.unit.test_09_judge_ner import TEXT, FakeSession, _egress_ner_on, _guard
from tests.unit.test_09_r2 import _advance_one_with, _summary

# --- MAJOR-r3-1: only a tick that committed an item resets the failure count -----------------


def test_09_r3_major1_tick_without_a_commit_keeps_the_failure_count(monkeypatch):
    async def nothing_saved(*a, budget, **kw):
        pass  # e.g. every item cut by the deadline

    redis, run = _advance_one_with(monkeypatch, nothing_saved)
    run()
    assert redis.deleted == [] and redis.incr_calls == 0


def test_09_r3_major1_tick_that_committed_resets_the_failure_count(monkeypatch):
    async def saved_one(*a, budget, **kw):
        budget.committed += 1

    redis, run = _advance_one_with(monkeypatch, saved_one)
    run()
    assert redis.deleted == [worker_tick.failures_key("ev")]


# --- NOTE-6 / MINOR-r3-4: NER outage on the judge's egress ----------------------------------


class _Ner503:
    """HttpNer as it fails when the API's NER answers 503 (recognizers.ner.NerUnavailable)."""

    model = "fake-ner"

    async def find(self, text, categories):
        from ffcore.guardrails.recognizers.ner import NerUnavailable

        raise NerUnavailable("internal ner failed: 503")


class _Rubric:
    def render(self, **kw):
        return TEXT


class _NeverCalled:
    async def complete(self, text):
        raise AssertionError("the judge model is not called without the egress check")


def test_09_r3_minor4_ner_outage_makes_the_item_not_run(monkeypatch):
    policy = _egress_ner_on(monkeypatch)
    guard = _guard(FakeSession(), policy, _Ner503())
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
    score = result.score
    assert (score.status, score.comment) == ("not_run", "ner_unavailable")
    item = _item(answer="Ayşe Yılmaz")
    r = item_result(item, _facts(), [Score("contains", 1.0, True), score], "")
    assert (r.passed, r.note) == (None, "ner_unavailable")
    ok = item_result(_item("q02"), _facts(), [Score("contains", 1.0, True)], "")
    s = _summary([r, ok])
    assert s["not_run"] == {"ner_unavailable": 1} and s["complete"] is False
    assert s["errors"] == {}


# --- MINOR-r3-1: the judge-call limit is strict after the first item -------------------------


def test_09_r3_minor1_judge_call_limit_is_strict_after_the_first_item():
    b = Budget(2)
    assert b.may_judge(5) is True  # the tick's first item always starts
    b.started, b.judge_calls = 1, 2 - 5
    assert b.may_judge(1) is False
    b = Budget(3)
    b.started, b.judge_calls = 1, 2
    assert b.may_judge(2) is True and b.may_judge(3) is False
    # Upper bound per tick: the limit, or the first item's calls when that is more.
    for limit, calls in ((3, [1, 1, 1, 1]), (3, [2, 2]), (2, [5, 1]), (4, [3, 1, 1])):
        b, used = Budget(limit), 0
        for c in calls:
            if not b.may_judge(c):
                break
            b.started += 1
            b.judge_calls -= c
            used += c
        assert used <= max(limit, calls[0]), (limit, calls, used)


# --- MINOR-r3-2: active exams, the oldest progress first --------------------------------------


def test_09_r3_minor2_active_exams_oldest_progress_first():
    from ffcore.evaluation.runner import active_runs

    captured = {}

    class _S:
        async def scalars(self, stmt):
            captured["sql"] = str(
                stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
            )
            return SimpleNamespace(all=lambda: [])

    anyio.run(active_runs, _S())
    assert "ORDER BY eval_runs.updated_at, eval_runs.id" in captured["sql"]
