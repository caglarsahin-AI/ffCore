"""16-1 migration 16_0001 on a real database: one head, the six tables, their CHECKs, the one
active run per source index, and a round trip that leaves the rest of the schema as it was."""

import uuid

import psycopg
import pytest

TABLES = {
    "data_sources",
    "source_items",
    "source_attachments",
    "sync_runs",
    "source_sync_state",
    "acl_mappings",
}


def _source(db) -> uuid.UUID:
    project, kb, source = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    db.conn.execute(
        "INSERT INTO projects (id, key, name, created_by) VALUES (%s, %s, 'P', 'test')",
        (project, f"p16-{project.hex[:8]}"),
    )
    db.conn.execute(
        "INSERT INTO knowledge_bases (id, project_id, key, name, embed_model, embed_dim,"
        " chunk_size, chunk_overlap, hybrid, rerank, rerank_model, default_top_k,"
        " normalizer_config_id, created_by) VALUES (%s, %s, 'kb', 'KB', 'm', 1024, 512, 0,"
        " true, false, 'r', 5, 'n', 'test')",
        (kb, project),
    )
    db.conn.execute(
        "INSERT INTO data_sources (id, project_id, kb_id, key, name, kind, created_by)"
        " VALUES (%s, %s, %s, 'fs1', 'FS', 'fs', 'test')",
        (source, project, kb),
    )
    return source


def _run(db, source, status="queued"):
    db.conn.execute(
        "INSERT INTO sync_runs (id, data_source_id, layer, mode, trigger, requested_by, status)"
        " VALUES (%s, %s, 'raw', 'full', 'manual', 'test', %s)",
        (uuid.uuid4(), source, status),
    )


def test_16_1_migration_round_trip(scratch_db):
    db = scratch_db
    heads = [line for line in db.run("heads").splitlines() if line.strip()]
    # 17_0001 sits above 16_0001 (17-1 rebase): one head, and 17's table goes down with it.
    assert len(heads) == 1 and heads[0].startswith("17_0001")
    schema = db.tables()
    assert TABLES <= schema
    db.run("downgrade", "14_0001")
    assert db.tables() == schema - TABLES - {"identity_group_mappings"}
    db.run("upgrade", "head")
    assert db.tables() == schema


def test_16_1_migration_constraints(scratch_db):
    db = scratch_db
    source = _source(db)
    _run(db, source)
    with pytest.raises(psycopg.errors.UniqueViolation):
        _run(db, source, "running")  # one active run per source
    _run(db, source, "completed")  # finished runs are history, any number
    for statement in (
        "UPDATE data_sources SET kind = 'gdrive'",
        "UPDATE data_sources SET deployment = 'onprem'",
        "UPDATE data_sources SET prune_max_ratio = 0",
        "UPDATE sync_runs SET prune_decision = 'maybe'",
    ):
        with pytest.raises(psycopg.errors.CheckViolation):
            db.conn.execute(statement)
    with pytest.raises(psycopg.errors.CheckViolation):
        db.conn.execute(
            "INSERT INTO acl_mappings (id, data_source_id, external_group, role, user_id,"
            " created_by) VALUES (%s, %s, 'g', NULL, NULL, 'test')",
            (uuid.uuid4(), source),
        )
