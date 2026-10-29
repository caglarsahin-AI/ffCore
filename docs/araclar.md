# FFCore Tools: MCP tools for agents

Agents act through tools. A tool is an MCP server (streamable HTTP) registered in a project;
the backend is the MCP client. It discovers the server's actions, keeps their settings and
calls them. This page covers package 05a: registering a tool, upstream identities, discovery,
approval settings, test calls, and the two built-in servers `mcp-search` and `mcp-sql`.

## Register a tool

`POST /api/v1/projects/{project_id}/tools` (project admin):

```json
{"key": "crm", "name": "CRM", "kind": "mcp",
 "endpoint_url": "https://crm.example.com/mcp",
 "auth": {"type": "bearer", "token": "..."}}
```

- `key` is unique in the project (`^[a-z][a-z0-9-]{1,63}$`).
- `endpoint_url` passes the outbound policy now and again at every call. Its host must be in
  `EGRESS_ALLOWLIST` (external) or `ALLOWED_INTERNAL_HOSTS` (internal). Loopback, private and
  metadata addresses are refused unless the host is internal. A refusal is `400 egress_*`.
- `kind: openapi` can be registered but not called yet (`501`); it arrives with 05b.

Developers can read tools; only admins change them. Every change is audited.

## Upstream identity

| `auth.type` | Sent to the server | Notes |
|---|---|---|
| `none` | nothing | |
| `bearer` | `Authorization: Bearer <token>` | |
| `header` | `<name>: <value>` | the header name is not secret |
| `basic` | `Authorization: Basic ...` | user name and password are both secret |
| `forward_user` | `Authorization: Bearer <SERVICE_TOKEN>` and `X-On-Behalf-Of: <JWT>` | internal FFCore services only |

Secret fields are stored encrypted (`FERNET_KEY`) and come back as `***`. To change other
fields, send `***` back: the stored value is kept (same auth type only). Secrets never appear
in logs, the audit log or API answers.

`forward_user` passes the calling user's identity:

- It is allowed only for hosts in `ALLOWED_INTERNAL_HOSTS`. A third-party host is refused with
  `400 forward_user_not_internal`.
- Every call signs a new token, valid for 60 s. It carries `sub` (the user), `project_id` and
  `aud = [<tool key>, "ffcore-backend"]`.
- The tool accepts only tokens that list its own key. A token cut for another tool is refused
  (`403 audience_mismatch`).
- The backend behind the tool accepts `ffcore-backend` and applies the user's permissions.
- The tool holds no signing key: it relays the token unchanged.

Every call opens its own MCP session; sessions are never shared between calls or users.

## Discover actions

`POST .../tools/{tool_id}/discover` runs MCP `tools/list` with the tool's identity.

- **A new action** arrives disabled and needing approval (`enabled=false`,
  `needs_approval=true`). An admin turns it on.
- **An existing action** keeps its settings; its description and input schema are refreshed.
- **An action the server no longer lists** becomes `status=missing` and is disabled. It is not
  deleted.
- **A failed discovery** answers `200` with `status=error` and `last_error_code`.
  - `tool_unreachable`, `tool_timeout`, `tool_auth_failed`, `tool_http_<status>`,
    `tool_protocol_error`: the call did not get through.
  - `egress_*`: the outbound policy refused the endpoint.

`PATCH .../tools/{tool_id}/actions/{name}` sets `enabled`, `needs_approval`,
`max_calls_per_run` and `timeout_s`. Discovery never changes them. `needs_approval` is honoured
by the agent runtime (06a, 07).

## Test call

`POST .../tools/{tool_id}/actions/{name}/invoke` with `{"arguments": {...}}` (admin) calls the
action with the tool's identity; for `forward_user` that is the admin's own identity.

- It runs whether or not the action is enabled and asks no approval: the admin calling it is
  the decision.
- The audit log records the call without its arguments or result.
- A failed call is `502` with one of the codes above.

## What a model gets

- **Result size.** A result longer than `TOOL_RESULT_MAX_CHARS` (default 20000) is cut and
  ends in `[truncated: N/M chars]`. It is never cut silently.
- **Timeout.** A call is bounded by the action's `timeout_s`, otherwise `MCP_CALL_TIMEOUT_S`
  (default 30).
- **Call log.** Every call writes one log line: `tool_call tool=... action=... status=...
  latency_ms=... truncated=...`. Arguments and results are not logged; the agent runtime
  stores them with the run (06a).

## Built-in: mcp-search

`search_documents(query, kb_key, top_k=5)` searches a knowledge base the user can read. It
returns numbered passages with document name and page.

Register it as tool key `mcp-search`, endpoint `http://mcp-search:8000/mcp`, auth
`forward_user`. The key matters: the service accepts only tokens cut for `mcp-search`.

## Built-in: mcp-sql

- `get_schema(question?)` returns the tables and columns in business language, narrowed to the
  question, and the project's five nearest question-SQL examples.
- `run_sql(sql, reason)` runs one read-only `SELECT` on the demo database:
  - the result is CSV with at most `SQL_MAX_ROWS` (500) rows; a longer result says it was cut;
  - each query has `SQL_TIMEOUT_S` (20 s).

The query is checked before it reaches the database:
- exactly one statement, and it is a query;
- no write or DDL anywhere, no `SELECT INTO`, no `FOR UPDATE`;
- no `pg_*` tables or functions, no `information_schema`;
- subqueries at most 3 deep;
- known tables only;
- a `LIMIT` is added when missing.

A refusal comes back as `sql_rejected: <code> (...)`, a database error as
`sql_error: <code> (...)`. The model can correct the query and try again.

Setup:

1. Set `AGENT_DEMO_DB_PASSWORD` in `.env`. The demo uses the database name `agent_demo`;
   choose another value for any other use.
2. `docker compose run --rm tools make seed-sql-demo` creates the database `agent_demo` in the
   existing Postgres:
   - the synthetic schema and data from `data/samples/schema`;
   - a read-only login user `mcp_sql`, with a statement timeout.
   It is idempotent.
3. `docker compose run --rm tools make seed-sql-context PROJECT=<key>` loads the table
   descriptions and SQL examples for `get_schema` into a project. A reload replaces them.
4. Register tool key `mcp-sql`, endpoint `http://mcp-sql:8000/mcp`, auth `forward_user`.

## Add your own MCP server

1. Run the server on the internal network or reach it through `EGRESS_ALLOWLIST`.
   - An internal host goes into `ALLOWED_INTERNAL_HOSTS`.
   - It must speak MCP over streamable HTTP.
2. Register it with the identity it expects, then discover.
3. Review each action, set `needs_approval` (actions that change data should keep it), and
   enable the ones agents may use.

## Contract (C7)

These are frozen with 05a; changes are additive only:
- streamable HTTP transport and `tools/list` discovery;
- `search_documents(query, kb_key, top_k)`;
- `get_schema(question?)`;
- `run_sql(sql, reason)`.

The API is in `backend/openapi/05a.yaml`.
