# FFCore backend API

Endpoint summary per package. Base path for application endpoints: `/api/v1` (03a onwards).

## Errors

Every 4xx response uses the OpenAI error shape:

```json
{"error": {"message": "Token audience mismatch.", "type": "permission_error", "code": "audience_mismatch"}}
```

`type` follows the status (`authentication_error` 401, `permission_error` 403, `not_found_error` 404,
`invalid_request_error` 400/422, `rate_limit_error` 429). Messages are English and never contain
secrets, tokens or request bodies. A 422 from body validation is `validation_error` with the
field paths, except a coded refusal raised by a model check (e.g. an agent definition, C8): then
`code` is that refusal's code and the message names the field (FOLLOWUP-105).

## Identity (03b)

`resolve_actor()` is the only place a caller is identified (CONTRACTS C2). Credentials:

| Caller | How | Actor |
|---|---|---|
| Internal service account (mcp-search, workers) | `Authorization: Bearer <SERVICE_TOKEN>` | `system` / `service` |
| Service acting for a user | service account + `X-On-Behalf-Of: <token>` | `user` / token `sub` |
| User session | added by 03a | `user` |
| API key | `Authorization: Bearer ffk_...` (03c; `impersonate` scope may send `X-On-Behalf-Of`) | `api_key` |

No recognised credential: 401 `unauthenticated`.

### X-On-Behalf-Of token

HS256 JWT signed by the backend with `OBO_JWT_SECRET`; signed fresh for every service or tool call.

| Claim | Meaning |
|---|---|
| `sub` | user id |
| `project_id` | project the call runs in |
| `aud` | target service or tool key; the backend accepts only `OBO_AUDIENCE` (default `ffcore-backend`) |
| `iat`, `exp` | issued and expiry time; `exp - iat` at most 300 s |
| `jti` | random id |

Expired, malformed, unsigned or longer-lived tokens: 401 (`token_expired`, `invalid_token`,
`token_lifetime_exceeded`). Valid token for another audience: 403 `audience_mismatch`.
The header is accepted only from a caller that may impersonate. From the console session it is
ignored and an `impersonation_denied` audit event is written, at most one per caller, address and
minute (anyone can send the header; the same throttle as rate-limited keys). From an API key (03c) it fails
loud: a key without `impersonate`, or a key whose token names another project, gets 403
`impersonation_denied` (audited with the reason; the body names no project).

## Audit (03b)

Every mutation endpoint is wrapped with `@audited(action, resource_type, redact_fields=[...],
audit_payload=True)` and writes one `audit_events` row:

`id, ts, actor_type (user|api_key|system), actor_id, project_id, action, resource_type,
resource_id, outcome (success|denied|error), before, after, request_id, ip`.

- Keys containing `password`, `key`, `token` or `secret` (any depth, any case) and the listed
  `redact_fields` are stored as `***`. `audit_payload=False` stores the event without content.
- Success is written in the mutation's transaction; denied and error outcomes are written in their
  own transaction, so they survive the rollback. This covers failures anywhere in the managed
  transaction (before-state load, endpoint, flush, commit). If the audit event itself cannot be
  written, the request fails with `AuditWriteError`; it is never swallowed.
- The table is append-only: UPDATE, DELETE and TRUNCATE fail for every database role. Rows live in
  monthly partitions (`audit_events_YYYY_MM`, UTC); the backend creates this and next month's
  partition on startup. Retention (03c) removes whole months by dropping partitions.
- Reading the trail: `GET /api/v1/audit` and `GET /api/v1/audit.csv` (03a, below).

## Outbound calls (03b)

All outbound HTTP (webhooks, tool endpoints, MCP upstreams, channels, sources) goes through
`SafeOutboundClient` with a mandatory `EgressTimeout(connect, read, total)`.

| Setting | Effect |
|---|---|
| `ALLOWED_INTERNAL_HOSTS` | names or CIDRs that may resolve to private addresses |
| `OFFLINE=true` | every other host is refused (`egress_offline`) |
| `EGRESS_ALLOWLIST` | otherwise the host must match (exact or `*.suffix`); empty means none (`egress_not_allowlisted`) |

Loopback, private (RFC 1918, CGNAT, unique-local), link-local and other non-public addresses are
refused (`egress_private_address`). The check runs on the address that is dialed, at connect time,
so DNS rebinding cannot bypass it. Redirects are followed one hop at a time and checked again
(at most 5). A redirect to another origin (scheme, host or port differs, including https to http)
drops `Authorization`, `Proxy-Authorization`, `Cookie`, `X-Api-Key`, `X-On-Behalf-Of` and any
`*-token`, `*-key`, `*-secret` header, and logs a `redirect_cross_origin` event with the target
origin and the dropped header names (never values); same-origin redirects keep them.
The client is stateless: it stores no cookies and ignores `Set-Cookie`, so the only cookie sent
is the caller's own `Cookie` header, under the same origin rule.
`request()` takes only `method, url, headers, params, content, json`: redirect handling, transport,
proxy, TLS verification and timeouts cannot be changed per call (`TypeError`). The host rules run
again at connect time. Environment proxy variables are ignored. Errors name only scheme and host.

