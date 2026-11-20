#!/bin/sh
# FFCore least-privileged application role (package 12, FOLLOWUP-46). Runs once, on a fresh
# volume (docker-entrypoint-initdb.d), after 10-litellm.sql. The entrypoint may source this
# file instead of running it, so it never calls `exit`.
# Both empty: no role, the application connects as the owner. One without the other: stop.
# The grants are in /ffcore/app-role.sql (deploy/postgres/app-role.sql), the one file an
# operator also runs on an existing volume; migration 12_0001 repeats them for later tables.
set -eu
if [ -n "${APP_DB_USER:-}" ] && [ -z "${APP_DB_PASSWORD:-}" ]; then
    # Review 12-2 r1 MAJOR-2: compose would hand the application ffcore_app with the owner's
    # password, a role this script never created; stop the first start instead.
    echo "20-app-role: APP_DB_USER is set but APP_DB_PASSWORD is empty; set both or neither" >&2
    false
elif [ -z "${APP_DB_USER:-}" ] && [ -n "${APP_DB_PASSWORD:-}" ]; then
    # FOLLOWUP-213: compose would connect as the owner with the role's password, and a role
    # nobody connects as would exist; stop the first start instead (`false`: sourced, no exit).
    echo "20-app-role: APP_DB_PASSWORD is set but APP_DB_USER is empty; set both or neither" >&2
    false
elif [ -z "${APP_DB_PASSWORD:-}" ]; then
    echo "20-app-role: APP_DB_USER and APP_DB_PASSWORD are empty; no ffcore_app role (the application connects as the owner)"
elif [ "${APP_DB_USER}" != "ffcore_app" ]; then
    echo "20-app-role: APP_DB_USER must be ffcore_app (or empty), got '${APP_DB_USER}'" >&2
    false
else
    # psql interpolates :'app_password' (quoted literal) only in input, never in -c.
    echo "CREATE ROLE ffcore_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD :'app_password';" |
        psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
            -v app_password="$APP_DB_PASSWORD"
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -f /ffcore/app-role.sql
    echo "20-app-role: ffcore_app created with its grants"
fi
