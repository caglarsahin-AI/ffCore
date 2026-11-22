# Changes

Behaviour and configuration changes that a deployment or an API client notices, newest first
(handbook/RELEASE_AND_ROLLBACK.md, CHANGE_CONTROL.md). Each entry names the package and what to do,
if anything.

## 2026-11-22 · 14-1 · User memory (backend)

- **What:** a member's assistant remembers lasting facts about them (role, preferences, recurring
  context, explicit decisions) inside the organisation. After a completed run a background job
  (`llm-background` queue, model slot interactive-low) asks the `memory-extract` model for 0-3
  items; each passes the memory PII check (the project's PII categories plus person names,
  action `block`), the confidence threshold and dedupe (similarity > 0.9 supersedes and archives
  the old item). At the next run `prepare` adds the user's items to the system message (profile
  always, then `recall_top_k`, within `context_policy.memory_max_tokens`) and records
  `memory_used` (ids and kinds only). Memory is **off** by default; turning it on needs the
  installation's NER model. Screens and the user guide come with 14-2.
- **API (additive, `backend/openapi/14.yaml`):** `…/memories` (own items: list, "remember this",
  edit, delete, delete all), `…/memories/opt-out`, `…/memories/stats` and `…/memories/settings`
  (admin), and the worker's `/internal/memories/{recall,related,candidates}` (service account).
  New error codes: `memory_pii_blocked` (400), `memory_not_owner` (403), `memory_disabled`,
  `memory_opted_out` (409), `memory_requires_ner` (422), `memory_unavailable` (502, a run's
  recall failed).
