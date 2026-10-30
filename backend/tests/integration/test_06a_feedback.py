"""06a F9 (K-06a-0005): expert feedback on a run, and the "pending" list."""

import pytest

from tests.integration.conftest import audit_rows
from tests.integration.runs_fixtures import *  # noqa: F403 - fixtures
from tests.integration.runs_fixtures import InlineQueue, post_run, publish
from tests.integration.runtime_support import (
    Ports,
    ScriptedModel,
    ScriptedRetriever,
    definition,
    source,
    turn,
)


@pytest.fixture
def completed(analyst, pg, harness, use_queue):
    project_id, client = analyst
    publish(pg, project_id, definition())
    use_queue(
        InlineQueue(
            harness, Ports(ScriptedModel(turn("30 gün [1].")), ScriptedRetriever([source()]))
        )
    )
    run_id = post_run(client, project_id)[0][2]["run_id"]
    return project_id, client, run_id


def _feedback(pg, run_id):
    return pg.execute(
        "SELECT feedback FROM messages WHERE run_id = %s AND role = 'assistant'", (run_id,)
    ).fetchone()[0]


def test_06a_18_feedback_stored_audited_and_reported(completed, pg):
    project_id, client, run_id = completed
    response = client.post(
        f"/api/v1/projects/{project_id}/runs/{run_id}/feedback",
        json={"vote": "partial", "note": "Madde numarası eksik."},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["vote"] == "partial" and body["run_id"] == run_id
    # The score goes to Langfuse when the run has a trace; delivery itself is the SDK's
    # (a failure is the 02 log line trace_delivery_failed, the request stays 200).
    trace_id = pg.execute("SELECT langfuse_trace_id FROM runs WHERE id = %s", (run_id,)).fetchone()[
        0
    ]
    assert body["score_sent"] is (trace_id is not None)
    stored = _feedback(pg, run_id)
    assert (stored["vote"], stored["note"]) == ("partial", "Madde numarası eksik.")
    assert stored["by"] and stored["at"]
    assert audit_rows(pg, "give_feedback", "success")


def test_06a_18_feedback_needs_write_access(completed, make_user, client_factory, pg):
    project_id, _, run_id = completed
    _, reader = make_user(memberships={project_id: ("analyst", "read")})
    response = client_factory(reader).post(
        f"/api/v1/projects/{project_id}/runs/{run_id}/feedback", json={"vote": "correct"}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "read_only_access"
    assert _feedback(pg, run_id) is None


def test_06a_18_feedback_vote_is_a_closed_list(completed):
    project_id, client, run_id = completed
    url = f"/api/v1/projects/{project_id}/runs/{run_id}/feedback"
    assert client.post(url, json={"vote": "great"}).status_code == 422
    assert client.post(url, json={"vote": "wrong", "note": "x" * 2001}).status_code == 422


def test_06a_18_feedback_only_on_completed_runs(analyst, pg, harness, use_queue):
    project_id, client = analyst
    publish(pg, project_id, definition())
    queue = use_queue(InlineQueue(harness, Ports(ScriptedModel()), run_now=False))
    with client.stream(
        "POST", f"/api/v1/projects/{project_id}/agents/asistan/runs", json={"input": "q"}
    ) as response:
        next(response.iter_lines())
    run_id = queue.jobs[0][0]
    response = client.post(
        f"/api/v1/projects/{project_id}/runs/{run_id}/feedback", json={"vote": "correct"}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "run_not_completed"


def test_06a_18_pending_lists_only_runs_without_feedback(completed):
    project_id, client, run_id = completed
    base = f"/api/v1/projects/{project_id}/runs"
    pending = client.get(base, params={"feedback": "pending"}).json()["items"]
    assert [r["id"] for r in pending] == [run_id]
    client.post(f"{base}/{run_id}/feedback", json={"vote": "correct"})
    assert client.get(base, params={"feedback": "pending"}).json()["items"] == []
    given = client.get(base, params={"feedback": "given"}).json()["items"]
    assert [r["id"] for r in given] == [run_id] and given[0]["feedback"]["vote"] == "correct"
