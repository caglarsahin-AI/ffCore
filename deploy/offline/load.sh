#!/usr/bin/env bash
# 19: load the transported archives on the PayCore server, then verify them against git.
#
#   deploy/offline/load.sh <archive_dir> --models-dir <dir> [--dry-run]
#
# 1. `sha256sum -c manifest.sha256` in <archive_dir> (transport integrity; every archive listed,
#    nothing extra loaded)
# 2. `docker load -i` each image archive (images/*.tar)
# 3. models.tar into <dir> (the host directory FFCore mounts at /models, e.g.
#    /opt/data/ffcore/models; created if missing, readable for the containers)
# 4. verify.sh --images --models <dir>: the result against images.txt / models.txt in git
# No network, no container. Stops at the first failure.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
DIR="" MODELS_DIR="" DRY=0
usage() { sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; }
while [ $# -gt 0 ]; do
  case "$1" in
    --models-dir) MODELS_DIR="${2:?--models-dir needs a directory}"; shift ;;
    --dry-run) DRY=1 ;;
    -h|--help) usage; exit 0 ;;
    -*) echo "load: unknown argument $1" >&2; usage >&2; exit 2 ;;
    *) DIR="$1" ;;
  esac
  shift
done
{ [ -n "$DIR" ] && [ -n "$MODELS_DIR" ]; } || { usage >&2; exit 2; }
run() { if [ "$DRY" = 1 ]; then echo "+ $*"; else "$@"; fi; }

[ -f "$DIR/manifest.sha256" ] || { echo "load: $DIR/manifest.sha256 missing" >&2; exit 1; }
listed="$(awk '{print $2}' "$DIR/manifest.sha256" | sed 's/^\*//' | sort)"
present="$(cd "$DIR" && find . -type f ! -name manifest.sha256 | sed 's|^\./||' | sort)"
if [ "$listed" != "$present" ]; then
  echo "load: archive files and manifest.sha256 differ (missing or extra file)" >&2; exit 1
fi
(cd "$DIR" && run sha256sum -c --quiet manifest.sha256)
[ -f "$DIR/models.tar" ] || { echo "load: $DIR/models.tar missing" >&2; exit 1; }

for tar in "$DIR"/images/*.tar; do run docker load -i "$tar"; done
run mkdir -p "$MODELS_DIR"
run tar --no-same-owner -xf "$DIR/models.tar" -C "$MODELS_DIR"
run chmod -R a+rX "$MODELS_DIR"
run "$HERE/verify.sh" --images --models "$MODELS_DIR"
echo "load: done"
