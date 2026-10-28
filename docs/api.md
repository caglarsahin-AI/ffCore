# FFCore backend API

Endpoint summary per package. Base path for application endpoints: `/api/v1` (03a onwards).

## Errors

Every 4xx response uses the OpenAI error shape:

```json
{"error": {"message": "Token audience mismatch.", "type": "permission_error", "code": "audience_mismatch"}}
```

`type` follows the status (`authentication_error` 401, `permission_error` 403, `not_found_error` 404,
`invalid_request_error` 400/422, `rate_limit_error` 429). Messages are English and never contain
secrets, tokens or request bodies.

## Identity (03b)

`resolve_actor()` is the only place a caller is identified (CONTRACTS C2). Credentials:

| Caller | How | Actor |
|---|---|---|
| Internal service account (mcp-search, workers) | `Authorization: Bearer <SERVICE_TOKEN>` | `system` / `service` |
| Service acting for a user | service account + `X-On-Behalf-Of: <token>` | `user` / token `sub` |
| User session | added by 03a | `user` |
| API key | added by 03c (`impersonate` scope may send `X-On-Behalf-Of`) | `api_key` |

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
The header is accepted only from a caller that may impersonate. From any other caller it is
ignored and an `impersonation_denied` audit event is written.

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
- Reading the trail (`GET /audit`, CSV export) comes with 03a.

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
`request()` takes only `method, url, headers, params, content, json`: redirect handling, transport,
proxy, TLS verification and timeouts cannot be changed per call (`TypeError`). The host rules run
again at connect time. Environment proxy variables are ignored. Errors name only scheme and host.
