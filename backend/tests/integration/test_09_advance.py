"""09-1 r1: the advancer on a real database and Redis (no Langfuse, no model).

MAJOR-2 one worker per exam and a follower independent of the tick; MAJOR-3 not_run notes from
the run's end code and one commit per item; MAJOR-4 the exam reads its own config snapshot;
MINOR-5 a cancelled waiting run closes its approval and is audited; MINOR-6 a resumed exam run
stays in the background queue.
"""

import asyncio
import json
import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import redis.asyncio as aioredis

from tests.integration.runtime_support import definition, seed_run


@pytest.fixture
def project(make_project):
    return make_project()


@pytest.fixture
def database(database_url):
    from ffcore.core import db

    db.configure(database_url, pooled=False)
    return db


def _item(i, *, answer="90 gün", must=("90",)):
    return {
        "id": i,
        "input": {"message": f"soru {i}", "variables": {}},
        "expectedOutput": {"answer": answer, "must_contain": list(must)},
        "metadata": {"style": "dogrudan", "answerable": True},
    }


def _finish(pg, run_id, *, answer="Fesih 90 gün.", status="completed"):
    pg.execute(
        "UPDATE runs SET status = %s, output = %s, outcome_label = 'answered',"
        " langfuse_trace_id = %s, user_id = %s, started_at = now() - interval '2 s',"
        " ended_at = now() WHERE id = %s",
        (status, answer, uuid.uuid4().hex, uuid.uuid4(), run_id),
    )


def _exam(
    pg, project, plan: dict, *, scorers, threshold=0.5, approve_tools=False, status="running"
):
    first = next(iter(plan.values()))[0]
    version_id = pg.execute("SELECT agent_version_id FROM runs WHERE id = %s", (first,)).fetchone()[
        0
    ]
    suite_id, ev_id = uuid.uuid4(), uuid.uuid4()
    pg.execute(
        "INSERT INTO eval_suites (id, project_id, key, name, langfuse_dataset_name, scorers,"
        " pass_threshold, created_by) VALUES (%s, %s, %s, 'Exam', 'p.exam', %s, 0.99, 't')",
        (suite_id, project, f"s-{suite_id.hex[:8]}", json.dumps([{"name": "llm_judge"}])),
    )
    config = {
        "scorers": scorers,
        "pass_threshold": threshold,
        "repeat": 1,
        "approve_tools": approve_tools,
        "dataset": "p.exam",
        "starter": {"actor_type": "user", "actor_id": "t", "request_id": "r", "ip": None},
    }
    items = {
        k: {"item": _item(k), "runs": [str(r) for r in runs], "scored": False, "attempts": 0}
        for k, runs in plan.items()
    }
    pg.execute(
        "INSERT INTO eval_runs (id, project_id, suite_id, agent_version_id, user_id,"
        " langfuse_run_name, status, item_runs, config, created_by)"
        " VALUES (%s, %s, %s, %s, %s, 'exam-x', %s, %s, %s, 't')",
        (ev_id, project, suite_id, version_id, uuid.uuid4(), status, json.dumps(items),
         json.dumps(config)),
    )  # fmt: skip
    return ev_id


class _Api:
    def __init__(self):
        self.scores, self.links = [], []

    async def link_run_item(self, *a, **kw):
        self.links.append(a)

    async def upsert_score(self, score_id, **kw):
        self.scores.append(score_id)


class _Judge:
    def __init__(self, delay=0.0):
        self.calls, self.delay = [], delay

    async def __call__(self, run, item, facts, cfg):
        from ffcore.evaluation.scorers import Score

        self.calls.append(item["id"])
        if self.delay:
            await asyncio.sleep(self.delay)
        return Score("llm_judge", 1.0, True, "score=5"), "ok"


async def _close(session, run, code):
    pass


