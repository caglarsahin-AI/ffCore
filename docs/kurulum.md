# Installation guide (llmaas)

The main installation guide for the product default, `llmaas` (model at an external provider,
everything else inside the network). The closed-network profile (`airgap`) has its own guide
on top of this one: [kurulum-kapali-ag.md](kurulum-kapali-ag.md).

Every command below was run on a local test stack (package 12) unless it says **not verified**.
Commands run from the FFCore checkout on the server, where `.env` is.

## Prerequisites

- A Linux server with Docker Engine and Docker Compose v2 (`docker compose version`; tested
  with 2.23). Sizing: [donanim.md](donanim.md). `llmaas` runs no model locally.
- The FFCore release checkout (git tag = `FFCORE_VERSION`) and its images, from the internal
  registry (`REGISTRY_PREFIX`) or the offline archive (package 19, `deploy/offline/`).
- For `llmaas`: a contract with the model provider, its API key, and the outbound hosts
  approved by the network team ([veri-isleme.md](veri-isleme.md), "Egress" below).
- A TLS certificate for the host name users open ("TLS reverse proxy" below).

## Settings (`.env`)

```bash
cp .env.example .env
```

Only the person installing FFCore fills in `.env`; nothing in FFCore writes it. Every empty
secret is mandatory: compose stops and names the missing variable. For `llmaas`:

| Setting | Value |
|---|---|
| `DEPLOY_PROFILE` | `llmaas` |
| `OFFLINE` | `false` |
| `REGISTRY_PREFIX`, `FFCORE_VERSION` | the internal registry (ending with `/`) and the release |
| `POSTGRES_PASSWORD`, `REDIS_PASSWORD`, `SERVICE_TOKEN`, `OBO_JWT_SECRET`, `SECRET_KEY`, `FERNET_KEY`, `LITELLM_*`, `LANGFUSE_*` | new random values (`.env.example` says how to make each) |
| `APP_DB_USER`, `APP_DB_PASSWORD` | `ffcore_app` and a new random value, always together: the application connects as `ffcore_app`, a role without DDL ("Database role"); one without the other stops the preflight (`db_role_incomplete`) |
| `EGRESS_ALLOWLIST` | the provider hosts, for example `api.anthropic.com` |
| `CONSOLE_ORIGINS` | `https://<host>` |
| `COMPOSE_PATH_SEPARATOR`, `COMPOSE_FILE`, `COMPOSE_PROFILES` | `,` / `compose.yaml,deploy/docker-compose.egress.yml,deploy/docker-compose.tls.yml` / `egress,tls` |
| `TLS_CERT_DIR` | the certificate directory |
| `LOCAL_LOGIN`, `LDAP_*` | optional: directory sign-in for the organisation's users (`docs/kimlik.md`); with a directory `LOCAL_LOGIN=superadmin_only` |

Langfuse's first install keys and admin password (printed once, copy them into `.env`):

```bash
docker compose run --rm tools make langfuse-init
```

Then check the settings before the first start:

```bash
python scripts/compose_preflight.py --env-file .env
```

## First start

```bash
docker compose up -d --wait
```

The first start takes minutes (LiteLLM and Langfuse migrate their databases; `migrate` runs
FFCore's schema and loads the model catalog). `--wait` returns when every healthcheck is green.

First superadmin (the password is read from standard input, never from a file or argument):

```bash
docker compose run --rm -T tools sh -c 'cd backend && python -m ffcore.cli create-superadmin --email admin@example.org --full-name "FFCore admin" --password-stdin'
```

Platform prompts into Langfuse, once:

```bash
docker compose run --rm tools make seed-prompts
```

Providers and models: in the console (Providers, Models), or for the first project from
`deploy/seed/models.llmaas.yaml` with the provider key given once in the shell:

```bash
docker compose run --rm -e SEED_ANTHROPIC_API_KEY tools make seed-models PROJECT=<project_key>
```

**not verified** (needs a provider key). Key rotation: enter the new key on the provider in
the console (Providers → edit); LiteLLM gets it at once (no restart); revoke the old key at the
provider afterwards.

## Health check

```bash
docker compose run --rm tools make smoke
docker compose exec backend curl -sS -w '\nHTTP %{http_code}\n' http://localhost:8000/readyz
```

`/readyz` answers 200 when every dependency and model weight is there, 503 with the failing
check named otherwise (a stack without `make models` weights answers 503). Smoke runs the
preflight, then checks the backend, LiteLLM (with its schema), Langfuse with the
project keys and the MCP servers; every line is `ok` or `FAIL` with the reason.

## Database role

New installations: set `APP_DB_USER=ffcore_app` and `APP_DB_PASSWORD` before the first start (both
or neither; initdb stops on a user without a password); the role is created with the
volume. An existing installation (volume created before 12):

```bash
docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < deploy/postgres/app-role.sql
docker compose exec postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\password ffcore_app"'
```

then put `APP_DB_USER=ffcore_app` and the same password into `.env` and `docker compose up -d
--wait`. The role has INSERT and SELECT only on the audit log; audit partitions younger than 365
days cannot be detached or dropped, not even through the owner's functions it may call. The role
reads and writes rows only; audit partitions go through the owner's functions (migration
12_0001); migrations and `tools` keep the owner.

## Backup

```bash
deploy/backup.sh --out /backup/ffcore-$(date +%F)
```

