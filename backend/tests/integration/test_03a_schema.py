"""03a migration: tables, constraints and the migration round trip on the compose Postgres."""

import uuid

import psycopg
import pytest

TABLES = {
    "users",
    "projects",
    "project_members",
    "providers",
    "provider_projects",
    "model_catalog",
    "models",
}


def _tables(pg) -> set[str]:
    rows = pg.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'").fetchall()
    return {row[0] for row in rows}


def _project(pg, key: str) -> uuid.UUID:
    pid = uuid.uuid4()
    pg.execute(
        "INSERT INTO projects (id, key, name, created_by) VALUES (%s, %s, %s, 'test')",
        (pid, key, key),
    )
    return pid


def test_03a_6_tables_created(pg):
    assert TABLES <= _tables(pg)


def test_03a_6_project_key_unique_and_format(pg):
    _project(pg, "schema-one")
    with pytest.raises(psycopg.errors.UniqueViolation):
        _project(pg, "schema-one")
    with pytest.raises(psycopg.errors.CheckViolation):
        _project(pg, "has.dot")


def test_03a_6_same_model_key_in_two_projects(pg):
    provider = uuid.uuid4()
    pg.execute(
        "INSERT INTO providers (id, key, label, driver, domains, config_encrypted, supports_test,"
        " created_by) VALUES (%s, %s, 'P', 'ollama', ARRAY['model'], '\\x00', true, 'test')",
        (provider, f"p-{provider.hex[:8]}"),
    )
    insert = (
        "INSERT INTO models (id, project_id, key, display_name, provider_id, category, model_id,"
        " capabilities, input_types, pricing, limits, upstream_api, request_policy, created_by)"
        " VALUES (%s, %s, 'chat-default', 'Chat', %s, 'llm', 'qwen3.5:35b', '{}', ARRAY['text'],"
        " '{}', '{}', 'chat', '{}', 'test')"
    )
    first, second = _project(pg, "schema-two"), _project(pg, "schema-three")
    pg.execute(insert, (uuid.uuid4(), first, provider))
    pg.execute(insert, (uuid.uuid4(), second, provider))
    with pytest.raises(psycopg.errors.UniqueViolation):
        pg.execute(insert, (uuid.uuid4(), first, provider))


def test_03a_6_live_email_unique_case_insensitive(pg):
    insert = "INSERT INTO users (id, email, password_hash, full_name) VALUES (%s, %s, 'x', 'Test')"
    pg.execute(insert, (uuid.uuid4(), "Owner@example.test"))
    with pytest.raises(psycopg.errors.UniqueViolation):
        pg.execute(insert, (uuid.uuid4(), "owner@example.test"))


def test_03a_6_superadmin_needs_access_mode(pg):
    with pytest.raises(psycopg.errors.CheckViolation):
        pg.execute(
            "INSERT INTO users (id, email, password_hash, full_name, is_superadmin)"
            " VALUES (%s, 'root@example.test', 'x', 'Root', true)",
            (uuid.uuid4(),),
        )


def test_03a_6_member_role_enum(pg):
    with pytest.raises(psycopg.errors.CheckViolation):
        pg.execute(
            "INSERT INTO project_members (project_id, user_id, role, access, created_by)"
            " VALUES (%s, %s, 'viewer', 'edit', 'test')",
            (uuid.uuid4(), uuid.uuid4()),
        )


def test_03a_6_migration_round_trip(scratch_db):
    # Since the merge revisions (FOLLOWUP-57) "03a@-1" is ambiguous; go down to the shared root,
    # bring 03b back alone and check that 03a's downgrade left nothing behind.
    db = scratch_db
    assert TABLES <= db.tables()
    db.run("downgrade", "0001")
    db.run("upgrade", "03b_0001")
    assert not (TABLES & db.tables())
    assert "audit_events" in db.tables()  # 03b stands on its own
    db.run("upgrade", "head")
    assert TABLES <= db.tables()
