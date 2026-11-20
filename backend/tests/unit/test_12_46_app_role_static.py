"""12-2 (FOLLOWUP-46): static checks for the least-privileged application role.

Behaviour: tests/integration/test_12_46_app_role.py (needs the role, i.e. a fresh volume).
"""

import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[3]
DEPLOY = REPO / "deploy"
COMPOSE = yaml.safe_load((DEPLOY / "docker-compose.yml").read_text(encoding="utf-8"))
SERVICES = COMPOSE["services"]
MIGRATION = next((REPO / "backend" / "alembic" / "versions").glob("12_0001_*.py"))
OWNER_URL = (
    "postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}"
)


def test_12_46_application_services_connect_as_the_app_role():
    url = SERVICES["backend"]["environment"]["DATABASE_URL"]
    assert url == (
        "postgresql+psycopg://${APP_DB_USER:-${POSTGRES_USER}}:"
        "${APP_DB_PASSWORD:-${POSTGRES_PASSWORD}}@postgres:5432/${POSTGRES_DB}"
    )
    for name in ("worker", "agent-worker", "agent-worker-bg"):
        assert SERVICES[name]["environment"]["DATABASE_URL"] == url, name


def test_12_46_migrate_and_tools_keep_the_owner():
    # DDL (alembic, checkpointer setup), seed-sql-demo and the test fixtures need the owner.
    assert SERVICES["migrate"]["environment"]["DATABASE_URL"] == OWNER_URL
    assert SERVICES["tools"]["environment"]["DATABASE_URL"] == OWNER_URL
    for name in ("APP_DB_USER", "APP_DB_PASSWORD"):
        assert SERVICES["tools"]["environment"][name] == f"${{{name}:-}}"


def test_12_46_postgres_gets_the_role_password_for_initdb():
    env = SERVICES["postgres"]["environment"]
    assert env["APP_DB_USER"] == "${APP_DB_USER:-}"
    assert env["APP_DB_PASSWORD"] == "${APP_DB_PASSWORD:-}"


def test_12_46_role_sql_has_no_password_and_is_idempotent():
    sql = (DEPLOY / "postgres" / "app-role.sql").read_text(encoding="utf-8")
    # No password clause (comments may name the setting and \password).
    assert not re.search(r"PASSWORD\s+['\":]", sql, re.I)
    assert "ALTER DEFAULT PRIVILEGES" in sql
    assert re.search(r"REVOKE\s+UPDATE,\s*DELETE,\s*TRUNCATE\s+ON\s+audit_events", sql)
    init = (DEPLOY / "postgres" / "initdb" / "20-app-role.sh").read_text(encoding="utf-8")
    assert "app-role.sql" in init and "APP_DB_PASSWORD" in init
    # initdb runs *.sql in its own directory too: the shared file must live outside it.
    assert not (DEPLOY / "postgres" / "initdb" / "app-role.sql").exists()


def test_12_46_migration_functions_are_definer_with_fixed_search_path():
    text = MIGRATION.read_text(encoding="utf-8")
    assert 'branch_labels = ("12",)' in text
    assert 'down_revision = "04b_0001"' in text
    for name in (
        "ffcore_audit_ensure_partition",
        "ffcore_audit_detach_partition",
        "ffcore_audit_drop_partition",
    ):
        assert name in text
    assert text.count("SECURITY DEFINER") >= 3
    assert text.count("SET search_path = public, pg_temp") >= 3
    assert "FROM PUBLIC" in text
    assert "^audit_events_[0-9]{4}_[0-9]{2}$" in text


def test_12_46_retention_uses_the_functions():
    source = (REPO / "backend" / "ffcore" / "services" / "retention_job.py").read_text(
        encoding="utf-8"
    )
    assert "DETACH PARTITION" not in source and "DROP TABLE" not in source
    assert "ffcore_audit_detach_partition" in source and "ffcore_audit_drop_partition" in source


def test_12_46_env_test_runs_stacks_as_the_app_role():
    env = (REPO / ".env.test").read_text(encoding="utf-8")
    assert re.search(r"^APP_DB_USER=ffcore_app$", env, re.M)
    assert re.search(r"^APP_DB_PASSWORD=\S+$", env, re.M)


def _initdb(tmp_path, **env):
    import os
    import subprocess

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    calls = tmp_path / "psql-calls"
    psql = bin_dir / "psql"
    psql.write_text(f'#!/bin/sh\necho "$*" >> {calls}\ncat > /dev/null\n', encoding="utf-8")
    psql.chmod(0o755)
    result = subprocess.run(
        ["sh", str(DEPLOY / "postgres" / "initdb" / "20-app-role.sh")],
        capture_output=True,
        text=True,
        env={
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "POSTGRES_USER": "o",
            "POSTGRES_DB": "d",
            **env,
        },
    )
    return result, (calls.read_text(encoding="utf-8") if calls.exists() else "")


def test_12_r2_initdb_refuses_a_user_without_password(tmp_path):
    result, calls = _initdb(tmp_path, APP_DB_USER="ffcore_app", APP_DB_PASSWORD="")
    assert result.returncode != 0 and "APP_DB_PASSWORD" in result.stderr
    assert calls == ""


def test_12_r2_initdb_skips_when_both_are_empty(tmp_path):
    result, calls = _initdb(tmp_path, APP_DB_USER="", APP_DB_PASSWORD="")
    assert result.returncode == 0 and "owner" in result.stdout
    assert calls == ""


def test_12_r2_initdb_creates_the_role_with_both(tmp_path):
    result, calls = _initdb(tmp_path, APP_DB_USER="ffcore_app", APP_DB_PASSWORD="x")
    assert result.returncode == 0, result.stderr
    assert "/ffcore/app-role.sql" in calls


def test_12_r2_env_example_keeps_the_pair_empty_together():
    env = (REPO / ".env.example").read_text(encoding="utf-8")
    assert re.search(r"^APP_DB_USER=$", env, re.M)
    assert re.search(r"^APP_DB_PASSWORD=$", env, re.M)


def test_12_r2_role_sql_keeps_audit_partitions_insert_and_select_only():
    sql = (DEPLOY / "postgres" / "app-role.sql").read_text(encoding="utf-8")
    assert "audit_events_%" in sql or "audit_events_" in sql
    assert re.search(r"REVOKE UPDATE, DELETE, TRUNCATE ON %I FROM ffcore_app", sql)


def test_12_r2_lint_covers_tests_deploy():
    makefile = (REPO / "Makefile").read_text(encoding="utf-8")
    lint = makefile.split("lint:\n", 1)[1].split("\n\n", 1)[0]
    assert lint.count("tests/deploy") == 2
