"""19 şart 5: no S1 set or exam report is tracked in this checkout.

    python3 scripts/m3_gate_check.py        (exit 0 clean, 1 with the offending paths)

Runs where git is (the host or the server checkout; the tools container has no git). Checks the
tracked file names only, never their contents: it is a gate for the files S1 runs produce.
"""

import re
import subprocess
import sys

FORBIDDEN = (
    re.compile(r"(^|/)eval/results/"),  # make eval's report directory (git-ignored)
    re.compile(r"(^|/)questions\.jsonl$"),  # PayCore S1 set file name (eval/scenario*/)
    re.compile(r"(^|/)eval-\d{8}-\d{4}\.md$"),  # a make eval report moved elsewhere
)


# Synthetic-set evidence committed before 19 (13b fake-llm pipeline run, sozlesme-33). Named one
# by one: a new report anywhere in the tree still fails the gate.
ALLOWED = frozenset({"state/pr/13b-a-kapilar/results/eval-20261030-2024.md"})


def violations(paths: list[str]) -> list[str]:
    return [p for p in paths if p not in ALLOWED and any(rx.search(p) for rx in FORBIDDEN)]


def main() -> int:
    tracked = subprocess.run(
        ["git", "ls-files"], check=True, capture_output=True, text=True
    ).stdout.splitlines()
    found = violations(tracked)
    for path in found:
        print(f"tracked and forbidden: {path}", file=sys.stderr)
    print("m3 gate check: " + ("FAIL" if found else "OK"))
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
