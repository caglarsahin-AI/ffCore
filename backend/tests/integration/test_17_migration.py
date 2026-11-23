"""17 migration 17_0001 on a real database: one head, the new columns and constraints, a round
trip, and a downgrade that refuses while directory accounts exist (no silent data loss)."""

import uuid

import psycopg
import pytest


def _columns(db, table) -> set[str]:
    rows = db.conn.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = %s", (table,)
    ).fetchall()
    return {r[0] for r in rows}


def _checks(db, table) -> set[str]:
    rows = db.conn.execute(
        "SELECT conname FROM pg_constraint WHERE conrelid = %s::regclass AND contype = 'c'",
        (table,),
    ).fetchall()
    return {r[0] for r in rows}


def test_17_migration_schema_and_roundtrip(scratch_db):
    db = scratch_db
    heads = [line for line in db.run("heads").splitlines() if line.strip()]
    assert len(heads) == 1
    assert {"auth_source", "external_id", "last_login_at", "must_change_password"} <= _columns(
        db, "users"
    )
    assert "membership_source" in _columns(db, "project_members")
    assert "identity_group_mappings" in db.tables()
    assert {
        "ck_users_auth_source",
        "ck_users_password_only_local",
        "ck_users_superadmin_is_local",
    } <= _checks(db, "users")
    assert "ck_project_members_membership_source" in _checks(db, "project_members")
    nullable = db.conn.execute(
        "SELECT is_nullable FROM information_schema.columns"
        " WHERE table_name = 'users' AND column_name = 'password_hash'"
    ).fetchone()[0]
    assert nullable == "YES"

    db.run("downgrade", "16_0001")
    assert "identity_group_mappings" not in db.tables()
    assert "auth_source" not in _columns(db, "users")
    db.run("upgrade", "head")
    assert "identity_group_mappings" in db.tables()


def test_17_migration_downgrade_refuses_with_directory_accounts(scratch_db):
    db = scratch_db
    db.conn.execute(
        "INSERT INTO users (id, email, password_hash, full_name, auth_source, external_id)"
        " VALUES (%s, 'dir@example.test', NULL, 'D', 'ldap', 'guid-1')",
        (uuid.uuid4(),),
    )
    done = db.alembic("downgrade", "16_0001")
    assert done.returncode != 0
    assert "17_0001 downgrade refused" in done.stderr
    assert "identity_group_mappings" in db.tables()


def test_17_migration_user_checks(scratch_db):
    for email, password_hash, source in (
        ("x1@example.test", "hash", "ldap"),  # a directory account never has a password
        ("x2@example.test", None, "local"),  # a local account always has one
        ("x3@example.test", "hash", "saml"),  # unknown source
    ):
        with pytest.raises(psycopg.errors.CheckViolation):
            scratch_db.conn.execute(
                "INSERT INTO users (id, email, password_hash, full_name, auth_source)"
                " VALUES (%s, %s, %s, 'X', %s)",
                (uuid.uuid4(), email, password_hash, source),
            )