def _advance(database, settings, ev_id, *, judge=None, embed=None, budget=20):
    from ffcore.evaluation.runner import Budget, advance_eval
    from ffcore.models.eval import EvalRun

    async def go():
        async with database.session_scope() as session:
            ev = await session.get(EvalRun, ev_id)
            await advance_eval(
                session,
                settings,
                ev,
                api=_Api(),
                judge=judge,
                sql=None,
                embed=embed,
                close=_close,
                budget=budget if isinstance(budget, Budget) else Budget(budget),
            )

    asyncio.run(go())


def _ev(pg, ev_id):
    row = pg.execute(
        "SELECT status, item_runs, summary FROM eval_runs WHERE id = %s", (ev_id,)
    ).fetchone()
    return row[0], row[1], row[2]


def test_09_r1_major3_not_run_survives_failed_tick_and_scored_item_not_rejudged(
    pg, project, database, app_settings
):
    d = definition()
    r1, r2, r3 = (seed_run(pg, project, d) for _ in range(3))
    _finish(pg, r1)
    _finish(pg, r2)
    pg.execute("UPDATE runs SET status = 'waiting_approval' WHERE id = %s", (r3,))
    pg.execute(
        "INSERT INTO approvals (id, project_id, run_id, tool_call_id, action, arguments,"
        " args_hash, assigned_role, expires_at, created_by)"
        " VALUES (%s, %s, %s, 'c1', 'sql__run_sql', '{}', %s, 'analyst', %s, 't')",
        (uuid.uuid4(), project, r3, "0" * 64, datetime.now(UTC) + timedelta(hours=1)),
    )
    scorers = [{"name": "contains"}, {"name": "llm_judge"}, {"name": "semantic"}]
    ev_id = _exam(pg, project, {"q1": [r1], "q2": [r2], "q3": [r3]}, scorers=scorers)
    judge = _Judge()
    calls = {"n": 0}

    async def flaky_embed(texts):
        calls["n"] += 1
        if calls["n"] == 2:  # q2 on the first tick
            raise RuntimeError("embed down")
        return [[1.0, 0.0], [1.0, 0.0]]

    with pytest.raises(RuntimeError):
        _advance(database, app_settings, ev_id, judge=judge, embed=flaky_embed)
    status, plan, _ = _ev(pg, ev_id)
    assert status == "running" and plan["q1"]["scored"] and not plan["q2"]["scored"]
    run3 = pg.execute("SELECT status, error_code FROM runs WHERE id = %s", (r3,)).fetchone()
    assert tuple(run3) == ("cancelled", "eval_approval_required")
    # MINOR-5: the approval is closed and the cancel audited.
    assert pg.execute("SELECT status FROM approvals WHERE run_id = %s", (r3,)).fetchone()[0] == (
        "expired"
    )
    audited = pg.execute(
        "SELECT count(*) FROM audit_events WHERE action = 'cancel_run' AND resource_id = %s",
        (str(r3),),
    ).fetchone()[0]
    assert audited == 1

    _advance(database, app_settings, ev_id, judge=judge, embed=flaky_embed)
    status, plan, summary = _ev(pg, ev_id)
    assert status == "completed"
    assert sorted(judge.calls) == ["q1", "q2"]  # q1 was not judged again
    assert summary["not_run"] == {"approval_required": 1} and summary["complete"] is False
    assert summary["scored"] == 2


def test_09_r1_major4_exam_reads_its_snapshot_not_the_suite(pg, project, database, app_settings):
    run = seed_run(pg, project, definition())
    _finish(pg, run, answer="hiçbiri")  # contains fails
    # The suite says llm_judge + 0.99 (as if PATCHed); the exam started with contains + 0.0x.
    ev_id = _exam(pg, project, {"q1": [run]}, scorers=[{"name": "contains"}], threshold=0.01)
    judge = _Judge()
    _advance(database, app_settings, ev_id, judge=judge)
    status, _, summary = _ev(pg, ev_id)
    assert status == "completed" and judge.calls == []
    assert summary["pass_threshold"] == 0.01 and "llm_judge" not in summary["scores"]


