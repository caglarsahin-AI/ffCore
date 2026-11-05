#!/usr/bin/env bash
# 08 tam 1c-b r1 MINOR-4: the model_cache paths models.txt lists, relative to the volume root,
# one per line, sorted: each listed snapshot file and each paddle file, plus each hf repo's
# refs/ (revision names such as `main`). save.sh packs exactly these (tar --dereference turns
# the hub's snapshot symlinks into files); verify.sh fails on any model directory or snapshot
# file outside them (an unlicensed candidate, a pickle copy). Nothing is deleted here.
#
#   deploy/offline/models-files.sh [models.txt] [--root <dir>]
#
# --root <dir>  leave out a repo's refs/ when <dir> has none (a snapshot downloaded by commit);
#               listed files are always printed, so a missing one fails tar loudly
set -euo pipefail

LIST="" ROOT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --root) ROOT="${2:?--root needs a directory}"; shift ;;
    -h|--help) sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) LIST="$1" ;;
  esac
  shift
done
LIST="${LIST:-$(cd "$(dirname "$0")" && pwd)/models.txt}"

while read -r kind repo rev path _rest; do
  case "$kind" in
    ''|'#'*) ;;
    hf)
      dir="huggingface/hub/models--${repo//\//--}"
      if [ -z "$ROOT" ] || [ -d "$ROOT/$dir/refs" ]; then printf '%s\n' "$dir/refs"; fi
      printf '%s\n' "$dir/snapshots/$rev/$path" ;;
    paddle) printf '%s\n' "paddleocr/$path" ;;
    *) echo "models-files: unknown kind '$kind' in $LIST" >&2; exit 1 ;;
  esac
done < "$LIST" | LC_ALL=C sort -u
