"""09: item scoring, summary, repeat, judge (fakes), seed (fake Langfuse), configuration."""

import functools
import json
from pathlib import Path

import anyio
import pytest
from pydantic import SecretStr, ValidationError

from ffcore.core.config import Settings
from ffcore.evaluation import judge as judge_mod
from ffcore.evaluation import seed as seed_mod
from ffcore.evaluation.diagnosis import Candidate
from ffcore.evaluation.engine import (
    ItemFacts,
    deterministic_scores,
    item_result,
    langfuse_scores,
    summarize,
)
from ffcore.evaluation.runner import _dump, combine, parse_csv_rows
from ffcore.evaluation.scorers import Score

REPO = Path(__file__).resolve().parents[3]


def _sync(fn):
    @functools.wraps(fn)
    def run():
        return anyio.run(fn)

    return run


def _item(i="q01", style="dogrudan", answerable=True, **expected):
    return {
        "id": i,
        "input": {"message": "Notice period?", "variables": {}},
        "expectedOutput": expected or {"must_contain": ["90 gün"], "must_cite": ["A.pdf"]},
        "metadata": {"style": style, "answerable": answerable, "expected_docs": ["A.pdf"]},
    }


def _facts(**kw):
    base = dict(
        run_id="r1",
        status="completed",
        error_code=None,
        outcome_label="answered",
        answer="Fesih bildirimi en az 90 gün.",
        trace_id="t1",
        duration_ms=1000,
        cost_usd=0.0,
        selected=["A.txt"],
        candidates=[Candidate("A.pdf", below_floor=False)],
    )
    base.update(kw)
    return ItemFacts(**base)


CFG = {"contains": {"name": "contains"}, "cites_source": {"name": "cites_source"}}


def test_09_1_summary_pass_fail():
    good = item_result(_item(), _facts(), deterministic_scores(_item(), _facts(), CFG, None), "")
    bad_facts = _facts(answer="bilmiyorum")
    bad = item_result(
        _item("q02"), bad_facts, deterministic_scores(_item(), bad_facts, CFG, None), ""
    )
    s = summarize([good, bad], pass_threshold=0.8, warmup_ms=None, latencies_ms=[])
    assert (s["passed_items"], s["scored"], s["pass_rate"], s["passed"]) == (1, 2, 0.5, False)
    s2 = summarize([good], pass_threshold=0.8, warmup_ms=None, latencies_ms=[])
    assert s2["passed"] is True


def test_09_2a_summary_outcome_and_style_distribution():
    a = item_result(_item(), _facts(), [], "")
    b_facts = _facts(candidates=[], selected=[])
    b = item_result(_item("q02", style="dolayli"), b_facts, [], "")
    s = summarize([a, b], pass_threshold=0.8, warmup_ms=None, latencies_ms=[])
    assert s["outcomes"]["answered"] == 1 and s["outcomes"]["not_retrieved"] == 1
    assert s["styles"]["dolayli"]["outcomes"] == {"not_retrieved": 1}
    assert set(s["outcomes"]) >= {"not_reranked", "below_rerank_floor", "unanswerable_held"}


def test_09_2b_not_retrieved_independent_of_judge_score():
    facts = _facts(candidates=[Candidate("B.pdf", below_floor=False)], selected=["B.pdf"])
    judged = [Score("llm_judge", 1.0, True, "score=5")]  # the judge liked the answer
    r = item_result(_item(), facts, judged, "")
    assert r.outcome == "not_retrieved"


def test_09_2c_declined_keeps_answer_text():
    facts = _facts(outcome_label="declined", answer="Belgelerde bulamadım.")
    r = item_result(_item(), facts, deterministic_scores(_item(), facts, CFG, None), "")
    assert r.outcome == "declined" and r.outcome != "answered"
    assert facts.answer == "Belgelerde bulamadım."  # the answer is scored, never dropped


def test_09_2d_warmup_reported_apart():
    r = item_result(_item(), _facts(), [], "")
    s = summarize([r, r], pass_threshold=0.5, warmup_ms=9000, latencies_ms=[1000, 3000])
    assert s["warm_cache"] is True and s["warmup_ms"] == 9000
    assert s["latency_ms"] == {"p50": 2000, "max": 3000}


def test_09_unanswerable_item_scored_by_holding():
    item = _item(answerable=False)
    held = _facts(outcome_label="declined")
    scores = deterministic_scores(item, held, CFG, None)
    assert [(s.name, s.passed) for s in scores] == [("holds", True)]
    assert item_result(item, held, scores, "").outcome == "unanswerable_held"


