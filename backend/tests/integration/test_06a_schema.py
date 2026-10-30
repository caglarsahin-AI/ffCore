"""06a migration: tables, constraints, checkpoints schema and round trip (compose Postgres)."""

import os
import subprocess
import uuid

import psycopg
import pytest

from tests.integration.conftest import BACKEND

TABLES = {"agents", "agent_versions", "conversations", "runs", "messages", "run_events"}


def _tables(pg) -> set[str]:
    rows = pg.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'").fetchall()
    return {row[0] for row in rows}


def _schemas(pg) -> set[str]:
    return {row[0] for row in pg.execute("SELECT nspname FROM pg_namespace").fetchall()}


def _agent(pg, project_id, key="sozlesme-asistani"):
    agent_id, version_id = uuid.uuid4(), uuid.uuid4()
    pg.execute(
        "INSERT INTO agents (id, project_id, key, name, created_by) VALUES (%s, %s, %s, 'A', 't')",
        (agent_id, project_id, key),
    )
    pg.execute(
        "INSERT INTO agent_versions (id, agent_id, version, definition, created_by)"
        " VALUES (%s, %s, 1, '{}', 't')",
        (version_id, agent_id),
    )
    return agent_id, version_id


def _run(pg, project_id, agent_id, version_id, **cols):
    run_id = uuid.uuid4()
    values = {"channel": "chat", "trigger_type": "chat", "input": "q", "created_by": "t", **cols}
    names = ", ".join(values)
    marks = ", ".join(["%s"] * len(values))
    pg.execute(
        f"INSERT INTO runs (id, project_id, agent_id, agent_version_id, {names})"
        f" VALUES (%s, %s, %s, %s, {marks})",
        (run_id, project_id, agent_id, version_id, *values.values()),
    )
    return run_id


def test_06a_schema_tables_and_checkpoints_schema(pg):
    assert TABLES <= _tables(pg)
    assert "checkpoints" in _schemas(pg)


def test_06a_schema_agent_key_unique_per_project_while_live(pg, make_project):
    project = make_project()
    agent_id, _ = _agent(pg, project)
    with pytest.raises(psycopg.errors.UniqueViolation):
        _agent(pg, project)
    pg.execute("UPDATE agents SET deleted_at = now() WHERE id = %s", (agent_id,))
    _agent(pg, project)  # a deleted agent's key can be reused


def test_06a_schema_published_agent_needs_a_version(pg, make_project):
    agent_id, version_id = _agent(pg, make_project())
    with pytest.raises(psycopg.errors.CheckViolation):
        pg.execute("UPDATE agents SET status = 'published' WHERE id = %s", (agent_id,))
    pg.execute(
        "UPDATE agents SET status = 'published', current_version_id = %s WHERE id = %s",
        (version_id, agent_id),
    )


@pytest.mark.parametrize(
    ("column", "value"),
    [("status", "paused"), ("channel", "email"), ("trigger_type", "cron"), ("outcome_label", "ok")],
)
def test_06a_schema_run_enums_enforced(pg, make_project, column, value):
    project = make_project()
    agent_id, version_id = _agent(pg, project)
    with pytest.raises(psycopg.errors.CheckViolation):
        _run(pg, project, agent_id, version_id, **{column: value})


def test_06a_schema_run_event_seq_unique_and_type_enforced(pg, make_project):
    project = make_project()
    agent_id, version_id = _agent(pg, project)
    run_id = _run(pg, project, agent_id, version_id)
    insert = "INSERT INTO run_events (run_id, seq, type) VALUES (%s, %s, %s)"
    pg.execute(insert, (run_id, 1, "queued"))
    with pytest.raises(psycopg.errors.UniqueViolation):
        pg.execute(insert, (run_id, 1, "progress"))
    with pytest.raises(psycopg.errors.CheckViolation):
        pg.execute(insert, (run_id, 2, "tool_started"))


def test_06a_schema_migration_round_trip(database_url, pg):
    env = {**os.environ, "DATABASE_URL": database_url}

    def alembic(*args):
        return subprocess.run(
            ["alembic", *args], cwd=BACKEND, env=env, check=True, capture_output=True, text=True
        ).stdout

    assert "06a_0001" in alembic("heads")
    alembic("downgrade", "06a@-1")
    assert not (TABLES & _tables(pg))
    assert "checkpoints" not in _schemas(pg)
    assert {"projects", "knowledge_bases", "audit_events"} <= _tables(pg)  # others untouched
    alembic("upgrade", "heads")
    assert TABLES <= _tables(pg)
    assert "checkpoints" in _schemas(pg)
