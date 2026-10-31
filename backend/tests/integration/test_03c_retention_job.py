"""03c retention job (R2.2, K-03c-0011): content after 30 days, jobs on terminal runs only, the
audit partition guards (365-day floor in code, two flags, detach -> record -> drop), dry run
that changes nothing, the lock and idempotency.

The database is shared by the session: every row these tests make old is their own (other tests
write rows of today), and each assertion looks at this test's rows only.
"""

import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from ffcore.core import db
from ffcore.services import retention_job
from tests.integration.runtime_support import definition, seed_run

TEXT = "eski-icerik-03c"


@pytest.fixture
def run_job(database_url, app_settings):
    def run(*, dry_run=False, audit_drop=False, now=None):
        settings = app_settings.model_copy(
            update={"retention_audit_drop_enabled": audit_drop, "retention_batch": 2}
        )

        async def go():
            db.configure(database_url, pooled=False)
            try:
                return await retention_job.execute(
                    settings, dry_run=dry_run, trigger="manual", actor_id="test", now=now
                )
            finally:
                db.reset()

        return asyncio.run(go())

    return run


def _old_run(pg, project, *, days, status="completed"):
    run_id = seed_run(pg, project, definition(), question=TEXT, status=status)
    pg.execute(
        "UPDATE runs SET output = %s, ended_at = now() - make_interval(days => %s) WHERE id = %s",
        (TEXT, days, run_id),
    )
    pg.execute(
        "INSERT INTO run_events (run_id, seq, type, payload) VALUES (%s, 1, 'answer', %s)",
        (run_id, json.dumps({"text": TEXT, "outcome_label": "answered"})),
    )
    return run_id


def _answer(pg, run_id):
    row = pg.execute(
        "SELECT payload->>'text' FROM run_events WHERE run_id = %s AND type = 'answer'", (run_id,)
    ).fetchone()
    return row[0] if row else None


def _audit_month(pg, month: str):
    """A partition for `month` (YYYY-MM-01) with one row; returns the partition name."""
    name = pg.execute("SELECT ffcore_audit_ensure_partition(%s::date)", (month,)).fetchone()[0]
    pg.execute(
        "INSERT INTO audit_events (id, ts, actor_type, actor_id, action, resource_type, outcome)"
        " VALUES (%s, %s::date + 1, 'system', 't', 'probe_03c_retention', 'probe', 'success')",
        (uuid.uuid4(), month),
    )
    return name


def _exists(pg, name) -> bool:
    return pg.execute("SELECT to_regclass(%s)", (name,)).fetchone()[0] is not None


def test_03c_5_retention_run_clears_31_day_content(pg, make_project, run_job):
    project = make_project()
    old, fresh = _old_run(pg, project, days=31), _old_run(pg, project, days=5)
    run_job()
    assert _answer(pg, old) == "[cleared]"
    assert pg.execute("SELECT input, output FROM runs WHERE id = %s", (old,)).fetchone() == (
        "[cleared]",
        "[cleared]",
    )
    assert _answer(pg, fresh) == TEXT
    rows = pg.execute(
        "SELECT dry_run, counts FROM retention_runs WHERE data_class = 'content'"
        " AND actor_id = 'test' ORDER BY ts DESC LIMIT 2"
    ).fetchall()
    assert {r[0] for r in rows} == {True, False}  # counted and recorded, then removed


def test_03c_5_dry_run_changes_nothing(pg, make_project, run_job):
    project = make_project()
    old = _old_run(pg, project, days=200)
    tables = ("run_events", "runs", "usage_daily", "guardrail_events", "kb_queries")
    before = {t: pg.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in tables}
    partitions = pg.execute("SELECT count(*) FROM pg_inherits").fetchone()[0]
    results = run_job(dry_run=True)
    after = {t: pg.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in tables}
    assert after == before
    assert pg.execute("SELECT count(*) FROM pg_inherits").fetchone()[0] == partitions
    assert _answer(pg, old) == TEXT
    content = next(r for r in results if r.data_class == "content" and r.project_id is None)
    assert content.counts["runs"] >= 1