def test_09_failed_run_fails_item_with_code():
    r = item_result(
        _item(), _facts(status="failed", error_code="limit_reached", outcome_label=None), [], ""
    )
    assert r.passed is False and r.note == "limit_reached" and r.outcome is None


def test_09_not_run_item_counted_apart():
    r = item_result(_item(), None, [], "approval_required")
    s = summarize([r], pass_threshold=0.8, warmup_ms=None, latencies_ms=[])
    assert s["not_run"] == {"approval_required": 1} and s["scored"] == 0 and s["passed"] is False


def test_09_judge_error_fails_item():
    r = item_result(
        _item(), _facts(), [Score("llm_judge", None, None, "judge_output_unreadable", "error")], ""
    )
    assert r.passed is False
    s = summarize([r], pass_threshold=0.5, warmup_ms=None, latencies_ms=[])
    assert s["errors"] == {"judge_output_unreadable": 1}


def test_09_langfuse_scores_carry_no_answer_text():
    r = item_result(_item(), _facts(), deterministic_scores(_item(), _facts(), CFG, None), "")
    rows = langfuse_scores(r, "r1", "t1", "")
    assert {row["name"] for row in rows} == {"contains", "cites_source", "outcome", "passed"}
    assert "90 gün" not in json.dumps(rows, ensure_ascii=False)
    assert all(row["score_id"].startswith("t1-") for row in rows)


def test_09_repeat_combines_by_majority_and_mean():
    item = _item()
    runs = [
        _dump(item_result(item, _facts(), [Score("contains", 1.0, True)], "")),
        _dump(item_result(item, _facts(), [Score("contains", 1.0, True)], "")),
        _dump(item_result(item, _facts(answer="x"), [Score("contains", 0.0, False)], "")),
    ]
    r = combine(item, runs)
    assert r.passed is True and abs(r.scores[0].value - 2 / 3) < 1e-9


def test_09_sql_csv_rows_and_truncation():
    assert parse_csv_rows("bed_capacity\n18\nrows: 1") == [["18"]]
    assert (
        parse_csv_rows("a\n1\nrows: 1\n[truncated: first 1 rows shown; the query returned more]")
        is None
    )


# --- judge with fakes --------------------------------------------------------------------------


class _Rubric:
    def render(self, *, question, expected, answer):
        return f"Q:{question}|E:{expected}|A:{answer}"


class _Guard:
    def __init__(self, action="allow"):
        self.action, self.seen = action, []

    async def egress(self, text):
        self.seen.append(text)
        return self.action, text.replace("ali@example.org", "<<PII_1>>")


class _Model:
    def __init__(self, reply):
        self.reply, self.seen = reply, []

    async def complete(self, text):
        self.seen.append(text)
        return self.reply


@_sync
async def test_09_g2_judge_text_through_egress():
    guard, model = _Guard(), _Model('{"score": 5, "reason": "ok"}')
    r = await judge_mod.judge(
        question="q",
        expected="e",
        answer="mail ali@example.org",
        rubric=_Rubric(),
        guard=guard,
        model=model,
        pass_min=4,
    )
    assert guard.seen and "ali@example.org" in guard.seen[0]
    assert model.seen == ["Q:q|E:e|A:mail <<PII_1>>"]  # the model only sees the egress output
    assert r.score.passed is True and r.score.value == 1.0


@_sync
async def test_09_judge_blocked_at_egress_is_an_error_not_a_score():
    model = _Model('{"score": 5}')
    r = await judge_mod.judge(
        question="q",
        expected="e",
        answer="a",
        rubric=_Rubric(),
        guard=_Guard("block"),
        model=model,
        pass_min=4,
    )
    assert r.score.status == "error" and r.score.comment == "judge_blocked_at_egress"
    assert model.seen == []


@_sync
async def test_09_3_judge_consistency_five_repeats_within_one():
    scores = []
    for _ in range(5):
        r = await judge_mod.judge(
            question="q",
            expected="e",
            answer="a",
            rubric=_Rubric(),
            guard=_Guard(),
            model=_Model('{"score": 4, "reason": "fine"}'),
            pass_min=4,
        )
        scores.append(r.score.value)
    assert max(scores) - min(scores) <= 0.25  # ±1 point on the 1-5 scale


def test_09_judge_reason_clipped_with_mark():
    text = judge_mod.clip("x" * 600)
    assert text.startswith("x" * 500) and text.endswith("[truncated: 500/600 chars]")


# --- seed (fake Langfuse) ----------------------------------------------------------------------