def test_09_r1_major2_judge_budget_per_tick(pg, project, database, app_settings):
    runs = [seed_run(pg, project, definition()) for _ in range(3)]
    for r in runs:
        _finish(pg, r)
    ev_id = _exam(
        pg,
        project,
        {f"q{i}": [r] for i, r in enumerate(runs, 1)},
        scorers=[{"name": "llm_judge"}],
    )
    judge = _Judge()
    _advance(database, app_settings, ev_id, judge=judge, budget=2)
    status, plan, _ = _ev(pg, ev_id)
    assert status == "running" and len(judge.calls) == 2
    _advance(database, app_settings, ev_id, judge=judge, budget=2)
    assert _ev(pg, ev_id)[0] == "completed" and len(judge.calls) == 3


def test_09_r1_major2_two_ticks_judge_each_item_once(
    pg, project, database, app_settings, monkeypatch
):
    from ffcore.evaluation import worker_tick
    from ffcore.models.eval import EvalRun

    runs = [seed_run(pg, project, definition()) for _ in range(3)]
    for r in runs:
        _finish(pg, r)
    ev_id = _exam(
        pg,
        project,
        {f"q{i}": [r] for i, r in enumerate(runs, 1)},
        scorers=[{"name": "llm_judge"}],
    )
    judge = _Judge(delay=0.3)

    async def only_mine(session):
        return [await session.get(EvalRun, ev_id)]

    monkeypatch.setattr(worker_tick, "active_runs", only_mine)
    monkeypatch.setattr(worker_tick, "LangfuseApi", lambda settings: _Api())
    monkeypatch.setattr(worker_tick, "_judge", lambda *a: judge)
    monkeypatch.setattr(worker_tick, "_sql", lambda *a: None)
    monkeypatch.setattr(worker_tick, "_embed", lambda *a: None)

    async def go():
        redis = aioredis.from_url(os.environ["REDIS_URL"])
        try:
            await asyncio.gather(
                worker_tick.tick(app_settings, redis, None, None),
                worker_tick.tick(app_settings, redis, None, None),
            )
        finally:
            await redis.aclose()

    asyncio.run(go())
    assert sorted(judge.calls) == ["q1", "q2", "q3"]
    assert _ev(pg, ev_id)[0] == "completed"


def test_09_r1_major2_runs_listened_while_a_long_judge_runs(pg, project, database, app_settings):
    from ffcore.evaluation import worker_tick
    from ffcore.runtime.events import listening_key

    done = seed_run(pg, project, definition())
    _finish(pg, done)
    slow_exam = _exam(pg, project, {"q1": [done]}, scorers=[{"name": "llm_judge"}])
    other = seed_run(pg, project, definition(), status="running")
    other_exam = _exam(pg, project, {"q1": [other]}, scorers=[{"name": "contains"}])
    settings = app_settings.model_copy(update={"eval_advance_interval_s": 1})
    judge = _Judge(delay=2.5)

    async def go():
        redis = aioredis.from_url(os.environ["REDIS_URL"])
        listener = asyncio.create_task(worker_tick.listen_loop(settings, redis))
        try:
            await asyncio.sleep(0.2)
            await redis.delete(listening_key(other))
            await asyncio.to_thread(_advance, database, settings, slow_exam, judge=judge)
            return await redis.exists(listening_key(other))
        finally:
            listener.cancel()
            await redis.aclose()

    assert asyncio.run(go()) == 1
    pg.execute("UPDATE eval_runs SET status = 'cancelled' WHERE id = %s", (other_exam,))


def test_09_r1_minor6_resumed_exam_run_is_an_exam_run(pg, project, database):
    from ffcore.evaluation.runner import is_exam_run

    run = seed_run(pg, project, definition())
    lone = seed_run(pg, project, definition())
    ev_id = _exam(pg, project, {"q1": [run]}, scorers=[{"name": "contains"}])

    async def go(rid):
        async with database.session_scope() as session:
            return await is_exam_run(session, rid)

    assert asyncio.run(go(run)) is True and asyncio.run(go(lone)) is False
    pg.execute("UPDATE eval_runs SET status = 'completed' WHERE id = %s", (ev_id,))
    assert asyncio.run(go(run)) is False