The FFCore and Langfuse databases, the knowledge storage, the Qdrant volume when that service
runs; `--with-traces` adds Langfuse's ClickHouse and MinIO (Langfuse stops meanwhile). The
LiteLLM database, the demo database, Redis and model weights are rebuilt, not backed up. The
databases and the files are copied one after the other from a running stack: take the backup
when traffic is low, and stop `backend` and `worker` first when the copy must match exactly (an
upload during the backup can leave a file without its row or the reverse). Keep
the backup like the server: it holds encrypted credentials and documents.

Restore onto fresh volumes (refused otherwise):

```bash
docker compose down -v
deploy/restore.sh --from /backup/ffcore-<date>
```

The script compares row and file counts with the backup before it starts the stack.

## Update

1. Back up (above).
2. Check out the new release tag, set `FFCORE_VERSION` to it, read `docs/degisiklikler.md`
   for the entries since your version.
3. `python scripts/compose_preflight.py --env-file .env`, then `docker compose up -d --wait`
   (`migrate` applies the new schema first; the backend does not start if it fails).
4. `docker compose run --rm tools make smoke`.

## Rollback

Schema first, then the release: `docker compose run --rm migrate alembic downgrade <revision of
the previous release>` (an explicit revision; docs/gelistirme-ortami.md), set `FFCORE_VERSION`
back, `docker compose up -d --wait`. If the schema cannot go back, restore the backup taken
before the update. **not verified** end to end (needs two releases).


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
| `profile_overlay_mismatch` | a profile with its own overlay (`ollama`, `vllm`, `egress`, `tls`) is on without its file in `COMPOSE_FILE`, or the reverse |
| `profile_backend_mismatch` | the `ollama` (or `vllm`) profile without `DEPLOY_PROFILE=airgap` and the matching `INFERENCE_BACKEND` |
| `ollama_context_length_missing` | the `ollama` profile with an empty `OLLAMA_CONTEXT_LENGTH` |
| `unknown_profile` | a name in `COMPOSE_PROFILES` no compose file defines |
| `egress_requires_llmaas` | the `egress` profile in `airgap` |
| `egress_allowlist_empty` / `egress_allowlist_invalid` | the `egress` profile with an empty or malformed `EGRESS_ALLOWLIST` |
| `egress_ports_invalid` | an `EGRESS_ALLOWED_PORTS` entry outside 1-65535 |
| `egress_requires_tls` | the `egress` profile without the `tls` profile (below) |
| `db_role_owner` | `llmaas` with empty `APP_DB_USER`/`APP_DB_PASSWORD`: the application would connect as the owner ("Database role"); `airgap` only names it |
| `db_role_incomplete` | `APP_DB_USER` without `APP_DB_PASSWORD` or the reverse, in every profile |
| `db_role_invalid` | `APP_DB_USER` other than `ffcore_app` |
| `local_login_invalid` | `LOCAL_LOGIN` other than `all`, `superadmin_only`, `off` (17) |
| `ldap_url_invalid` / `ldap_plaintext_forbidden` / `ldap_incomplete` | `LDAP_URL` not `ldaps://` (plaintext only with `LDAP_ALLOW_PLAINTEXT=true`, then a warning line), or without `LDAP_BIND_DN`, `LDAP_BIND_PASSWORD`, `LDAP_USER_BASE` (17; directory sign-in, `docs/kimlik.md`) |

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
- The backend's own outbound calls (remote MCP servers, OpenAPI tools, alert webhooks, external
  agents) go through the proxy as well: the overlay sets
  `EGRESS_PROXY_URL=http://egress-proxy:3128` for `backend` and the workers (FOLLOWUP-208).
  The backend first applies its host rules (scheme, `OFFLINE`, `EGRESS_ALLOWLIST`, every
  redirect hop again), then sends the request to the proxy **by host name** (`CONNECT` for
  https; TLS and the certificate check stay end to end in the backend). The backend cannot
  resolve outside names on the internal network, so the address check (private address, DNS
  rebinding) is the proxy's: it resolves the name and checks the address it dials. A refusal by
  the proxy reaches the caller as `egress_proxy_denied`, never as the target's own 403. Hosts
  in `ALLOWED_INTERNAL_HOSTS` stay direct and pinned. Nothing falls back from one path to the
  other: an unreachable proxy is a failed call.
- Without the `egress` profile `EGRESS_PROXY_URL` is empty and the backend dials external
  hosts itself, checking every resolved address (unchanged).
- Not through the proxy: SMTP alerts (the proxy carries HTTP and `CONNECT` only) fail with a
  connection error under the `egress` profile; use a webhook alert channel there. The
  `/readyz` probe of the alert job calls the backend itself (internal) and is not affected.

Where the address check runs, by path:

| Check | Without proxy (`EGRESS_PROXY_URL` empty) | Through the proxy (`egress` profile) |
|---|---|---|
| scheme, port, `OFFLINE`, `EGRESS_ALLOWLIST`, platform target | backend | backend, then the proxy's own `EGRESS_ALLOWLIST` |
| every redirect hop | backend | backend |
| private / non-global address, DNS rebinding | backend (Python `is_global`, on the dialed address) | proxy (`to_private` in `deploy/egress/squid.conf`, on the dialed address) |
| documentation ranges (192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24, 2001:db8::/32) and 192.0.0.0/24 | refused | **allowed** (no provider resolves there; the egress test stack uses 198.51.100.0/24 as its outside) |
| internal hosts (`ALLOWED_INTERNAL_HOSTS`) | direct, pinned | direct, pinned |
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
resolves to a private address. The proxy log line names the host. A backend call (tool, webhook,
remote MCP server) refused this way fails with `egress_proxy_denied`; `egress_not_allowlisted`
means the backend's own `EGRESS_ALLOWLIST` refused it before the proxy.