class _FakeApi:
    def __init__(self):
        self.datasets, self.items_by_id = {}, {}

    async def upsert_dataset(self, name, *, description, metadata):
        self.datasets[name] = metadata

    async def upsert_item(
        self, dataset, item_id, *, input, expected_output, metadata, status="ACTIVE"
    ):
        self.items_by_id[item_id] = {
            "id": item_id,
            "datasetName": dataset,
            "status": status,
            "input": input,
            "expectedOutput": expected_output,
            "metadata": metadata,
        }

    async def items(self, dataset):
        return [i for i in self.items_by_id.values() if i["datasetName"] == dataset]


class _Project:
    id, key = "00000000-0000-0000-0000-000000000001", "hastane-a"


class _Session:
    def __init__(self):
        self.added = []
        self.suite = None

    async def scalar(self, stmt):
        text = str(stmt)
        if "FROM projects" in text:
            return _Project()
        return self.suite

    def add(self, row):
        self.added.append(row)
        self.suite = row

    async def commit(self):
        pass


def _settings(**kw):
    return Settings.model_construct(eval_pass_threshold=0.8, eval_judge_model=None, **kw)


def test_09_g1_seed_eval_idempotent(tmp_path):
    suite = REPO / "data" / "samples" / "eval" / "suite.json"
    items = REPO / "data" / "samples" / "eval" / "sozlesme-33.json"
    api, session = _FakeApi(), _Session()

    async def go():
        r1 = await seed_mod.seed(
            session,
            _settings(),
            api,
            project_key="hastane-a",
            suite_path=suite,
            items_path=items,
            without={"llm_judge"},
        )
        r2 = await seed_mod.seed(
            session,
            _settings(),
            api,
            project_key="hastane-a",
            suite_path=suite,
            items_path=items,
            without={"llm_judge"},
        )
        return r1, r2

    r1, r2 = anyio.run(go)
    assert r1.dataset == "hastane-a.sozlesme-33" and len(api.items_by_id) == 33
    assert r1.suite_created and not r2.suite_created and r2.items_archived == 0
    assert all(k.startswith("hastane-a.sozlesme-33-") for k in api.items_by_id)
    assert {s["name"] for s in session.suite.scorers} == {"contains", "cites_source", "sql_result"}

    smaller = tmp_path / "items.json"
    data = json.loads(items.read_text(encoding="utf-8"))[:-1]
    smaller.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    r3 = anyio.run(
        lambda: seed_mod.seed(
            session,
            _settings(),
            api,
            project_key="hastane-a",
            suite_path=suite,
            items_path=smaller,
            without={"llm_judge"},
        )
    )
    assert r3.items_archived == 1


def test_09_seed_refuses_judge_without_model():
    suite = REPO / "data" / "samples" / "eval" / "suite.json"
    items = REPO / "data" / "samples" / "eval" / "sozlesme-33.json"
    with pytest.raises(seed_mod.SeedError, match="EVAL_JUDGE_MODEL"):
        anyio.run(
            lambda: seed_mod.seed(
                _Session(),
                _settings(),
                _FakeApi(),
                project_key="hastane-a",
                suite_path=suite,
                items_path=items,
                without=set(),
            )
        )


# --- configuration -----------------------------------------------------------------------------


def _full(**env):
    base = dict(service_token=SecretStr("x" * 40))
    base.update(env)
    return Settings(**base)


def test_09_g5_threshold_from_config_not_profile_branch(monkeypatch):
    for profile, value in (("llmaas", "0.85"), ("airgap", "0.8")):
        monkeypatch.setenv("DEPLOY_PROFILE", profile)
        monkeypatch.setenv("EVAL_PASS_THRESHOLD", value)
        assert _full().eval_pass_threshold == float(value)
    monkeypatch.setenv("EVAL_PASS_THRESHOLD", "")
    assert _full().eval_pass_threshold is None


def test_09_advance_interval_must_stay_under_abandon_grace(monkeypatch):
    monkeypatch.setenv("EVAL_ADVANCE_INTERVAL_S", "30")
    monkeypatch.setenv("RUN_ABANDON_GRACE_S", "20")
    with pytest.raises(ValidationError, match="eval_advance_interval_invalid"):
        _full()
    monkeypatch.setenv("EVAL_ADVANCE_INTERVAL_S", "7")
    monkeypatch.setenv("RUN_ABANDON_GRACE_S", "120")
    with pytest.raises(ValidationError, match="divide 60"):
        _full()


def test_09_g6_background_queue_name():
    from ffcore.runtime.queue import ArqRunQueue

    s = Settings.model_construct(
        redis_url=SecretStr("redis://r:6379/0"),
        arq_queue_interactive="llm-interactive",
        arq_queue_background="llm-background",
    )
    assert ArqRunQueue(s)._queue_name == "llm-interactive"
    assert ArqRunQueue(s, s.arq_queue_background)._queue_name == "llm-background"


