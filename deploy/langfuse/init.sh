#!/bin/sh
# Langfuse first install (package 02): prints a new project key pair and an admin password.
# Nothing is written to disk: copy the lines into .env yourself (an agent or script never writes
# .env). Langfuse creates the organisation, project, keys and admin user from them on start
# (LANGFUSE_INIT_*); LiteLLM and the backend use the same keys. Run once:
#   docker compose run --rm tools make langfuse-init
set -eu
python3 - <<'PY'
import secrets

print("# Langfuse first install: copy these lines into .env (shown once, not stored).")
print("LANGFUSE_INIT_PROJECT_PUBLIC_KEY=pk-lf-" + secrets.token_hex(16))
print("LANGFUSE_INIT_PROJECT_SECRET_KEY=sk-lf-" + secrets.token_hex(24))
print("LANGFUSE_INIT_USER_PASSWORD=" + secrets.token_urlsafe(24))
PY
