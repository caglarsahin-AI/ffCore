#!/usr/bin/env bash
# FFCore restore (package 12, plan/12 7): puts a deploy/backup.sh directory back on a FRESH
# stack (new volumes: `docker compose down -v` first, or a new server with the same .env).
# Refuses a target that already has FFCore tables; there is no --force.
#
#   deploy/restore.sh --from DIR [--dry-run]
#
# Steps: check manifest.sha256; start only the two Postgres services; refuse a non-fresh
# target; pg_restore both databases (--no-owner --no-acl --exit-on-error); re-apply the
# ffcore_app grants (deploy/postgres/app-role.sql) when that role exists; restore the
# knowledge storage (and the Qdrant / Langfuse trace volumes when the backup has them);
# compare the row and file counts with counts.json (a difference exits 1); start the stack.
# The LiteLLM model list is rebuilt by the backend's start-up reconcile.
#
# FFCORE_COMPOSE overrides the compose command (default: docker compose).
set -euo pipefail

from="" dry=0
while [ $# -gt 0 ]; do
    case "$1" in
        --from) from=${2:?--from needs a directory}; shift 2 ;;
        --dry-run) dry=1; shift ;;
        -h|--help)
            echo "usage: deploy/restore.sh --from DIR [--dry-run]"
            sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'
            exit 0 ;;
        *) echo "restore: unknown option $1 (see --help)" >&2; exit 2 ;;
    esac
done
[ -n "$from" ] || { echo "restore: --from DIR is required (see --help)" >&2; exit 2; }
[ -f "$from/manifest.sha256" ] || { echo "restore: $from/manifest.sha256 not found" >&2; exit 1; }
if ! (cd "$from" && sha256sum --quiet -c manifest.sha256 >&2); then
    echo "restore: $from does not match its manifest.sha256; not restoring" >&2
    exit 1
fi
from=$(cd "$from" && pwd)

read -ra DC <<< "${FFCORE_COMPOSE:-docker compose}"
PG='psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At'

step() { echo "restore: $*"; }
run() {
    local what=$1; shift
    step "$what"
    if [ "$dry" = 1 ]; then printf '    %s\n' "$*"; return 0; fi
    "$@"
}
from_file() {  # from_file <file> <command...>: the file on standard input
    local file=$1; shift
    if [ "$dry" = 1 ]; then printf '    %s < %s\n' "$*" "$file"; return 0; fi
    "$@" < "$from/$file"
}
sql() {  # sql <service> <statement>
    "${DC[@]}" exec -T "$1" sh -c "$PG -c \"$2\"" | tr -d '\r'
}

run "start the Postgres services only" "${DC[@]}" up -d --wait postgres langfuse-postgres

step "check the target is fresh (no tables in either database)"
if [ "$dry" = 0 ]; then
    for service in postgres langfuse-postgres; do
        tables=$(sql "$service" "SELECT count(*) FROM pg_tables WHERE schemaname = 'public'")
        if [ "$tables" != "0" ]; then
            echo "restore: $service already has $tables tables; restore needs fresh volumes" \
                "(docker compose down -v, then run this again)" >&2
            exit 1
        fi
    done
fi

step "ffcore.dump -> postgres (pg_restore)"
from_file ffcore.dump "${DC[@]}" exec -T postgres sh -c \
    'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-acl --exit-on-error'
step "langfuse.dump -> langfuse-postgres (pg_restore)"
from_file langfuse.dump "${DC[@]}" exec -T langfuse-postgres sh -c \
    'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-acl --exit-on-error'

step "ffcore_app grants (app-role.sql) when the role exists"
if [ "$dry" = 1 ]; then
    printf '    %s exec -T postgres psql -f /ffcore/app-role.sql\n' "${DC[*]}"
elif [ "$(sql postgres "SELECT count(*) FROM pg_roles WHERE rolname = 'ffcore_app'")" = "1" ]; then
    "${DC[@]}" exec -T postgres sh -c "$PG -f /ffcore/app-role.sql" > /dev/null
else
    step "no ffcore_app role on this server: the application connects as the owner"
fi

step "knowledge_storage.tar -> backend:/data/storage"
from_file knowledge_storage.tar "${DC[@]}" run --rm --no-deps -T --entrypoint tar backend \
    -C /data/storage -xf -
restore_volume() {  # restore_volume <file> <service> <path>
    if [ "$dry" = 1 ] || [ -f "$from/$1" ]; then
        step "$1 -> $2:$3"
        from_file "$1" "${DC[@]}" run --rm --no-deps -T --entrypoint tar "$2" -C "$3" -xf -
    fi
}
restore_volume qdrant_storage.tar qdrant /qdrant/storage
restore_volume langfuse_clickhouse.tar langfuse-clickhouse /var/lib/clickhouse
restore_volume langfuse_minio.tar langfuse-minio /data

step "compare counts.json (before the stack starts: the restored data only)"
if [ "$dry" = 1 ]; then
    printf '    rows per table and storage files against counts.json\n'
else
    COUNTS_SQL="SELECT json_build_object('projects', (SELECT count(*) FROM projects), 'agents', (SELECT count(*) FROM agents), 'knowledge_bases', (SELECT count(*) FROM knowledge_bases), 'documents', (SELECT count(*) FROM documents), 'conversations', (SELECT count(*) FROM conversations), 'runs', (SELECT count(*) FROM runs), 'messages', (SELECT count(*) FROM messages), 'audit_events', (SELECT count(*) FROM audit_events))"
    rows=$(sql postgres "$COUNTS_SQL")
    files=$("${DC[@]}" run --rm --no-deps -T --entrypoint sh backend -c 'find /data/storage -type f | wc -l' | tr -d ' \r')
    now=$(printf '{"tables": %s, "storage_files": %s}' "$rows" "$files")
    before=$(tr -d '\r\n' < "$from/counts.json")
    if [ "$now" != "$before" ]; then
        echo "restore: counts differ" >&2
        echo "  backup: $before" >&2
        echo "  now:    $now" >&2
        exit 1
    fi
    step "counts equal: $now"
fi

run "start the stack" "${DC[@]}" up -d --wait
step "done; the backend's start-up reconcile rebuilds LiteLLM's model list"