def test_09_g4_no_local_dataset_tables():
    from ffcore.models import Base

    assert not {"datasets", "dataset_items", "eval_datasets", "eval_dataset_items"} & set(
        Base.metadata.tables
    )
    assert {"eval_suites", "eval_runs"} <= set(Base.metadata.tables)


def test_09_judge_guardrail_source_is_an_08_event_source():
    # Stack finding: an unknown source broke guardrail_events' check and stalled the exam.
    from ffcore.guardrails.categories import EVENT_SOURCES

    assert judge_mod.JUDGE_SOURCE in EVENT_SOURCES


# --- start: the exam is queued until every item run exists (stack finding b) --------------------


class _StartSession:
    def __init__(self):
        self.rows, self.commits = [], 0

    def add(self, row):
        self.rows.append(row)

    async def flush(self):
        for r in self.rows:
            r.id = getattr(r, "id", None) or "ev-1"

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        pass

    async def get(self, _model, _id):
        return self.rows[0]


class _ItemsApi:
    async def items(self, _dataset):
        return [_item("q01"), _item("q02")]


def _start(monkeypatch, fail_on: int | None = None):
    from types import SimpleNamespace

    from ffcore.evaluation import runner

    seen = []

    async def fake_start_run(session, settings, queue, **kw):
        ev = session.rows[0]
        seen.append(ev.status)
        if fail_on is not None and len(seen) == fail_on:
            raise RuntimeError("queue down")
        return SimpleNamespace(id=f"run-{len(seen)}")

    async def no_audit(session, entry):
        pass

    monkeypatch.setattr(runner, "start_run", fake_start_run)
    monkeypatch.setattr(runner, "write_event", no_audit)
    session = _StartSession()
    suite = SimpleNamespace(id="s", project_id="p", key="k", repeat=1, langfuse_dataset_name="p.k")
    starter = runner.Starter("u", "user", "u", "req", None)

    async def go():
        return await runner.start_eval(
            session,
            None,
            suite=suite,
            agent=SimpleNamespace(id="a"),
            version=SimpleNamespace(id="v", version=1),
            starter=starter,
            api=_ItemsApi(),
            queue=None,
            queued_event=None,
        )

    return session, seen, go


def test_09_exam_is_queued_until_every_item_run_started(monkeypatch):
    session, seen, go = _start(monkeypatch)
    ev = anyio.run(go)
    assert seen == ["queued", "queued"] and ev.status == "running"


def test_09_broken_start_ends_exam_failed(monkeypatch):
    session, seen, go = _start(monkeypatch, fail_on=2)
    with pytest.raises(RuntimeError):
        anyio.run(go)
    ev = session.rows[0]
    assert (ev.status, ev.error_code) == ("failed", "start_failed")


def test_09_advancer_takes_only_running_exams():
    from sqlalchemy.dialects import postgresql

    from ffcore.evaluation import runner

    captured = {}

    class _S:
        async def scalars(self, stmt):
            captured["sql"] = str(
                stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
            )
            return type("R", (), {"all": lambda self: []})()

    anyio.run(runner.active_runs, _S())
    assert "eval_runs.status = 'running'" in captured["sql"]


def test_09_repeated_tick_failure_ends_exam_failed(monkeypatch):
    # Stack finding a: a tick that keeps failing must not leave the exam running forever.
    from contextlib import asynccontextmanager
    from types import SimpleNamespace

    from ffcore.evaluation import worker_tick
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
    for _ in range(MAX_ATTEMPTS - 1):
        anyio.run(worker_tick._count_failure, redis, "ev", ValueError("x"))
    assert ev.status == "running"
    anyio.run(worker_tick._count_failure, redis, "ev", ValueError("x"))
    assert (ev.status, ev.error_code) == ("failed", "advance_failed:ValueError")


def test_09_approval_expired_counted_apart_and_marks_incomplete():
    expired = _facts(status="failed", error_code="approval_expired", outcome_label=None)
    r = item_result(_item(), expired, [], "")
    assert r.passed is None and r.note == "approval_expired"
    ok = item_result(_item("q02"), _facts(), [Score("contains", 1.0, True)], "")
    s = summarize([r, ok], pass_threshold=0.8, warmup_ms=None, latencies_ms=[])
    assert s["not_run"] == {"approval_expired": 1} and s["scored"] == 1
    assert s["complete"] is False and s["passed"] is True
