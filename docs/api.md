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
ignored and an `impersonation_denied` audit event is written. From an API key (03c) it fails
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

03a lives on Alembic branch `03a` (`03a_0001`). To roll back only this package:
`docker compose run --rm migrate alembic downgrade 03a@-1`. Do not use `03a@base`: it resolves to
the shared root `0001` and also drops 03b.

## API keys, quotas and usage (03c)

### API keys

`/api/v1/projects/{project_id}/api-keys`: `POST` (create), `GET` (own keys; `?all=true` all keys,
project admin), `GET /{key_id}`, `PATCH /{key_id}` (name, scopes, acl_role, allowed_cidrs,
expires_at), `POST /{key_id}/revoke`. Members from analyst up manage their own keys; a project
admin sees and revokes every key. A key is never deleted, only revoked.

- The raw key (`ffk_<8 hex>_<secret>`) is in the create response only, once. The database keeps
  its public prefix (`key_prefix`, shown in lists and audit) and its SHA-256.
- Clients send `Authorization: Bearer ffk_...`. Every request checks the key, `revoked_at`,
  `expires_at` and `allowed_cidrs` (empty: any address). A wrong, revoked or expired key, or a key
  of a deleted project: 401 `invalid_api_key`, the same answer whatever the reason. An address
  outside `allowed_cidrs`: 403 `ip_not_allowed`.
- More than `API_KEY_AUTH_FAILURES_PER_MIN` (20) wrong keys from one address in a minute: 429
  `too_many_auth_failures` for that address, valid keys included, until the minute ends. Audit
  `api_key_auth_rate_limited` (actor `system` / `anonymous`).
- `scopes` (CONTRACTS C2): `chat_direct`, `agents`, `impersonate`, `kb_search`, `tools_invoke`.
  Only a project admin grants `impersonate`, and a key with it needs `allowed_cidrs` (422
  `cidrs_required_for_impersonate`). `acl_role` (default `analyst`) is the role the key's own
  searches run under and never exceeds its creator's role (403 `scope_not_allowed`).
- With `impersonate`, the key sends `X-On-Behalf-Of` for a user of the key's own project; the user
  is then the actor (membership and ACL are the user's) and audit rows carry `via_key_id`.
- A key is not a console member: project routes answer it 403 `insufficient_role`. Keys are used
  on the facade (06b).
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

### Migrations

03c lives on Alembic branch `03c` (`03c_0001`: `api_keys`, `quotas`, `usage_daily`,
`audit_events.via_key_id`). Roll back: `docker compose run --rm migrate alembic downgrade 03c@-1`.

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

04a lives on Alembic branch `04a` (`04a_0001`, depends on `03a_0001`); roll back with
`alembic downgrade 04a@-1`. `chunks.embedding` is `vector(EMBED_DIM)` as read at migration time.
