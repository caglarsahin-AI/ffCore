"""mcp-sql core (05a): the SQL validator and the read-only executor behind `run_sql`.

Rules (brief 05 B; KARARLAR "05a review r1 kararları" item 5), checked with sqlglot before
any database connection:
- exactly one statement, and it is a query (SELECT, WITH ... SELECT, or a set operation
  UNION / EXCEPT / INTERSECT whose every branch is a SELECT; no VALUES lists);
- no write or DDL anywhere in it (also not inside a CTE), no SELECT INTO, no FOR UPDATE;
- no system catalogs: pg_* tables, information_schema;
- no function from the closed list of functions that change state, wait or reach outside the
  query (sequences, settings, pg_*, lo_*, dblink*, txid_*);
- comments are stripped: what runs is sqlglot's rendering of the parsed query, without them;
- subquery depth at most 3 (the outer SELECT counts as 1);
- only tables of the target database (CTE names are not tables);
- a LIMIT of SQL_MAX_ROWS + 1 is added when the query has none.
The database side is read-only as well: the login user has the agent_readonly role
(default_transaction_read_only, statement_timeout), and every session sets both again.
"""

import csv
import io
from collections.abc import Awaitable, Callable, Iterable
from typing import Any

import psycopg
import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

MAX_DEPTH = 3
DIALECT = "postgres"
# Anything that writes, changes schema or rights, or runs a non-SQL command.
_FORBIDDEN = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Merge,
    exp.Create,
    exp.Drop,
    exp.Alter,
    exp.Copy,
    exp.TruncateTable,
    exp.Grant,
    exp.Command,
    exp.Into,
    exp.Lock,
    exp.Values,
)
_SYSTEM_SCHEMAS = ("pg_catalog", "information_schema", "pg_toast")
_CLOSED_FUNCTION_PREFIXES = ("pg_", "lo_", "dblink", "txid_")
_CLOSED_FUNCTIONS = (
    "setval",
    "nextval",
    "lastval",
    "currval",
    "set_config",
    "current_setting",
    "query_to_xml",
    "table_to_xml",
    "copy",
)

TABLES_QUERY = (
    "SELECT table_name FROM information_schema.tables "
    "WHERE table_schema = 'public' AND table_type IN ('BASE TABLE', 'VIEW')"
)


