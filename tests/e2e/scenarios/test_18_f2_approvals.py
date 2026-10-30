"""F2 stage 3 (07 merged, K-SEN-0036): the ticket assistant's reply waits in 07's approval queue
and only a console decision moves it on. Agent `e2e-bilet` (seed.py) calls ticket-desk's
send_reply through fake-llm's tool mode; the decision goes through 07's endpoints, not 06a's
resume. Whether the model then *says* it was declined is the model's answer: NOT_RUN with
"gerçek model"; that the model is told is checked on the request it gets.
"""

import json
import os

import httpx
import pytest

PROJECT = "hastane-a"
TICKET_DESK_URL = os.environ.get("E2E_TICKET_DESK_URL", "http://ticket-desk:8000")
ACTION = "ticket-desk__send_reply"


def _desk(path: str, method: str = "GET"):
    r = httpx.request(method, TICKET_DESK_URL + path, timeout=10)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture
def waiting(login):
    """A run of e2e-bilet waiting for its send_reply approval, and that approval (07)."""
    analyst = login(PROJECT, "analyst", "edit")
    pid = analyst.project_id(PROJECT)
    _desk("/_reset", "POST")
    run = analyst.start_run(pid, "e2e-bilet", "tkt-001 için yanıt gönder.")
    assert run.events[-1]["event"] == "approval_required", run.names()
    assert analyst.settle(pid, run).detail["status"] == "waiting_approval"
    queue = analyst.get(f"/api/v1/projects/{pid}/approvals", params={"status": "pending"})
    assert queue.status_code == 200, queue.text
    mine = [a for a in queue.json()["data"] if a["run_id"] == run.id]
    assert len(mine) == 1, queue.json()
    return analyst, pid, run, mine[0]


def test_18_f2_8_reply_waits_in_the_queue(waiting, login):
    analyst, pid, _, approval = waiting
    assert approval["action"] == ACTION and approval["tool_key"] == "ticket-desk"
    assert approval["arguments"]["ticket_id"] == "tkt-001", approval["arguments"]
    assert approval["assigned_role"] == "analyst" and approval["can_decide"] is True
    count = analyst.get(f"/api/v1/projects/{pid}/approvals/count").json()
    assert count["status"] == "pending" and count["count"] >= 1
    assert _desk("/_sent") == []  # nothing reached the ticket system yet
    reader = login(PROJECT, "admin", "read")
    seen = reader.get(f"/api/v1/projects/{pid}/approvals/{approval['id']}")
    assert seen.status_code == 200 and seen.json()["can_decide"] is False
    refused = reader.post(f"/api/v1/projects/{pid}/approvals/{approval['id']}/approve", json={})
    assert refused.status_code == 403, refused.text
    assert _desk("/_sent") == []


def test_18_f2_9_console_approval_sends_the_reply(waiting):
    analyst, pid, run, approval = waiting
    decided = analyst.post(
        f"/api/v1/projects/{pid}/approvals/{approval['id']}/approve", json={"note": "uygun"}
    )
    assert decided.status_code == 200, decided.text
    body = decided.json()
    assert body["status"] == "approved" and body["resolved_by"], body
    rest = analyst.stream(pid, run.id, body["stream_after"])
    assert rest and rest[-1]["event"] == "done", [e["event"] for e in rest]
    run = analyst.settle(pid, run)
    assert run.detail["status"] == "completed", run.detail
    sent = _desk("/_sent")
    assert [s["ticket_id"] for s in sent] == ["tkt-001"], sent
    again = analyst.post(f"/api/v1/projects/{pid}/approvals/{approval['id']}/approve", json={})
    assert again.status_code == 409, again.text  # decided once
    assert len(_desk("/_sent")) == 1


def test_18_f2_10_rejection_sends_nothing_and_tells_the_model(waiting, fake_llm):
    analyst, pid, run, approval = waiting
    fake_llm.reset()
    decided = analyst.post(
        f"/api/v1/projects/{pid}/approvals/{approval['id']}/reject", json={"note": "e2e ret"}
    )
    assert decided.status_code == 200, decided.text
    assert decided.json()["status"] == "rejected"
    run = analyst.settle(pid, run)
    assert run.detail["status"] == "completed", run.detail
    assert _desk("/_sent") == []
    told = json.dumps(fake_llm.requests(), ensure_ascii=False)
    assert "The approver rejected this action. Comment: e2e ret" in told
    events = analyst.run_events(pid, run.id)
    resolved = [e["payload"] for e in events if e["type"] == "approval_resolved"]
    assert [r["decision"] for r in resolved] == ["rejected"], resolved


def test_18_f2_10b_rejected_run_is_declined():
    pytest.skip(
        "NOT_RUN: gerçek model gerekir; outcome_label=declined the model's own reply after the "
        "rejection (fake-llm answers 'hello …', DECLINE_PATTERN does not match)"
    )
