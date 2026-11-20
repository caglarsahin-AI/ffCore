# Installation guide (llmaas)

The main installation guide for the product default, `llmaas` (model at an external provider,
everything else inside the network). The closed-network profile gets its own guide on top of
this one (`docs/kurulum-kapali-ag.md`, 12-2; until then the server runbook of package 19).

> Status (package 12-1): this file has the egress proxy, TLS reverse proxy, preflight and
> troubleshooting sections. Prerequisites, first `up`, Langfuse init, first admin, backup,
> update and rollback arrive with 12-2. Every command below was run on a local test stack
> unless it says **not verified**.

## Preflight

Two settings choose what runs: `COMPOSE_PROFILES` (which optional services start) and
`COMPOSE_FILE` (which overlay files compose reads). Compose cannot derive them from
`DEPLOY_PROFILE`, so they stay explicit and a check refuses every incoherent pair. Run it on the
host before `docker compose up` (Python 3, standard library only):

```bash
python scripts/compose_preflight.py --env-file .env
```

It prints one `ok` line per check, or one `FAIL` line with the error code and the fix, and exits
1. Overlay files may be given with relative or absolute paths; an unquoted ` #` in `.env`
starts a comment, as in compose. `make smoke` runs the same check first. The rules:

| Error | Meaning |
|---|---|
| `profile_overlay_mismatch` | a profile with its own overlay (`ollama`, `egress`, `tls`) is on without its file in `COMPOSE_FILE`, or the reverse |
| `profile_backend_mismatch` | the `ollama` profile without `DEPLOY_PROFILE=airgap` and `INFERENCE_BACKEND=ollama` |
| `ollama_context_length_missing` | the `ollama` profile with an empty `OLLAMA_CONTEXT_LENGTH` |
| `unknown_profile` | a name in `COMPOSE_PROFILES` no compose file defines |
| `egress_requires_llmaas` | the `egress` profile in `airgap` |
| `egress_allowlist_empty` / `egress_allowlist_invalid` | the `egress` profile with an empty or malformed `EGRESS_ALLOWLIST` |
| `egress_ports_invalid` | an `EGRESS_ALLOWED_PORTS` entry outside 1-65535 |
| `egress_requires_tls` | the `egress` profile without the `tls` profile (below) |

Use a comma as the path separator so the same `.env` line works on every OS:

```
COMPOSE_PATH_SEPARATOR=,
COMPOSE_FILE=compose.yaml,deploy/docker-compose.egress.yml,deploy/docker-compose.tls.yml
COMPOSE_PROFILES=egress,tls
```

## Egress

With the `egress` profile the stack has one way out: a forward proxy (Squid,
`deploy/docker-compose.egress.yml`) that allows only the hosts in `EGRESS_ALLOWLIST`.

- The app network becomes `internal`: no container except the proxy can open a connection to
  the outside. A firewall rule on the host is not needed for that; the corporate firewall
  still gets the list below.
- LiteLLM sends provider calls through the proxy (`HTTP_PROXY`/`HTTPS_PROXY`). The proxy checks
  the destination host name against `EGRESS_ALLOWLIST` (exact name or `*.suffix`), allows only
  the ports in `EGRESS_ALLOWED_PORTS` (default `443`; each 1-65535), and refuses any
  destination that resolves to a non-global address (private, loopback, link-local, CGNAT,
  benchmark, reserved, multicast, IPv4-mapped IPv6), even an allowlisted one; the list is
  the backend's own check (`core/egress.py`), with the documentation ranges left out.
- Methods: TLS tunnels (`CONNECT`) and plain requests are both allowed to allowlisted hosts on
  the allowed ports. With the default port list that means 443 only; a CONNECT-only rule
  is FOLLOWUP-211.
- The proxy logs one line per request to `docker compose logs egress-proxy`: time, client,
  method, host and port, status, bytes. No path or query.