class SqlRejected(Exception):
    """The validator refused the query; `code` is one of sql_parse_error, sql_multiple_statements,
    sql_not_select, sql_system_catalog, sql_function_not_allowed, sql_too_deep,
    sql_unknown_table."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def _select_depth(root: exp.Expression) -> int:
    """Deepest chain of SELECTs nested inside each other."""

    def walk(node: exp.Expression, level: int) -> int:
        here = level + 1 if isinstance(node, exp.Select) else level
        return max([here, *(walk(child, here) for child in node.iter_expressions())])

    return walk(root, 0)


def check_structure(sql: str) -> exp.Expression:
    """Every rule that needs no database; raises SqlRejected."""
    try:
        statements = [s for s in sqlglot.parse(sql, read=DIALECT) if s is not None]
    except ParseError:
        raise SqlRejected("sql_parse_error", "the query could not be parsed") from None
    if not statements:
        raise SqlRejected("sql_parse_error", "the query is empty")
    if len(statements) > 1:
        raise SqlRejected("sql_multiple_statements", "send exactly one statement")
    root = statements[0]
    for node in root.walk():
        if isinstance(node, _FORBIDDEN):
            raise SqlRejected("sql_not_select", f"{type(node).__name__} is not allowed")
    if not isinstance(root, exp.Query):
        raise SqlRejected("sql_parse_error", "not a query")
    for table in root.find_all(exp.Table):
        schema = (table.db or "").lower()
        if schema in _SYSTEM_SCHEMAS or table.name.lower().startswith("pg_"):
            raise SqlRejected("sql_system_catalog", "system catalogs are not available")
    for func in root.find_all(exp.Func):
        name = (func.name if isinstance(func, exp.Anonymous) else func.sql_name()).lower()
        if name.startswith(_CLOSED_FUNCTION_PREFIXES) or name in _CLOSED_FUNCTIONS:
            raise SqlRejected("sql_function_not_allowed", f"function {name} is not available")
    for operation in root.find_all(exp.SetOperation):
        for branch in (operation.left, operation.right):
            if not isinstance(branch, exp.Select | exp.SetOperation | exp.Subquery):
                raise SqlRejected("sql_not_select", "every branch of a set operation is a SELECT")
    if _select_depth(root) > MAX_DEPTH:
        raise SqlRejected("sql_too_deep", f"subqueries nest deeper than {MAX_DEPTH}")
    return root


def check_tables(root: exp.Expression, tables: Iterable[str]) -> None:
    known = {t.lower() for t in tables}
    ctes = {cte.alias_or_name.lower() for cte in root.find_all(exp.CTE)}
    for table in root.find_all(exp.Table):
        name = table.name.lower()
        if name not in known and name not in ctes:
            raise SqlRejected("sql_unknown_table", f"unknown table {table.name}")


def with_limit(root: exp.Expression, max_rows: int) -> str:
    if root.args.get("limit") is None:
        root = root.limit(max_rows + 1)
    return root.sql(dialect=DIALECT, comments=False)


def validate(sql: str, tables: Iterable[str], *, max_rows: int) -> str:
    root = check_structure(sql)
    check_tables(root, tables)
    return with_limit(root, max_rows)


def format_rows(columns: list[str], rows: list[tuple[Any, ...]], max_rows: int) -> str:
    """Compact CSV with a header; a cut result says so (never a silent cut)."""
    truncated = len(rows) > max_rows
    shown = rows[:max_rows]
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(columns)
    writer.writerows(["" if v is None else v for v in row] for row in shown)
    text = out.getvalue() + f"rows: {len(shown)}"
    if truncated:
        text += f"\n[truncated: first {max_rows} rows shown; the query returned more]"
    return text


Connect = Callable[[], Awaitable[psycopg.AsyncConnection]]

# How run_sql_text starts a refusal and a database error. mcp-sql returns both as a tool error
# with this text (09-1 r2 MAJOR-r2-3): the model still reads the code, the run records
# `is_error` with the code, and a failed query is never taken for a result.
SQL_ERROR_PREFIXES = ("sql_rejected:", "sql_error:")


def error_code(text: str) -> str | None:
    """`sql_rejected` or `sql_error` for a run_sql_text refusal or error, else None."""
    prefix = next((p for p in SQL_ERROR_PREFIXES if text.startswith(p)), None)
    return prefix.rstrip(":") if prefix else None


async def run_sql_text(sql: str, *, connect: Connect, max_rows: int, timeout_s: int = 20) -> str:
    """What run_sql returns to the model. Rejections and database errors are text that starts
    with their code, so the model can correct the query; nothing here raises."""
    try:
        root = check_structure(sql)
    except SqlRejected as exc:
        return f"sql_rejected: {exc.code} ({exc.detail})"
    try:
        async with await connect() as conn:
            await conn.execute(f"SET statement_timeout = '{int(timeout_s)}s'")
            await conn.execute("SET default_transaction_read_only = on")
            tables = [r[0] for r in await (await conn.execute(TABLES_QUERY)).fetchall()]
            try:
                check_tables(root, tables)
            except SqlRejected as exc:
                return f"sql_rejected: {exc.code} ({exc.detail})"
            cursor = await conn.execute(with_limit(root, max_rows))
            rows = await cursor.fetchmany(max_rows + 1)
            columns = [c.name for c in cursor.description or []]
    except psycopg.errors.QueryCanceled:
        return f"sql_error: sql_timeout (exceeded {int(timeout_s)} s)"
    except psycopg.Error as exc:
        # The primary message is about the query (unknown column, bad cast); never the data.
        primary = exc.diag.message_primary if exc.diag else None
        return f"sql_error: {exc.sqlstate or 'unknown'} ({primary or type(exc).__name__})"
    return format_rows(columns, rows, max_rows)
