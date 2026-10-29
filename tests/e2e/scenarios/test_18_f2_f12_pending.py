"""F2 (ticket triage with an approved draft) and F12 (outage behaviour), plan/18.

Both need pieces that are not in the stack yet: F2 the 07 approvals and a triage agent (the
fake ticket-desk tool is in the test stack since 18-ticket-desk, auth none: no identity reaches
it); F12 stops services, which the tests cannot do without a Docker socket, so its runner is a
compose-level script (13b decides).
The criteria are listed so the NOT_RUN table in the PR stays complete.
"""

import pytest


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
        "fake-llm stopped: run failed + model_unavailable, no external request",
        "Langfuse stopped: run completes, trace_delivery_failed recorded",
        "Qdrant stopped: search returns a coded error, worker stays healthy",
        "LLM_SLOTS full: run queued, the wait is visible as an event",
    ],
)
def test_18_f12_1_outage(criterion):
    pytest.skip(f"NOT_RUN: {criterion}; service stop needs a compose-level runner (13b)")
