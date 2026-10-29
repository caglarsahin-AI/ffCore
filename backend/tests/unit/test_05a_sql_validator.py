"""05a slice 5: the mcp-sql validator (sqlglot). Acceptance 2 and the brief's rules: one
SELECT, no writes, no system catalogs, known tables only, depth <= 3, LIMIT added."""

import asyncio

import pytest

from ffcore.services import mcp_sql
from ffcore.services.mcp_sql import SqlRejected, validate
from tests.sql_matrix import REJECTED

TABLES = {"departments", "beds", "admissions", "devices", "device_faults", "contracts_meta"}


def code_of(sql):
    with pytest.raises(SqlRejected) as err:
        validate(sql, TABLES, max_rows=500)
    return err.value.code


def test_05a_sql_select_passes_and_gets_a_limit():
    out = validate("SELECT code, bed_capacity FROM departments", TABLES, max_rows=500)
    assert out.endswith("LIMIT 501")


def test_05a_sql_own_limit_kept():
    out = validate("SELECT code FROM departments LIMIT 3", TABLES, max_rows=500)
    assert out.endswith("LIMIT 3")


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM departments",
        "INSERT INTO departments (id) VALUES (99)",
        "UPDATE beds SET is_active = false",
        "DROP TABLE beds",
        "ALTER TABLE beds ADD COLUMN x int",
        "COPY departments TO STDOUT",
        "TRUNCATE beds",
        "CREATE TABLE x (id int)",
        "GRANT SELECT ON beds TO public",
        "SELECT * INTO new_table FROM beds",
        "WITH gone AS (DELETE FROM beds RETURNING *) SELECT * FROM gone",
    ],
)
def test_05a_sql_writes_rejected(sql):
    assert code_of(sql) == "sql_not_select"


def test_05a_sql_single_statement_only():
    assert code_of("SELECT 1 FROM beds; SELECT 2 FROM beds") == "sql_multiple_statements"


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM pg_catalog.pg_tables",
        "SELECT * FROM pg_user",
        "SELECT * FROM information_schema.tables",
    ],
)
def test_05a_sql_system_catalogs_rejected(sql):
    assert code_of(sql) == "sql_system_catalog"


def test_05a_sql_unknown_table_rejected():
    assert code_of("SELECT * FROM patients") == "sql_unknown_table"


def test_05a_sql_cte_names_are_not_tables():
    out = validate(
        "WITH busy AS (SELECT department_id FROM admissions) SELECT * FROM busy",
        TABLES,
        max_rows=500,
    )
    assert "LIMIT 501" in out


def test_05a_sql_depth_limit():
    three = (
        "SELECT * FROM beds WHERE department_id IN (SELECT id FROM departments WHERE id IN "
        "(SELECT department_id FROM admissions WHERE department_id IN "
        "(SELECT id FROM departments)))"
    )
    assert code_of(three) == "sql_too_deep"
    ok = (
        "SELECT * FROM beds WHERE department_id IN (SELECT id FROM departments WHERE id IN "
        "(SELECT department_id FROM admissions))"
    )
    assert validate(ok, TABLES, max_rows=500)


def test_05a_sql_locking_rejected():
    assert code_of("SELECT * FROM beds FOR UPDATE") == "sql_not_select"


def test_05a_sql_parse_error_coded():
    assert code_of("SELEC * FRM beds") == "sql_parse_error"


def test_05a_2_delete_rejected_before_db():
    """Acceptance 2: the validator answers first; no connection is ever opened."""
    opened = []

    async def connect():
        opened.append(True)
        raise AssertionError("the database must not be reached")

    result = asyncio.run(
        mcp_sql.run_sql_text("DELETE FROM departments", connect=connect, max_rows=500)
    )
    assert result.startswith("sql_rejected: sql_not_select")
    assert opened == []


def _never_connect(opened):
    async def connect():
        opened.append(True)
        raise AssertionError("the database must not be reached")

    return connect


@pytest.mark.parametrize(("sql", "code"), REJECTED)
def test_05a_sql_matrix_rejected_before_db(sql, code):
    """Review r1 MINOR-1: every row is refused by the validator, with no connection opened."""
    opened = []
    result = asyncio.run(mcp_sql.run_sql_text(sql, connect=_never_connect(opened), max_rows=500))
    assert result.startswith(f"sql_rejected: {code} "), result
    assert opened == []


def test_05a_sql_set_operation_of_selects_passes():
    sql = "SELECT code FROM departments UNION SELECT code FROM departments"
    assert validate(sql, TABLES, max_rows=500).endswith("LIMIT 501")


@pytest.mark.parametrize(
    "sql",
    [
        # Comments never reach the database (KARARLAR r1 item 5). sqlglot already escapes a
        # "*/" inside a comment it writes back; stripping removes the question altogether.
        "SELECT 1 FROM beds -- */ ; DELETE FROM beds; /*",
        "SELECT 1 FROM beds /* hidden */",
        "SELECT /* a */ code -- b\nFROM departments",
    ],
)
def test_05a_sql_comments_stripped_from_what_runs(sql):
    out = validate(sql, TABLES, max_rows=500)
    assert "/*" not in out and "--" not in out and "DELETE" not in out.upper(), out
