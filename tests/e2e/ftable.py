"""The F table of an e2e run (13b, K-13b-0001 S2): one row per plan/18 use case with passed /
failed / NOT_RUN counts, the failing tests and the NOT_RUN reasons.

Pure functions; tests/e2e/conftest.py feeds them the run's results and prints the table (and
writes it with `--f-table <path>`). A failure listed in known_findings.json is shown as
"failed (known: FOLLOWUP-…)": still a failure, never a pass; a row with any other failure is
plain "failed". plan/18's status column can be built from this table.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
KNOWN_FILE = HERE / "known_findings.json"
_F_ROW = re.compile(r"::test_18_f(\d+)_")
_SETUP = re.compile(r"::test_(?:18_env|18_seed|13b_ftable)_")
_NEGATIVE = re.compile(r"::test_13b_neg_")
_NAME = re.compile(r"::(test_[A-Za-z0-9_]+)")
_TEST_DEF = re.compile(r"^def (test_[A-Za-z0-9_]+)\(", re.MULTILINE)


@dataclass(frozen=True)
class Result:
    nodeid: str
    outcome: str  # passed | failed | skipped
    reason: str = ""


@dataclass
class Row:
    row: str
    passed: int = 0
    failed: int = 0
    not_run: int = 0
    failures: list[str] = field(default_factory=list)  # "name (FOLLOWUP-…: note)" or "name"
    reasons: list[str] = field(default_factory=list)  # distinct NOT_RUN reasons
    known_ids: list[str] = field(default_factory=list)
    unknown_failure: bool = False

    @property
    def status(self) -> str:
        if self.failed:
            if self.unknown_failure:
                return "failed"
            return f"failed (known: {', '.join(sorted(set(self.known_ids)))})"
        if self.passed:
            return "passed"
        return "NOT_RUN"


def row_of(nodeid: str) -> str:
    if match := _F_ROW.search(nodeid):
        return f"F{int(match.group(1))}"
    if _NEGATIVE.search(nodeid):
        return "Negative"
    if _SETUP.search(nodeid):
        return "Setup"
    return "Other"


def _order(row: str) -> tuple:
    if row.startswith("F"):
        return (0, int(row[1:]))
    return (1, ["Negative", "Setup", "Other"].index(row))


def test_name(nodeid: str) -> str:
    match = _NAME.search(nodeid)
    return match.group(1) if match else nodeid


def summarize(results: list[Result], known: dict) -> list[Row]:
    rows: dict[str, Row] = {}
    for r in results:
        row = rows.setdefault(row_of(r.nodeid), Row(row_of(r.nodeid)))
        name = test_name(r.nodeid)
        if r.outcome == "passed":
            row.passed += 1
        elif r.outcome == "skipped":
            row.not_run += 1
            if r.reason and r.reason not in row.reasons:
                row.reasons.append(r.reason)
        else:
            row.failed += 1
            entry = known.get(name)
            if entry:
                row.known_ids.append(entry["followup"])
                row.failures.append(f"{name} ({entry['followup']}: {entry['note']})")
            else:
                row.unknown_failure = True
                row.failures.append(name)
    return sorted(rows.values(), key=lambda r: _order(r.row))


def markdown(rows: list[Row]) -> str:
    lines = [
        "| Use case | Status | Passed | Failed | NOT_RUN | Failing tests | NOT_RUN reasons |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r.row} | {r.status} | {r.passed} | {r.failed} | {r.not_run} | "
            f"{'; '.join(r.failures)} | {'; '.join(r.reasons)} |"
        )
    return "\n".join(lines) + "\n"


def load_known(path: Path = KNOWN_FILE) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def collected_test_names(root: Path = HERE) -> set[str]:
    names = set()
    for path in root.rglob("test_*.py"):
        names |= set(_TEST_DEF.findall(path.read_text(encoding="utf-8")))
    return names