- **Run events:** `llm_call.request_messages` shows the memory block as
  `[memory: n items <ids>]` (the text is the user's, analysts read run events); `budget` gains
  `memory` (`on`, `off`, `opt_out`, `no_user`) when the run has a user; the extraction outcome is a
  `progress` event `{"memory_extraction": {...}}` with ids and counts.
- **Migration:** `14_0001` creates `memories` (`embedding vector(EMBED_DIM)`), `memory_settings`
  and `memory_opt_outs` (no change to existing tables; `alembic downgrade 11_0001` removes them).
  Retention class `memory` now deletes items unused for `keep_days` (365) and expired ones.
- **Configuration:** `MEMORY_MIN_CONFIDENCE` (llmaas 0.6, airgap 0.7; `.env.example`). Langfuse
  prompt `memory_extract` (seed `backend/prompts/memory_extract.md`, `make seed-prompts`).
- **Action:** `make seed-prompts` once (adds `memory_extract`); the `migrate` service applies
  `14_0001` at `make up`. New `frontend/lib/api/schema-14.d.ts` for API clients.

## 2026-11-22 · followup-triage-2 · Readiness model window, e2e image and screenshots, hook comments

- **What:** `/readyz` `ollama_context` and `ollama_runtime_context` read each active Ollama
  model's `limits.context_window` (the field the console and the seed write) and check it even
  when no agent is published; before, they read a `context_tokens` key models never carry and
  were skipped without an agent (FOLLOWUP-219). Published agents' `limits.context_tokens` still
  count. The detail text says `largest needed context=N`.
- **Changed (tests and tooling, no API change):** the e2e service runs an image with the
  frontend's `node_modules` built in (`frontend/Dockerfile.e2e`, `ffcore/e2e:<FFCORE_VERSION>`);
  runs no longer call `npm ci` and do not reach the npm registry; a changed lock file stops the
  run with `e2e_deps_stale` (FOLLOWUP-220). Screenshots are written only when
  `E2E_SCREENSHOT_DIR` is set (FOLLOWUP-221). The agent hook reads `#` comments as comments and
  checks commands behind `timeout` (FOLLOWUP-214).
- **Action:** an install with `INFERENCE_BACKEND=ollama` whose `OLLAMA_CONTEXT_LENGTH` is below
  an active Ollama model's `context_window` now gets 503 `context_configuration_invalid` from
  `/readyz` (it was hidden before): raise `OLLAMA_CONTEXT_LENGTH` or lower the model's window in
  the console. An active Ollama model with no published agent while Ollama does not answer now
  gets 503 `ollama_unreachable` from `ollama_runtime_context` (it was `skipped`, 200 before):
  start Ollama or deactivate the model. e2e: build the image once per stack
  (`docker compose --profile e2e up --build --pull never --no-start --no-deps e2e`, docs/onyuz.md)
  and drop `npm ci &&` from `run e2e` commands.

## 2026-11-21 · 11-2 · Chat approval, question, rating and portal settings

- **What:** the chat (docs/chat.md) approves or rejects an action inline for a member with `edit`
  access and role >= the approver role, and says who approves to anyone else; it answers an
  agent's `ask_user` question; it rates an answer (helpful / not helpful, optional note). The
  console's agent screen gets a Portal tab: welcome text, up to three example questions and an
  accent colour, shown by the chat (docs/agentlar.md, "Chat portal settings").
- **API (additive):** `POST …/runs/{id}/feedback` takes `source` (`review`, the default and the
  old behaviour, or `chat`: the run's own user only, stored in `messages.user_feedback`, Langfuse
  score `user_feedback`). `PATCH …/agents/{id}` takes `portal_config`; `AgentOut`,
  `GET …/chat/agents` and the conversation messages (`user_feedback`) return the new fields.
- **Migration:** `11_0001` adds two nullable `jsonb` columns, `messages.user_feedback` and
  `agents.portal_config` (no data change; `alembic downgrade 12_0002` removes them).
- **Changed:** the console test panel's approval and answer texts moved to the shared
  `RunCards` messages; the panel looks and behaves as before.
- **Action:** none beyond the usual upgrade: the `migrate` service applies `11_0001` at `make up`. Regenerated
  `frontend/lib/api/schema-06a.d.ts` and `schema-06b.d.ts` for API clients that use them.

## 2026-11-20 · 11-1 · End user chat (`/chat`)

- **What:** the console serves `/chat` (docs/chat.md): the selected project's published agents,
  your own conversations, streamed answers with tool cards and source cards that open the cited
  passage, the "not found in the sources" badge, soft delete. A `user` member lands on `/chat`
  after sign-in. New 06a calls: `GET …/chat/agents`, `GET …/conversations`,
  `GET …/conversations/{id}/messages`, `DELETE …/conversations/{id}` (open in read-only access,
  audit `delete_conversation`), `GET …/runs/{id}/sources/{chunk_id}` (the caller's document ACL;
  `source_deleted`, `source_reindexed`, `source_not_visible`).
- **Changed:** a new conversation's title is the first 60 characters of its first message,
  whitespace collapsed (was 80). The console test panel's tool and source cards are the shared
  chat components; the panel looks and behaves as before.
- **Action:** none. Regenerated `frontend/lib/api/schema-06a.d.ts` for API clients that use it.

## 2026-11-20 · hook-egress-1 · Backend egress through the forward proxy, initdb role pair, agent guard in block mode

- **What:** with the `egress` profile the backend's own outbound calls (remote MCP servers,
  OpenAPI tools, alert webhooks, external agents) go through the forward proxy: `EGRESS_PROXY_URL` (new setting, `http://<host>:<port>` or empty; the egress
  overlay sets `http://egress-proxy:3128` for `backend`, `worker`, `agent-worker`,
  `agent-worker-bg`). The backend keeps its host rules and sends external hosts to the proxy by
  name; the proxy applies the address rules. A proxy refusal is the error code
  `egress_proxy_denied`; an invalid setting stops start-up with `egress_proxy_url_invalid`
  (FOLLOWUP-208).
- **What:** initdb (`deploy/postgres/initdb/20-app-role.sh`) also stops when `APP_DB_PASSWORD`
  is set without `APP_DB_USER`; the preflight's `db_role_owner` message asks for both settings
  (FOLLOWUP-213).
