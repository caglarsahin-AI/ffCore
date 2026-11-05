"""09-2 D3: an exam item from a run (plan/09 Akış 4, KARARLAR "09-2 plan kararları").

POST /projects/{pid}/eval-suites/{id}/items/from-run/{run_id}: the run's question becomes an
item of the suite's Langfuse dataset with the expected answer the caller gives. The question
goes through the agent's egress policy first (masked; with GUARDRAIL_EGRESS_NER=false the
regex categories only); a blocked one is 422 `run_input_blocked`. The run is read with the run
API's own rule (a `user` reads only their runs). Audited without content.
"""

import json
import uuid

import pytest

from tests.integration.conftest import audit_rows
from tests.integration.runtime_support import definition, seed_run

P = "/api/v1/projects/{}"
TC = "10000000146"  # a checksum-valid TR identity number (synthetic)


@pytest.fixture
def project(make_project):
    return make_project()


class _Langfuse:
    def __init__(self):
        self.items = []

    async def upsert_item(self, dataset, item_id, **kw):
        self.items.append({"dataset": dataset, "id": item_id, **kw})
        return {"id": item_id}


@pytest.fixture
def langfuse(app):
    from ffcore.api.eval import langfuse_dependency

    fake = _Langfuse()
    app.dependency_overrides[langfuse_dependency] = lambda: fake
    yield fake
    app.dependency_overrides.pop(langfuse_dependency, None)


def _suite(pg, project):
    suite_id = uuid.uuid4()
    pg.execute(
        "INSERT INTO eval_suites (id, project_id, key, name, langfuse_dataset_name, scorers,"
        " pass_threshold, created_by) VALUES (%s, %s, 'live', 'Live', 'p.live', %s, 0.8, 't')",
        (suite_id, project, json.dumps([{"name": "contains"}])),
    )
    return suite_id


def _run(pg, project, *, question, status="completed", user_id=None):
    run_id = seed_run(pg, project, definition(), question=question, status=status)
    pg.execute(
        "UPDATE runs SET user_id = %s, variables = %s WHERE id = %s",
        (user_id or uuid.uuid4(), json.dumps({"unit": "kardiyoloji"}), run_id),
    )
    return run_id


BODY = {"expected": {"answer": "90 gün", "must_contain": ["90"]}, "style": "dolayli",
        "answerable": True}  # fmt: skip


def test_09_2_from_run_writes_a_masked_item(pg, project, langfuse, client_factory, make_user):
    suite_id = _suite(pg, project)
    run_id = _run(pg, project, question=f"TC {TC} olan hastanın fesih süresi nedir?")
    _, email = make_user(memberships={project: ("analyst", "edit")})
    r = client_factory(email).post(
        f"{P.format(project)}/eval-suites/{suite_id}/items/from-run/{run_id}", json=BODY
    )
    assert r.status_code == 201, r.text
    (item,) = langfuse.items
    assert item["dataset"] == "p.live" and item["id"] == f"live-run-{run_id}"
    assert TC not in json.dumps(item) and "<<PII_" in item["input"]["message"]
    assert item["input"]["variables"] == {"unit": "kardiyoloji"}
    assert item["expected_output"] == BODY["expected"]
    assert item["metadata"] == {"style": "dolayli", "answerable": True, "source": "from_run",
                                "run_id": str(run_id)}  # fmt: skip
    assert r.json()["item_id"] == item["id"] and TC not in r.text
    ((_, outcome, after),) = audit_rows(pg, "eval_item_from_run", project=project)
    assert outcome == "success" and TC not in json.dumps(after)
    assert after == {"suite_id": str(suite_id), "item_id": item["id"], "run_id": str(run_id)}


def test_09_2_from_run_needs_a_completed_readable_run(
    pg, project, make_project, langfuse, client_factory, make_user
):
    suite_id = _suite(pg, project)
    base = f"{P.format(project)}/eval-suites/{suite_id}/items/from-run"
    _, email = make_user(memberships={project: ("analyst", "edit")})
    analyst = client_factory(email)
    running = _run(pg, project, question="soru", status="running")
    r = analyst.post(f"{base}/{running}", json=BODY)
    assert r.status_code == 409 and r.json()["error"]["code"] == "run_not_completed"
    foreign = _run(pg, make_project(), question="soru")
    assert analyst.post(f"{base}/{foreign}", json=BODY).status_code == 404
    assert langfuse.items == []


def test_09_2_from_run_read_mode_cannot_write(pg, project, langfuse, client_factory, make_user):
    suite_id = _suite(pg, project)
    run_id = _run(pg, project, question="soru")
    _, email = make_user(memberships={project: ("analyst", "read")})
    r = client_factory(email).post(
        f"{P.format(project)}/eval-suites/{suite_id}/items/from-run/{run_id}", json=BODY
    )
    assert r.status_code == 403 and langfuse.items == []


def test_09_2_from_run_blocked_question_is_422(
    pg, project, langfuse, client_factory, make_user, monkeypatch
):
    from ffcore.guardrails import engine

    async def block(text, stage, policy, *, ctx):
        return engine.Decision(action="block", text_out="", message="blocked", reference_id="r",
                               events=[])  # fmt: skip

    monkeypatch.setattr(engine, "evaluate", block)
    suite_id = _suite(pg, project)
    run_id = _run(pg, project, question="soru")
    _, email = make_user(memberships={project: ("analyst", "edit")})
    r = client_factory(email).post(
        f"{P.format(project)}/eval-suites/{suite_id}/items/from-run/{run_id}", json=BODY
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "run_input_blocked"
    assert langfuse.items == []
