"""07 slices 4-5 on Postgres: opening an approval, not asking twice, TTL expiry, age report.

The clock is injected (`now`), so the 60-minute TTL is tested without waiting. Closing the run
uses a closer that changes the runs row in the sweep's transaction (the real one, run_closer,
also writes the events; test_07_flow covers it).
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from ffcore.core import db
from ffcore.services import approvals
from tests.integration.runtime_support import definition, seed_run

T0 = datetime(2026, 10, 30, 9, 0, tzinfo=UTC)
ARGS = {"sql": "SELECT count(*) FROM invoices", "reason": "[EMAIL_ADDRESS] asked"}


def _run(database_url, work):
    async def go():
        db.configure(database_url, pooled=False)
        try:
            async with db.session_scope() as session:
                return await work(session)
        finally:
            db.reset()

    return asyncio.run(go())


def _open(session, settings, project, run_id, call="call-1", args=ARGS, now=T0, **extra):
    return approvals.open_for_interrupt(
        session,
        project_id=project,
        run_id=run_id,
        tool_call_id=call,
        action="mcp-sql__run_sql",
        arguments=args,
        assign_to=extra.pop("assign_to", "analyst"),
        created_by="system:runtime",
        now=now,
        settings=settings,
        **extra,
    )


def _status(pg, approval_id):
    return pg.execute("SELECT status FROM approvals WHERE id = %s", (approval_id,)).fetchone()[0]


def test_07_args_hash_is_canonical():
    assert approvals.args_hash({"a": 1, "b": [1, 2]}) == approvals.args_hash({"b": [1, 2], "a": 1})
    assert approvals.args_hash({"a": 1}) != approvals.args_hash({"a": 2})


def test_07_open_sets_ttl_and_is_idempotent(database_url, app_settings, make_project, pg):
    project = make_project()
    run_id = seed_run(pg, project, definition())

    async def work(session):
        first = await _open(session, app_settings, project, run_id)
        await session.commit()
        again = await _open(session, app_settings, project, run_id)
        return first, again

    first, again = _run(database_url, work)
    assert not first.reused and again.approval.id == first.approval.id
    assert first.approval.expires_at == T0 + timedelta(minutes=app_settings.approval_ttl_min)
    assert first.approval.args_hash == approvals.args_hash(ARGS)


def test_07_assign_to_user_refused(database_url, app_settings, make_project, pg):
    project = make_project()
    run_id = seed_run(pg, project, definition())

    async def work(session):
        await _open(session, app_settings, project, run_id, assign_to="user")

    with pytest.raises(ValueError):
        _run(database_url, work)


def test_07_same_args_not_asked_twice(database_url, app_settings, make_project, pg):
    project = make_project()
    run_id = seed_run(pg, project, definition())

    async def first(session):
        opened = await _open(session, app_settings, project, run_id)
        await session.commit()
        return opened.approval.id

    approval_id = _run(database_url, first)
    # Pending is not enough: only an approved twin answers for the second call.
    still = _run(database_url, lambda s: _open(s, app_settings, project, run_id, call="call-2"))
    assert not still.reused and still.approval.id != approval_id
    pg.execute(
        "UPDATE approvals SET status = 'approved', resolved_at = now() WHERE id = %s",
        (approval_id,),
    )
    reused = _run(database_url, lambda s: _open(s, app_settings, project, run_id, call="call-3"))
    assert reused.reused and reused.approval.id == approval_id
    other_args = {**ARGS, "sql": "SELECT 2"}
    fresh = _run(
        database_url,
        lambda s: _open(s, app_settings, project, run_id, call="call-4", args=other_args),
    )
    assert not fresh.reused
    another = seed_run(pg, project, definition())
    other_run = _run(database_url, lambda s: _open(s, app_settings, project, another))
    assert not other_run.reused  # never across runs


def _closer(closed, fail_first=False):
    """A run closer as run_closer behaves on the database: waiting run -> failed, else no-op.
    `fail_first` raises once before touching anything (the review r1 retry case)."""
    state = {"fail": fail_first}

    async def close(session, run_id, code):
        if state["fail"]:
            state["fail"] = False
            raise RuntimeError("runtime unavailable")
        changed = await session.execute(
            text(
                "UPDATE runs SET status = 'failed', error_code = :code"
                " WHERE id = :id AND status = 'waiting_approval'"
            ),
            {"id": run_id, "code": code},
        )
        if changed.rowcount == 1:
            closed.append((run_id, code))
        return changed.rowcount == 1

    return close


def _run_status(pg, run_id):
    return pg.execute("SELECT status FROM runs WHERE id = %s", (run_id,)).fetchone()[0]


def test_07_ttl_expires_and_closes_run(database_url, app_settings, make_project, pg, caplog):
    project = make_project()
    due_run, fresh_run, decided_run = (
        seed_run(pg, project, definition(), status="waiting_approval") for _ in range(3)
    )

    async def setup(session):
        rows = [
            await _open(session, app_settings, project, due_run),
            await _open(session, app_settings, project, fresh_run, now=T0 + timedelta(minutes=30)),
            await _open(session, app_settings, project, decided_run),
        ]
        await session.commit()
        return [r.approval.id for r in rows]

    due, fresh, decided = _run(database_url, setup)
    pg.execute(
        "UPDATE approvals SET status = 'rejected', resolved_at = now() WHERE id = %s", (decided,)
    )
    closed = []
    close_run = _closer(closed)
    ttl = timedelta(minutes=app_settings.approval_ttl_min)
    ours = {due, fresh, decided}
    # The test database is shared by the session: other tests' pending rows expire too; only
    # this test's rows are asserted. One second before the TTL nothing happens.
    early = _run(
        database_url,
        lambda s: approvals.expire_due(s, now=T0 + ttl - timedelta(seconds=1), close_run=close_run),
    )
    assert not {row.id for row in early} & ours
    assert not {run for run, _ in closed} & {due_run, fresh_run, decided_run}
    with caplog.at_level(logging.WARNING, logger="ffcore.approvals"):
        expired = _run(
            database_url, lambda s: approvals.expire_due(s, now=T0 + ttl, close_run=close_run)
        )
    assert {row.id for row in expired} & ours == {due}
    assert (due_run, "approval_expired") in closed
    assert not {run for run, _ in closed} & {fresh_run, decided_run}
    assert _status(pg, due) == "expired" and _status(pg, fresh) == "pending"
    assert _status(pg, decided) == "rejected"  # a decision that landed first wins
    assert _run_status(pg, due_run) == "failed"
    resolved_by = pg.execute("SELECT resolved_by FROM approvals WHERE id = %s", (due,)).fetchone()
    assert resolved_by == ("system:approval_ttl",)
    assert "approval_expired" in caplog.text
    # A second tick finds nothing left to expire or close.
    again = _run(database_url, lambda s: approvals.expire_due(s, now=T0 + ttl, close_run=close_run))
    assert not {row.id for row in again} & ours
    assert [run for run, _ in closed].count(due_run) == 1


def test_07_ttl_close_failure_retried_next_tick(database_url, app_settings, make_project, pg):
    # Review r1 MAJOR-1: expiring the approval and closing its run are one transaction; a
    # failed close leaves both as they were and the next tick does both.
    project = make_project()
    run_id = seed_run(pg, project, definition(), status="waiting_approval")

    async def setup(session):
        opened = await _open(session, app_settings, project, run_id)
        await session.commit()
        return opened.approval.id

    approval_id = _run(database_url, setup)
    closed = []
    close_run = _closer(closed, fail_first=True)
    ttl = timedelta(minutes=app_settings.approval_ttl_min)
    with pytest.raises(RuntimeError, match="could not be closed"):
        _run(database_url, lambda s: approvals.expire_due(s, now=T0 + ttl, close_run=close_run))
    assert _status(pg, approval_id) == "pending"
    assert _run_status(pg, run_id) == "waiting_approval"
    retried = _run(
        database_url, lambda s: approvals.expire_due(s, now=T0 + ttl, close_run=close_run)
    )
    assert approval_id in {row.id for row in retried}
    assert _status(pg, approval_id) == "expired" and _run_status(pg, run_id) == "failed"
    assert closed == [(run_id, "approval_expired")]


def test_07_ttl_closes_run_of_stranded_expired_approval(
    database_url, app_settings, make_project, pg
):
    # An approval already expired while its run still waits (a close lost before this fix) is
    # picked up again; the approval row itself is not rewritten.
    project = make_project()
    run_id = seed_run(pg, project, definition(), status="waiting_approval")

    async def setup(session):
        opened = await _open(session, app_settings, project, run_id)
        await session.commit()
        return opened.approval.id

    approval_id = _run(database_url, setup)
    pg.execute(
        "UPDATE approvals SET status = 'expired', resolved_at = now(), resolved_by = 'old'"
        " WHERE id = %s",
        (approval_id,),
    )
    closed = []
    swept = _run(database_url, lambda s: approvals.expire_due(s, now=T0, close_run=_closer(closed)))
    assert approval_id in {row.id for row in swept}
    assert closed == [(run_id, "approval_expired")] and _run_status(pg, run_id) == "failed"
    resolved_by = pg.execute(
        "SELECT resolved_by FROM approvals WHERE id = %s", (approval_id,)
    ).fetchone()
    assert resolved_by == ("old",)


def test_07_pending_age_reported_once(database_url, app_settings, make_project, pg, caplog):
    project = make_project()
    old, young = (seed_run(pg, project, definition()) for _ in range(2))

    async def setup(session):
        await _open(session, app_settings, project, old)
        await _open(session, app_settings, project, young, now=T0 + timedelta(minutes=20))
        await session.commit()

    _run(database_url, setup)
    at = T0 + timedelta(minutes=app_settings.approval_alert_age_min)
    with caplog.at_level(logging.WARNING, logger="ffcore.approvals"):
        first = _run(
            database_url, lambda s: approvals.report_pending_age(s, now=at, settings=app_settings)
        )
        second = _run(
            database_url, lambda s: approvals.report_pending_age(s, now=at, settings=app_settings)
        )
    assert len(first) == 1 and second == []
    assert caplog.text.count("approval_pending_age") == 1
