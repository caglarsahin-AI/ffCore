"""F1 (sourced document assistant) and F3 (read-only data questions), plan/18.

The exam scores themselves (≥ 80 %) come from 13b's `make eval` on Langfuse datasets; these
tests check the behaviour the score cannot show: every answer carries sources, an unanswerable
question is declined, and no disguised write gets past mcp-sql.
"""

import pytest

from .conftest import load

PROJECT = "hastane-a"


@pytest.fixture(scope="module")
def analyst(login):
    return login(PROJECT, "analyst", "edit")


def test_18_f1_1_answer_has_sources(analyst):
    pid = analyst.project_id(PROJECT)
    item = next(i for i in load("eval/sozlesme-33.json") if i["metadata"]["answerable"])
    run = analyst.settle(pid, analyst.start_run(pid, "sozlesme-asistani", item["input"]["message"]))
    assert run.detail["status"] == "completed", run.detail
    assert run.detail["outcome_label"] == "answered"
    assert "sources" in run.names(), run.names()
    sources = next(e["data"] for e in run.events if e["event"] == "sources")
    assert sources, "answered without sources (F1: no unsourced answer)"


def test_18_f1_2_unanswerable_is_declined(analyst):
    pid = analyst.project_id(PROJECT)
    item = next(i for i in load("eval/sozlesme-33.json") if not i["metadata"]["answerable"])
    run = analyst.settle(pid, analyst.start_run(pid, "sozlesme-asistani", item["input"]["message"]))
    # K-06a-0004: "not found" is completed + outcome_label=declined, not a failure
    assert run.detail["status"] == "completed", run.detail
    assert run.detail["outcome_label"] == "declined"


def test_18_f3_8_sql_question_one_call(analyst):
    """One sql-20 question end to end: a single run_sql call, approved, the expected number in
    the answer. The full 20-question score is `make eval` (13b)."""
    pytest.skip("NOT_RUN: needs 07 (run_sql is an approved action) and 05a's mcp-sql in the stack")


@pytest.mark.parametrize("attempt", load("eval/sql-write-attempts.json"), ids=lambda a: a["id"])
def test_18_f3_9_write_attempt_refused(analyst, attempt):
    """mcp-sql refuses each attempt with its code over the real chain and the demo DB is
    unchanged (row counts are checked by the 13b fixture that owns the demo DB). The codes
    themselves are proven against the merged validator by test_18td_12 (K-SEN-0002 cond. 2)."""
    pytest.skip("NOT_RUN: needs 13b's demo DB fixture in the e2e stack")
