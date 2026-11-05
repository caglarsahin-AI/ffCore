"""09-2 D2: the exam gate on publish (plan/09 Akış 3, KARARLAR "09 Evaluation plan kararları" S2,
"09-1 r1 kararları" NOTE-2, "09-2 plan kararları" S1/S3).

Every live suite bound to the agent needs, for the version being published, a latest completed
exam that passed, is complete and has nothing not run. Otherwise 409 `eval_gate_failed` naming
each suite and why. `force` is admin only, needs `force_reason` and is audited as
`eval_gate_forced`. Rollback is not gated.
"""

import json
import uuid

import pytest

from tests.integration.conftest import audit_rows
from tests.integration.test_06a_agents import TEMPLATE, _base, _model, ollama_32k  # noqa: F401

pytestmark = pytest.mark.usefixtures("ollama_32k")


@pytest.fixture
def project(make_project, pg, app_settings):
    project_id = make_project()
    _model(pg, project_id)
    return project_id


def _agent(client, project):
    base = _base(project)
    agent = client.post(
        base, json={"key": f"a-{uuid.uuid4().hex[:8]}", "name": "A", "model": "chat-default"}
    ).json()
    url = f"{base}/{agent['id']}"
    assert client.put(f"{url}/versions/1", json={"definition": TEMPLATE}).status_code == 200
    return agent["id"], url


def _version_id(pg, agent_id, version=1):
    return pg.execute(
        "SELECT id FROM agent_versions WHERE agent_id = %s AND version = %s", (agent_id, version)
    ).fetchone()[0]


def _suite(pg, project, agent_id, *, key="gate", approve_tools=False):
    suite_id = uuid.uuid4()
    pg.execute(
        "INSERT INTO eval_suites (id, project_id, key, name, agent_id, langfuse_dataset_name,"
        " scorers, pass_threshold, approve_tools, created_by)"
        " VALUES (%s, %s, %s, 'Gate', %s, %s, %s, 0.8, %s, 't')",
        (suite_id, project, key, agent_id, f"p.{key}", json.dumps([{"name": "contains"}]),
         approve_tools),
    )  # fmt: skip
    return suite_id


def _exam(pg, project, suite_id, version_id, *, passed=True, complete=True, not_run=None,
          status="completed", age_s=0):  # fmt: skip
    ev_id = uuid.uuid4()
    summary = {"passed": passed, "complete": complete, "not_run": not_run or {}, "n": 1}
    pg.execute(
        "INSERT INTO eval_runs (id, project_id, suite_id, agent_version_id, user_id,"
        " langfuse_run_name, status, item_runs, summary, config, ended_at, created_by)"
        " VALUES (%s, %s, %s, %s, %s, 'exam-x', %s, '{}', %s, '{}',"
        " now() - make_interval(secs => %s), 't')",
        (ev_id, project, suite_id, version_id, uuid.uuid4(), status, json.dumps(summary), age_s),
    )  # fmt: skip
    return ev_id


@pytest.fixture
def analyst(client_factory, make_user, project):
    _, email = make_user(memberships={project: ("analyst", "edit")})
    return client_factory(email)


@pytest.fixture
def admin(client_factory, make_user, project):
    _, email = make_user(memberships={project: ("admin", "edit")})
    return client_factory(email)


def _gate_error(r, *reasons):
    assert r.status_code == 409, r.text
    err = r.json()["error"]
    assert err["code"] == "eval_gate_failed"
    for reason in reasons:
        assert reason in err["message"], err["message"]
    return err


def test_09_2_gate_without_exam_refuses_publish(pg, analyst, project):
    agent_id, url = _agent(analyst, project)
    _suite(pg, project, agent_id)
    _gate_error(analyst.post(f"{url}/publish", json={"version": 1}), "gate=no_exam")


