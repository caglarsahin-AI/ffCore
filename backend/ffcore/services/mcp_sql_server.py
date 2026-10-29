"""mcp-sql (05a): the MCP server behind `get_schema(question?)` and `run_sql(sql, reason)` (C7).

Runs as its own compose service from the backend image: `python -m ffcore.services.
mcp_sql_server`. get_schema asks the backend (descriptions and few-shot examples, on behalf of
the caller); run_sql validates the query (services/mcp_sql) and runs it on the demo database
with a read-only login user (SQL_DEMO_DATABASE_URL). Request checks:
services/mcp_server_common.CallerCheck with an OboVerifier: the caller's token is verified by
the backend before any request reaches a tool, and the tools ask the verifier again (one cached
answer per token) for the project, so neither tool acts on a token the backend has not verified
(review r1 MAJOR-1). Every call is logged by the backend's MCP client; this service logs only
the query outcome code, never the query or the rows.
"""

import logging
from typing import Annotated

import psycopg
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from ffcore.core.config import Settings
from ffcore.services import mcp_server_common, mcp_sql
from ffcore.services.mcp_server_common import OboVerifier, Relay, VerifyRefused, obo_token

log = logging.getLogger("ffcore.mcp_sql")

DEFAULT_TOOL_KEY = "mcp-sql"


def format_context(body: dict) -> str:
    lines = []
    if not body["matched"]:
        lines.append("No table matched the question; all tables are listed.")
    lines.append("Tables:")
    for table in body["tables"]:
        lines.append(f"- {table['name']}: {table['description']}")
        for column in table["columns"]:
            extra = ""
            if column["is_metric"] and column["formula"]:
                extra = f" Metric: {column['formula']}."
            elif column["sample_values"]:
                extra = " Examples: " + ", ".join(map(str, column["sample_values"][:5])) + "."
            lines.append(f"  - {column['name']}: {column['description']}{extra}")
    if body["examples"]:
        lines.append("")
        lines.append("Examples:")
        for example in body["examples"]:
            lines.append(f"Q: {example['question']}")
            lines.append(f"SQL: {example['sql']}")
    return "\n".join(lines)


def build_server(settings: Settings, *, tool_key: str, verifier: OboVerifier) -> MCPServer:
    server = MCPServer("mcp-sql")

    async def verified(ctx: Context) -> dict:
        try:
            return await verifier.claims(obo_token(ctx.headers))
        except VerifyRefused as exc:
            raise ToolError(exc.code) from None

    @server.tool()
    async def get_schema(
        ctx: Context,
        question: Annotated[str | None, Field(max_length=2000)] = None,
    ) -> str:
        """Tables and columns of the database in business language, narrowed to the question,
        with example questions and their SQL. Call this before run_sql."""
        claims = await verified(ctx)
        relay = Relay(ctx.headers, project_id=claims["project_id"])
        body = await relay.call(
            settings,
            "POST",
            f"/api/v1/projects/{relay.project_id}/tools/sql-context",
            {"tool_key": tool_key, "question": question},
        )
        return format_context(body)

    @server.tool()
    async def run_sql(
        sql: Annotated[str, Field(min_length=1, max_length=20000)],
        reason: Annotated[str, Field(min_length=1, max_length=1000)],
        ctx: Context,
    ) -> str:
        """Run one read-only SELECT. Results come as CSV, at most SQL_MAX_ROWS rows; a longer
        result says it was cut. A refused or failed query returns its code."""
        await verified(ctx)  # before any connection to the database
        url = settings.sql_demo_database_url
        if url is None:
            raise ToolError("sql_database_not_configured")

        async def connect() -> psycopg.AsyncConnection:
            return await psycopg.AsyncConnection.connect(url.get_secret_value(), autocommit=True)

        text = await mcp_sql.run_sql_text(
            sql, connect=connect, max_rows=settings.sql_max_rows, timeout_s=settings.sql_timeout_s
        )
        log.info("run_sql outcome=%s", text.split(":", 1)[0] if text.startswith("sql_") else "ok")
        return text

    return server


def build_app(settings: Settings, *, tool_key: str, allowed_hosts: list[str]):
    verifier = OboVerifier(settings, tool_key)
    return mcp_server_common.build_app(
        build_server(settings, tool_key=tool_key, verifier=verifier),
        settings,
        tool_key=tool_key,
        allowed_hosts=allowed_hosts,
        verifier=verifier,
    )


if __name__ == "__main__":
    mcp_server_common.serve(build_app, default_key=DEFAULT_TOOL_KEY, key_env="MCP_SQL_TOOL_KEY")
