"""09-2 D4: FOLLOWUP-176, the items 09-1's reviews left for 09-2 (BLOCKERS 176).

C (r6 PR note 3, KARARLAR "09-1 r6"): a cut of the first item of the first exam of a tick
always counts. r4 NOTE-3 (KARARLAR "09-2 plan kararları"): an API NER that refuses (4xx) or
runs another model is a misconfiguration, a loud tick failure `advance_failed:
ner_misconfigured`; a 5xx or no connection stays `ner_unavailable` (not run). The rest: tests
for behaviour 09-1 had without one.
"""

import asyncio
import time
from types import SimpleNamespace

import anyio
import pytest

from ffcore.evaluation import judge as judge_mod
from ffcore.evaluation import worker_tick
from ffcore.evaluation.engine import deterministic_scores, item_result, summarize
from ffcore.evaluation.runner import Budget, _dump, combine
from ffcore.evaluation.scorers import Score
from tests.unit.test_09_engine import _facts, _item
from tests.unit.test_09_judge_ner import TEXT, FakeSession, _egress_ner_on, _guard
from tests.unit.test_09_r2 import _advance_one_with
from tests.unit.test_09_r3 import _NeverCalled, _Rubric

# --- C: the first item of the tick's first exam always counts its cut -------------------------


def test_09_2_c_first_item_of_the_tick_counts_its_cut():
    first = Budget(20, call_s=1.0, hard_s=100.0, total_s=540.0, first_in_tick=True)
    first.started = 1
    assert first.counts_cut(1, 0.5) is True  # a partial window, but nobody ran before it
    first.started = 2
    assert first.counts_cut(1, 0.5) is False  # a later item of the same exam: the window rule
    other = Budget(20, call_s=1.0, hard_s=100.0, total_s=540.0)
    other.started = 1
    assert other.counts_cut(1, 0.5) is False


def test_09_2_c_only_the_first_held_exam_of_a_tick_is_first(monkeypatch):
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def scope():
        yield SimpleNamespace()

    async def exams(session):
        return [SimpleNamespace(id=i) for i in ("a", "b", "c")]

    async def listen(settings, redis):
        pass

    @asynccontextmanager
    async def lock(redis, ev_id):
        yield ev_id != "a"  # another worker holds "a"

    seen = []

    async def advance(*a, first_in_tick, **kw):
        seen.append((a[5], first_in_tick))

    monkeypatch.setattr(worker_tick.db, "session_scope", scope)
    monkeypatch.setattr(worker_tick, "active_runs", exams)
    monkeypatch.setattr(worker_tick, "keep_listening", listen)
    monkeypatch.setattr(worker_tick, "exam_lock", lock)
    monkeypatch.setattr(worker_tick, "LangfuseApi", lambda settings: None)
    monkeypatch.setattr(worker_tick, "_advance_one", advance)
    anyio.run(worker_tick.tick, None, None, None, None)
    assert seen == [("b", True), ("c", False)]


# --- r4 NOTE-3: NER misconfiguration is a loud tick failure, an outage is not run ---------------


class _NerFails:
    model = "fake-ner"

    def __init__(self, message, **kw):
        self.message, self.kw = message, kw

    async def find(self, text, categories):
        from ffcore.guardrails.recognizers.ner import NerUnavailable

        raise NerUnavailable(self.message, **self.kw)


def _judge_with(monkeypatch, message, **kw):
    policy = _egress_ner_on(monkeypatch)
    guard = _guard(FakeSession(), policy, _NerFails(message, **kw))
    return anyio.run(
        lambda: judge_mod.judge(
            question="q", expected="e", answer=TEXT, rubric=_Rubric(), guard=guard,
            model=_NeverCalled(), pass_min=4,
        )
    )  # fmt: skip


def test_09_2_ner_outage_stays_not_run(monkeypatch):
    # 09-2 r1 MINOR-6/7: told apart by status and code (HttpNer), not by the message text.
    for message, kw in (
        ("internal ner failed: 503", {"status": 503}),
        ("internal ner unreachable: refused", {}),
    ):
        score = _judge_with(monkeypatch, message, **kw).score
        assert (score.status, score.comment) == ("not_run", "ner_unavailable"), message


def test_09_2_ner_misconfiguration_is_a_loud_failure(monkeypatch):
    for message, kw in (
        ("internal ner failed: 401", {"status": 401}),
        ("internal ner failed: 422", {"status": 422}),
        ("API runs NER other@1, worker expects fake-ner@2", {"code": "ner_model_mismatch"}),
    ):
        with pytest.raises(judge_mod.NerMisconfigured):
            _judge_with(monkeypatch, message, **kw)