def test_09_2_gate_needs_passed_complete_and_nothing_not_run(pg, analyst, project):
    agent_id, url = _agent(analyst, project)
    suite_id = _suite(pg, project, agent_id)
    v1 = _version_id(pg, agent_id)
    _exam(pg, project, suite_id, v1, passed=False, age_s=30)
    _gate_error(analyst.post(f"{url}/publish", json={"version": 1}), "gate=not_passed")
    # Passed but one item not run (an approval nobody gave): still not through the gate.
    _exam(pg, project, suite_id, v1, complete=False, not_run={"approval_rejected": 1}, age_s=20)
    _gate_error(analyst.post(f"{url}/publish", json={"version": 1}), "gate=incomplete")
    # A running exam does not count; the latest completed one does.
    _exam(pg, project, suite_id, v1, status="running", age_s=0)
    _exam(pg, project, suite_id, v1, age_s=10)
    assert analyst.post(f"{url}/publish", json={"version": 1}).status_code == 200


def test_09_2_gate_counts_only_the_published_versions_exam(pg, analyst, project):
    agent_id, url = _agent(analyst, project)
    suite_id = _suite(pg, project, agent_id)
    _exam(pg, project, suite_id, _version_id(pg, agent_id))
    assert analyst.post(f"{url}/publish", json={"version": 1}).status_code == 200
    assert analyst.post(f"{url}/versions", json={}).status_code == 201
    _gate_error(analyst.post(f"{url}/publish", json={"version": 2}), "gate=no_exam")


def test_09_2_force_is_admin_only_needs_a_reason_and_is_audited(pg, analyst, admin, project):
    agent_id, url = _agent(analyst, project)
    suite_id = _suite(pg, project, agent_id)
    r = analyst.post(f"{url}/publish", json={"version": 1, "force": True, "force_reason": "demo"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "force_requires_admin"
    r = admin.post(f"{url}/publish", json={"version": 1, "force": True})
    assert r.status_code == 422 and r.json()["error"]["code"] == "force_reason_required"
    r = admin.post(
        f"{url}/publish",
        json={"version": 1, "force": True, "force_reason": "customer demo, exam pending"},
    )
    assert r.status_code == 200, r.text
    ((actor_id, outcome, after),) = audit_rows(pg, "eval_gate_forced", project=project)
    assert outcome == "success" and after["agent_id"] == agent_id
    assert after["reason"] == "customer demo, exam pending"
    assert after["suites"] == [
        {"suite_id": str(suite_id), "key": "gate", "eval_run_id": None, "reason": "no_exam"}
    ]


def test_09_2_reason_without_force_is_refused(analyst, project):
    _, url = _agent(analyst, project)
    r = analyst.post(f"{url}/publish", json={"version": 1, "force_reason": "x"})
    assert r.status_code == 422


def test_09_2_unattended_suite_on_a_version_asking_approval_is_not_gateable(
    pg, analyst, project, monkeypatch
):
    # S1 A: checked at publish, only when the version binds an action that asks for approval.
    from ffcore.evaluation import gate

    agent_id, url = _agent(analyst, project)
    suite_id = _suite(pg, project, agent_id, approve_tools=False)
    _exam(pg, project, suite_id, _version_id(pg, agent_id))

    async def asks(session, project_id, definition):
        return True

    monkeypatch.setattr(gate, "version_asks_approval", asks)
    _gate_error(analyst.post(f"{url}/publish", json={"version": 1}), "gate=suite_not_gateable")
    pg.execute("UPDATE eval_suites SET approve_tools = true WHERE id = %s", (suite_id,))
    assert analyst.post(f"{url}/publish", json={"version": 1}).status_code == 200


def test_09_2_rollback_is_not_gated(pg, analyst, project):
    agent_id, url = _agent(analyst, project)
    assert analyst.post(f"{url}/publish", json={"version": 1}).status_code == 200
    assert analyst.post(f"{url}/versions", json={}).status_code == 201
    assert analyst.post(f"{url}/publish", json={"version": 2}).status_code == 200
    _suite(pg, project, agent_id)  # bound after both were published; v1 has no exam
    r = analyst.post(f"{url}/rollback", json={"version": 1})
    assert r.status_code == 200, r.text


def test_09_2_deleted_suite_does_not_gate(pg, analyst, project):
    agent_id, url = _agent(analyst, project)
    suite_id = _suite(pg, project, agent_id)
    pg.execute("UPDATE eval_suites SET deleted_at = now() WHERE id = %s", (suite_id,))
    assert analyst.post(f"{url}/publish", json={"version": 1}).status_code == 200
