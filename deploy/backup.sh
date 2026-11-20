#!/usr/bin/env bash
# FFCore backup (package 12, plan/12 7). Run on the server from the FFCore checkout, with the
# stack up. Writes one directory: Postgres dumps, the knowledge storage, row counts and a
# SHA-256 manifest. deploy/restore.sh puts it back on a fresh stack. docs/kurulum.md "Backup".
#
#   deploy/backup.sh --out DIR [--with-traces] [--dry-run]
#
# What is in it: the FFCore database (projects, agents, documents and chunks, run history,
# audit), the Langfuse database (prompts, projects), the knowledge storage volume (raw and
# silver files) and, when the qdrant compose service runs, its volume (stopped for the copy).
# --with-traces adds Langfuse's ClickHouse and MinIO volumes (Langfuse is stopped meanwhile).
# Left out on purpose, rebuilt instead: the LiteLLM database (the backend reconciles it from
# FFCore's tables at start), the agent_demo database (synthetic, make seed-sql-demo), Redis
# (queues), model weights (offline archive, package 19), an external Qdrant (its owner's).
# The backup holds sensitive data (encrypted credentials, hashed keys, documents): keep it
# like the server itself.
#
# FFCORE_COMPOSE overrides the compose command (default: docker compose).
set -euo pipefail

usage() {
    sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
}

out="" traces=0 dry=0
while [ $# -gt 0 ]; do
    case "$1" in
        --out) out=${2:?--out needs a directory}; shift 2 ;;
        --with-traces) traces=1; shift ;;
        --dry-run) dry=1; shift ;;
        -h|--help) echo "usage: deploy/backup.sh --out DIR [--with-traces] [--dry-run]"; usage; exit 0 ;;
        *) echo "backup: unknown option $1 (see --help)" >&2; exit 2 ;;
    esac
done
[ -n "$out" ] || { echo "backup: --out DIR is required (see --help)" >&2; exit 2; }
if [ -e "$out" ] && [ -n "$(ls -A "$out" 2>/dev/null)" ]; then
    echo "backup: $out is not empty; give a new directory" >&2
    exit 1
fi

read -ra DC <<< "${FFCORE_COMPOSE:-docker compose}"
PG='psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At'

step() { echo "backup: $*"; }
# run <description> <command...>: print in --dry-run, run otherwise.
run() {
    local what=$1; shift
    step "$what"
    if [ "$dry" = 1 ]; then printf '    %s\n' "$*"; return 0; fi
    "$@"
}
to_file() {  # to_file <file> <command...>
    local file=$1; shift
    if [ "$dry" = 1 ]; then printf '    %s > %s\n' "$*" "$file"; return 0; fi
    "$@" > "$out/$file"
}
running() { "${DC[@]}" ps --status running --services 2>/dev/null | grep -qx "$1"; }
volume_tar() {  # volume_tar <service> <path in container> <file>: service stopped meanwhile
    local service=$1 path=$2 file=$3
    run "stop $service" "${DC[@]}" stop "$service"
    step "$file ($service:$path)"
    to_file "$file" "${DC[@]}" run --rm --no-deps -T --entrypoint tar "$service" -C "$path" -cf - .
    run "start $service" "${DC[@]}" start "$service"
}

[ "$dry" = 1 ] || mkdir -p "$out"

step "ffcore.dump (pg_dump -Fc of the FFCore database)"
to_file ffcore.dump "${DC[@]}" exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc'
step "langfuse.dump (pg_dump -Fc of the Langfuse database)"
to_file langfuse.dump "${DC[@]}" exec -T langfuse-postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc'
step "knowledge_storage.tar (backend:/data/storage)"
to_file knowledge_storage.tar "${DC[@]}" exec -T backend tar -C /data/storage -cf - .

if [ "$dry" = 1 ] || running qdrant; then
    volume_tar qdrant /qdrant/storage qdrant_storage.tar
fi
if [ "$traces" = 1 ]; then
    run "stop langfuse-web langfuse-worker" "${DC[@]}" stop langfuse-web langfuse-worker
    volume_tar langfuse-clickhouse /var/lib/clickhouse langfuse_clickhouse.tar
    volume_tar langfuse-minio /data langfuse_minio.tar
    run "start langfuse-web langfuse-worker" "${DC[@]}" start langfuse-web langfuse-worker
fi

step "counts.json (rows per table and storage files, compared by restore.sh)"
COUNTS_SQL="SELECT json_build_object('projects', (SELECT count(*) FROM projects), 'agents', (SELECT count(*) FROM agents), 'knowledge_bases', (SELECT count(*) FROM knowledge_bases), 'documents', (SELECT count(*) FROM documents), 'conversations', (SELECT count(*) FROM conversations), 'runs', (SELECT count(*) FROM runs), 'messages', (SELECT count(*) FROM messages), 'audit_events', (SELECT count(*) FROM audit_events))"
if [ "$dry" = 1 ]; then
    printf '    %s exec -T postgres psql ... > counts.json\n' "${DC[*]}"
else
    rows=$("${DC[@]}" exec -T postgres sh -c "$PG -c \"$COUNTS_SQL\"")
    files=$("${DC[@]}" exec -T backend sh -c 'find /data/storage -type f | wc -l' | tr -d ' \r')
    printf '{"tables": %s, "storage_files": %s}\n' "$rows" "$files" > "$out/counts.json"
fi

step "manifest.sha256"
if [ "$dry" = 1 ]; then
    printf '    sha256sum * > manifest.sha256\n'
else
    (cd "$out" && sha256sum -- * > manifest.sha256)
    step "done: $out ($(du -sh "$out" | cut -f1))"
fi
