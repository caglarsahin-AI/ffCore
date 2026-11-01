"""07 slice 1: the approvals table on the compose Postgres (migration 07_0001).

A project-owned root table with the C3 common columns. `assigned_role` is never `user` (brief:
the `user` role never approves; agent schema 06a refuses it too). A decided or expired approval
has `resolved_at`; a pending one has not. One approval per tool call of a run.
"""

import uuid
from datetime import UTC, datetime, timedelta

import psycopg
import pytest

from tests.integration.runtime_support import definition, seed_run

ARGS = '{"sql": "SELECT 1"}'


def _insert(pg, project, **extra):
    # run_id references runs (06a): a real run of the project unless the test gives one.
    if "run_id" not in extra:
        extra["run_id"] = seed_run(pg, project, definition())
    row = {
        "id": uuid.uuid4(),
        "project_id": project,
        "tool_call_id": "call-1",
        "action": "mcp-sql__run_sql",
        "arguments": ARGS,
        "args_hash": "0" * 64,
        "assigned_role": "analyst",
        "expires_at": datetime.now(UTC) + timedelta(minutes=60),
        "created_by": "test",
        **extra,
    }
    columns = ", ".join(row)
    values = ", ".join(f"%({k})s" for k in row)
    pg.execute(f"INSERT INTO approvals ({columns}) VALUES ({values})", row)
    return row


def test_07_approvals_table_and_defaults(pg, make_project):
    row = _insert(pg, make_project())
    status, requested_at, resolved_at = pg.execute(
        "SELECT status, requested_at, resolved_at FROM approvals WHERE id = %s", (row["id"],)
    ).fetchone()
    assert status == "pending" and requested_at is not None and resolved_at is None


@pytest.mark.parametrize("role", ["user", "superadmin", ""])
def test_07_assigned_role_closed_list(pg, make_project, role):
    with pytest.raises(psycopg.errors.CheckViolation):
        _insert(pg, make_project(), assigned_role=role)


def test_07_status_closed_list(pg, make_project):
    with pytest.raises(psycopg.errors.CheckViolation):
        _insert(pg, make_project(), status="waiting")


def test_07_resolved_at_matches_status(pg, make_project):
    project = make_project()
    with pytest.raises(psycopg.errors.CheckViolation):
        _insert(pg, project, status="approved")  # decided without resolved_at
    with pytest.raises(psycopg.errors.CheckViolation):
        _insert(pg, project, resolved_at=datetime.now(UTC))  # pending with resolved_at
    _insert(pg, project, status="expired", resolved_at=datetime.now(UTC))


def test_07_one_approval_per_tool_call(pg, make_project):
    project = make_project()
    first = _insert(pg, project)
    with pytest.raises(psycopg.errors.UniqueViolation):
        _insert(pg, project, run_id=first["run_id"])
    _insert(pg, project, run_id=first["run_id"], tool_call_id="call-2")


def test_07_project_must_exist(pg, make_project):
    run_id = seed_run(pg, make_project(), definition())
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        _insert(pg, uuid.uuid4(), run_id=run_id)


def test_07_run_must_exist(pg, make_project):
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        _insert(pg, make_project(), run_id=uuid.uuid4())


def test_07_pending_expiry_index(pg):
    # The TTL job scans pending rows by expires_at (plan U2): a partial index serves it.
    (definition,) = pg.execute(
        "SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_approvals_pending_expires_at'"
    ).fetchone()
    assert "expires_at" in definition and "pending" in definition


def test_07_migration_roundtrip(scratch_db):
    # Explicit revisions since the merge revisions (FOLLOWUP-57): "07@-1" is ambiguous.
    db = scratch_db
    assert "approvals" in db.tables()
    db.run("downgrade", "0001")
    for rev in ("03b_0001", "06a_0002"):  # everything 07 stands on, without 07
        db.run("upgrade", rev)
    assert "approvals" not in db.tables()
    assert {"projects", "users", "audit_events", "runs"} <= db.tables()
    db.run("upgrade", "head")
    assert "approvals" in db.tables()
