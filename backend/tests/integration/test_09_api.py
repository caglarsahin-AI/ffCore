"""09 API on a real database (no Langfuse call): read-mode parity, roles, dataset name rule."""

import json
import uuid

import pytest

from tests.integration.runtime_support import definition, seed_run

P = "/api/v1/projects/{}"


@pytest.fixture
def project(make_project):
    return make_project()


@pytest.fixture
def member(client_factory, make_user, project):
    def make(role, access="edit"):
        _, email = make_user(memberships={project: (role, access)})
        return client_factory(email)

    return make


def _suite_and_run(pg, project):
    run_id = seed_run(pg, project, definition())
    version_id = pg.execute(
        "SELECT agent_version_id FROM runs WHERE id = %s", (run_id,)
    ).fetchone()[0]
    suite_id, eval_id = uuid.uuid4(), uuid.uuid4()
    pg.execute(
        "INSERT INTO eval_suites (id, project_id, key, name, langfuse_dataset_name, scorers,"
        " pass_threshold, created_by) VALUES (%s, %s, 'exam', 'Exam', 'p.exam', %s, 0.8, 't')",
        (suite_id, project, json.dumps([{"name": "contains"}])),
    )
    pg.execute(
        "INSERT INTO eval_runs (id, project_id, suite_id, agent_version_id, user_id,"
        " langfuse_run_name, status, item_runs, summary, created_by)"
        " VALUES (%s, %s, %s, %s, %s, 'exam-v1-x', 'completed', %s, %s, 't')",
        (
            eval_id,
            project,
            suite_id,
            version_id,
            uuid.uuid4(),
            json.dumps({"q1": {"runs": [str(run_id)], "scored": True}}),
            json.dumps({"n": 1, "passed": True}),
        ),
    )
    return suite_id, eval_id


def test_09_read_mode_get_parity(pg, member, project):
    suite_id, eval_id = _suite_and_run(pg, project)
    edit, read = member("analyst", "edit"), member("analyst", "read")
    base = P.format(project)
    for path in ("/eval-suites", f"/eval-suites/{suite_id}", f"/eval-suites/{suite_id}/runs",
                 f"/eval-runs/{eval_id}"):  # fmt: skip
        a, b = edit.get(base + path), read.get(base + path)
        assert (a.status_code, b.status_code) == (200, 200), (path, a.text)
        assert a.json() == b.json(), path


def test_09_read_mode_cannot_mutate(pg, member, project):
    suite_id, eval_id = _suite_and_run(pg, project)
    read = member("analyst", "read")
    base = P.format(project)
    assert read.post(f"{base}/eval-runs/{eval_id}/cancel").status_code == 403
    assert read.delete(f"{base}/eval-suites/{suite_id}").status_code == 403


def test_09_other_project_sees_404(pg, member, project, make_project, make_user, client_factory):
    suite_id, eval_id = _suite_and_run(pg, project)
    other = make_project()
    _, email = make_user(memberships={other: ("admin", "edit")})
    stranger = client_factory(email)
    assert stranger.get(f"{P.format(project)}/eval-suites/{suite_id}").status_code == 404
    assert stranger.get(f"{P.format(project)}/eval-runs/{eval_id}").status_code == 404


def test_09_cancel_finished_exam_is_409(pg, member, project):
    _, eval_id = _suite_and_run(pg, project)
    r = member("analyst").post(f"{P.format(project)}/eval-runs/{eval_id}/cancel")
    assert r.status_code == 409 and r.json()["error"]["code"] == "eval_run_finished"
