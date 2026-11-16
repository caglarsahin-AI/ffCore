"""Context budget check (decision 16 Nov 2026, docs/takim/ajanlarla-gelistirme.md 9.4).

Prints the size of the files every session reads at start against their targets.
Exit code 1 when any target is exceeded (fail-loud; the wave report carries the table).
Run: py -3.12 scripts/context_budget.py
"""

from __future__ import annotations

import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KB = 1024


def size(path: str) -> int:
    p = os.path.join(ROOT, path)
    return os.path.getsize(p) if os.path.exists(p) else 0


def kararlar_index_size() -> int:
    p = os.path.join(ROOT, "KARARLAR.md")
    if not os.path.exists(p):
        return 0
    text = open(p, encoding="utf-8").read()
    m = re.search(r"^## İndeks.*?(?=^## )", text, re.S | re.M)
    return len(m.group(0).encode("utf-8")) if m else 0


def main() -> int:
    mandatory = [
        "CLAUDE.md",
        "FELSEFE.md",
        "handbook/FELSEFE_UYGULAMA.md",
        "handbook/MULTI_AGENT_PROTOCOL.md",
        "handbook/SECURITY_AND_PERMISSIONS.md",
    ]
    rows: list[tuple[str, int, int]] = []
    rows.append(
        (
            "zorunlu küme (" + ", ".join(mandatory) + ") + KARARLAR indeksi",
            sum(size(p) for p in mandatory) + kararlar_index_size(),
            60 * KB,
        )
    )
    rows.append(("KARARLAR indeksi", kararlar_index_size(), 15 * KB))
    rows.append(("state/BLOCKERS.md (açık)", size("state/BLOCKERS.md"), 30 * KB))
    rows.append(("state/WORK_QUEUE.md", size("state/WORK_QUEUE.md"), 15 * KB))
    for p in sorted(glob.glob(os.path.join(ROOT, "state", "kanal", "*.md"))):
        rows.append(("state/kanal/" + os.path.basename(p), os.path.getsize(p), 50 * KB))
    over = 0
    print(f"{'dosya':<70} {'boyut':>9} {'hedef':>8}  durum")
    for name, b, target in rows:
        ok = b <= target
        over += 0 if ok else 1
        print(f"{name[:70]:<70} {b / KB:>7.1f}K {target / KB:>6.0f}K  {'ok' if ok else 'AŞIM'}")
    print(f"aşım: {over}")
    return 1 if over else 0


if __name__ == "__main__":
    sys.exit(main())
