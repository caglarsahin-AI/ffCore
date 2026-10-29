"""CONTRACTS C3: project-owned root tables carry the common columns; exceptions are named here.

This list is the single place in code for the C3 exception list (KARARLAR "03a kararları",
DRIFT-53). Adding a table here is a class B change and goes into CONTRACTS.md as well.
"""

from ffcore.models import Base

COMMON_COLUMNS = {"id", "project_id", "created_at", "updated_at", "created_by", "deleted_at"}

C3_EXCEPTIONS = {
    # global
    "users": "global",
    "projects": "the project itself",
    "providers": "tenant level",
    "model_catalog": "tenant level, static",
    # link tables
    "project_members": "link",
    "provider_projects": "link",
    # child tables: the project comes through the parent (04a)
    "attachments": "child of documents",
    "chunks": "child of documents",
    # child tables (05a; named in CONTRACTS C3)
    "tool_actions": "child of tools",
    "few_shots": "child of the project's SQL tool data, append-only examples",
    # append-only event tables
    "audit_events": "append-only",
    "guardrail_events": "append-only (08; named in CONTRACTS C3)",
    "kb_queries": "append-only (04a)",
}


def test_c3_root_tables_have_common_columns():
    missing = {
        name: sorted(COMMON_COLUMNS - set(table.columns.keys()))
        for name, table in Base.metadata.tables.items()
        if name not in C3_EXCEPTIONS
    }
    assert {name: cols for name, cols in missing.items() if cols} == {}


def test_c3_models_is_a_root_table():
    assert "models" in Base.metadata.tables
    assert "models" not in C3_EXCEPTIONS


def test_c3_exceptions_are_real_tables():
    # A stale entry would silently exempt a future table with the same name.
    assert set(C3_EXCEPTIONS) <= set(Base.metadata.tables)
