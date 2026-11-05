#!/usr/bin/env bash
# 19 şart 3: compare what is on this host with the lists in git (images.txt, models.txt).
# The archive's own manifest.sha256 proves transport integrity only; this proves the loaded
# images and model files are the ones FFCore pinned. Runs on the server (no network needed).
#
#   deploy/offline/verify.sh [--images] [--models <dir>] [--dry-run]
#
# --images        every images.txt line: `docker image inspect --format '{{.Id}}'` of
#                 ${REGISTRY_PREFIX}<image> equals image_id (PENDING is a failure)
# --models <dir>  every models.txt file under <dir> (the model_cache content: huggingface/,
#                 paddleocr/) has the listed sha256 and size, and no hub model directory or
#                 snapshot file outside models.txt is there
# --dry-run       print what would be checked, run nothing
# Exit 0 only if every check passes; each failure is one line with the image or file name.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
IMAGES="${IMAGES_TXT:-$HERE/images.txt}"
MODELS="${MODELS_TXT:-$HERE/models.txt}"
PREFIX="${REGISTRY_PREFIX:-}"
DRY=0 DO_IMAGES=0 MODELS_DIR=""

usage() { sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'; }
while [ $# -gt 0 ]; do
  case "$1" in
    --images) DO_IMAGES=1 ;;
    --models) MODELS_DIR="${2:?--models needs a directory}"; shift ;;
    --dry-run) DRY=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "verify: unknown argument $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done
if [ "$DO_IMAGES" = 0 ] && [ -z "$MODELS_DIR" ]; then
  echo "verify: say what to check: --images and/or --models <dir>" >&2; exit 2
fi

fail=0
resolve() {  # <FFCORE_VERSION> in a reference needs the release the user built
  case "$1" in
    *"<FFCORE_VERSION>"*)
      [ -n "${FFCORE_VERSION:-}" ] || { echo "verify: FFCORE_VERSION is not set" >&2; exit 2; }
      printf '%s' "${1//<FFCORE_VERSION>/$FFCORE_VERSION}" ;;
    *) printf '%s' "$1" ;;
  esac
}

if [ "$DO_IMAGES" = 1 ]; then
  while read -r image _digest want _platform; do
    case "$image" in ''|'#'*) continue ;; esac
    ref="$PREFIX$(resolve "$image")"
    if [ "$DRY" = 1 ]; then echo "would check image $ref id $want"; continue; fi
    if [ "$want" = PENDING ]; then
      echo "FAIL image $ref: image_id PENDING in images.txt (commit the id save.sh printed)"
      fail=1; continue
    fi
    got="$(docker image inspect --format '{{.Id}}' "$ref" 2>/dev/null || true)"
    if [ -z "$got" ]; then echo "FAIL image $ref: not loaded"; fail=1
    elif [ "$got" != "$want" ]; then echo "FAIL image $ref: id differs from images.txt"; fail=1
    else echo "OK image $ref"; fi
  done < "$IMAGES"
fi

if [ -n "$MODELS_DIR" ]; then
  while read -r kind repo rev path want size; do
    case "$kind" in ''|'#'*) continue ;; esac
    if [ "$kind" = hf ]; then
      file="$MODELS_DIR/huggingface/hub/models--${repo//\//--}/snapshots/$rev/$path"
    else
      file="$MODELS_DIR/paddleocr/$path"
    fi
    if [ "$DRY" = 1 ]; then echo "would check model $file"; continue; fi
    if [ ! -f "$file" ]; then echo "FAIL model $repo $path: missing"; fail=1; continue; fi
    got="$(sha256sum -b "$file" | cut -d' ' -f1)"
    got_size="$(stat -L -c %s "$file")"
    if [ "$got" != "$want" ] || [ "$got_size" != "$size" ]; then
      echo "FAIL model $repo $path: sha256 or size differs from models.txt"; fail=1
    fi
  done < "$MODELS"
  # 08 tam 1c-b r1 MINOR-4: nothing outside the list is shipped or loaded unnoticed (an
  # unlicensed candidate, a pickle copy). Named, never deleted (docs/guardrail.md, cleanup).
  hub="$MODELS_DIR/huggingface/hub"
  if [ "$DRY" = 0 ] && [ -d "$hub" ]; then
    listed="$(bash "$HERE/models-files.sh" "$MODELS")"
    for dir in "$hub"/models--*; do
      [ -d "$dir" ] || continue
      name="${dir##*/}"
      if ! grep -q "^huggingface/hub/$name/" <<<"$listed"; then
        echo "FAIL model dir $name: not in models.txt"; fail=1; continue
      fi
      repo="${name#models--}"; repo="${repo//--//}"
      while IFS= read -r file; do
        grep -qxF "huggingface/hub/$name/${file#./}" <<<"$listed" && continue
        echo "FAIL model $repo ${file#./snapshots/}: not in models.txt"; fail=1
      done < <(cd "$dir" && find ./snapshots \( -type f -o -type l \) 2>/dev/null | LC_ALL=C sort)
    done
  fi
  [ "$DRY" = 1 ] || [ "$fail" = 1 ] || echo "OK models ($(grep -cv '^#' "$MODELS") files)"
fi

[ "$DRY" = 1 ] && exit 0
if [ "$fail" = 1 ]; then echo "verify: FAIL"; exit 1; fi
echo "verify: OK"
