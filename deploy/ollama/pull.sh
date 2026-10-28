#!/bin/sh
# DEPLOY_PROFILE'a göre deploy/ollama/models.${DEPLOY_PROFILE}.txt listesindeki modelleri çeker.
# tools konteynerinde koşar: docker compose run --rm tools make pull
set -eu

: "${DEPLOY_PROFILE:?DEPLOY_PROFILE tanımlı değil}"
OLLAMA_URL="${OLLAMA_URL:-http://ollama:11434}"
LIST="$(dirname "$0")/models.${DEPLOY_PROFILE}.txt"

case ",${COMPOSE_PROFILES:-}," in
  *,ollama,*) ;;
  *) echo "skipped: ollama profile inactive (COMPOSE_PROFILES=${COMPOSE_PROFILES:-})"; exit 0 ;;
esac

[ -f "$LIST" ] || { echo "error: model listesi yok: $LIST" >&2; exit 1; }

grep -v '^[[:space:]]*#' "$LIST" | grep -v '^[[:space:]]*$' | while read -r model; do
  echo "pull: $model"
  curl -fsS -X POST "$OLLAMA_URL/api/pull" -d "{\"model\": \"$model\", \"stream\": false}" >/dev/null
done
echo "pull: tamam ($LIST)"
