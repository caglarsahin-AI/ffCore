"""09-2 D2: the exam gate on publish (plan/09 Akış 3, KARARLAR "09 Evaluation plan kararları" S2,
"09-1 r1 kararları" NOTE-2, "09-2 plan kararları" S1/S3).

Every live suite bound to the agent needs, for the version being published, a latest completed
exam that passed, is complete and has nothing not run. Otherwise 409 `eval_gate_failed` naming
each suite and why. `force` is admin only, needs `force_reason` and is audited as
`eval_gate_forced`. Rollback is not gated.
"""

import hashlib
import json
import uuid

import pytest

from tests.integration.conftest import audit_rows
from tests.integration.test_03c_keys import impersonator, owner  # noqa: F401
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


def digest(definition: dict) -> str:
    """The exam's `definition_sha256` (09-2 r1 MAJOR-1), computed here as the spec says:
    sha256 of the definition as canonical JSON (sorted keys, no spaces, UTF-8)."""
    text = json.dumps(definition, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode()).hexdigest()


def exam_config(pg, version_id, **over) -> dict:
    """An exam config as start_eval writes it, for the version's definition as it is now and
    the suite as `_suite` writes it."""
    (definition,) = pg.execute(
        "SELECT definition FROM agent_versions WHERE id = %s", (version_id,)
    ).fetchone()
    config = {"scorers": [{"name": "contains"}], "pass_threshold": 0.8, "repeat": 1,
              "approve_tools": False, "definition_sha256": digest(definition)}  # fmt: skip
    return {**config, **over}


