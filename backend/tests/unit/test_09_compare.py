"""09-2 D1: comparing two exams of one suite (plan/09 Akış 2, KARARLAR "09-2 plan kararları" S2).

Only the local results are read (`eval_runs.item_runs[*].result`, the same `combine` the summary
uses); no Langfuse call. Both exams must be `completed` and of the same suite; an item not run
in either is `not_comparable`, never guessed.
"""

import uuid
from types import SimpleNamespace

import pytest

from ffcore.evaluation.compare import CompareError, compare
from ffcore.evaluation.engine import item_result
from ffcore.evaluation.runner import _dump
from ffcore.evaluation.scorers import Score
from tests.unit.test_09_engine import _facts, _item

SUITE = uuid.uuid4()
CONFIG = {"scorers": [{"name": "contains"}], "pass_threshold": 0.5, "repeat": 1,
          "approve_tools": False}  # fmt: skip


def _entry(i, *, value=None, not_run=None):
    item = _item(i)
    if not_run:
        facts = _facts(status="cancelled", error_code=not_run, outcome_label=None)
        res = item_result(item, facts, [], "")
    else:
        res = item_result(item, _facts(), [Score("contains", value, value >= 0.5)], "")
    return {"item": item, "runs": ["r"], "scored": True,
            "result": {"runs": [{"run_id": "r", **_dump(res)}]}}  # fmt: skip


def _exam(entries, *, status="completed", suite=SUITE, config=CONFIG, complete=True):
    plan = {e["item"]["id"]: e for e in entries}
    return SimpleNamespace(
        id=uuid.uuid4(), suite_id=suite, status=status, config=config, item_runs=plan,
        summary={"pass_rate": sum(1 for e in entries if e["result"]["runs"][0]["passed"])
                 / max(len(entries), 1), "complete": complete, "scored": len(entries),
                 "passed_items": 0, "scores": {}, "outcomes": {}, "not_run": {}},
    )  # fmt: skip


def test_09_2_compare_classifies_every_item():
    a = _exam([_entry("q1", value=1.0), _entry("q2", value=0.0), _entry("q3", value=1.0),
               _entry("q4", value=1.0), _entry("q5", value=1.0)])  # fmt: skip
    b = _exam([_entry("q1", value=1.0), _entry("q2", value=1.0), _entry("q3", value=0.0),
               _entry("q4", not_run="eval_waiting_user"), _entry("q6", value=1.0)])  # fmt: skip
    out = compare(a, b)
    change = {i["item_id"]: i["change"] for i in out["items"]}
    assert change == {"q1": "same", "q2": "fixed", "q3": "regressed", "q4": "not_comparable",
                      "q5": "only_a", "q6": "only_b"}  # fmt: skip
    assert out["counts"] == {"same": 1, "fixed": 1, "regressed": 1, "not_comparable": 1,
                             "only_a": 1, "only_b": 1}  # fmt: skip
    q4 = next(i for i in out["items"] if i["item_id"] == "q4")
    assert q4["b"]["passed"] is None and q4["b"]["note"] == "waiting_user"
    assert q4["mean_delta"] is None  # nothing guessed for the not-run side
    q3 = next(i for i in out["items"] if i["item_id"] == "q3")
    assert q3["mean_delta"] == -1.0


def test_09_2_compare_worst_ten_regressions_first():
    a = _exam([_entry(f"q{i:02d}", value=1.0) for i in range(14)])
    b = _exam([_entry(f"q{i:02d}", value=0.0 if i < 12 else 1.0) for i in range(14)])
    out = compare(a, b)
    assert len(out["worst"]) == 10
    assert all(i["change"] == "regressed" for i in out["worst"])
    assert [i["item_id"] for i in out["worst"]] == [f"q{i:02d}" for i in range(10)]


def test_09_2_compare_summary_diff_complete_and_config():
    a = _exam([_entry("q1", value=1.0), _entry("q2", value=0.0)])
    b = _exam([_entry("q1", value=1.0), _entry("q2", value=1.0)], complete=False,
              config={**CONFIG, "pass_threshold": 0.8})  # fmt: skip
    out = compare(a, b)
    assert out["summary"]["pass_rate"] == {"a": 0.5, "b": 1.0, "delta": 0.5}
    assert out["complete"] == {"a": True, "b": False}
    assert out["config_differs"] is True
    assert compare(a, a)["config_differs"] is False


def test_09_2_compare_needs_same_suite_and_finished_exams():
    a = _exam([_entry("q1", value=1.0)])
    with pytest.raises(CompareError) as err:
        compare(a, _exam([_entry("q1", value=1.0)], suite=uuid.uuid4()))
    assert err.value.reason == "different_suite"
    with pytest.raises(CompareError) as err:
        compare(a, _exam([_entry("q1", value=1.0)], status="running"))
    assert err.value.reason == "not_completed"