- **Known limit (FOLLOWUP-208):** the backend's own outbound calls do not use a proxy (they pin
  the address they checked). With the `egress` profile, remote MCP servers, OpenAPI tools,
  alert webhooks and external agents fail with a connection error; leave the profile off where
  those are needed until FOLLOWUP-208 lands. Model calls are not affected.
- Published ports do not reach the host on an internal network (measured, Docker 24), so the
  `egress` profile needs the `tls` profile as the way in; the preflight enforces it.

Typical `llmaas` list (only what is in use):

```
EGRESS_ALLOWLIST=api.anthropic.com,*.openai.azure.com
```

The firewall request for the network team, from the same setting:

```bash
python scripts/compose_preflight.py --env-file .env --egress-list
```

prints `<host> <port>/tcp` lines. The backend applies the same `EGRESS_ALLOWLIST` itself as a
second layer (`core/egress.py`).

## TLS reverse proxy

The session cookie is `Secure`, so the console needs HTTPS. The `tls` profile adds an nginx
reverse proxy (`deploy/docker-compose.tls.yml`, config `deploy/tls/nginx.conf`) with two
listeners:

| Listener | Host port | Serves |
|---|---|---|
| internal | `TLS_PORT` (443) | the console (`/`), the OpenAI-compatible API (`/v1/`), MCP servers (`/mcp/`) |
| public | `TLS_PUBLIC_BIND`:`TLS_PUBLIC_PORT` (127.0.0.1:8444) | only `/channels/teams/messages` (Teams, package 15), sent to the backend as that fixed path whatever the client wrote (`/x/../channels/teams/messages` arrives normalised); every other path is the proxy's own 404 |

Steps:

1. Get a certificate for the host name users open from the corporate CA. Put the full chain
   and the key into one directory as `fullchain.pem` and `privkey.pem`; set `TLS_CERT_DIR` to
   it. Nothing in FFCore creates or renews certificates.
2. Set `CONSOLE_ORIGINS=https://<host>` (the origin in the browser's address bar; with a port
   other than 443, include it).
3. Publish the backend and frontend on localhost only, so the proxy is the one way in:
   `BACKEND_PORT=127.0.0.1:8000`, `FRONTEND_PORT=127.0.0.1:3000`.
4. Add the overlay and the profile (preflight section), then `docker compose up -d --wait`.
5. Open the public listener only when Teams is set up: `TLS_PUBLIC_BIND=0.0.0.0` and route only
   that port from the network the Bot Framework traffic arrives from.

TLS 1.2 and 1.3 only; HSTS on both listeners; `server_tokens off`. Requests through the proxy
reach the backend from the proxy's address; the audit log records that address for them (the
same as for console requests through the frontend today).

## Troubleshooting

**`litellm_schema_incomplete` in `make smoke`, or LiteLLM stays unhealthy.** LiteLLM's first
start migrates its database; on a slow machine the migration can stop half-way and later starts
cannot take its lock (FOLLOWUP-82). The healthcheck and smoke ask `/key/info` for a key that
cannot exist: `404` means the key table is there, `500` means the schema is incomplete (the
500 and the unhealthy container were reproduced in review r1 by hiding the key table). Fix: stop
LiteLLM, drop and recreate its database, start it and wait for healthy (run on a test stack in
r2; a real half-migrated database was not produced):

```bash
docker compose stop litellm
docker compose exec postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "DROP DATABASE litellm" -c "CREATE DATABASE litellm"'
docker compose up -d --wait litellm
make render-litellm
```

`render-litellm` (run in the tools container: `docker compose run --rm tools make render-litellm`)
puts the models back from FFCore's tables; LiteLLM's database holds nothing else FFCore needs.

**`egress-proxy` exits at start.** `docker compose logs egress-proxy` names the reason: an empty
or malformed `EGRESS_ALLOWLIST` (scheme, port, path or an inner `*`), or a non-numeric
`EGRESS_ALLOWED_PORTS`.

**A provider call fails with 403 from the proxy.** The host is not in `EGRESS_ALLOWLIST`, or it
resolves to a private address. The proxy log line names the host.