- **Not through the proxy:** SMTP alerts; under the `egress` profile they fail with a connection
  error (use a webhook alert channel).
- **What to do:** nothing for existing installations without the `egress` profile. With it,
  remove any workaround that kept the profile off for tools, webhooks or remote MCP servers
  (docs/kurulum.md "Egress").
- **Development only:** the agent guard (`.claude/settings.json`) runs in `block` mode; bare
  `docker build`/`buildx build` is refused like `compose build` (FOLLOWUP-210).

## 2026-11-20 · 12-2 · Least-privileged database role, backup and restore, vLLM overlay, installation guides

- **What:** the application can connect to Postgres as `ffcore_app`, a role without DDL
  (FOLLOWUP-46): initdb creates it from `APP_DB_PASSWORD` on a fresh volume
  (`deploy/postgres/app-role.sql` holds the grants and serves existing volumes); migration
  `12_0001` makes the audit partition functions run as the owner (SECURITY DEFINER, fixed
  `search_path`, no PUBLIC execute) and adds detach/drop functions that retention now uses;
  `12_0002` keeps partitions younger than 365 days out of their reach and leaves the role
  INSERT and SELECT only on the audit log.
  `deploy/backup.sh` and `deploy/restore.sh` (FFCore and Langfuse databases, knowledge storage,
  Qdrant volume, optional traces; counts and SHA-256 manifest; restore only onto fresh volumes).
  `deploy/docker-compose.vllm.yml` (profile `vllm`, GPU) with its image in
  `deploy/offline/images-vllm.txt`. `docs/kurulum.md` is the full `llmaas` guide,
  `docs/kurulum-kapali-ag.md` the closed-network one, `docs/donanim.md` the sizing page.
- **Changed:** application services read `DATABASE_URL` with `APP_DB_USER`/`APP_DB_PASSWORD`
  (owner when empty); `migrate` and `tools` keep the owner. `make smoke` (preflight) fails in
  `llmaas` when the application would connect as the owner (`db_role_owner`) and knows the
  `vllm` profile. The tools image has no apt layer of its own (FOLLOWUP-95; make and curl are in
  the base layer, so the runtime image carries them too); `UV_INDEX_URL`/`UV_FIND_LINKS` build
  arguments point uv at an internal mirror (`deploy/offline/wheels.sh`). `deploy/offline/save.sh`
  takes `IMAGES_TXT` like `verify.sh`.
- **Action:** `llmaas` installations: set `APP_DB_USER=ffcore_app` and `APP_DB_PASSWORD` (both or
  neither: `db_role_incomplete` otherwise, in every profile); on an existing volume run
  `deploy/postgres/app-role.sql` once and set the role's password (docs/kurulum.md, "Database
  role"), or `make smoke` fails. `airgap` installations may stay on the owner (smoke names it).
  Run the backup before updating.

## 2026-11-20 · 12-1 · Egress proxy and TLS reverse proxy overlays, compose preflight, LiteLLM schema health

- **What:** two optional overlays for `llmaas` (docs/kurulum.md): `egress` (Squid forward proxy;
  the app network becomes internal, LiteLLM's provider calls go through the proxy, which applies
  `EGRESS_ALLOWLIST` by host name and refuses private destinations) and `tls` (nginx; internal
  HTTPS listener for the console and API, public listener for `/channels/teams/messages` only).
  New `scripts/compose_preflight.py` (`make preflight`, `make egress-list`); `make smoke` runs it
  first. `docs/veri-isleme.md`, the data processing record template.
- **Changed:** LiteLLM's healthcheck and `make smoke` also ask `/key/info` with the master key; a
  half-migrated LiteLLM database (500) is now unhealthy instead of healthy (FOLLOWUP-82). `make
  smoke` fails on an incoherent `COMPOSE_PROFILES`/`COMPOSE_FILE` pair (FOLLOWUP-35) and on an
  unknown profile name. `deploy/offline/images.txt` lists the proxy and nginx images, so the
  offline archive (package 19) carries them too.
