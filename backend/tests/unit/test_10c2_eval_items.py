"""10c-2 D8 (FOLLOWUP-185): the exam's item table and the typed summary.

`item_rows` reads only the exam's own results (`eval_runs.item_runs`), combined per item with the
same `combine` the summary and compare use; items are ordered failed, not run, passed, not yet
scored, then by id. `EvalSummary` is the contract of `summarize()`: every key it writes, typed.
"""

from types import SimpleNamespace

import pytest

from ffcore.api.eval_schemas import EvalRunItem, EvalSummary
from ffcore.evaluation.engine import item_result, summarize
from ffcore.evaluation.items import ITEM_STATUSES, item_rows, select_rows
from ffcore.evaluation.runner import _dump, combine
from ffcore.evaluation.scorers import Score
from tests.unit.test_09_engine import _facts, _item


def _run(res, run_id="r"):
    return {"run_id": run_id, **_dump(res)}


def _entry(i, *values, not_run=None, scored=True):
    item = _item(i)
    if not scored:
        return {"item": item, "runs": [], "scored": False, "attempts": 0}
    if not_run:
        facts = _facts(status="cancelled", error_code=not_run, outcome_label=None)
        runs = [_run(item_result(item, facts, [], ""))]
    else:
        runs = [
            _run(item_result(item, _facts(), [Score("contains", v, v >= 0.5)], ""), f"r{n}")
            for n, v in enumerate(values)
        ]
    return {"item": item, "runs": [r["run_id"] for r in runs], "scored": True,
            "attempts": len(runs), "result": {"runs": runs}}  # fmt: skip


def _plan(*entries):
    return {e["item"]["id"]: e for e in entries}


PLAN = _plan(
    _entry("q1", 1.0),
    _entry("q2", 0.0),
    _entry("q3", not_run="eval_waiting_user"),
    _entry("q4", scored=False),
    _entry("q0", 1.0),
    _entry("q5", 0.2),
)


def test_10c2_items_ordered_failed_not_run_passed_pending_then_id():
    rows = item_rows(PLAN)
    assert [r["item_id"] for r in rows] == ["q2", "q5", "q3", "q0", "q1", "q4"]
    by_id = {r["item_id"]: r for r in rows}
    assert by_id["q2"]["passed"] is False and by_id["q2"]["mean"] == 0.0
    assert by_id["q3"]["passed"] is None and by_id["q3"]["note"] == "waiting_user"
    assert by_id["q4"]["scored"] is False and by_id["q4"]["scores"] == []
    assert by_id["q1"]["scores"][0] == {
        "name": "contains", "value": 1.0, "passed": True, "status": "ok", "comment": ""
    }  # fmt: skip
    assert by_id["q1"]["style"] == "dogrudan" and by_id["q1"]["run_ids"] == ["r0"]
    for row in rows:
        EvalRunItem.model_validate(row)


@pytest.mark.parametrize(
    ("status", "ids"),
    [
        ("all", ["q2", "q5", "q3", "q0", "q1", "q4"]),
        ("failed", ["q2", "q5"]),
        ("not_run", ["q3"]),
        ("passed", ["q0", "q1"]),
    ],
)
def test_10c2_items_status_filter(status, ids):
    assert [r["item_id"] for r in select_rows(item_rows(PLAN), status)] == ids


def test_10c2_items_status_values_are_closed():
    assert ITEM_STATUSES == ("all", "failed", "passed", "not_run")
    with pytest.raises(ValueError):
        select_rows(item_rows(PLAN), "pending")


def test_10c2_items_repeats_are_combined_like_the_summary():
    rows = item_rows(_plan(_entry("q1", 1.0, 0.0, 1.0)))
    assert rows[0]["passed"] is True  # most decided repeats pass (runner.combine)
    assert rows[0]["attempts"] == 3 and rows[0]["run_ids"] == ["r0", "r1", "r2"]
    assert rows[0]["mean"] == pytest.approx(0.6667, abs=1e-4)


def test_10c2_items_of_an_empty_exam():
    assert item_rows({}) == [] and item_rows(None) == []


def _summary(plan):
    return [combine(e["item"], e["result"]["runs"]) for e in plan.values() if e.get("result")]


@pytest.mark.parametrize(
    ("results", "warmup", "latencies"),
    [
        ([], None, []),
        ("plan", 1200, [800, 900, 1500]),
    ],
)
def test_10c2_summarize_output_is_exactly_the_eval_summary_schema(results, warmup, latencies):
    if results == "plan":
        results = _summary(PLAN)
    out = summarize(results, pass_threshold=0.8, warmup_ms=warmup, latencies_ms=latencies)
    # Every key summarize() writes is in the contract and nothing else: a new key is a contract
    # change (09.yaml, gen:api), never a silent extra.
    assert set(out) == set(EvalSummary.model_fields)
    typed = EvalSummary.model_validate(out)
    assert typed.model_dump(mode="json") == out


def test_10c2_eval_summary_rejects_a_partial_summary():
    with pytest.raises(ValueError):
        EvalSummary.model_validate({"n": 1, "passed": True})


def test_10c2_run_out_types_the_summary():
    from ffcore.api.eval import run_out

    out = summarize(_summary(PLAN), pass_threshold=0.8, warmup_ms=None, latencies_ms=[])
    row = SimpleNamespace(
        id="00000000-0000-0000-0000-000000000001",
        project_id="00000000-0000-0000-0000-000000000002",
        suite_id="00000000-0000-0000-0000-000000000003",
        agent_version_id="00000000-0000-0000-0000-000000000004",
        langfuse_run_name="exam", status="completed", error_code=None, item_runs=PLAN,
        summary=out, cost_usd=None, started_at=None, ended_at=None,
        created_at="2026-11-17T08:00:00Z",
    )  # fmt: skip
    assert isinstance(run_out(row).summary, EvalSummary)
