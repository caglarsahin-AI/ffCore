"""10c-2 r2 NOTE-2 `kismi-ozet-500` (KARARLAR "10c-2 r1 kararları"): a stored summary that does not
fit `EvalSummary` (an older shape, a partial write) never turns the exam read into a 500. The
exam is answered with `summary: null` and a warning log `eval_summary_invalid` names the exam and
the missing keys.
"""

import logging
from types import SimpleNamespace

from ffcore.api.eval import run_out
from ffcore.evaluation.engine import summarize


def _row(summary):
    return SimpleNamespace(
        id="00000000-0000-0000-0000-000000000001",
        project_id="00000000-0000-0000-0000-000000000002",
        suite_id="00000000-0000-0000-0000-000000000003",
        agent_version_id="00000000-0000-0000-0000-000000000004",
        langfuse_run_name="exam", status="completed", error_code=None, item_runs={},
        summary=summary, cost_usd=None, started_at=None, ended_at=None,
        created_at="2026-11-18T08:00:00Z",
    )  # fmt: skip


def test_10c2_r2_partial_summary_is_null_and_logged(caplog):
    with caplog.at_level(logging.WARNING):
        out = run_out(_row({"n": 1, "pass_rate": 1.0}))
    assert out.summary is None
    lines = [r.getMessage() for r in caplog.records if "eval_summary_invalid" in r.getMessage()]
    assert len(lines) == 1
    assert "00000000-0000-0000-0000-000000000001" in lines[0]
    assert "scored" in lines[0] and "worst" in lines[0]  # missing keys are named


def test_10c2_r2_wrong_type_summary_is_null_and_logged(caplog):
    good = summarize([], pass_threshold=0.8, warmup_ms=None, latencies_ms=[])
    with caplog.at_level(logging.WARNING):
        out = run_out(_row({**good, "complete": "yes"}))
    assert out.summary is None
    assert any("eval_summary_invalid" in r.getMessage() for r in caplog.records)


def test_10c2_r2_valid_and_missing_summary_log_nothing(caplog):
    good = summarize([], pass_threshold=0.8, warmup_ms=None, latencies_ms=[])
    with caplog.at_level(logging.WARNING):
        assert run_out(_row(good)).summary is not None
        assert run_out(_row(None)).summary is None
    assert not any("eval_summary_invalid" in r.getMessage() for r in caplog.records)
