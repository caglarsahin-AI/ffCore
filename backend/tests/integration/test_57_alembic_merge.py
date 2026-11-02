"""FOLLOWUP-57/132: one migration head on a real database.

`upgrade head` (singular) builds an empty database and upgrades a database at the pre-merge
state of main (four package rows) to the single merge row; the migrate service's `upgrade heads`
does the same. Merged branches roll back with an explicit revision; relative steps from the merge
point fail loudly (Alembic: "Ambiguous walk").
"""

import uuid

from alembic.config import Config
from alembic.script import ScriptDirectory

from tests.integration.conftest import BACKEND

# The rows main's databases carried before the merge: every other package head was folded into
# them through `depends_on` (03a_0001, 03b_0001, 06a_0002, 07_0001 had no row of their own).
PRE_MERGE_ROWS = {"03c_0002", "04a_0001", "05a_0001", "08_0001"}
LIFETIME = {"checkpoint_deleted_at", "source_deleted_at"}  # 06a_0002
RETENTION = {"retention_policies", "retention_runs", "alert_rules", "alerts"}  # 03c_0002


def _head() -> str:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    (head,) = ScriptDirectory.from_config(cfg).get_heads()
    return head


def _run_columns(db) -> set[str]:
    rows = db.conn.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'runs'"
    ).fetchall()
    return {r[0] for r in rows}


def test_57_1_alembic_heads_prints_one_line(scratch_db):
    lines = [line for line in scratch_db.run("heads").splitlines() if line.strip()]
    assert len(lines) == 1, lines
    assert lines[0].startswith(_head())


def test_57_2_empty_database_upgrade_head_and_back(scratch_db):
    db = scratch_db  # the fixture already ran `upgrade head` on an empty database
    assert db.versions() == {_head()}
    schema = db.tables()
    assert {"projects", "audit_events", "runs", "approvals", "api_keys"} | RETENTION <= schema

    db.run("downgrade", "57_0001")  # undo step 2 of the merge only
    assert db.versions() == PRE_MERGE_ROWS | {"57_0001"}
    assert db.tables() == schema  # the merge revisions carry no schema

    db.run("upgrade", "head")
    assert db.versions() == {_head()}

    # The migrate service runs `upgrade heads`; on a merged database it changes nothing.
    db.run("upgrade", "heads")
    assert db.versions() == {_head()}
    assert db.tables() == schema


def test_57_3_pre_merge_database_upgrades_to_one_head(scratch_db):
    # A database installed from main before the merge (four rows), as on a running installation,
    # with data in it: the merge revisions carry no schema, so nothing is lost.
    db = scratch_db
    db.run("downgrade", "0001")
    assert db.versions() == {"0001"}
    for rev in sorted(PRE_MERGE_ROWS):
        db.run("upgrade", rev)
    assert db.versions() == PRE_MERGE_ROWS
    schema = db.tables()
    project = uuid.uuid4()
    db.conn.execute(
        "INSERT INTO projects (id, key, name, created_by) VALUES (%s, %s, %s, 'test')",
        (project, f"p57-{project.hex[:8]}", "Merge test"),
    )

    db.run("upgrade", "head")
    assert db.versions() == {_head()}
    assert db.tables() == schema
    name = db.conn.execute("SELECT name FROM projects WHERE id = %s", (project,)).fetchone()
    assert name == ("Merge test",)


def test_57_5_downgrade_to_the_root_and_back(scratch_db):
    # The full explicit round trip: every package's downgrade runs, then everything comes back.
    db = scratch_db
    schema = db.tables()
    db.run("downgrade", "0001")
    assert db.versions() == {"0001"}
    assert db.tables() == {"alembic_version"}
    db.run("upgrade", "head")
    assert db.versions() == {_head()}
    assert db.tables() == schema


def test_57_3_pre_merge_database_upgrade_heads(scratch_db):
    db = scratch_db
    db.run("downgrade", "0001")
    for rev in sorted(PRE_MERGE_ROWS):
        db.run("upgrade", rev)
    db.run("upgrade", "heads")  # the migrate service's command
    assert db.versions() == {_head()}


MERGE = "57_0002"


def test_57_4_relative_downgrade_from_the_merge_fails_loudly(scratch_db):
    db = scratch_db
    # Revisions above the merge (06b_0001, 06b-2) are a plain chain; go down to the merge point
    # explicitly first: relative steps from there are what must fail loudly.
    db.run("downgrade", MERGE)
    assert db.versions() == {MERGE}
    schema = db.tables()
    for target in ("-1", "06a@-1", "03a@-1"):
        done = db.alembic("downgrade", target)
        assert done.returncode != 0, target
        assert "Ambiguous walk" in done.stdout + done.stderr, target
        assert db.versions() == {MERGE}  # nothing moved
    assert db.tables() == schema


def test_57_4_explicit_revision_rolls_back_one_package_revision(scratch_db):
    # Roll back 06a_0002: Alembic removes it, its dependant 03c_0002 and the merge revisions;
    # every other package stays.
    db = scratch_db
    assert LIFETIME <= _run_columns(db)
    db.run("downgrade", "06a_0001")
    assert not (LIFETIME & _run_columns(db))
    assert not (RETENTION & db.tables())
    assert {"runs", "approvals", "api_keys", "knowledge_bases", "tools", "pii_policies"} <= (
        db.tables()
    )
    db.run("upgrade", "head")
    assert LIFETIME <= _run_columns(db)
    assert RETENTION <= db.tables()
    assert db.versions() == {_head()}
