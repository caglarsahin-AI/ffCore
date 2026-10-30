"""Produce the console's brand files from the PNG renders in assets/icons/.

Every output is either a byte copy of a source file or a LANCZOS resize saved without metadata, so
a second run writes the same bytes. `--check` rebuilds in memory and fails, listing the files, if
anything under frontend/ differs from what the sources give.

    py -3.12 assets/icons/scripts/make_web_brand.py          # write
    py -3.12 assets/icons/scripts/make_web_brand.py --check  # verify, exit 1 on drift
"""

from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

from PIL import Image

ICONS = Path(__file__).resolve().parents[1]
FRONTEND = ICONS.parents[1] / "frontend"

# target (relative to frontend/) -> (source relative to assets/icons/, size or None for a byte copy)
OUTPUTS: dict[str, tuple[str, int | None]] = {
    "app/favicon.ico": ("favicon/favicon.ico", None),
    "app/icon.png": ("png/ffcore-icon-48x48.png", None),
    "app/apple-icon.png": ("png/apple-touch-icon-180x180.png", None),
    "public/brand/ffcore-icon-128.png": ("png/ffcore-icon-128x128.png", None),
    "public/brand/ffcore-icon-192.png": ("png/ffcore-icon-1024x1024.png", 192),
    "public/brand/ffcore-icon-512.png": ("png/ffcore-icon-512x512.png", None),
    "public/brand/ffcore-badge-256.png": ("png/ffcore-badge-transparent-1024.png", 256),
    "public/brand/ffcore-badge-512.png": ("png/ffcore-badge-transparent-1024.png", 512),
    "public/brand/ffcore-brand-variant-b-512.png": ("png/ffcore-brand-variant-b.png", 512),
}


def render(source: str, size: int | None) -> bytes:
    path = ICONS / source
    if size is None:
        return path.read_bytes()
    with Image.open(path) as image:
        if image.size[0] != image.size[1] or image.size[0] < size:
            raise SystemExit(f"{source}: expected a square image of at least {size} px, got {image.size}")
        resized = image.resize((size, size), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    resized.save(out, format="PNG", optimize=True)
    return out.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="compare instead of writing; exit 1 on drift")
    args = parser.parse_args()

    drift = []
    for target, (source, size) in OUTPUTS.items():
        data = render(source, size)
        path = FRONTEND / target
        if args.check:
            if not path.is_file() or path.read_bytes() != data:
                drift.append(target)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        print(f"{target} <- {source}" + (f" ({size} px)" if size else " (copy)"))

    if drift:
        print("out of date (run without --check): " + ", ".join(drift), file=sys.stderr)
        return 1
    if args.check:
        print(f"{len(OUTPUTS)} files up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
