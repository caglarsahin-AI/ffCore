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
    # r1 NOTE-1: the mark counts towards the limit.
    assert len(text) <= judge_mod.REASON_MAX and text.endswith("/600 chars]")
    kept = text.split(" [truncated: ")[0]
    assert text.endswith(f"[truncated: {len(kept)}/600 chars]")


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


# --- start: checked, queued with a snapshot; the advancer starts the item runs (r1) ------------


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
    def __init__(self, items=None):
        self._items = items or [_item("q01"), _item("q02")]

    async def items(self, _dataset):
        return self._items


def _suite(**kw):
    from types import SimpleNamespace

    base = dict(
        id="s",
        project_id="p",
        key="k",
        repeat=1,
        langfuse_dataset_name="p.k",
        scorers=[{"name": "contains"}],
        pass_threshold=0.8,
        approve_tools=False,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _version():
    from types import SimpleNamespace

    from tests.unit.test_06a_definition import MINIMAL  # a valid agent definition

    return SimpleNamespace(id="v", version=1, definition=MINIMAL)


def _start_eval(monkeypatch, *, suite=None, items=None, max_runs=500):
    from types import SimpleNamespace

    from ffcore.evaluation import runner

    async def no_audit(session, entry):
        pass

    monkeypatch.setattr(runner, "write_event", no_audit)
    session = _StartSession()
    starter = runner.Starter("u", "user", "u", "req", None)
    settings = SimpleNamespace(eval_max_item_runs=max_runs)

    async def go():
        return await runner.start_eval(
            session,
            settings,
            suite=suite or _suite(),
            version=_version(),
            starter=starter,
            api=_ItemsApi(items),
        )

    return session, go


def test_09_r1_major4_exam_starts_queued_with_a_suite_snapshot(monkeypatch):
    session, go = _start_eval(monkeypatch, suite=_suite(approve_tools=True, repeat=2))
    ev = anyio.run(go)
    assert ev.status == "queued" and session.commits == 1
    assert ev.config["scorers"] == [{"name": "contains"}] and ev.config["repeat"] == 2
    assert ev.config["approve_tools"] is True and ev.config["pass_threshold"] == 0.8
    assert ev.config["starter"]["actor_id"] == "u"
    assert {k: v["runs"] for k, v in ev.item_runs.items()} == {"q01": [], "q02": []}


def test_09_r1_minor2_too_many_item_runs_is_422(monkeypatch):
    from ffcore.core.errors import ApiError

    session, go = _start_eval(monkeypatch, suite=_suite(repeat=3), max_runs=5)
    with pytest.raises(ApiError) as err:
        anyio.run(go)
    assert err.value.code == "eval_too_many_runs" and session.rows == []


def test_09_r1_minor2_every_item_checked_before_anything_is_written(monkeypatch):
    from ffcore.core.errors import ApiError

    bad = _item("q03")
    bad["input"]["variables"] = {"not_declared": "x"}
    session, go = _start_eval(monkeypatch, items=[_item("q01"), _item("q02"), bad])
    with pytest.raises(ApiError) as err:
        anyio.run(go)
    assert err.value.code == "item_input_invalid" and "q03" in str(err.value)
    assert session.rows == []


def _start_items(monkeypatch, fail_on=None):
    from types import SimpleNamespace

    from ffcore.evaluation import runner

    started = []

    async def fake_start_run(session, settings, queue, **kw):
        if fail_on is not None and len(started) + 1 == fail_on:
            raise RuntimeError("queue down")
        started.append(kw["input"])
        return SimpleNamespace(id=f"run-{len(started)}")

    monkeypatch.setattr(runner, "start_run", fake_start_run)
    monkeypatch.setattr(runner, "flag_modified", lambda *_: None)
    version = SimpleNamespace(id="v", version=1, agent_id="a")

    class _S(_StartSession):
        async def get(self, model, _id):
            return version if model.__name__ == "AgentVersion" else SimpleNamespace(id="a")

    ev = SimpleNamespace(
        id="ev",
        project_id="p",
        agent_version_id="v",
        user_id="u",
        status="queued",
        config={
            "repeat": 1,
            "starter": {"actor_type": "user", "actor_id": "u", "request_id": "r", "ip": None},
        },
        item_runs={
            "q01": {"item": _item("q01"), "runs": [], "scored": False},
            "q02": {"item": _item("q02"), "runs": [], "scored": False},
        },
    )
    return ev, _S(), started


def test_09_exam_is_queued_until_every_item_run_started(monkeypatch):
    from ffcore.evaluation import runner

    ev, session, started = _start_items(monkeypatch)
    anyio.run(lambda: runner.start_items(session, None, ev, queue=None, queued_event=None))
    assert len(started) == 2 and ev.status == "running"
    assert all(len(e["runs"]) == 1 for e in ev.item_runs.values())


def test_09_r1_minor2_broken_start_resumes_next_tick(monkeypatch):
    from ffcore.evaluation import runner

    ev, session, started = _start_items(monkeypatch, fail_on=2)
    with pytest.raises(RuntimeError):
        anyio.run(lambda: runner.start_items(session, None, ev, queue=None, queued_event=None))
    assert ev.status == "queued" and sum(len(e["runs"]) for e in ev.item_runs.values()) == 1
    ev2, session2, started2 = _start_items(monkeypatch)
    ev2.item_runs = ev.item_runs  # the plan as committed
    anyio.run(lambda: runner.start_items(session2, None, ev2, queue=None, queued_event=None))
    assert len(started2) == 1 and ev2.status == "running"


def test_09_advancer_takes_queued_and_running_exams():
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
    assert "eval_runs.status IN ('queued', 'running')" in captured["sql"]


# --- 09-1 r1 MAJOR-1: only SQL the run really executed is read again ---------------------------


def _ev(kind, **payload):
    from types import SimpleNamespace

    return SimpleNamespace(type=kind, payload=payload)


def _call(cid, sql, needs_approval=True, name="sql__run_sql"):
    return _ev(
        "tool_call",
        tool_call_id=cid,
        name=name,
        arguments={"sql": sql},
        needs_approval=needs_approval,
    )


def test_09_r1_major1_rejected_sql_is_not_read_again():
    from ffcore.evaluation.engine import executed_sql

    events = [
        _call("c1", "SELECT 1"),
        _ev("approval_resolved", tool_call_id="c1", decision="rejected"),
    ]
    assert executed_sql(events) == ([], True)


def test_09_r1_major1_unbound_tool_is_not_read_again():
    from ffcore.evaluation.engine import executed_sql

    events = [
        _call("c1", "SELECT 1", needs_approval=False, name="other__run_sql"),
        _ev("tool_result", tool_call_id="c1", is_error=True, error_code="tool_unknown"),
    ]
    assert executed_sql(events) == ([], False)


def test_09_r1_major1_approved_then_rejected_reads_the_approved_one():
    from ffcore.evaluation.engine import executed_sql

    events = [
        _call("c1", "SELECT good"),
        _ev("approval_resolved", tool_call_id="c1", decision="approved"),
        _ev("tool_result", tool_call_id="c1", is_error=False, error_code=None),
        _call("c2", "SELECT bad"),
        _ev("approval_resolved", tool_call_id="c2", decision="rejected"),
    ]
    assert executed_sql(events) == ([("sql", "SELECT good")], True)


def test_09_r1_major1_call_without_approval_needs_a_result():
    from ffcore.evaluation.engine import executed_sql

    asked_only = [_call("c1", "SELECT 1", needs_approval=False)]
    assert executed_sql(asked_only) == ([], False)
    ran = [*asked_only, _ev("tool_result", tool_call_id="c1", is_error=False)]
    assert executed_sql(ran) == ([("sql", "SELECT 1")], False)


def test_09_r1_major1_tool_not_given_to_the_version_is_not_used():
    from types import SimpleNamespace

    from ffcore.evaluation import worker_tick
    from tests.unit.test_06a_definition import MINIMAL

    queried = []

    class _S:
        async def get(self, _model, _id):
            return SimpleNamespace(definition=MINIMAL)

        async def execute(self, stmt):
            queried.append(stmt)
            return SimpleNamespace(first=lambda: ("tool", "action"))

    run = SimpleNamespace(agent_version_id="v", project_id="p")
    found = anyio.run(worker_tick.bound_sql_action, _S(), run, "not-given")
    assert found is None and queried == []


# --- 09-1 r1 MAJOR-2 / MAJOR-3 / MINOR-3 / MINOR-8 ---------------------------------------------


class _LockRedis:
    def __init__(self):
        self.kv = {}

    async def set(self, key, value, nx=False, ex=None):
        if nx and key in self.kv:
            return None
        self.kv[key] = value
        return True

    async def get(self, key):
        return self.kv.get(key)

    async def expire(self, key, ttl):
        return key in self.kv

    async def delete(self, key):
        self.kv.pop(key, None)

    async def eval(self, script, numkeys, key, token, *args):
        # r2 MINOR-r2-2: owner-checked renew (expire) and release (del) scripts.
        if self.kv.get(key) != token:
            return 0
        if "del" in script:
            self.kv.pop(key)
        return 1


def test_09_r1_major2_one_holder_per_exam_lock():
    from ffcore.evaluation.worker_tick import exam_lock

    redis = _LockRedis()

    async def go():
        async with exam_lock(redis, "ev") as first:
            async with exam_lock(redis, "ev") as second:
                inner = (first, second)
        async with exam_lock(redis, "ev") as again:
            return inner, again

    assert anyio.run(go) == ((True, False), True)


def test_09_r1_major3_cancelled_waiting_runs_are_not_run_from_their_code():
    for code, note in (
        ("eval_approval_required", "approval_required"),
        ("eval_waiting_user", "waiting_user"),
        ("approval_expired", "approval_expired"),
    ):
        r = item_result(
            _item(), _facts(status="cancelled", error_code=code, outcome_label=None), [], ""
        )
        assert (r.passed, r.note) == (None, note)


def test_09_r1_minor3_item_without_any_checked_scorer_fails_visibly():
    r = item_result(
        _item(), _facts(), [Score("contains", None, None, "no_expectation", "not_run")], ""
    )
    assert r.passed is False and r.note == "nothing_scored"
    s = summarize([r], pass_threshold=0.8, warmup_ms=None, latencies_ms=[])
    assert s["complete"] is True and s["errors"] == {"nothing_scored": 1}


def test_09_r1_minor3_repeat_keeps_errors_and_leaves_out_not_run_repeats():
    item = _item()
    ok = _dump(item_result(item, _facts(), [Score("contains", 1.0, True)], ""))
    err = _dump(
        item_result(item, _facts(), [Score("contains", None, None, "judge_failed:x", "error")], "")
    )
    skipped = _dump(
        item_result(
            item,
            _facts(status="cancelled", error_code="eval_waiting_user", outcome_label=None),
            [],
            "",
        )
    )
    r = combine(item, [ok, ok, err])
    assert r.passed is False and r.scores[0].status == "error"
    r2 = combine(item, [ok, skipped])
    assert r2.passed is True and r2.note == "not_run=1/2"


def test_09_r1_minor3_outcome_ties_follow_diagnosis_order():
    from ffcore.evaluation.diagnosis import DIAGNOSIS_ORDER

    assert DIAGNOSIS_ORDER.index("below_rerank_floor") < DIAGNOSIS_ORDER.index("not_reranked")
    item = _item()
    floor = _dump(item_result(item, _facts(candidates=[Candidate("A.pdf", True)]), [], ""))
    cut = _dump(item_result(item, _facts(selected=[]), [], ""))
    assert floor["outcome"] == "below_rerank_floor" and cut["outcome"] == "not_reranked"
    assert combine(item, [cut, floor]).outcome == "below_rerank_floor"


def test_09_r1_minor3_judge_needs_an_expectation():
    from ffcore.evaluation.runner import _judge_expectation

    assert _judge_expectation(_item(answer="90 gün")) is True
    assert _judge_expectation(_item(regex="9.")) is False


def test_09_r1_minor8_transport_error_is_a_langfuse_error():
    from ffcore.core.egress import EgressTimeoutError
    from ffcore.evaluation.langfuse_api import LangfuseApi, LangfuseApiError

    class _Down:
        async def request(self, *a, **kw):
            raise EgressTimeoutError("timeout", "http://langfuse:3000", "read")

    api = LangfuseApi(
        _settings(
            langfuse_host="http://langfuse:3000",
            langfuse_public_key=SecretStr("pk"),
            langfuse_secret_key=SecretStr("sk"),
        ),
        transport=_Down(),
    )
    with pytest.raises(LangfuseApiError) as err:
        anyio.run(api.items, "p.k")
    assert err.value.code == "langfuse_unreachable"


def test_09_r1_minor8_a_good_tick_resets_the_failure_count(monkeypatch):
    from contextlib import asynccontextmanager
    from types import SimpleNamespace

    from ffcore.evaluation import worker_tick

    deleted = []

    class _R:
        async def delete(self, key):
            deleted.append(key)

    @asynccontextmanager
    async def scope():
        class _S:
            async def get(self, *_):
                return SimpleNamespace(status="running", cancel_requested_at=None)

        yield _S()

    async def fine(*a, budget, **kw):
        budget.committed += 1  # r3 MAJOR-r3-1: only a tick that committed resets the count

    monkeypatch.setattr(worker_tick.db, "session_scope", scope)
    monkeypatch.setattr(worker_tick, "advance_eval", fine)
    for name in ("_judge", "_sql", "_embed", "_closer"):
        monkeypatch.setattr(worker_tick, name, lambda *a: None)
    settings = SimpleNamespace(
        eval_judge_calls_per_tick=1,
        llm_call_timeout_s=60,
        background_window="",
        background_window_weekends=False,
        background_window_tz="Europe/Istanbul",
    )
    anyio.run(worker_tick._advance_one, settings, _R(), None, None, None, "ev", None)
    assert deleted == [worker_tick.failures_key("ev")]


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


def test_09_r1_minor4_refused_reread_is_a_coded_failure_and_audited_as_failure(monkeypatch):
    from contextlib import asynccontextmanager
    from types import SimpleNamespace

    from ffcore.evaluation import worker_tick
    from ffcore.models.audit import ACTOR_TYPES
    from ffcore.services import mcp_client, mcp_tools

    audits, commits = [], []

    @asynccontextmanager
    async def scope():
        class _S:
            async def commit(self):
                commits.append(1)

        yield _S()

    async def bound(session, run, key):
        return SimpleNamespace(), SimpleNamespace(name="run_sql", timeout_s=5)

    async def refused(*a, **kw):
        return SimpleNamespace(is_error=False, text="sql_rejected: sql_not_select (UPDATE)")

    async def record(session, entry):
        audits.append(entry)

    monkeypatch.setattr(worker_tick.db, "session_scope", scope)

    async def given(session, run, key):
        return True

    monkeypatch.setattr(worker_tick, "sql_tool_given", given)
    monkeypatch.setattr(worker_tick, "bound_sql_action", bound)
    monkeypatch.setattr(worker_tick, "write_event", record)
    monkeypatch.setattr(mcp_client, "call", refused)
    monkeypatch.setattr(mcp_tools, "target_of", lambda tool, settings: "t")
    reread = worker_tick._sql(None, None)
    run = SimpleNamespace(id="r", user_id="u", project_id="p")
    rows, code = anyio.run(reread, run, "sql", "UPDATE x")
    assert (rows, code) == (None, "no_sql_result:sql_rejected")
    (entry,) = audits
    assert entry.outcome == "failure" and entry.actor_type in ACTOR_TYPES and commits == [1]
