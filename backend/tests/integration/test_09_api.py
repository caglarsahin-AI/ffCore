"""09 API on a real database (no Langfuse call): read-mode parity, roles, dataset name rule."""

import json
import uuid

import pytest

from ffcore.evaluation.engine import summarize
from tests.integration.runtime_support import definition, seed_run

P = "/api/v1/projects/{}"


def exam_summary(**over) -> dict:
    """A summary as the runner writes it (summarize() output; EvalSummary since 10c-2 D8)."""
    return {**summarize([], pass_threshold=0.8, warmup_ms=None, latencies_ms=[]), **over}


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
        " langfuse_run_name, status, item_runs, summary, config, created_by)"
        " VALUES (%s, %s, %s, %s, %s, 'exam-v1-x', 'completed', %s, %s, '{}', 't')",
        (
            eval_id,
            project,
            suite_id,
            version_id,
            uuid.uuid4(),
            json.dumps({"q1": {"runs": [str(run_id)], "scored": True}}),
            json.dumps(exam_summary(n=1, scored=1, passed_items=1, pass_rate=1.0, passed=True)),
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


def test_09_start_with_another_projects_version_is_the_same_404(
    pg, app, project, make_project, make_user, client_factory
):
    # r1 NOTE-6: a version of another project answers like a missing one.
    from ffcore.api.eval import langfuse_dependency

    suite_id, _ = _suite_and_run(pg, project)
    other = make_project()
    foreign = pg.execute(
        "SELECT agent_version_id FROM runs WHERE id = %s", (seed_run(pg, other, definition()),)
    ).fetchone()[0]
    _, email = make_user(memberships={project: ("analyst", "edit")})
    client = client_factory(email)
    app.dependency_overrides[langfuse_dependency] = lambda: object()
    try:
        base = f"{P.format(project)}/eval-suites/{suite_id}/run"
        a = client.post(f"{base}?agent_version_id={foreign}")
        b = client.post(f"{base}?agent_version_id={uuid.uuid4()}")
    finally:
        app.dependency_overrides.pop(langfuse_dependency, None)
    assert (a.status_code, b.status_code) == (404, 404)
    assert a.json()["error"]["code"] == b.json()["error"]["code"]


def test_09_r5_start_plan_longer_than_a_tick_is_422_over_http(
    pg, app, project, make_user, client_factory
):
    # r5 NOTE-2: the start refusal over HTTP, before Langfuse is asked anything.
    from ffcore.api.eval import langfuse_dependency

    run_id = seed_run(pg, project, definition())
    version_id = pg.execute(
        "SELECT agent_version_id FROM runs WHERE id = %s", (run_id,)
    ).fetchone()[0]
    suite_id = uuid.uuid4()
    pg.execute(
        "INSERT INTO eval_suites (id, project_id, key, name, langfuse_dataset_name, scorers,"
        " pass_threshold, repeat, created_by)"
        " VALUES (%s, %s, 'judged', 'Judged', 'p.judged', %s, 0.8, 10, 't')",
        (suite_id, project, json.dumps([{"name": "llm_judge"}])),
    )
    _, email = make_user(memberships={project: ("analyst", "edit")})
    client = client_factory(email)

    class _NoLangfuse:
        async def items(self, name):
            raise AssertionError("refused before the dataset is read")

    app.dependency_overrides[langfuse_dependency] = lambda: _NoLangfuse()
    try:
        r = client.post(
            f"{P.format(project)}/eval-suites/{suite_id}/run?agent_version_id={version_id}"
        )
    finally:
        app.dependency_overrides.pop(langfuse_dependency, None)
    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == "eval_plan_exceeds_tick"


def _scored_exam(pg, project, suite_id, version_id, passed: dict):
    """A completed exam whose item results are given as {item_id: passed}."""
    ev_id = uuid.uuid4()
    plan = {
        i: {
            "item": {"id": i, "input": {"message": i, "variables": {}},
                     "expectedOutput": {"must_contain": ["x"]},
                     "metadata": {"style": "dogrudan", "answerable": True}},
            "runs": ["r"],
            "scored": True,
            "result": {"runs": [{"run_id": "r", "outcome": "answered", "passed": ok, "note": "",
                                  "scores": [{"name": "contains", "value": 1.0 if ok else 0.0,
                                              "passed": ok, "status": "ok", "comment": ""}]}]},
        }
        for i, ok in passed.items()
    }  # fmt: skip
    pg.execute(
        "INSERT INTO eval_runs (id, project_id, suite_id, agent_version_id, user_id,"
        " langfuse_run_name, status, item_runs, summary, config, created_by)"
        " VALUES (%s, %s, %s, %s, %s, 'exam-x', 'completed', %s, %s, %s, 't')",
        (ev_id, project, suite_id, version_id, uuid.uuid4(), json.dumps(plan),
         json.dumps(exam_summary(n=len(passed), pass_rate=0.5, scored=len(passed))),
         json.dumps({"scorers": [{"name": "contains"}], "pass_threshold": 0.8, "repeat": 1,
                     "approve_tools": False})),
    )  # fmt: skip
    return ev_id


def test_09_2_compare_over_http_and_read_mode(pg, member, project):
    suite_id, _ = _suite_and_run(pg, project)
    version_id = pg.execute(
        "SELECT agent_version_id FROM eval_runs WHERE suite_id = %s", (suite_id,)
    ).fetchone()[0]
    a = _scored_exam(pg, project, suite_id, version_id, {"q1": True, "q2": False})
    b = _scored_exam(pg, project, suite_id, version_id, {"q1": False, "q2": True})
    edit, read = member("analyst", "edit"), member("analyst", "read")
    r = read.get(f"{P.format(project)}/eval-runs/compare?a={a}&b={b}")
    assert r.status_code == 200, r.text
    # 09-2 r1 MAJOR-2: the route is out of the 03a scan (it needs two exams); parity is here.
    assert edit.get(f"{P.format(project)}/eval-runs/compare?a={a}&b={b}").content == r.content
    body = r.json()
    assert {i["item_id"]: i["change"] for i in body["items"]} == {"q1": "regressed", "q2": "fixed"}
    assert body["worst"][0]["item_id"] == "q1" and body["complete"] == {"a": True, "b": True}


def test_09_2_r1_major2_bare_compare_is_the_same_422_in_both_modes(member, project):
    # KARARLAR "09-2 r1 kararları" MAJOR-2 A: two required parameters; a call without them is
    # a 422 in either mode, the same body (no empty 200: fail-loud).
    url = f"{P.format(project)}/eval-runs/compare"
    edit, read = member("analyst", "edit").get(url), member("analyst", "read").get(url)
    assert edit.status_code == 422, edit.text
    assert (read.status_code, read.content) == (edit.status_code, edit.content)


def test_09_2_compare_other_suite_is_422(pg, member, project):
    suite_a, _ = _suite_and_run(pg, project)
    version_id = pg.execute(
        "SELECT agent_version_id FROM eval_runs WHERE suite_id = %s", (suite_a,)
    ).fetchone()[0]
    suite_b = uuid.uuid4()
    pg.execute(
        "INSERT INTO eval_suites (id, project_id, key, name, langfuse_dataset_name, scorers,"
        " pass_threshold, created_by) VALUES (%s, %s, 'other', 'O', 'p.other', %s, 0.8, 't')",
        (suite_b, project, json.dumps([{"name": "contains"}])),
    )
    a = _scored_exam(pg, project, suite_a, version_id, {"q1": True})
    b = _scored_exam(pg, project, suite_b, version_id, {"q1": True})
    r = member("analyst").get(f"{P.format(project)}/eval-runs/compare?a={a}&b={b}")
    assert r.status_code == 422 and r.json()["error"]["code"] == "eval_runs_not_comparable"


def test_09_2_r3n11_patch_checks_scorers_and_delete_audits_the_suite(pg, member, project):
    # FOLLOWUP-176 (r3 NOTE-11): r1 MINOR-7 had no HTTP test.
    from tests.integration.conftest import audit_rows

    suite_id, _ = _suite_and_run(pg, project)
    client = member("analyst")
    base = f"{P.format(project)}/eval-suites/{suite_id}"
    bad = client.patch(base, json={"scorers": [{"name": "no_such_scorer"}]})
    assert bad.status_code == 422
    assert client.patch(base, json={"pass_threshold": None}).status_code == 422
    assert client.delete(base).status_code == 204
    rows = pg.execute(
        "SELECT resource_id FROM audit_events WHERE action = %s AND project_id = %s",
        ("delete_eval_suite", project),
    ).fetchall()
    assert [r[0] for r in rows] == [str(suite_id)], audit_rows


def test_10c1_r2_exam_stream_is_not_compressed_or_buffered(pg, member, project):
    # 10c-1 r2 (K-10C1-0008): the console's proxy gzip-buffered the exam stream until it ended.
    _, eval_id = _suite_and_run(pg, project)
    with member("analyst", "read").stream(
        "GET", f"{P.format(project)}/eval-runs/{eval_id}/stream"
    ) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        assert r.headers["cache-control"] == "no-cache, no-transform"
        assert r.headers["x-accel-buffering"] == "no"
        text = "".join(r.iter_text())
    assert "event: done" in text
