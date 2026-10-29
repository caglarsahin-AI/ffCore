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
    # append-only event tables
    "audit_events": "append-only",
    "guardrail_events": "append-only (08; named in CONTRACTS C3)",
    "kb_queries": "append-only (04a)",
}

# Child tables take the project through their parent (CONTRACTS C3): the column named here is a
# NOT NULL foreign key whose chain ends in a root table. Being listed does not skip the check
# (05a review r1 BLOCKER-1).
CHILD_TABLES = {
    "attachments": "document_id",  # 04a
    "chunks": "document_id",  # 04a
    "tool_actions": "tool_id",  # 05a
    "few_shots": "tool_id",  # 05a: examples of the project's registered mcp-sql tool
}
C3_EXCEPTIONS |= {name: f"child via {column}" for name, column in CHILD_TABLES.items()}


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


def _parent(table_name: str) -> str:
    table = Base.metadata.tables[table_name]
    column = table.columns[CHILD_TABLES[table_name]]
    assert not column.nullable, f"{table_name}.{column.name} must be NOT NULL"
    targets = {fk.column.table.name for fk in column.foreign_keys}
    assert len(targets) == 1, f"{table_name}.{column.name} needs exactly one foreign key"
    return targets.pop()


def test_c3_child_tables_reach_a_root_table():
    for name in CHILD_TABLES:
        chain, current = [name], name
        while current in CHILD_TABLES:
            current = _parent(current)
            assert current not in chain, f"cycle: {chain}"
            chain.append(current)
        root = Base.metadata.tables[current]
        assert current not in C3_EXCEPTIONS, f"{name}: chain {chain} ends outside a root table"
        assert COMMON_COLUMNS <= set(root.columns.keys()), chain


def test_c3_child_tables_have_no_own_project_id():
    # The project comes only through the chain; a second source could disagree with it.
    assert [n for n in CHILD_TABLES if "project_id" in Base.metadata.tables[n].columns] == []