# --- 09-1 r2 MAJOR-r2-2: tick time budget and the background window ---------------------------


def _judged_exam(pg, project, n=3):
    runs = [seed_run(pg, project, definition()) for _ in range(n)]
    for r in runs:
        _finish(pg, r)
    return _exam(
        pg, project, {f"q{i}": [r] for i, r in enumerate(runs, 1)}, scorers=[{"name": "llm_judge"}]
    )


def test_09_r2_major2_closed_window_waits_without_judging(pg, project, database, app_settings):
    from ffcore.evaluation.runner import Budget

    ev_id = _judged_exam(pg, project)
    judge = _Judge()
    _advance(database, app_settings, ev_id, judge=judge, budget=Budget(20, is_open=lambda: False))
    status, plan, _ = _ev(pg, ev_id)
    assert status == "running" and judge.calls == []
    assert not any(e["scored"] for e in plan.values())
    _advance(database, app_settings, ev_id, judge=judge)  # the window opened
    assert _ev(pg, ev_id)[0] == "completed" and len(judge.calls) == 3


def test_09_r2_major2_slow_judge_spreads_over_ticks_and_finishes(
    pg, project, database, app_settings
):
    import time

    from ffcore.evaluation.runner import Budget

    ev_id = _judged_exam(pg, project)
    judge = _Judge(delay=0.3)
    ticks = 0
    while _ev(pg, ev_id)[0] == "running":
        ticks += 1
        assert ticks <= 5, "the exam does not progress"
        budget = Budget(20, deadline=time.monotonic() + 0.7, call_s=0.2)
        _advance(database, app_settings, ev_id, judge=judge, budget=budget)  # never raises
    status, _, summary = _ev(pg, ev_id)
    assert status == "completed" and ticks == 2 and summary["scored"] == 3
    assert sorted(judge.calls) == ["q1", "q2", "q3"]


def test_09_r2_major2_judge_cut_by_the_deadline_is_not_a_failure(
    pg, project, database, app_settings
):
    import time

    from ffcore.evaluation.runner import Budget

    ev_id = _judged_exam(pg, project, n=1)
    budget = Budget(20, deadline=time.monotonic() + 0.3, call_s=0.1)
    _advance(database, app_settings, ev_id, judge=_Judge(delay=2.0), budget=budget)
    status, plan, _ = _ev(pg, ev_id)
    assert status == "running" and not plan["q1"]["scored"]
    assert budget.committed == 0
    _advance(database, app_settings, ev_id, judge=_Judge())
    assert _ev(pg, ev_id)[0] == "completed"


# --- 09-1 r2 MINOR-r2-5: the resume path of an exam run uses the background queue -------------


def test_09_r2_minor5_resumed_exam_run_goes_to_the_background_queue(
    pg, project, database, app_settings, monkeypatch
):
    from ffcore.core.auth import Actor
    from ffcore.runtime import queue as queue_mod
    from ffcore.runtime import resume

    class _Queue:
        def __init__(self):
            self.enqueued = []

        async def enqueue(self, run_id, payload):
            self.enqueued.append(run_id)

    interactive, background = _Queue(), _Queue()
    monkeypatch.setattr(queue_mod, "get_background_queue", lambda settings: background)
    user = uuid.uuid4()
    exam_run, lone = (seed_run(pg, project, definition()) for _ in range(2))
    for r in (exam_run, lone):
        pg.execute("UPDATE runs SET status = 'waiting_user', user_id = %s WHERE id = %s", (user, r))
    _exam(pg, project, {"q1": [exam_run]}, scorers=[{"name": "contains"}])

    async def go(rid):
        async with database.session_scope() as session:
            await resume.resume_run(
                session,
                interactive,
                app_settings,
                project_id=project,
                run_id=rid,
                actor=Actor("user", str(user)),
                answer="evet",
            )

    asyncio.run(go(exam_run))
    asyncio.run(go(lone))
    assert background.enqueued == [str(exam_run)] and interactive.enqueued == [str(lone)]
