# FFCore Tools: MCP tools for agents

Agents act through tools. A tool is an MCP server (streamable HTTP) registered in a project;
the backend is the MCP client. It discovers the server's actions, keeps their settings and
calls them. This page covers package 05a: registering a tool, upstream identities, discovery,
approval settings, test calls, and the two built-in servers `mcp-search` and `mcp-sql`; and
package 05b: publishing an OpenAPI document or a remote MCP server as an MCP server of FFCore.

## Register a tool

`POST /api/v1/projects/{project_id}/tools` (project admin):

```json
{"key": "crm", "name": "CRM", "kind": "mcp",
 "endpoint_url": "https://crm.example.com/mcp",
 "auth": {"type": "bearer", "token": "..."}}
```

- `key` is unique in the project (`^[a-z][a-z0-9-]{1,63}$`).
- `endpoint_url` is scheme, host, port and path only. User info (`user:pass@`), a query
  string or a fragment is refused with `400 endpoint_url_not_allowed`: credentials go into
  `auth`, where they are encrypted and masked.
- `endpoint_url` passes the outbound policy now and again at every call. Its host must be in
  `EGRESS_ALLOWLIST` (external) or `ALLOWED_INTERNAL_HOSTS` (internal). Loopback, private and
  metadata addresses are refused unless the host is internal. A refusal is `400 egress_*`.
- `kind: openapi` is refused (`422 openapi_tool_via_mcp_server`, 05b): an OpenAPI service
  becomes a tool by publishing it as an MCP server and adding that server to the tools (see
  "Publish an MCP server"). There is one HTTP path for OpenAPI, not two.
- The backend itself is a tool only as a published server's own endpoint,
  `<INTERNAL_API_URL>/mcp/<key>/` with `forward_user`; any other backend URL (another path,
  another identity, loopback on port 8000) is `400 endpoint_is_platform`, even when
  `ALLOWED_INTERNAL_HOSTS` lists the backend.

Analysts and above read tools and their actions (the agent wizard lists them); only admins with
edit access change them. Secret `auth` fields are `***` for every reader. Every change is audited.

## Upstream identity

| `auth.type` | Sent to the server | Notes |
|---|---|---|
| `none` | nothing | |
| `bearer` | `Authorization: Bearer <token>` | |
| `header` | `<name>: <value>` | the header name is not secret; see below |
| `basic` | `Authorization: Basic ...` | user name and password are both secret |
| `forward_user` | `Authorization: Bearer <SERVICE_TOKEN>` and `X-On-Behalf-Of: <JWT>` | internal FFCore services only |

A `header` name is an HTTP token and never a header the transport or FFCore sets: `Host`,
`Content-Length`, `Connection`, `Transfer-Encoding`, `Upgrade`, `TE`, `Trailer`,
`Keep-Alive`, any `Proxy-*`, `Authorization` (use `bearer` or `basic`), `X-On-Behalf-Of`,
`X-Run-Id`. Such a name is refused with `400 header_name_not_allowed`, at registration and
again at call time.

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
- A tool that acts on the user's identity itself asks the backend to verify the token first:
  `POST /api/v1/internal/obo/verify` (service account only) checks the signature, the tool's
  own key in `aud` and the lifetime, and answers the verified claims (401 `invalid_token`,
  `token_expired`; 403 `audience_mismatch`). `mcp-sql` does this for every request and keeps
  one answer per token until it expires.

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
  question, and the project's five nearest question-SQL examples. mcp-sql reads them from
  `POST /api/v1/projects/{project_id}/tools/sql-context` on behalf of the user who runs the
  agent. That endpoint is a read: it is a POST only because the question travels in the body.
  Every project member who may start a run (role `user` and up) gets an answer; a non-member
  gets 404. Narrowing it to admins would break the SQL assistant for the analysts who run it
  (FOLLOWUP-113, closed).
- `run_sql(sql, reason)` runs one read-only `SELECT` on the demo database:
  - the result is CSV with at most `SQL_MAX_ROWS` (500) rows; a longer result says it was cut;
  - each query has `SQL_TIMEOUT_S` (20 s).

Before the query reaches the database, the backend checks its caller's token (see Upstream
identity) and the query itself:
- exactly one statement, and it is a query; comments are removed and do not count;
- `UNION`, `EXCEPT` and `INTERSECT` only when every branch is a `SELECT`; no `VALUES` lists;
- no write or DDL anywhere, also not inside a `WITH`; no `SELECT INTO`, no `FOR UPDATE`;
- no `pg_*` tables, no `information_schema`;
- no function that changes state, waits or reaches outside the query: `setval`, `nextval`,
  `lastval`, `currval`, `set_config`, `current_setting`, `pg_*`, `lo_*`, `dblink*`,
  `txid_*` (`sql_function_not_allowed`);
- subqueries at most 3 deep;
- known tables only;
- a `LIMIT` is added when missing.

A refusal comes back as a tool error with the text `sql_rejected: <code> (...)`, a database
error as `sql_error: <code> (...)`; the run's `tool_result` event has `is_error: true` and
`error_code` `sql_rejected` / `sql_error`. The model reads the code, can correct the query and
try again.

