"""Comparing two exams of one suite (09-2, plan/09 Akış 2; KARARLAR "09-2 plan kararları" S2).

Reads only the exams' own results (`eval_runs.item_runs[*].result`, combined per item exactly
as the summary is): no Langfuse call, so its read-back lag cannot change the answer. Both exams
must be `completed` and of the same suite; `complete=false` exams are compared too and say so.
An item not run in either exam is `not_comparable`: its pass/fail is never guessed.
"""

from collections import Counter
from typing import Any

from ffcore.evaluation.runner import combine

CHANGES = ("fixed", "regressed", "same", "not_comparable", "only_a", "only_b")
WORST = 10
CONFIG_KEYS = ("scorers", "pass_threshold", "repeat", "approve_tools")


class CompareError(ValueError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _results(ev) -> dict[str, Any]:
    out = {}
    for item_id, entry in (ev.item_runs or {}).items():
        if entry.get("scored") and entry.get("result"):
            out[item_id] = combine(entry["item"], entry["result"]["runs"])
    return out


def _side(r) -> dict | None:
    if r is None:
        return None
    return {"passed": r.passed, "mean": r.mean(), "outcome": r.outcome, "note": r.note}


def _change(x, y) -> str:
    if y is None:
        return "only_a"
    if x is None:
        return "only_b"
    if x.passed is None or y.passed is None:
        return "not_comparable"
    if x.passed == y.passed:
        return "same"
    return "fixed" if y.passed else "regressed"


def _diff(a, b) -> dict:
    delta = round(b - a, 4) if isinstance(a, int | float) and isinstance(b, int | float) else None
    return {"a": a, "b": b, "delta": delta}


def _summary(sa: dict, sb: dict) -> dict:
    scores = sorted(set(sa.get("scores") or {}) | set(sb.get("scores") or {}))
    outcomes = sorted(set(sa.get("outcomes") or {}) | set(sb.get("outcomes") or {}))
    return {
        "pass_rate": _diff(sa.get("pass_rate"), sb.get("pass_rate")),
        "scored": _diff(sa.get("scored"), sb.get("scored")),
        "passed_items": _diff(sa.get("passed_items"), sb.get("passed_items")),
        "scores": {
            k: _diff((sa.get("scores") or {}).get(k), (sb.get("scores") or {}).get(k))
            for k in scores
        },  # fmt: skip
        "outcomes": {
            k: _diff((sa.get("outcomes") or {}).get(k, 0), (sb.get("outcomes") or {}).get(k, 0))
            for k in outcomes
        },  # fmt: skip
        "not_run": {"a": dict(sa.get("not_run") or {}), "b": dict(sb.get("not_run") or {})},
    }


def compare(a, b) -> dict[str, Any]:
    if a.suite_id != b.suite_id:
        raise CompareError("different_suite")
    if a.status != "completed" or b.status != "completed":
        raise CompareError("not_completed")
    ra, rb = _results(a), _results(b)
    items = []
    for item_id in sorted(set(ra) | set(rb)):
        x, y = ra.get(item_id), rb.get(item_id)
        change = _change(x, y)
        mx = x.mean() if x is not None and x.passed is not None else None
        my = y.mean() if y is not None and y.passed is not None else None
        items.append(
            {
                "item_id": item_id,
                "style": (x or y).style,
                "change": change,
                "a": _side(x),
                "b": _side(y),
                "mean_delta": round(my - mx, 4) if mx is not None and my is not None else None,
            }
        )
    counts = Counter(i["change"] for i in items)
    worse = [i for i in items if i["change"] == "regressed" or (i["mean_delta"] or 0) < 0]
    worse.sort(key=lambda i: (i["change"] != "regressed", i["mean_delta"] or 0.0, i["item_id"]))
    sa, sb = a.summary or {}, b.summary or {}
    ca, cb = a.config or {}, b.config or {}
    return {
        "a": a.id,
        "b": b.id,
        "suite_id": a.suite_id,
        "complete": {"a": bool(sa.get("complete")), "b": bool(sb.get("complete"))},
        "config_differs": any(ca.get(k) != cb.get(k) for k in CONFIG_KEYS),
        "summary": _summary(sa, sb),
        "counts": {c: counts.get(c, 0) for c in CHANGES},
        "items": items,
        "worst": worse[:WORST],
    }
