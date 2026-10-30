"""F2 (ticket triage with an approved draft) and F12 (outage behaviour), plan/18 stage 2.

F2 needs 07 approvals and a triage agent (the fake ticket-desk tool is in the test stack since
18-ticket-desk, auth none: no identity reaches it). F12: what the API can show runs here (a
dropped stream does not cancel the run and resumes after Last-Event-ID; a failing model ends
the run with a code); stopping services needs a Docker socket, so those rows are NOT_RUN until
13b's compose-level runner.
"""

import pytest

PROJECT = "hastane-a"


@pytest.mark.parametrize(
    "criterion",
    [
        "triage class accuracy >= 80 % on tickets/tickets-20.jsonl (labels.json)",
        "send_reply reaches ticket-desk only after approval (/_sent empty before)",
        "PII tickets reach the model masked (fake-llm /_requests)",
    ],
)
def test_18_f2_6_triage_e2e(criterion):
    pytest.skip(f"NOT_RUN: {criterion}; needs 07 approvals and a triage agent")


@pytest.mark.parametrize(
    "criterion",
    [
        "Langfuse stopped: run completes, trace_delivery_failed recorded",
        "Qdrant stopped: search returns a coded error, worker stays healthy",
        "LLM_SLOTS full: run queued, the wait is visible as an event",
        "airgap: provider down, no request to an external host",
    ],
)
def test_18_f12_1_outage(criterion):
    pytest.skip(f"NOT_RUN: {criterion}; service stop needs a compose-level runner (13b)")


def test_18_f12_2_model_down_fails_with_code(login):
    """chat-fail → fake-llm answers 500: the run fails with model_unavailable, no silent answer."""
    analyst = login(PROJECT, "analyst", "edit")
    pid = analyst.project_id(PROJECT)
    run = analyst.settle(pid, analyst.start_run(pid, "e2e-hatali", "Merhaba"))
    assert run.detail["status"] == "failed", run.detail
    assert run.detail["error_code"] == "model_unavailable", run.detail
    assert not run.detail.get("output"), run.detail


def test_18_f12_3_dropped_stream_does_not_cancel_and_resumes(login):
    """The client drops the SSE connection after the first event (06a S8): the run goes on to
    completed, and the stream resumed with Last-Event-ID brings only the later events."""
    analyst = login(PROJECT, "analyst", "edit")
    pid = analyst.project_id(PROJECT)
    run = analyst.start_run(pid, "e2e-yavas", "Merhaba", stop_after=1)
    first = run.events[0]
    assert first["event"] == "progress" and first["id"], first
    run = analyst.settle(pid, run)
    assert run.detail["status"] == "completed", run.detail
    resumed = analyst.stream(pid, run.id, first["id"])
    assert resumed and first["id"] not in {e["id"] for e in resumed}, resumed[:3]
    assert resumed[-1]["event"] == "done", [e["event"] for e in resumed]