- **Review r1 (before merge):** the public listener sends the fixed Teams path to the backend,
  never the client's raw path; the proxy also refuses benchmark, reserved, unspecified and
  IPv4-mapped IPv6 destinations; `EGRESS_ALLOWED_PORTS` must be 1-65535 (preflight and proxy).
- **Known limit:** with the `egress` overlay the backend's own direct external calls (remote MCP
  servers, OpenAPI tools, alert webhooks, external agents) fail with a connection error until
  FOLLOWUP-208.
- **Action:** none for existing installations (both overlays are off unless added). An
  installation whose `COMPOSE_PROFILES` names a profile no compose file defines now fails smoke
  by name: remove the name.

## 2026-11-20 · triage-1 · Admin manages user-only documents, one audit row per refusal, no backend as provider or webhook

- **What:** a project admin (and a superadmin) gets, changes and deletes a knowledge base document
  readable by named users only through `GET`, `PATCH` and `DELETE …/documents/{id}` (it got 404
  before; FOLLOWUP-202). The document list, search and ingest report still hide it.
- **Changed:** a refusal inside a change endpoint (for example an analyst changing a document's
  ACL or renaming an external agent) writes one `denied` audit row, not two: the row of the
  change, with the resource it is about and the reason (`after.code`, `after.min_role`,
  `after.write`; FOLLOWUP-203). Refusals before the endpoint keep their `route` row. A provider
  `base_url`/`api_base`, an alert rule `webhook_url` and the default webhook URL that point at the
  backend itself (its `INTERNAL_API_URL` origin, the `backend` service name, loopback on port 8000)
  are refused with 400 `endpoint_is_platform` when saved, even when `ALLOWED_INTERNAL_HOSTS` lists
  the backend; the connection test answers `endpoint_is_platform`, LiteLLM reconcile skips such a
  model with that code and a webhook delivery fails with it (FOLLOWUP-194).
- **Action:** audit queries that counted two rows per refusal count one. A provider or webhook
  saved earlier with the backend's address stops working; give the target service's address.

## 2026-11-19 · 04b-2 · Scope filter, Turkish normalizer layer, video flag, threshold table, Ollama runtime context

- **What:** agent definitions accept `knowledge[].filter.scope` (document sources, exact match)
  and the search API takes a list as a metadata filter value (any of the values). Opt-in
  `TEXT_NORMALIZE_TR` (circumflex folding on silver and queries). `VIDEO_TRANSCRIPT_ENABLED`
  (stays `false`: this build has no transcriber) and the `video` reconversion preset. New
  `GET …/knowledge-bases/{kb_id}/query-stats` and the threshold table (docs/bilgi-tabani.md).
  `/readyz` adds `ollama_runtime_context` (Ollama `/api/ps`, not yet verified against the pinned
  image, ENV-204) and `ingest_queue`.
- **Changed:** Markdown uploads are read as written instead of through Docling (engine
  `markdown`, no weights needed; FOLLOWUP-87). Kapı 2 counts English function words too, so
  short English prose is no longer `no_prose` (FOLLOWUP-145). A search answers 409
  `normalizer_config_mismatch` while indexed documents are in another normalizer form than the
  setting gives. The internal key search applies `filters` (it ignored them before).
- **Action:** none by default. Switching `TEXT_NORMALIZE_TR` on needs `make reindex LAYER=silver
  FULL=1` per knowledge base; until then its searches answer 409. Do not set
  `VIDEO_TRANSCRIPT_ENABLED=true` (start-up stops with `video_transcriber_unavailable`). Markdown
  documents indexed before keep their Docling silver until a silver reindex.

## 2026-11-19 · 10c-3 · MCP servers screen and monitoring; exam summary fix