def test_03c_14_jobs_terminal_only(pg, make_project, run_job):
    project = make_project()
    finished = _old_run(pg, project, days=120)
    waiting = _old_run(pg, project, days=120, status="waiting_user")
    run_job()
    assert pg.execute(
        "SELECT count(*) FROM run_events WHERE run_id = %s", (finished,)
    ).fetchone() == (0,)
    assert pg.execute("SELECT status FROM runs WHERE id = %s", (finished,)).fetchone() == (
        "completed",
    )
    assert _answer(pg, waiting) == TEXT  # waiting runs: never


def test_03c_14_project_override(pg, make_project, run_job):
    short, normal = make_project(), make_project()
    pg.execute(
        "INSERT INTO retention_policies (id, data_class, project_id, keep_days, min_days,"
        " max_days, expiry_behavior, updated_by) VALUES (%s, 'content', %s, 3, 1, 90,"
        " 'clear_content', 'test')",
        (uuid.uuid4(), short),
    )
    a, b = _old_run(pg, short, days=5), _old_run(pg, normal, days=5)
    run_job()
    assert _answer(pg, a) == "[cleared]" and _answer(pg, b) == TEXT


def test_03c_14_audit_364_days_never_dropped(pg, run_job):
    """Even with the policy row forced to 1 day and both flags on, nothing younger than 365
    days goes: the floor is in code."""
    now = datetime.now(UTC)
    recent = (now - timedelta(days=300)).strftime("%Y-%m-01")
    name = _audit_month(pg, recent)
    pg.execute(
        "UPDATE retention_policies SET min_days = 1, keep_days = 1"
        " WHERE data_class = 'audit' AND project_id IS NULL"
    )
    try:
        run_job(audit_drop=True)
    finally:
        pg.execute(
            "UPDATE retention_policies SET min_days = 365, keep_days = 365"
            " WHERE data_class = 'audit' AND project_id IS NULL"
        )
    assert _exists(pg, name)


def test_03c_14_audit_drop_needs_both_flags(pg, run_job):
    name = _audit_month(pg, "2019-03-01")
    run_job(dry_run=True, audit_drop=True)
    assert _exists(pg, name)
    run_job(dry_run=False, audit_drop=False)
    assert _exists(pg, name)
    skipped = pg.execute(
        "SELECT counts FROM retention_runs WHERE data_class = 'audit' AND NOT dry_run"
        " ORDER BY ts DESC LIMIT 1"
    ).fetchone()[0]
    assert name in skipped["partitions"] and "RETENTION_AUDIT_DROP_ENABLED" in skipped["skipped"]


def test_03c_14_audit_drop_detach_record_then_drop(pg, run_job):
    name = _audit_month(pg, "2019-05-01")
    run_job(audit_drop=True)
    assert not _exists(pg, name)
    record = pg.execute(
        "SELECT counts FROM retention_runs WHERE counts->>'partition' = %s", (name,)
    ).fetchone()[0]
    assert record["rows"] == 1 and record["detached"] is True and len(record["sha256"]) == 64
    event = pg.execute(
        "SELECT actor_type, after FROM audit_events WHERE action = 'audit_partition_dropped'"
        " AND resource_id = %s",
        (name,),
    ).fetchone()
    assert event[0] == "system" and event[1]["sha256"] == record["sha256"]


def test_03c_14_external_and_no_target_reported(run_job):
    results = {r.data_class: r for r in run_job(dry_run=True)}
    assert results["traces"].counts == {"target": "external:langfuse"}
    for name in ("metrics", "results", "memory"):
        assert results[name].counts == {"target": "none"}


def test_03c_14_idempotent_second_pass(pg, make_project, run_job):
    project = make_project()
    _old_run(pg, project, days=40)
    run_job()
    second = run_job()
    content = next(r for r in second if r.data_class == "content" and r.project_id is None)
    assert content.counts.get("runs", 0) == 0


def test_03c_14_lock_one_pass_at_a_time(pg, run_job):
    pg.execute("SELECT pg_advisory_lock(%s)", (retention_job.LOCK_KEY,))
    try:
        with pytest.raises(retention_job.RetentionBusy):
            run_job(dry_run=True)
    finally:
        pg.execute("SELECT pg_advisory_unlock(%s)", (retention_job.LOCK_KEY,))


def test_03c_14_retention_runs_append_only(pg, run_job):
    run_job(dry_run=True)
    with pytest.raises(Exception, match="append-only"):
        pg.execute("UPDATE retention_runs SET actor_id = 'x'")
    with pytest.raises(Exception, match="append-only"):
        pg.execute("DELETE FROM retention_runs")