## Identity, projects, providers and models (03a)

The contract is `backend/openapi/03a.yaml`, rendered from the code
(`python -m ffcore.api.openapi_export > openapi/03a.yaml`; a contract test fails when it drifts).
Lists are `{"data": [...]}`. Changes after the draft are additive only.

PATCH bodies: an omitted field is left as it is. An explicit `null` is accepted only where the
schema says so (`UserUpdate.superadmin_access`, `ProjectUpdate.description`,
`ProviderUpdate.description`, `ModelUpdate.reasoning_default`) and clears the value; for every
other field `null` is a 422 `validation_error`.

### Sign-in and session

| Endpoint | Notes |
|---|---|
| `POST /auth/login` | email + password (argon2id). Sets `ffcore_session`: HttpOnly, SameSite=Strict, Secure, Path=/. Wrong email and wrong password give the same 401 `invalid_credentials` |
| `POST /auth/logout` | clears the cookie and revokes every session token of the user |
| `GET /auth/me` | `{user, role, access, memberships[]}` |
| `POST /auth/password` | own password; allowed in read-only access mode; revokes other sessions |

The cookie holds an HS256 token signed with `SECRET_KEY` (not `OBO_JWT_SECRET`), lifetime
`SESSION_TTL_S` (default 8 h). It carries the user's `token_version`; logout, password change,
deactivation and deletion bump it, so older tokens stop working at once.
`resolve_actor()` still decides who calls: the session is one registered credential resolver.

Cross-origin rule (C6): a cookie-authenticated `POST/PUT/PATCH/DELETE` is refused with 403
`cross_origin_forbidden` when `Sec-Fetch-Site` is `cross-site` or `same-site`, or when `Origin`
is not listed in `CONSOLE_ORIGINS`. There is no CORS middleware and no CSRF token; the console
reaches the backend from its own origin through the Next.js rewrite.

First superadmin (nobody can sign in on an empty installation; run once, by hand):

```bash
docker compose run --rm -T backend python -m ffcore.cli create-superadmin --email admin@example.org --full-name "Admin" --password-stdin < password.txt
```

The password is read from stdin, never from the command line. The command fails if the email
already exists. It writes a `user.create_superadmin` audit event with actor `system/cli`.

### Roles and access mode

Roles `user < analyst < developer < admin`; access mode `edit | read` per membership. In this
release only `admin` and `analyst` can be assigned (422 `role_reserved` for the others).
A superadmin (`users.is_superadmin`) acts as `admin` in every project with its own
`superadmin_access`.

| Scope | Who |
|---|---|
| Users, providers, provider drivers, project create/delete, unscoped audit | superadmin |
| Project read, members list, models list, readiness | project `analyst` or higher |
| Project update, members, models | project `admin` |
| Audit with `project_id` | that project's `admin` |
| Model catalog | any signed-in user |

A service calling on behalf of a user (`X-On-Behalf-Of`) is bounded by the token's project for
the whole call: the project list, memberships and `GET /auth/me` show only that project, only the
user's membership there counts (superadmin rights do not apply), and tenant administration
(users, providers, provider drivers, project create/delete, unscoped audit) or another project
gives 403 `obo_project_scope`.

Every mutation route depends on a role check with `write=True`, so `read` access gets 403
`read_only_access`; a member whose role is too low gets 403 `insufficient_role`. Both denials are
written to the audit trail before the response.

A project the caller cannot see answers exactly like a missing one: a caller who is not a member
(and is not a superadmin), a deleted project and an unknown id all get 404 `not_found_error`
`project_not_found` with the same body, on every `/projects/{project_id}/...` route. A project id
therefore confirms nothing to an outsider. The denial is still audited (`outcome=denied`,
`after.code=project_not_found`); the real reason is in `after.reason` (`not_member` or
`no_project`) and never in the response. Tenant-level routes (for example project delete) refuse
non-superadmins with 403 `insufficient_role` before any project lookup, the same answer for an
existing and a missing project. A CI test fails if a mutation route lacks the `write` check
(exceptions: login, logout, own password).

### Projects

`key` matches `^[a-z][a-z0-9-]{1,31}$`, is globally unique and can never change or be reused,
even after the project is deleted: it is part of every LiteLLM model name
`"<project_key>.<model_key>"` (CONTRACTS C1). Projects, users and models are soft deleted.

`GET /projects/{id}/readiness` returns `{passed, total, checks[]}` with three checks: an active
model provider is assigned, an active vector provider is assigned, the project has an active
admin member. (03c adds limits and alert rules.)

