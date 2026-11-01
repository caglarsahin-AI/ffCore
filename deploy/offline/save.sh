#!/usr/bin/env bash
# 19: build the transport archive on the INTERNET-CONNECTED PREPARATION MACHINE (never the
# server; the agent never runs this, it pulls from registries).
#
#   FFCORE_VERSION=<release> REGISTRY_PREFIX=nexus.paycore.com/ \
#     deploy/offline/save.sh <out_dir> [--models-volume <name>] [--dry-run]
#
# 1. pull every third-party image in images.txt and check its RepoDigests carry registry_digest
#    and its id equals image_id (provenance, here where the registry is reachable)
# 2. ffcore/backend and ffcore/frontend are built from this checkout (`docker compose build`) and
#    their ids are PRINTED: commit them into images.txt (replacing PENDING) before transport
# 3. tag each with REGISTRY_PREFIX, `docker save` into <out_dir>/images/
# 4. the model_cache volume (filled by `make models`) into <out_dir>/models.tar, after
#    verify.sh --models has checked it against models.txt
# 5. <out_dir>/manifest.sha256 over every file (transport integrity only)
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="" VOLUME="04a-knowledge-core_model_cache" DRY=0
usage() { sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'; }
while [ $# -gt 0 ]; do
  case "$1" in
    --models-volume) VOLUME="${2:?--models-volume needs a name}"; shift ;;
    --dry-run) DRY=1 ;;
    -h|--help) usage; exit 0 ;;
    -*) echo "save: unknown argument $1" >&2; usage >&2; exit 2 ;;
    *) OUT="$1" ;;
  esac
  shift
done
[ -n "$OUT" ] || { usage >&2; exit 2; }
: "${FFCORE_VERSION:?FFCORE_VERSION is not set (the release to build and ship)}"
PREFIX="${REGISTRY_PREFIX:-}"
run() { if [ "$DRY" = 1 ]; then echo "+ $*"; else "$@"; fi; }
run mkdir -p "$OUT/images"

while read -r image digest want _platform; do
  case "$image" in ''|'#'*) continue ;; esac
  ref="${image//<FFCORE_VERSION>/$FFCORE_VERSION}"
  if [ "$digest" = local-build ]; then
    if [ "$DRY" = 0 ]; then
      got="$(docker image inspect --format '{{.Id}}' "$ref")"
      echo "images.txt: $image local-build $got (commit this id; was $want)"
    else
      echo "+ docker image inspect --format {{.Id}} $ref   # print id for images.txt"
    fi
  else
    run docker pull "$ref"
    if [ "$DRY" = 0 ]; then
      docker image inspect --format '{{json .RepoDigests}}' "$ref" | grep -q "$digest" \
        || { echo "save: $ref: registry digest differs from images.txt" >&2; exit 1; }
      [ "$(docker image inspect --format '{{.Id}}' "$ref")" = "$want" ] \
        || { echo "save: $ref: image id differs from images.txt" >&2; exit 1; }
    fi
  fi
  [ -z "$PREFIX" ] || run docker tag "$ref" "$PREFIX$ref"
  slug="$(printf '%s' "$ref" | tr '/:@' '___')"
  run docker save -o "$OUT/images/$slug.tar" "$PREFIX$ref"
done < "$HERE/images.txt"

run docker run --rm --network none -v "$VOLUME:/models:ro" -v "$HERE:/offline:ro" \
  -e MODELS_TXT=/offline/models.txt --entrypoint bash "ffcore/backend:$FFCORE_VERSION" \
  /offline/verify.sh --models /models
run docker run --rm --network none -v "$VOLUME:/models:ro" -v "$(cd "$OUT" && pwd):/out" \
  --entrypoint sh "ffcore/backend:$FFCORE_VERSION" -c 'tar -cf /out/models.tar -C /models .'
if [ "$DRY" = 1 ]; then
  echo "+ (cd $OUT && find . -type f ! -name manifest.sha256 | sort | xargs sha256sum -b > manifest.sha256)"
else
  (cd "$OUT" && find . -type f ! -name manifest.sha256 | sed 's|^\./||' | sort \
    | xargs sha256sum -b > manifest.sha256)
fi
echo "save: archive in $OUT; commit images.txt if ids were printed, then carry $OUT"