def test_09_2_worker_judge_lets_a_misconfiguration_through(monkeypatch):
    async def misconfigured(**kw):
        raise judge_mod.NerMisconfigured("internal ner failed: 401")

    class Session:
        async def get(self, model, key):
            return SimpleNamespace(definition={})

    async def policy(*a, **kw):
        return None

    monkeypatch.setattr(worker_tick, "parse_definition",
                        lambda d: SimpleNamespace(guardrail_policy_key="default"))  # fmt: skip
    monkeypatch.setattr(worker_tick, "resolve_policy", policy)
    monkeypatch.setattr(worker_tick.judge_mod, "judge", misconfigured)
    monkeypatch.setattr(worker_tick.judge_mod, "EgressGuard", lambda *a, **kw: None)
    monkeypatch.setattr(worker_tick.judge_mod, "LiteLLMJudgeModel", lambda inner: None)
    monkeypatch.setattr("ffcore.runtime.adapters.LiteLLMModel", lambda *a, **kw: None)
    monkeypatch.setattr("ffcore.services.quota.QuotaGate", lambda *a, **kw: None)
    monkeypatch.setattr("ffcore.services.quota.engine_for", lambda *a: None)
    settings = SimpleNamespace(eval_judge_model="judge", ner_model="m", ner_revision="r")
    run_judge = worker_tick._judge(settings, Session(), None, None, None)
    run = SimpleNamespace(agent_version_id="v", id="r", project_id="p", user_id="u")
    item = {"input": {"message": "q"}, "expectedOutput": {"answer": "a"}}
    with pytest.raises(judge_mod.NerMisconfigured):
        anyio.run(run_judge, run, item, SimpleNamespace(answer="x"), {})


def test_09_2_misconfiguration_ends_the_exam_with_its_code(monkeypatch):
    from contextlib import asynccontextmanager

    from ffcore.evaluation.engine import MAX_ATTEMPTS

    ev = SimpleNamespace(status="running", error_code=None, ended_at=None)

    class _Redis:
        n = 0

        async def incr(self, _k):
            self.n += 1
            return self.n

        async def expire(self, *_):
            pass

        async def delete(self, *_):
            pass

    class _Sess:
        async def get(self, *_):
            return ev

        async def commit(self):
            pass

    @asynccontextmanager
    async def scope():
        yield _Sess()

    monkeypatch.setattr(worker_tick.db, "session_scope", scope)
    redis = _Redis()
    for _ in range(MAX_ATTEMPTS):
        anyio.run(worker_tick._count_failure, redis, "ev", judge_mod.NerMisconfigured("401"))
    assert (ev.status, ev.error_code) == ("failed", "advance_failed:ner_misconfigured")


# --- tests for 09-1 behaviour that had none (r3 NOTE-1/3/5, r4 NOTE-4/11/13) --------------------


def test_09_2_r3n1_rejection_without_sql_scorer_and_on_unanswerable_items():
    rejected = _facts(answer="cevap", sql=[], sql_rejected=True)
    cfg = {"contains": {"name": "contains"}}
    r = item_result(_item(), rejected, deterministic_scores(_item(), rejected, cfg, None), "")
    assert (r.passed, r.note) == (None, "approval_rejected")
    unanswerable = _item("q2", answerable=False)
    scores = deterministic_scores(unanswerable, rejected, cfg, None)
    r = item_result(unanswerable, rejected, scores, "")
    assert (r.passed, r.note) == (None, "approval_rejected")


def _run_dump(item, res):
    return {"run_id": "r", **_dump(res)}


def test_09_2_r3n3_r4n4_partly_not_run_repeats_keep_their_code():
    item = _item()
    ok = item_result(item, _facts(), [Score("contains", 1.0, True)], "")
    rejected = item_result(item, _facts(sql=[], sql_rejected=True), [], "")
    ner = item_result(item, _facts(), [Score("llm_judge", None, None, "ner_unavailable",
                                             "not_run")], "")  # fmt: skip
    for left_out, key in (
        (rejected, "partial:approval_rejected"),
        (ner, "partial:ner_unavailable"),
    ):
        combined = combine(item, [_run_dump(item, ok), _run_dump(item, left_out)])
        s = summarize([combined], pass_threshold=0.5, warmup_ms=None, latencies_ms=[])
        assert combined.passed is True and s["not_run"] == {key: 1}, key
        assert s["complete"] is False


def test_09_2_r3n5_waiting_tick_neither_counts_nor_resets(monkeypatch):
    # A tick that only waited (window closed, or nothing fitted) saved nothing: the count stays.
    async def waited(*a, budget, **kw):
        return None

    redis, run = _advance_one_with(monkeypatch, waited)
    run()
    assert redis.incr_calls == 0 and redis.deleted == []


def test_09_2_r4n11_start_that_fails_halfway_counts(monkeypatch):
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def scope():
        class _S:
            async def get(self, *_):
                return SimpleNamespace(status="queued", cancel_requested_at=None)

            async def rollback(self):
                pass

        yield _S()

    async def half(*a, **kw):
        raise RuntimeError("queue down after two runs")

    redis, run = _advance_one_with(monkeypatch, None)
    monkeypatch.setattr(worker_tick.db, "session_scope", scope)
    monkeypatch.setattr(worker_tick, "start_items", half)
    monkeypatch.setattr(worker_tick, "_queue", lambda settings: None)
    monkeypatch.setattr(worker_tick, "_queued", lambda: None)
    run()
    assert redis.incr_calls == 1 and redis.deleted == []


def test_09_2_r4n13_a_given_deadline_is_kept_even_when_zero():
    from tests.unit.test_09_r2 import _window_settings

    assert worker_tick.tick_budget(_window_settings(open_now=True), 0.0).deadline == 0.0
    now = time.monotonic()
    assert worker_tick.tick_budget(_window_settings(open_now=True)).deadline > now


def test_09_2_cancelled_error_is_not_swallowed_by_the_c_flag(monkeypatch):
    async def cancelled(*a, budget, **kw):
        raise asyncio.CancelledError

    redis, run = _advance_one_with(monkeypatch, cancelled)
    with pytest.raises(asyncio.CancelledError):
        run()
    assert redis.incr_calls == 1