### Providers

Providers are tenant level and always assigned to at least one project. Drivers and their fields
(which are required and which are secret) are listed by `GET /provider-drivers`:
`ollama, vllm, anthropic, openai, azure_openai, bedrock, openai_compatible, local_flagembedding,
pgvector, qdrant, local_fs`.

The configuration is stored encrypted with `FERNET_KEY`; a value that does not decrypt is an
error, never an empty configuration. Secret fields are returned and audited as `"***"`; sending
`"***"` back in a PATCH keeps the stored value.

Connection test: `POST /providers/test` (unsaved configuration) and `POST /providers/{id}/test`
(stored). One listing call through `SafeOutboundClient`, so `OFFLINE`, `EGRESS_ALLOWLIST` and the
private-address rules apply. The result is `{supported, ok, code, message, latency_ms}`; a failed
test never blocks saving. `bedrock` (needs SigV4 signing), `pgvector`, `local_fs` and
`local_flagembedding` have no test and answer `supported: false`,
`code: connection_test_unsupported`.

A provider used by an active model cannot be deactivated, neither by `DELETE` nor by
`PATCH {"is_active": false}` (409 `provider_in_use`; deactivate or delete the models first), and it
cannot be removed from a project whose models use it.

### Models

Models belong to a project. The provider must be active, assigned to the project and serve the
category's domain (`embedding` for embedding models, `model` for the others). `upstream_api`
(`chat | responses`) is always chosen explicitly. The response carries `litellm_name`.

Embedding models: `embed_dim` is measured at registration through the provider driver's probe and
must equal `EMBED_DIM` (400 `embed_dim_mismatch`). Without a probe for that driver the model is
refused with 409 `embedding_probe_unavailable` (the in-process `local_flagembedding` probe comes
with 04a). Embedding models are not served through LiteLLM.

`GET /model-catalog?driver=&model_id=` reads the static catalog loaded from
`deploy/seed/model_catalog.yaml` by the `migrate` service. It lists only entries whose values can
be traced to a source (`source`, `as_of`); an empty result means "not in the catalog".

Catalog changes (providers, assignments, models) are delivered to registered listeners after the
transaction commits; package 01's reconciler is such a listener. Without one, each change is
logged as `catalog_change_unhandled`.

### Audit trail (read)

`GET /audit?project_id=&actor_id=&action=&resource_type=&outcome=&since=&until=&limit=&offset=`
returns newest first. `GET /audit.csv` takes the same filters and exports at most 10,000 rows
(400 `export_too_large` otherwise). Values are as stored (already masked); cells starting with
`=`, `+`, `-` or `@` are prefixed with `'`.

### Migrations

03a lives on Alembic branch `03a` (`03a_0001`). Since the package branches were merged into one
head (`57_0002`, FOLLOWUP-57), `03a@-1` is refused ("Ambiguous walk"); roll back with an explicit
revision: `docker compose run --rm migrate alembic downgrade <revision to keep>` removes everything
above it. Every other package depends on `03a_0001`, so removing it means going down to the shared
root `0001` (docs/gelistirme-ortami.md).

## API keys, quotas and usage (03c)

### API keys

`/api/v1/projects/{project_id}/api-keys`: `POST` (create), `GET` (own keys; `?all=true` all keys,
project admin), `GET /{key_id}`, `PATCH /{key_id}` (name, scopes, acl_role, allowed_cidrs,
expires_at), `POST /{key_id}/revoke`. Members from analyst up manage their own keys; a project
admin sees and revokes every key. A key is never deleted, only revoked. Creating, changing and revoking need the
user's own console session: a service or an impersonating key acting for the user gets 403
`requires_console_session`.

- The raw key (`ffk_<8 hex>_<secret>`) is in the create response only, once. The database keeps
  its public prefix (`key_prefix`, shown in lists and audit) and its SHA-256.
- Clients send `Authorization: Bearer ffk_...`. Every request checks the key, `revoked_at`,
  `expires_at` and `allowed_cidrs` (empty: any address). A wrong, revoked or expired key, or a key
  of a deleted project: 401 `invalid_api_key`, the same answer whatever the reason. An address
  outside `allowed_cidrs`: 403 `ip_not_allowed`.
- More than `API_KEY_AUTH_FAILURES_PER_MIN` (20) wrong keys from one address in a minute: 429
  `too_many_auth_failures` for that address, valid keys included, until the minute ends. Audit
  `api_key_auth_rate_limited` (actor `system` / `anonymous`) at most once per address and minute;
  the next minute's row says how many were held back (`blocked_in_previous_window`), and all
  addresses together write at most 100 such rows a minute (then one `audit_rate_capped`). Without
  Redis a key cannot be checked: 503 `auth_backend_unavailable`, nothing is written.