- **What:** the console gets the MCP servers screen (`/mcp-servers`, Build menu, developer and up;
  changes are a project admin's): publish an OpenAPI document or a remote MCP server, choose and
  rename its operations, publish or stop it, test the upstream, add it as a tool, and a
  Monitoring tab with the last 24 hours and the last calls (docs/onyuz.md "MCP servers").
- **Changed:** the tool form no longer offers the OpenAPI kind (the backend already refused it
  with `422 openapi_tool_via_mcp_server`); OpenAPI services go through MCP servers.
- **Fixed (09, FOLLOWUP-197):** a stored exam summary that is not an object at all (a bare number
  or `true`) made `GET /eval-runs/{id}` and the suite's exam list answer 500; it is now
  `summary: null` with the `eval_summary_invalid` warning, like any other summary that does not
  fit the contract.
- **Action:** none.

## 2026-11-19 · 04b-1 · migrate-vectors, ingest report, document ACL edit, reconversion presets

- **What:** `make migrate-vectors` copies a knowledge base's vectors between pgvector and Qdrant
  without re-embedding and exits 1 when the counts differ (docs/bilgi-tabani.md "Moving vectors
  between drivers"). New `GET …/knowledge-bases/{kb_id}/ingest-report`; `PATCH
  …/documents/{id}` takes `acl_roles`, `acl_users`, `acl_open` (project admin only); `POST …/reindex` takes `preset`
  (`make reconvert`); the search response adds `filtered` and `rerank_truncated` (additive).
- **Changed:** uploading identical bytes under the same name keeps the version (was version + 1;
  outcome `unchanged` as before, FOLLOWUP-157). Deleting a document or a knowledge base removes
  its silver and `.raw.md` files; raw stays (FOLLOWUP-133). Re-uploading under an existing
  name keeps the document's ACL when no ACL is sent (was reset to `analyst`); a different
  ACL is admin only (403), and a name whose document the caller cannot read is 409
  `document_name_taken` (admins exempt).
- **Schema:** migration `04b_0001` adds `chunks.sparse` (jsonb, nullable); the bge-m3 sparse
  weights are stored with every new chunk, so Qdrant reuses unchanged vectors at a gold reindex.
  Rows written before stay `NULL` until a gold reindex or `migrate-vectors … TO=qdrant`.
- **Action:** run the migration (`migrate` service, on every `up`). Nothing else; the vector
  driver changes only when the operator changes `VECTOR_BACKEND`.

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
- **Upstream safety (05b review r1):** OpenAPI path keys must start with one `/` and stay in the
  base path (`422 openapi_path_invalid` at upload); every call keeps the registered scheme, host
  and port (`upstream_origin_mismatch`) and refusals before a request are logged as `denied`.
- **New setting:** `MCP_UPSTREAM_MAX_BYTES` (default 1048576): the largest upstream answer a
  published OpenAPI server accepts.
- **Action:** run the migration (`migrate` service, on every `up`). Existing tools keep working.

## 2026-11-17 · 10c-2 · Governance screens; exam items endpoint; typed exam summary

- **What:** the console gets Overview, Usage, API keys, Quotas, Alerts (new menu item, with a
  header badge of open alerts) and Data retention screens on the existing 03c API. The exam API
  gets `GET /projects/{pid}/eval-runs/{id}/items` (paged item results, status filter) and
  `EvalRunOut.summary` is the typed `EvalSummary` in 09.yaml (same JSON as before). The run page
  keeps reading a run it could not read and says why; a run that is gone (404/410) stops it.
- **Why:** brief 10 (10c-2), FOLLOWUP-185 (the console showed only the 10 worst exam items),
  FOLLOWUP-192, FOLLOWUP-130 (the retention screen says the real run ignores `RETENTION_DRY_RUN`).
- **Action:** none. Data retention is in the menu only for superadmins (the API serves it only to
  them); API keys stay admin-only.

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
