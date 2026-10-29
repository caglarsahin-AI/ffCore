# mcp-sql

MCP server (streamable HTTP) for text-to-SQL on the demo database (13a, synthetic; contract C7):

- `get_schema(question?)`: tables and columns in business language, narrowed to the question,
  with the project's five nearest question-SQL examples. Call it before `run_sql`.
- `run_sql(sql, reason)`: one read-only SELECT, validated first; CSV, at most `SQL_MAX_ROWS`
  rows (a longer result says it was cut), `SQL_TIMEOUT_S` per query.

Code: `backend/ffcore/services/mcp_sql_server.py` (server), `mcp_sql.py` (validator, executor),
`mcp_sql_context.py` (backend side of get_schema). The service runs from the backend image
(`python -m ffcore.services.mcp_sql_server`); this folder holds no code.

Caller: every request carries the caller's `X-On-Behalf-Of` token. The service holds no signing
key; it asks the backend to verify the token (`POST /api/v1/internal/obo/verify`, its own tool
key as the audience) before any tool runs, keeps one answer per token until it expires, and
takes the project from the verified claims. A refused token is 401/403 with its code.

Validator (sqlglot, before any database connection): exactly one statement and it is a query,
comments removed; set operations only with SELECT branches, no VALUES lists; no write or DDL
anywhere (CTEs included), no SELECT INTO, no FOR UPDATE; no `pg_*` tables, no
`information_schema`; no function from the closed list (sequences, settings, `pg_*`, `lo_*`,
`dblink*`, `txid_*`); subquery depth at most 3; known tables only; a LIMIT is added when
missing. A refusal comes back as `sql_rejected: <code> (...)`; a database error as
`sql_error: <sqlstate> (...)`; the model can correct the query.

Database: its own database `agent_demo` in the existing Postgres, made by
`docker compose run --rm tools make seed-sql-demo` (13a schema and data, the `agent_readonly`
role, login user `mcp_sql` with `AGENT_DEMO_DB_PASSWORD` from `.env`). The login user is
read-only (`default_transaction_read_only`) with a statement timeout; every session sets both
again. The tool data for `get_schema` goes into a project and its registered `mcp-sql` tool
with `make seed-sql-context PROJECT=<key>` (register the tool first; examples belong to it).

Register it in a project as tool key `mcp-sql` with auth type `forward_user` (see mcp-search's
README for why the key matters). See `docs/araclar.md`.
