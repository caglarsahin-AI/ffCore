#!/usr/bin/env bash
# 19: load the transported archives on the PayCore server, then verify them against git.
#
#   deploy/offline/load.sh <archive_dir> [--models-volume <name>] [--dry-run]
#
# 1. `sha256sum -c manifest.sha256` in <archive_dir> (transport integrity; every archive listed,
#    nothing extra loaded)
# 2. `docker load -i` each image archive (images/*.tar)
# 3. models.tar into the named volume (default ffcore_model_cache), read back as written
# 4. verify.sh --images --models: the loaded result against images.txt / models.txt in git
# No network. Stops at the first failure.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
DIR="" VOLUME="ffcore_model_cache" DRY=0
usage() { sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'; }
while [ $# -gt 0 ]; do
  case "$1" in
    --models-volume) VOLUME="${2:?--models-volume needs a name}"; shift ;;
    --dry-run) DRY=1 ;;
    -h|--help) usage; exit 0 ;;
    -*) echo "load: unknown argument $1" >&2; usage >&2; exit 2 ;;
    *) DIR="$1" ;;
  esac
  shift
done
[ -n "$DIR" ] || { usage >&2; exit 2; }
run() { if [ "$DRY" = 1 ]; then echo "+ $*"; else "$@"; fi; }

[ -f "$DIR/manifest.sha256" ] || { echo "load: $DIR/manifest.sha256 missing" >&2; exit 1; }
listed="$(awk '{print $2}' "$DIR/manifest.sha256" | sed 's/^\*//' | sort)"
present="$(cd "$DIR" && find . -type f ! -name manifest.sha256 | sed 's|^\./||' | sort)"
if [ "$listed" != "$present" ]; then
  echo "load: archive files and manifest.sha256 differ (missing or extra file)" >&2; exit 1
fi
(cd "$DIR" && run sha256sum -c --quiet manifest.sha256)

for tar in "$DIR"/images/*.tar; do run docker load -i "$tar"; done
if [ -f "$DIR/models.tar" ]; then
  run docker volume create "$VOLUME"
  run docker run --rm --network none -v "$VOLUME:/models" -v "$DIR:/in:ro" \
    "${REGISTRY_PREFIX:-}ffcore/backend:${FFCORE_VERSION:?FFCORE_VERSION is not set}" \
    sh -c 'tar -xf /in/models.tar -C /models'
fi
run "$HERE/verify.sh" --images
if [ -f "$DIR/models.tar" ]; then
  run docker run --rm --network none -v "$VOLUME:/models:ro" -v "$HERE:/offline:ro" \
    -e MODELS_TXT=/offline/models.txt --entrypoint bash \
    "${REGISTRY_PREFIX:-}ffcore/backend:${FFCORE_VERSION}" /offline/verify.sh --models /models
fi
echo "load: done"
