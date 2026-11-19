"""An exam's item table (10c-2, FOLLOWUP-185): one row per item from `eval_runs.item_runs`.

Each scored item is combined from its runs exactly as the summary and compare do (`combine`), so
the table, the summary and a comparison never disagree; nothing is read from Langfuse. Rows come
failed, not run, passed, not yet scored, then by item id: the items an analyst looks at first.
"""

from typing import Any

from ffcore.evaluation.runner import combine

ITEM_STATUSES = ("all", "failed", "passed", "not_run")


def _rank(row: dict[str, Any]) -> int:
    if not row["scored"]:
        return 3
    return {False: 0, None: 1, True: 2}[row["passed"]]


def _row(item_id: str, entry: dict) -> dict[str, Any]:
    item = entry.get("item") or {"id": item_id}
    meta = item.get("metadata") or {}
    base = {
        "item_id": item_id,
        "style": meta.get("style", "-"),
        "attempts": int(entry.get("attempts") or 0),
        "run_ids": [str(r) for r in entry.get("runs") or []],
    }
    result = entry.get("result")
    if not (entry.get("scored") and result):
        return {**base, "scored": False, "passed": None, "mean": None, "outcome": None,
                "note": "", "repeats_not_run": "", "scores": []}  # fmt: skip
    r = combine(item, result["runs"])
    mean = r.mean()
    return {
        **base,
        "style": r.style,
        "scored": True,
        "passed": r.passed,
        "mean": None if mean is None else round(mean, 4),
        "outcome": r.outcome,
        "note": r.note,
        "repeats_not_run": r.repeats_not_run,
        "scores": [
            {
                "name": s.name,
                "value": s.value,
                "passed": s.passed,
                "status": s.status,
                "comment": s.comment or "",
            }  # fmt: skip
            for s in r.scores
        ],
    }


def item_rows(item_runs: dict | None) -> list[dict[str, Any]]:
    rows = [_row(item_id, entry) for item_id, entry in (item_runs or {}).items()]
    rows.sort(key=lambda row: (_rank(row), row["item_id"]))
    return rows


def select_rows(rows: list[dict[str, Any]], status: str) -> list[dict[str, Any]]:
    """`failed` / `passed`: decided items; `not_run`: scored but not run; `all`: every row, the
    not yet scored ones too. Any other value is refused (the API validates it first)."""
    if status not in ITEM_STATUSES:
        raise ValueError(f"unknown item status: {status}")
    if status == "all":
        return rows
    wanted = {"failed": False, "passed": True, "not_run": None}[status]
    return [row for row in rows if row["scored"] and row["passed"] is wanted]
