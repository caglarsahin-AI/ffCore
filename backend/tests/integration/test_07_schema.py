"""07 slice 1: the approvals table on the compose Postgres (migration 07_0001).

A project-owned root table with the C3 common columns. `assigned_role` is never `user` (brief:
the `user` role never approves; agent schema 06a refuses it too). A decided or expired approval
has `resolved_at`; a pending one has not. One approval per tool call of a run.
"""

import os
import subprocess
import uuid
from datetime import UTC, datetime, timedelta

import psycopg
import pytest

from tests.integration.conftest import BACKEND

ARGS = '{"sql": "SELECT 1"}'


def _insert(pg, project, **extra):
    row = {
        "id": uuid.uuid4(),
        "project_id": project,
        "run_id": uuid.uuid4(),
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


def test_07_project_must_exist(pg):
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        _insert(pg, uuid.uuid4())


def test_07_pending_expiry_index(pg):
    # The TTL job scans pending rows by expires_at (plan U2): a partial index serves it.
    (definition,) = pg.execute(
        "SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_approvals_pending_expires_at'"
    ).fetchone()
    assert "expires_at" in definition and "pending" in definition


def test_07_migration_roundtrip(database_url, pg):
    env = {**os.environ, "DATABASE_URL": database_url}

    def alembic(*args):
        return subprocess.run(["alembic", *args], cwd=BACKEND, env=env, capture_output=True)

    def tables():
        rows = pg.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        return {r[0] for r in rows.fetchall()}

    assert "approvals" in tables()
    assert alembic("downgrade", "07@-1").returncode == 0
    assert "approvals" not in tables()
    assert {"projects", "users", "audit_events"} <= tables()
    assert alembic("upgrade", "heads").returncode == 0
    assert "approvals" in tables()
    assert "07_0001" in alembic("heads").stdout.decode()