def _exam(pg, project, suite_id, version_id, *, passed=True, complete=True, not_run=None,
          status="completed", age_s=0, config=None):  # fmt: skip
    ev_id = uuid.uuid4()
    summary = {"passed": passed, "complete": complete, "not_run": not_run or {}, "n": 1}
    config = exam_config(pg, version_id) if config is None else config
    pg.execute(
        "INSERT INTO eval_runs (id, project_id, suite_id, agent_version_id, user_id,"
        " langfuse_run_name, status, item_runs, summary, config, ended_at, created_by)"
        " VALUES (%s, %s, %s, %s, %s, 'exam-x', %s, '{}', %s, %s,"
        " now() - make_interval(secs => %s), 't')",
        (ev_id, project, suite_id, version_id, uuid.uuid4(), status, json.dumps(summary),
         json.dumps(config), age_s),
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
    assert r.json()["error"]["code"] == "force_reason_without_force"  # r1 NOTE-15


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


# --- 09-2 r1 MAJOR-1 (KARARLAR "09-2 r1 kararları" A): the gate publishes what was examined -----


def _edit_draft(client, url, prompt="A changed instruction after the exam."):
    r = client.put(f"{url}/versions/1", json={"definition": {**TEMPLATE, "system_prompt": prompt}})
    assert r.status_code == 200, r.text


def test_09_2_r1_major1_draft_edited_after_its_exam_is_stale(pg, analyst, project):
    agent_id, url = _agent(analyst, project)
    suite_id = _suite(pg, project, agent_id)
    v1 = _version_id(pg, agent_id)
    _exam(pg, project, suite_id, v1, age_s=10)
    _edit_draft(analyst, url)
    _gate_error(analyst.post(f"{url}/publish", json={"version": 1}), "gate=stale_exam")
    # A new exam of the edited draft opens the gate; the stale one is no longer the latest.
    _exam(pg, project, suite_id, v1, age_s=0)
    assert analyst.post(f"{url}/publish", json={"version": 1}).status_code == 200


def test_09_2_r1_major1_exam_without_a_definition_digest_is_stale(pg, analyst, project):
    # An exam that cannot show what it examined (no digest) never opens the gate.
    agent_id, url = _agent(analyst, project)
    suite_id = _suite(pg, project, agent_id)
    v1 = _version_id(pg, agent_id)
    config = exam_config(pg, v1)
    del config["definition_sha256"]
    _exam(pg, project, suite_id, v1, config=config)
    _gate_error(analyst.post(f"{url}/publish", json={"version": 1}), "gate=stale_exam")


@pytest.mark.parametrize(
    "change",
    [
        "pass_threshold = 0.9",
        "repeat = 2",
        """scorers = '[{"name": "contains"}, {"name": "regex"}]'""",
    ],
)
def test_09_2_r1_major1_suite_changed_after_the_exam_is_stale(pg, analyst, project, change):
    agent_id, url = _agent(analyst, project)
    suite_id = _suite(pg, project, agent_id)
    _exam(pg, project, suite_id, _version_id(pg, agent_id))
    pg.execute(f"UPDATE eval_suites SET {change} WHERE id = %s", (suite_id,))
    _gate_error(analyst.post(f"{url}/publish", json={"version": 1}), "gate=stale_suite")


def test_09_2_r1_major1_approve_tools_change_is_not_stale(pg, analyst, project):
    # approve_tools is not part of stale_suite: true -> false is suite_not_gateable or an
    # incomplete exam already; false -> true asks nothing new of a passed, complete exam.
    agent_id, url = _agent(analyst, project)
    suite_id = _suite(pg, project, agent_id)
    _exam(pg, project, suite_id, _version_id(pg, agent_id))
    pg.execute("UPDATE eval_suites SET approve_tools = true WHERE id = %s", (suite_id,))
    assert analyst.post(f"{url}/publish", json={"version": 1}).status_code == 200


# --- 09-2 r1 MINOR-1/2/3 ----------------------------------------------------------------------


def test_09_2_r1_minor1_blank_force_reason_is_refused(pg, admin, project):
    _, url = _agent(admin, project)
    r = admin.post(f"{url}/publish", json={"version": 1, "force": True, "force_reason": "   "})
    assert r.status_code == 422 and r.json()["error"]["code"] == "force_reason_required"
    assert audit_rows(pg, "eval_gate_forced", project=project) == []


def test_09_2_r1_minor1_force_reason_is_audited_stripped(pg, analyst, admin, project):
    agent_id, url = _agent(analyst, project)
    _suite(pg, project, agent_id)
    r = admin.post(
        f"{url}/publish", json={"version": 1, "force": True, "force_reason": "  demo day  "}
    )
    assert r.status_code == 200, r.text
    ((_, _, after),) = audit_rows(pg, "eval_gate_forced", project=project)
    assert after["reason"] == "demo day"


def test_09_2_r1_minor2_the_version_names_the_exam_that_opened_the_gate(pg, analyst, project):
    agent_id, url = _agent(analyst, project)
    first, second = _suite(pg, project, agent_id, key="g1"), _suite(pg, project, agent_id, key="g2")
    v1 = _version_id(pg, agent_id)
    _exam(pg, project, first, v1, age_s=20)
    latest = _exam(pg, project, second, v1, age_s=10)
    assert analyst.post(f"{url}/publish", json={"version": 1}).status_code == 200
    (eval_run_id,) = pg.execute(
        "SELECT eval_run_id FROM agent_versions WHERE id = %s", (v1,)
    ).fetchone()
    assert eval_run_id == latest  # several suites: the latest of the exams that passed
    assert analyst.get(f"{url}/versions/1").json()["eval_run_id"] == str(latest)


def test_09_2_r1_minor2_forced_or_ungated_publish_names_no_exam(pg, analyst, admin, project):
    agent_id, url = _agent(analyst, project)
    assert analyst.post(f"{url}/publish", json={"version": 1}).status_code == 200  # no suite
    assert pg.execute(
        "SELECT eval_run_id FROM agent_versions WHERE id = %s", (_version_id(pg, agent_id),)
    ).fetchone() == (None,)
    assert analyst.post(f"{url}/versions", json={}).status_code == 201
    _suite(pg, project, agent_id)
    r = admin.post(f"{url}/publish", json={"version": 2, "force": True, "force_reason": "demo"})
    assert r.status_code == 200, r.text
    assert pg.execute(
        "SELECT eval_run_id FROM agent_versions WHERE id = %s", (_version_id(pg, agent_id, 2),)
    ).fetchone() == (None,)


def test_09_2_r1_minor3_forced_publish_through_a_key_is_audited_with_it(
    request, app, make_user, client_factory, app_settings, pg
):
    # An admin acting through an impersonating API key (03c, K-03c-0006): the forced publish
    # is the user's, with the key's id beside it, as every other audited mutation.
    from tests.integration.test_03c_keys import _client, _token

    project, key = request.getfixturevalue("impersonator")
    _model(pg, project)
    user_id, email = make_user(memberships={project: ("admin", "edit")})
    agent_id, url = _agent(client_factory(email), project)
    _suite(pg, project, agent_id)
    client = _client(app)
    try:
        r = client.post(
            f"{url}/publish",
            json={"version": 1, "force": True, "force_reason": "demo"},
            headers={"Authorization": f"Bearer {key['key']}",
                     "X-On-Behalf-Of": _token(app_settings, user_id, project)},
        )  # fmt: skip
    finally:
        client.__exit__(None, None, None)
    assert r.status_code == 200, r.text
    row = pg.execute(
        "SELECT actor_id, via_key_id FROM audit_events WHERE action = 'eval_gate_forced'"
        " AND project_id = %s",
        (str(project),),
    ).fetchone()
    assert row == (str(user_id), uuid.UUID(key["id"]))


# --- 09-2 r2 MINOR-1/5 (KARARLAR "09-2 r2 ekleri") -------------------------------------------


def _exam_status(pg, ev_id):
    return pg.execute(
        "SELECT status, error_code, ended_at IS NOT NULL FROM eval_runs WHERE id = %s", (ev_id,)
    ).fetchone()


def test_09_2_r2_minor1_editing_a_draft_ends_its_running_exams(pg, analyst, project):
    # Change and change back between two advancer ticks: the item runs may have loaded B while
    # the digest says A again. The PUT itself ends the version's queued and running exams.
    agent_id, url = _agent(analyst, project)
    suite_id = _suite(pg, project, agent_id)
    v1 = _version_id(pg, agent_id)
    running = _exam(pg, project, suite_id, v1, status="running")
    queued = _exam(pg, project, suite_id, v1, status="queued")
    done = _exam(pg, project, suite_id, v1, age_s=30)
    _edit_draft(analyst, url, prompt="B")
    _edit_draft(analyst, url, prompt=TEMPLATE["system_prompt"])  # back to A
    assert _exam_status(pg, running) == ("failed", "definition_changed", True)
    assert _exam_status(pg, queued) == ("failed", "definition_changed", True)
    assert _exam_status(pg, done)[0] == "completed"  # a finished exam is the gate's to judge


def test_09_2_r2_minor1_saving_the_same_definition_keeps_the_exam(pg, analyst, project):
    agent_id, url = _agent(analyst, project)
    suite_id = _suite(pg, project, agent_id)
    running = _exam(pg, project, suite_id, _version_id(pg, agent_id), status="running")
    _edit_draft(analyst, url, prompt=TEMPLATE["system_prompt"])  # unchanged
    assert _exam_status(pg, running) == ("running", None, False)


def test_09_2_r2_minor5_publish_and_draft_edit_lock_the_agent_row(pg, analyst, project):
    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    agent_id, url = _agent(analyst, project)
    seen: list[str] = []

    def grab(conn, cursor, statement, *args):
        seen.append(statement)

    def locks() -> int:
        return sum(1 for s in seen if "FROM agents" in s and "FOR UPDATE" in s)

    event.listen(Engine, "before_cursor_execute", grab)
    try:
        _edit_draft(analyst, url, prompt="locked edit")
        after_put = locks()
        assert analyst.post(f"{url}/publish", json={"version": 1}).status_code == 200
        after_publish = locks()
    finally:
        event.remove(Engine, "before_cursor_execute", grab)
    assert after_put >= 1 and after_publish > after_put