Setup:

1. Set `AGENT_DEMO_DB_PASSWORD` in `.env`. The demo uses the database name `agent_demo`;
   choose another value for any other use.
2. `docker compose run --rm tools make seed-sql-demo` creates the database `agent_demo` in the
   existing Postgres:
   - the synthetic schema and data from `data/samples/schema`;
   - a read-only login user `mcp_sql`, with a statement timeout.
   It is idempotent.
3. Register tool key `mcp-sql`, endpoint `http://mcp-sql:8000/mcp`, auth `forward_user`.
4. `docker compose run --rm tools make seed-sql-context PROJECT=<key>` loads the table
   descriptions into the project and the SQL examples into its `mcp-sql` tool (another key:
   `TOOL=<key>`). The tool must be registered first. A reload replaces them. Examples belong to
   the tool: deleting the tool takes them out of `get_schema`.

## Add your own MCP server

1. Run the server on the internal network or reach it through `EGRESS_ALLOWLIST`.
   - An internal host goes into `ALLOWED_INTERNAL_HOSTS`.
   - It must speak MCP over streamable HTTP.
2. Register it with the identity it expects, then discover.
3. Review each action, set `needs_approval` (actions that change data should keep it), and
   enable the ones agents may use.

## Publish an MCP server (05b)

Corporate systems with an OpenAPI document (Superset, HBYS, SAP, Jira) become agent tools
without code: FFCore serves the document's operations as MCP tools at `/mcp/<key>/`. A remote
MCP server can be served the same way, behind FFCore's identity, guardrail and log.

`POST /api/v1/projects/{project_id}/mcp-servers` (project admin):

```json
{"key": "superset", "name": "Superset", "source_kind": "openapi",
 "spec": "<OpenAPI 3 document, YAML or JSON>",
 "upstream_base_url": "https://superset.example.com",
 "upstream_auth": {"type": "bearer", "token": "..."},
 "access": "internal", "guardrail_mode": "monitor", "guardrail_policy_key": "default"}
```

- `key` is unique in the installation (the endpoint path has no project):
  `409 mcp_server_key_taken`. So an admin can learn that a key is used in another project;
  choose keys that say nothing confidential.
- `source_kind: remote_mcp` takes no `spec`; `upstream_base_url` is the remote MCP endpoint.
  Run `POST .../mcp-servers/{id}/discover` to read its `tools/list`.
- `upstream_auth` is `none`, `bearer`, `header` or `basic` (encrypted, `***` when read).
  `forward_user` is not offered: platform services are never an upstream.
- `upstream_base_url` follows the tool endpoint rules (scheme, host, port, path; egress policy,
  `400 egress_*`) and is never a platform service (`422 upstream_url_refused`: the backend,
  LiteLLM, Langfuse, Postgres, mcp-search, mcp-sql and the other compose services).
- The server starts as `draft` with no operation selected.

**Operations.** Each OpenAPI operation becomes one tool: `operationId` is the name, path and
query parameters and the JSON request body (`body`) form `inputSchema`, the description is the
operation's description or summary. Local `$ref`s are resolved. An operation that cannot be
served stays in the list with `exposable: false` and a `reason`: `operation_id_missing`,
`operation_name_invalid`, `operation_id_duplicate`, `parameter_location_unsupported` (header or
cookie parameters), `parameter_name_conflict`, `request_body_unsupported` (not JSON),
`external_ref`, `ref_not_found`, `ref_cycle`. A bad document is `422 spec_invalid`,
`spec_version_unsupported` (only OpenAPI 3) or `spec_too_large` (1 000 000 characters).

A path key is joined to the base URL's path (`https://h/api` + `/v1/x` is `https://h/api/v1/x`),
so it must start with one `/` and have no empty, `.` or `..` segment, no `?`, `#` or backslash,
and no percent-encoded `.`, `/` or backslash (`%2e`, `%2f`, `%5c` in any case, also encoded again
as `%252e`): an upstream that decodes them would leave the base path. A document with any other
path key (`v1/x`, `:8080/x`, `//other-host/x`, `/a/../b`, `/a/%2e%2e/b`, `/a%2Fb`) is refused
whole: `422 openapi_path_invalid`. A path parameter value `.`, `..` or one holding such an
encoding (`%2e%2e`, `a%2Fb`) is `invalid_arguments`; nothing is sent upstream.

`PATCH .../mcp-servers/{id}` selects what is served and how it looks to the model:

```json
{"exposed_operations": ["searchDashboards", "createChart"],
 "aliases": {"searchDashboards": {"name": "find_dashboard", "description": "Find a dashboard."}},
 "status": "active"}
```

Only `exposed_operations` are listed and callable. A new document (`PUT .../spec`) keeps the
selection and aliases by operation name; a selected operation missing from it is
`409 exposed_operation_missing` and nothing changes. `POST .../test` sends one GET to the
upstream (or `initialize` and `tools/list` for a remote server) and shows the status.

