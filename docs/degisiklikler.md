# Changes

Behaviour and configuration changes that a deployment or an API client notices, newest first
(handbook/RELEASE_AND_ROLLBACK.md, CHANGE_CONTROL.md). Each entry names the package and what to do,
if anything.

## 2026-11-17 · 05b · Published MCP servers at /mcp/{key}/

- **What:** an OpenAPI 3 document or a remote MCP server can be published as an MCP server of
  FFCore at `/mcp/<key>/` (new API `/api/v1/projects/{project_id}/mcp-servers`, tables
  `mcp_servers` and `mcp_server_calls`, migration `05b_0001`). Callers: the platform runtime,
  and with `access: token` API keys with the `tools_invoke` scope. Each call passes the request
  quota and the guardrail (`tool.pre`, `tool.post`) and is logged (docs/araclar.md "Publish an
  MCP server").
- **Changed:** registering a tool with `kind: openapi` is `422 openapi_tool_via_mcp_server` (was
  `201`, not callable): publish the document and add the server to the tools instead. A tool
  endpoint on the backend itself is `400 endpoint_is_platform` unless it is a published server's
  own `<INTERNAL_API_URL>/mcp/<key>/` with `forward_user` (FOLLOWUP-159).
- **New setting:** `MCP_UPSTREAM_MAX_BYTES` (default 1048576): the largest upstream answer a
  published OpenAPI server accepts.
- **Action:** run the migration (`migrate` service, on every `up`). Existing tools keep working.

## 2026-11-17 · fix/10b-sse-bekci · A silent run stream reconnects

- **What:** the console ends a run event stream (agent test panel) that sends nothing for 30 s,
  three backend keepalive intervals, and reconnects with `Last-Event-ID`; a failed read is
  treated the same way. While the stream reconnects, or after it is reported lost, the test panel
  reads the run with `GET /runs/{id}` every few seconds and shows the server status; a failed read
  is shown with its code and retried until the server answers or the run has ended. A start
  request that hangs for 30 s ends as lost without a run id (the run may exist: open it in Runs).
- **Why:** a half-open connection (backend restarted, a proxy dropping an idle socket) never
  closes, so the panel kept showing the run as live with no update (FOLLOWUP-188; the exam
  stream got the same watchdog in 10c-1).
- **Action:** none with the default `sse_keepalive_s` (10 s). The console expects a keepalive at
  least every 30 s: raising `SSE_KEEPALIVE_S` to 30 s or more makes quiet runs reconnect needlessly.

## 2026-11-16 · release · Version 0.1.0-m3 (M3 server rollout)

- **What:** the first named FFCore release is `0.1.0-m3`: git tag `0.1.0-m3` on `main` and
  `FFCORE_VERSION=0.1.0-m3` in `.env.example`. Image tags (`ffcore/backend`, `ffcore/frontend`,
  `ffcore/tools`) and the offline bundle (`deploy/offline/save.sh`) use the same value.
- **Why:** the PayCore M3 server runbook and Jenkins/Nexus plan need one version string for
  checkout, image build and `.env`; `0.0.0` was a placeholder.
- **Deployment:** set `FFCORE_VERSION=0.1.0-m3` in the server `.env`; check out tag `0.1.0-m3`
  before `docker compose build backend frontend`.

## 2026-11-16 · 10c-1 r2 · Event streams are not compressed or buffered

- **What:** every event stream (`text/event-stream`: 06a `POST /agents/{key}/runs`,
  `GET /runs/{id}/stream`, `POST /runs/{id}/resume`; 09 `GET /eval-runs/{id}/stream`) is sent
  with `Cache-Control: no-cache, no-transform` and `X-Accel-Buffering: no`. Before, the exam
  stream had only `no-cache` and the run streams `no-cache` + `X-Accel-Buffering: no`.
- **Why:** the console reaches the API through its Next.js proxy, which gzip-compresses
  responses and so held a live stream back until it ended: the exam page showed no progress
  until the exam was over. `no-transform` tells any proxy not to compress the stream.
- **Action:** none. A reverse proxy in front of the console that compresses or buffers responses
  must leave `text/event-stream` alone; if progress arrives in one piece at the end, check its
  compression and buffering settings for these paths.
