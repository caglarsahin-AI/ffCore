"""06b-2 migration 06b_0001 on a real database: one head, round trip, the two CHECKs, and a
downgrade that refuses while external agents exist (no silent data loss)."""

import uuid

KEEP = "57_0002"


def _constraints(db) -> dict[str, str]:
    rows = db.conn.execute(
        "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint "
        "WHERE conrelid = 'agents'::regclass AND contype = 'c'"
    ).fetchall()
    return dict(rows)


def _columns(db) -> set[str]:
    rows = db.conn.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'agents'"
    ).fetchall()
    return {r[0] for r in rows}


def _project(db) -> uuid.UUID:
    project = uuid.uuid4()
    db.conn.execute(
        "INSERT INTO projects (id, key, name, created_by) VALUES (%s, %s, 'P', 'test')",
        (project, f"p06b2-{project.hex[:8]}"),
    )
    return project


def _agent(db, project, kind, status="draft", config=None) -> uuid.UUID:
    agent = uuid.uuid4()
    db.conn.execute(
        "INSERT INTO agents (id, project_id, key, name, status, kind, external_config, created_by)"
        " VALUES (%s, %s, %s, 'A', %s, %s, %s, 'test')",
        (agent, project, f"a{agent.hex[:8]}", status, kind, config),
    )
    return agent


def test_06b2_1_migration_roundtrip(scratch_db):
    db = scratch_db
    assert "06b_0001" in db.versions()
    heads = [line for line in db.run("heads").splitlines() if line.strip()]
    assert len(heads) == 1 and heads[0].startswith("06b_0001")
    assert "external_config" in _columns(db)
    checks = _constraints(db)
    assert "kind = 'external'" in checks["ck_agents_published_has_version"]
    assert "ck_agents_external_config" in checks

    project = _project(db)
    # an external agent is published without a version, and must carry its configuration
    _agent(db, project, "external", "published", b"token")
    for kind, config in (("external", None), ("native", b"token")):
        try:
            _agent(db, project, kind, "draft", config)
        except Exception as exc:  # psycopg CheckViolation
            assert "ck_agents_external_config" in str(exc)
        else:
            raise AssertionError(f"{kind} with config={config!r} was accepted")

    # downgrade refuses while external agents exist
    done = db.alembic("downgrade", KEEP)
    assert done.returncode != 0 and "external agent(s) exist" in done.stderr
    assert "06b_0001" in db.versions()

    db.conn.execute("DELETE FROM agents WHERE kind = 'external'")
    db.run("downgrade", KEEP)
    assert db.versions() == {KEEP}
    assert "external_config" not in _columns(db)
    assert "kind = 'external'" not in _constraints(db)["ck_agents_published_has_version"]

    db.run("upgrade", "head")
    assert "06b_0001" in db.versions() and "external_config" in _columns(db)
