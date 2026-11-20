#!/usr/bin/env bash
# 12 (FOLLOWUP-95): collect the backend's locked Python wheels on the INTERNET-CONNECTED
# PREPARATION MACHINE, for an internal package mirror (e.g. a Nexus PyPI proxy/hosted repo)
# that the image build then uses instead of PyPI:
#
#   deploy/offline/wheels.sh <out_dir> [--dry-run]
#   docker compose build --build-arg UV_INDEX_URL=https://<mirror>/simple ...
#
# The list is backend/uv.lock (dev group included: the tools image needs it), exported by uv
# and downloaded by pip as manylinux x86_64 / CPython 3.12 wheels only (--only-binary: a
# package without a wheel fails here, loudly, instead of compiling on the server). Runs in the
# pinned Python image of backend/Dockerfile; writes only <out_dir>. Not run by agents.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
OUT="" DRY=0
usage() { sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; }
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1 ;;
    -h|--help) echo "usage: deploy/offline/wheels.sh <out_dir> [--dry-run]"; usage; exit 0 ;;
    -*) echo "wheels: unknown argument $1" >&2; exit 2 ;;
    *) OUT="$1" ;;
  esac
  shift
done
[ -n "$OUT" ] || { echo "wheels: <out_dir> is required (--help)" >&2; exit 2; }

IMAGE="${REGISTRY_PREFIX:-}python:3.12.10-slim-bookworm"
UV_VERSION="0.10.12"  # backend/Dockerfile's uv
SCRIPT="pip install -q uv==$UV_VERSION \
  && cd /src && uv export --frozen --no-hashes --no-emit-project --all-groups -o /tmp/requirements.txt \
  && pip download -q -r /tmp/requirements.txt -d /out --only-binary=:all: \
       --platform manylinux_2_28_x86_64 --platform manylinux2014_x86_64 \
       --python-version 3.12 --implementation cp \
  && ls /out | wc -l"

if [ "$DRY" = 1 ]; then
  echo "+ docker run --rm -v $REPO/backend:/src:ro -v $OUT:/out $IMAGE sh -c '$SCRIPT'"
  exit 0
fi
mkdir -p "$OUT"
count=$(docker run --rm -v "$REPO/backend:/src:ro" -v "$(cd "$OUT" && pwd):/out" "$IMAGE" sh -c "$SCRIPT")
echo "wheels: $count files in $OUT; upload them to the internal mirror, then build with"
echo "        --build-arg UV_INDEX_URL=<mirror>/simple"