**Who may call `/mcp/<key>/`.** The endpoint is the backend's second external surface, next to
the facade (PLAN R1.2). Every request is checked before the MCP SDK sees it:

| `access` | API key | Platform runtime (agent run) |
|---|---|---|
| `internal` (default) | `403 mcp_server_internal` | yes |
| `token` | with the `tools_invoke` scope (`403 scope_missing` without) | yes |

A key only reaches servers of its own project; an unknown, deleted, inactive or other project's
server is one `404 mcp_server_not_found`. A console session or a bare service token is
`401 mcp_credentials_required`. The SDK's Host header check (DNS rebinding protection) is off on
this endpoint: there is no cookie or other ambient credential on it, every request carries a key
or the service token, and the public Host behind a reverse proxy is not known in advance. The
identity check above runs first on every request, whatever the Host.

**Each call** goes: request quota (the request windows of the project's quotas, like the facade;
no token or USD counting, there is no model) -> guardrail `tool.pre` on the arguments ->
upstream -> result cut to `TOOL_RESULT_MAX_CHARS` (`[truncated: N/M chars]`) -> guardrail
`tool.post` -> answer. The upstream call goes only to the registered origin and base path: at
every call the base URL passes the registration checks again (the egress policy may have
narrowed since) and the final URL must keep its scheme, host and port
(`upstream_origin_mismatch`); such a refusal sends nothing and the call is logged as `denied`
with its code. Redirects are not followed (`egress_too_many_redirects`); an answer larger than `MCP_UPSTREAM_MAX_BYTES` is
refused (`upstream_response_too_large`). Failures reach the caller as an error result with a
code (`upstream_http_<status>`, `upstream_timeout`, `upstream_unreachable`, `egress_*`,
`invalid_arguments`, `unknown_tool`, `quota_exceeded`, `guardrail_blocked`,
`upstream_origin_mismatch`, `openapi_path_invalid`, `upstream_url_refused`,
`endpoint_url_not_allowed`); upstream text never does.

**Guardrail.** `guardrail_policy_key` names the project's policy (default `default`).
`guardrail_mode` makes it stricter, never looser: each rule runs in the stricter of the server
mode and its own (`off` < `monitor` < `enforce`). `off` runs the policy as it is, `monitor` logs
an `off` policy too, `enforce` enforces every rule. Rules of type `tool_args` match the tool as
`<server key>.<operation>`. Events go to the guardrail log with source `api`.

**Log.** Every call writes one `mcp_server_calls` row (operation, status, code, latency, run,
caller; no arguments or results) and one `mcp_server_call` audit row.
`GET .../mcp-servers/{id}/calls?hours=24` gives requests, errors, blocked calls, p50/p95 latency
and the last 50 calls (the console's MCP monitoring tab, 10c-3; docs/onyuz.md "MCP servers").

**Reading a call's status (FOLLOWUP-195).** `status` and `error_code` together say where a call
ended:

| `status` | Meaning | Example codes |
|---|---|---|
| `ok` | The upstream answered (2xx). | none |
| `error` | The request was made and failed, or the argument check refused it (then no request left). | `upstream_http_<status>` (for example `upstream_http_404`), `upstream_timeout`, `upstream_unreachable`, `upstream_response_too_large`, `invalid_arguments` (a bad argument, also a path value such as `..`, `.`, `%2e%2e` or `a%2Fb`) |
| `denied` | Refused before any request left by a quota, egress, origin or path rule: nothing reached the upstream. | `quota_exceeded`, `quota_unavailable`, `upstream_origin_mismatch`, `upstream_url_refused`, `endpoint_url_not_allowed`, `egress_not_allowlisted` and the other `egress_*` refusals, `openapi_path_invalid` |
| `blocked` | Stopped by the guardrail policy (`tool.pre` or `tool.post`). | `guardrail_blocked` |

`openapi_path_invalid` under `denied` has two sources: an unsafe path in the stored document, or
a caller's path value that contains `/` or `\` (such as `a/b` or `../x`). In both cases no request
left; the `error_code` says why a call ended where it did, so read it together with the caller's
arguments. `errors` in the summary counts every call that did not end `ok` (error, denied and
blocked).

**Agents use it** through the tools registry: `POST .../mcp-servers/{id}/tools` adds a tool with
the server's key at `<INTERNAL_API_URL>/mcp/<key>/` and `forward_user`, so the runtime calls the
endpoint with the run user's identity. Discover it in the tools registry; its actions start
disabled and needing approval (05a rule). Keep approval on actions that change data
(`createChart` in the Superset sample): the run waits in the approval queue (07) before the
call. Approval is on the agent side; an external client with a `token` key decides for itself.

The Superset sample is `data/samples/openapi/superset.yaml` (6 operations; `createChart` and
`addChartToDashboard` change data). The API is in `backend/openapi/05b.yaml`.

## Contract (C7)

These are frozen with 05a; changes are additive only:
- streamable HTTP transport and `tools/list` discovery;
- `search_documents(query, kb_key, top_k)`;
- `get_schema(question?)`;
- `run_sql(sql, reason)`.

The API is in `backend/openapi/05a.yaml`.