- `scopes` (CONTRACTS C2): `chat_direct`, `agents`, `impersonate`, `kb_search`, `tools_invoke`.
  Only a project admin grants `impersonate`, and a key with it needs `allowed_cidrs` (422
  `cidrs_required_for_impersonate`). `acl_role` (default `analyst`) is the role the key's own
  searches run under and never exceeds its creator's role (403 `scope_not_allowed`).
- With `impersonate`, the key sends `X-On-Behalf-Of` for a user of the key's own project; the user
  is then the actor (membership and ACL are the user's) and audit rows carry `via_key_id`.
- A key is not a console member: project routes answer it 403 `insufficient_role`. Keys are used
  on the facade (06b, below). Scopes in use there: `chat_direct` (direct model calls), `agents`
  (agent runs), `impersonate` (the `user` field and `X-On-Behalf-Of`). `kb_search` and
  `tools_invoke` have no consumer in 06b (05b's published MCP servers).
- `last_used_at` is written at most once per `API_KEY_LAST_USED_FLUSH_S` (60 s).

### Quotas

`/api/v1/projects/{project_id}/quotas`: `GET`, `POST`, `GET|PATCH|DELETE /{quota_id}`. Analyst
reads, project admin changes. One form:

| Field | Meaning |
|---|---|
| `scope_type`, `scope_id` | `project` (scope_id is the project), `api_key` (a key of the project) or `user` (a member). `group`, `model`, `provider` do not exist (no enforcer) |
| `windows` | `rpm`, `rph`, `rpd`, `rpm_month` calls per UTC minute/hour/day/month; `concurrent` calls in flight |
| `tokens` | `tpm`, `tpd`, `tpm_month` tokens per window; `max_input`, `max_output`, `max_total` per call |
| `budget` | `daily_usd`, `monthly_usd` |
| `action` | `block` refuses the call (`quota_exceeded`); `warn` lets it run and reports it |
| `is_active`, `activate_at`, `priority` | a quota counts from `activate_at` on |

Every applying quota is checked: the project's quota is a ceiling for each key and user in it.
Decisions come from Redis counters at call time (C20): calls are counted as they start (a refused
call counts nowhere), tokens and cost when they finish, so a budget is crossed by at most the call
that crossed it. Cost is `models.pricing` x tokens, the formula LiteLLM applies. A USD budget is
refused while an active model of the project has no price (422 `pricing_missing`, FOLLOWUP-69),
and a call under a budget on an unpriced model is refused too: it would count 0. Without Redis
the call is refused (`quota_unavailable`), never let through unlimited.

A console run whose model call is refused fails with `quota_exceeded`, `pricing_missing` or
`quota_unavailable` (docs/agentlar.md error codes). The facade answers 429 (06b).

### Usage

`GET /api/v1/projects/{project_id}/usage?date_from=&date_to=` (analyst; default the last 30 UTC
days, at most 400): `usage_daily` rows (day, model, API key, user, tokens, cost, requests) and
totals. A row is upserted when a model call finishes, once per LiteLLM call id (the brief's
"hourly sync from LiteLLM spend data" was replaced: LiteLLM's spend log carries neither the API
key nor a cost for streamed calls, K-03c-0008, DRIFT-124). `unpriced_requests` counts calls on a
model without a price; their cost is not in `cost_usd`. A row that could not be written is logged
`usage_write_failed` and counted in Redis (`ffcore:usage:write_failed`); the call is not affected.
Usage is reporting only: quotas never read it. LiteLLM is configured not to store prompt or answer
text in its spend log.

### Retention

Superadmin: `GET /api/v1/retention/policies`, `PUT /retention/policies/{data_class}` (`keep_days`,
optional `project_id` for a project override; outside the class's min/max: 422
`retention_out_of_range`), `DELETE /retention/policies/{data_class}/overrides/{override_project_id}`,
`POST /retention/dry-run` (counts), `POST /retention/run` (removes now), `GET /retention/runs`
(the removal record, append-only). The daily job (03:00 UTC, background worker) only counts while
`RETENTION_DRY_RUN=true` (the default). One pass at a time; per class the count is recorded, then
rows are removed in batches (`RETENTION_BATCH`) and what was removed is recorded; a failing class
is recorded `partial` and the other classes go on.

| Class | Default (min-max) days | What expires |
|---|---|---|
| `content` | 30 (1-90) | prompt and answer text of finished runs: `llm_call.request_messages`, `answer.text`, `question`, tool call and approval arguments, `runs.input/output`, conversation messages, approval arguments (their `args_hash` and the decision's audit row stay). **Conversation contents are cleared after 30 days.** Metrics, timing, outcome and source references stay |
| `jobs` | 90 (30-365) | every event of terminal runs (the run row stays; waiting runs never) |
| `telemetry` | 90 (30-400) | `guardrail_events`, `kb_queries` |
| `alerts` | 180 (90-730) | `alerts` |
| `usage` | 760 (400-1095) | `usage_daily` |
| `audit` | 365 (365-3650) | whole monthly `audit_events` partitions older than max(keep_days, 365) days, only when `RETENTION_AUDIT_DROP_ENABLED=true` too: detached, recorded (rows, first/last time, SHA-256), then dropped and audited (`audit_partition_dropped`). 365 days is a floor in code |
| `traces` | 30 (7-180) | Langfuse keeps its own traces; reported `external:langfuse`. Set Langfuse's own retention in its project settings to match |
| `metrics`, `results`, `memory` | | no table yet (09, 14); reported `none` |

Deleting a document (or its knowledge base) clears at once the text of every finished run that
showed it as a source (FOLLOWUP-119); runs still going end `source_deleted` (FOLLOWUP-116) and are
cleared within a minute after.

### Alerts and notifications

Rules: `/api/v1/projects/{project_id}/alert-rules` (analyst reads, admin changes) and
`/api/v1/alert-rules` for the installation (superadmin). `kind`, `channel` (`ui`, `email`,
`webhook`), `recipients`, `params` (`thresholds` for budget_threshold, default 50/80/100;
`webhook_url`). `GET /api/v1/alert-kinds` lists the kinds something emits today: budget_threshold,
service_down, quota_warn, approval_pending_age, checkpoint_purge_overdue; any other kind is 422
`alert_kind_unavailable`. Alerts: `GET .../alerts`, `GET .../alerts/count` (open), `POST
.../alerts/{id}/ack`. An alert fires once per rule and condition (budget: per month and
threshold; service_down: per outage; quota_warn: per quota, window and day). Delivery status is in
`payload.delivery`; a failed delivery is logged `alert_delivery_failed`, never silent.

The evaluator runs every minute in the background worker: `budget_threshold` compares the month's
`usage_daily` cost with the project's `monthly_usd` quota; `service_down` fires when the API's
`/readyz` has failed for `ALERT_SERVICE_DOWN_S` (300 s).

Notification settings: `GET|PUT /api/v1/projects/{project_id}/notification-settings` (admin) and
`/api/v1/notification-settings` (installation, superadmin): `smtp` (`host`, `port` 25/465/587,
`username`, `password`, `starttls`), `default_webhook_url`, `from_address`. The SMTP password is
stored encrypted and answered `"***"` (sending `"***"` keeps it). `POST .../notifications/test`
sends a test mail or webhook (422 `notification_failed` with the delivery code). The mail server
passes the same outbound rules as HTTP (OFFLINE, EGRESS_ALLOWLIST, no private address unless in
ALLOWED_INTERNAL_HOSTS) and the connection dials the checked address; webhooks use the safe
outbound client.

### Readiness

`GET /api/v1/projects/{project_id}/readiness` has five checks: model provider, vector provider,
project admin, `limits` (an active quota), `alert_rules` (an active rule of the project or the
installation).

### Migrations

03c lives on Alembic branch `03c` (`03c_0001`: `api_keys`, `quotas`, `usage_daily`,
`audit_events.via_key_id`; `03c_0002`: `retention_policies`, `retention_runs`, `alert_rules`,
`alerts`, `notification_settings`, `runs.content_cleared_at`). Roll back `03c_0002` only: `docker compose run --rm migrate alembic downgrade 03c_0001` (an explicit revision; `03c@-1` is refused since the merge, FOLLOWUP-57).

## Knowledge bases (04a)

The contract is `backend/openapi/04a.yaml` (`python -m ffcore.api.openapi_export 04a >
openapi/04a.yaml`; contract test `test_04a_20_*`). Lists are `{"data": [...]}`. Prefix:
`/api/v1/projects/{project_id}/knowledge-bases`.

| Endpoint | Role | Notes |
|---|---|---|
| `GET ""`, `GET /{kb_id}` | analyst | counts of documents and chunks; `chunk_max_tokens` is derived (1.5 × `chunk_size`) |
| `POST ""`, `PATCH /{kb_id}`, `DELETE /{kb_id}` | admin + edit | one embedding model per installation: `embed_model`/`embed_dim` other than `EMBED_MODEL`/`EMBED_DIM` is 400 `embed_model_mismatch` / `embed_dim_mismatch`; `chunk_overlap` other than 0 is 422 `chunk_overlap_unsupported` |
| `POST /{kb_id}/documents` | analyst + edit | multipart, several `files`; 202 with `outcome` per file: `created`, `new_version` (same file name, new content), `unchanged` (same bytes: version + 1, nothing queued; an ACL change still reaches the vector store). A request over `UPLOAD_MAX_REQUEST_BYTES` is 413 `request_too_large` before the body is read. Optional `updated_at_source` (ISO 8601) is the source date of every file of the request; omitted, it stays unknown (`null`), never the upload time (FOLLOWUP-101) |
| `GET /{kb_id}/documents`, `GET …/{document_id}` | analyst | status, the three gate decisions with reasons, converter and seconds, `updated_at_source` |
| `PATCH …/{document_id}` | analyst + edit | `{updated_at_source}`: the source date (ISO 8601, `null` clears it); takes effect in search at once; audited as `update_document`, readable to the caller or 404 |
| `DELETE …/{document_id}` | analyst + edit | the document leaves search at once; raw stays on disk |
| `POST /{kb_id}/reindex` | analyst + edit | `{layer: silver or gold, full}`; gold never reads raw or the source |
| `POST /{kb_id}/search` | analyst, also in read mode | `{query, top_k?, filters{document_ids, metadata}, hybrid?}`; header `X-Run-Id` is stored in `kb_queries.run_id` |
| `POST /{kb_id}/test-query` | analyst, also in read mode | the same search, logged with `source=playground` |
| `POST /internal/embed` | service account only | for the ingest worker; 403 `service_account_required` for anybody else |
| `GET /readyz` | none | 200 ready; 503 `warming`, `warmup_failed`, `embed_dim_mismatch`, `context_configuration_invalid`, `vector_store_unavailable` |

Document ACL: `acl_roles` and `acl_users`. A manual upload without either gets `["analyst"]`
(shown in the response). An empty ACL (open to every member of the project, C15) is only set on
purpose with `acl_open=true`. A search sees documents whose ACL is empty, or names the caller's
role or a role below it, or names the caller; through `X-On-Behalf-Of` the caller is the end user
and the call is limited to the token's project.

Search response: hits newest source first with `age_days`, each with `embed_score` and
`rerank_score`; `threshold_mode` says which single threshold applied (`rerank_floor` with the
reranker on, `min_score` with it off) and `filtered_by_*` how many candidates it removed.

04a lives on Alembic branch `04a` (`04a_0001`, depends on `03a_0001`); roll back with an explicit
revision (`alembic downgrade <revision to keep>`; `04a@-1` is refused since the merge,
FOLLOWUP-57, docs/gelistirme-ortami.md). `chunks.embedding` is `vector(EMBED_DIM)` as read at migration time.

## OpenAI-compatible facade (06b, contract C11)

The one public entry for model calls. An OpenAI client changes only its base URL
(`https://<ffcore>/v1`) and API key (`Authorization: Bearer ffk_...`); LiteLLM stays on the
internal network and is called with one internal key. Machine-readable draft:
`backend/openapi/06b.yaml`.

### Routes

- `POST /v1/chat/completions`: OpenAI chat completions, `stream: true` for server-sent events
  (OpenAI `chat.completion.chunk`, ending with `data: [DONE]`; `: keepalive` comment lines while a
  run produces nothing).
- `GET /v1/models`: the key's own project only: its active chat models as
  `<project_key>.<model_key>` (scope `chat_direct`) and its published agents as
  `agent:<project_key>/<agent_key>` (scope `agents`), external agents included once published.

### Choosing the target

| `model` | Path | Scope |
|---|---|---|
| `<project_key>.<model_key>`, or the short `<model_key>` | direct model call through LiteLLM | `chat_direct` |
| `agent:<project_key>/<agent_key>` | a run of the agent's published version | `agents` |

The scope is checked before anything is looked up (403 `scope_missing`), so a key learns nothing
about targets outside its scopes. Another project's model or agent, or a missing one: 404
`model_not_found`. An agent that is not published: 404 `agent_not_published`. An external agent
(`kind: external`) has its own path (below).

### Who acts

- The key itself by default: runs carry `api_key_id` and no `user_id`; the key's `acl_role` (and
  every role below it) decides which documents its runs find; audit rows show `actor_type=api_key`.
- With the `impersonate` scope, the OpenAI `user` field (an e-mail) or `X-On-Behalf-Of` names a
  member of the key's project: that user acts (membership role and ACL), rows carry `via_key_id`.
  An unknown e-mail, an inactive user and a non-member all get the same `403
  impersonation_denied`, byte for byte; the reason (`user_not_mapped`, `not_member`) is only in
  the audit row. Without the scope the `user` field is a log label only and the refusal is
  audited (`reason: scope_missing`, at most once per key, address and minute).
- A console session or the service token is not a facade caller: 401 `api_key_required`.

### Direct model path

- Only these OpenAI parameters pass to LiteLLM: `temperature, top_p, max_tokens,
  max_completion_tokens, stop, presence_penalty, frequency_penalty, seed, response_format, tools,
  tool_choice, logit_bias` (plus `stream`, `user`, `n=1`). Anything else: 400
  `unsupported_field` (LiteLLM reads provider settings from the body; nothing is passed or
  dropped silently).
- Numbers are strictly typed, in OpenAI's ranges: `temperature` 0-2, `top_p` 0-1,
  `presence_penalty` and `frequency_penalty` -2 to 2 (numbers); `max_tokens` and
  `max_completion_tokens` at least 1, `seed` (integers); `n` only 1; `true`/`false` is not a
  number; `logit_bias` maps token ids to numbers. Otherwise 400 `invalid_parameter` with OpenAI's
  `param` naming the field; the value is not echoed and never reaches the model.
- Messages carry OpenAI's fields only: `role, content, name, tool_calls, tool_call_id`; any other
  message field: 400 `unsupported_field`. An earlier answer sent back as an SDK returned it may
  keep `annotations`, `refusal` and `audio` on its assistant message: they are left out of what
  the model sees and recorded by name (`dropped_fields`: in the run's `start_run` audit row on the
  agent path, in the backend log on the direct path). Content parts must be text (400 `content_type_not_supported`: a guardrail
  cannot check images).
- The `user` field is never passed on: LiteLLM (and the provider) see the acting user's id or
  `api_key:<key id>`, not the client's label.
- Guardrails (the project's `default` policy, 08): `input.pre` on system, developer, user and tool
  messages; `egress` on every text field that leaves (llmaas; `GUARDRAIL_EGRESS_ENABLED`): message
  content, `name`, `tool_call_id` and earlier `tool_calls`, and the `stop`, `tools`, `tool_choice`
  and `response_format` parameters (strings inside them; their structure is kept); `output.pre` on
  the answer and on returned `tool_calls` arguments. A block: 400 `guardrail_blocked` (reference in
  the message). When a rule that checks output is in enforce mode (its own mode, or the policy's
  when it has none), the answer is held until `output.pre` has seen it: the stream starts with
  `x_platform: {"event": "progress", "kind": "output_buffered"}` and the checked answer comes in one
  piece, so the first token is later; a held answer over 1 MB is cut off with
  `output_buffer_exceeded`. A request's tokenized values share one token scope (`facade-<uuid>`).
- Personal data tokenized at `egress` stays a placeholder (`<<PII_n>>`) in the answer: placeholders
  are not turned back into the values until 08's full release (C17, permission-bound). This is the
  safe side; the agent path behaves the same.
- The client's own tools: definitions pass, the model's `tool_calls` come back with OpenAI's
  meaning. The client runs them; they are not platform tools and do not go through the approval
  queue (07).
- Quota (03c): the project and key quotas apply per call; a blocking quota answers 429
  `quota_exceeded`, a USD budget on an unpriced model 409 `pricing_missing`, no Redis 503
  `quota_unavailable`. The call is counted once per LiteLLM call id in `usage_daily` with the key.
- LiteLLM's configured `chat-fallback` may answer; the response then carries
  `x_platform: {"event": "fallback", ...}`. No other fallback.

### Agent path

- A run of the published version with `channel=api`, `trigger_type=api`; the response headers
  carry `X-Run-Id` and `X-Conversation-Id`.
- The request parameters are checked as on the direct path (unknown field 400
  `unsupported_field`, wrong type or range 400 `invalid_parameter`), before any run starts. Valid
  values do not change the run: the agent's definition sets its model and settings.
- Context: without `X-Conversation-Id` each request is a new conversation; earlier `user` and
  `assistant` messages become its history after `input.pre` and `egress`, the last message must be
  the user's question. With `X-Conversation-Id` (the caller's own conversation) send only the new
  question (400 `conversation_history_conflict` otherwise). `system`, `developer` and `tool`
  messages are refused (400 `role_not_supported`): the agent's own instructions govern.
- Chunks: tokens as `delta.content`; each tool call, tool result, sources list, progress and
  fallback as one chunk with `x_platform: {"event": ..., ...}` (tool arguments as `tool.pre` left
  them, never raw); sources also as `annotations[]` (`url_citation`, URL
  `ffcore://knowledge-bases/<kb>/documents/<id>#page=<n>`, one per `[n]` marker in the answer) on
  the last chunk; the last chunk carries `usage`. `X-Agent-Events: none` sends text and
  annotations only.
- Approval: a run waiting for a person ends the stream with `finish_reason: "approval_required"` and
  `x_platform: {"event": "approval_required", "run_id", "approval_id", "expires_at", ...}` (with
  `X-Agent-Events: none` only these ids, never the action's arguments). The client cannot approve:
  a person decides in the console. Then `X-Resume-Run-Id: <run id>` on the same route follows the
  run from where it stopped (409 `run_still_waiting` before the decision; 404 `run_not_found` for
  another caller's run). A run belongs to its actor: a key's own run to that key, a user's run
  (through `impersonate`) to that user, so another key acting for the same user may follow it.
- A question to the user (`ask_user`) ends with `finish_reason: "stop"` and
  `x_platform: {"event": "question", ...}`; answering it is a console action for now.
- Errors: non-streaming requests get the HTTP status (400 `guardrail_blocked`, 429
  `quota_exceeded`, 502 with the run's code); once a stream has started, the error is an event
  `data: {"error": {"message", "type", "code"}}` followed by `data: [DONE]`.

### External agent path (06b-2)

An external agent (`kind: external`) is an OpenAI-compatible agent elsewhere, registered by a
project administrator and called through the same `agent:<project_key>/<agent_key>` name.

- Registration (admin + edit, audited, routes in `backend/openapi/06b.yaml`, tag
  `agent-external`): `POST /api/v1/projects/{id}/agents/external` (`key, name, description,
  base_url, model, api_key`) creates a draft; `GET`/`PUT .../agents/{agent_id}/external` reads or
  changes the endpoint (omitted fields stay; `kind` never changes, 422);
  `POST .../agents/{agent_id}/external/publish` publishes it (no versions; 409
  `external_agent_not_configured` without an endpoint). The `api_key` is stored with Fernet and is
  never returned (`***`), never in an audit row, never in a manifest. Version, rollback and
  manifest routes refuse an external agent (409 `external_agent_has_no_versions`, 422
  `external_agent_not_available`); the console's `POST .../agents` cannot create one (422).
- The base URL passes the egress policy at registration, update and publish (422
  `external_agent_url_refused` with the reason code): `http`/`https` only, no credentials in the URL,
  no query or fragment (422 `base_url_query_not_allowed`), a valid port, host in `EGRESS_ALLOWLIST` (or `ALLOWED_INTERNAL_HOSTS`), `OFFLINE=true` refuses
  every other host, and every resolved address must be public unless the host is internal. The
  platform's own services are never a target, even when internal (422
  `external_agent_host_reserved`): every compose service name (`litellm`, `langfuse-*`, `mcp-*`,
  `ollama`, `backend`, ...; `RESERVED_HOSTS` in `services/facade_external.py`),
  `host.docker.internal`, the hosts of `LITELLM_URL` and `LANGFUSE_HOST`, and a loopback address
  on the backend's own port; other internal hosts stay valid targets. The same egress check runs
  again at every connection (a name that resolves to a private address at call time is refused at
  the dial). Redirects are not followed: a 3xx answer is a failure (audit reason
  `egress_too_many_redirects`).
- The call is one non-streaming `POST <base_url>/chat/completions` with the registered `model`,
  the client's `user`/`assistant` messages and its numeric parameters and `stop`; only the
  registered key is sent (`Authorization: Bearer`): no user identity, no `X-On-Behalf-Of`, none of
  the client's headers. `system`, `developer`, `tool` roles, `tool_calls`, `tools`, `tool_choice`,
  `response_format`, `logit_bias` are refused (400). Messages pass `input.pre` (user) and
  `egress` (all) under the project's `default` policy.
- The answer is untrusted text: only `choices[0].message.content` is taken; `tool_calls`,
  `function_call` and any other field are never executed or turned into text (their names are
  logged). The text passes `output.pre` (a block: 400 `guardrail_blocked`). A placeholder-like
  string in it (`<<PII_n>>`) is not one of this request's tokens and stays as it is.
- Limits: the whole call within `LLM_CALL_TIMEOUT_S` (504 `external_agent_timeout`), the answer
  at most 64 KiB (502 `external_agent_response_too_large`; nothing partial is sent); a refused
  address, an error status, a non-JSON or empty answer: 502 `external_agent_failed` (the reason is
  in the audit row, the upstream body is never echoed).
- Streaming: the answer comes whole, so the stream sends `x_platform: {"event": "progress",
  "kind": "output_buffered"}`, `: keepalive` lines while waiting, the checked text in one chunk, a
  finish chunk and `data: [DONE]`. The external agent's `x_platform` events are frozen as
  `EXTERNAL_X_PLATFORM_EVENTS = ("progress",)`.
- Record: the call is not a run (no `runs` row, no Langfuse trace: it does not go through
  LiteLLM). Each call writes one audit row `external_agent_call` (actor, agent, host, upstream
  status or error code, duration, answer bytes; never content) and the guardrail events (source
  `api`). It is not counted in token or USD quotas (the cost is the other party's; request and
  concurrency windows are FOLLOWUP-144); the key's `agents` scope, allowed CIDRs, the timeout and the
  size limit bound it.

### Internal

`POST /internal/knowledge-bases/{kb_id}/key-search` (service token only): the worker's search for a
run whose actor is a key. The body names the key, project and run; the role is read from the key
row (revoked, expired, project and the run's own key checked again; 403 `api_key_not_valid`), any
role in the body is ignored.
