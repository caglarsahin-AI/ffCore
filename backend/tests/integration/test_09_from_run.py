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


# --- 09-2 r1 (KARARLAR "09-2 r1 kararları") ----------------------------------------------------


def _post(client_factory, make_user, project, suite_id, run_id, body=BODY):
    _, email = make_user(memberships={project: ("analyst", "edit")})
    return client_factory(email).post(
        f"{P.format(project)}/eval-suites/{suite_id}/items/from-run/{run_id}", json=body
    )


def test_09_2_r1_minor9_expected_output_is_masked_with_the_question(
    pg, project, langfuse, client_factory, make_user
):
    # The same token store for question and expected answer: one value, one placeholder.
    suite_id = _suite(pg, project)
    run_id = _run(pg, project, question=f"TC {TC} olan hastanın fesih süresi nedir?")
    body = {**BODY, "expected": {"answer": f"{TC} için 90 gün", "must_contain": ["90", TC],
                                 "must_cite": ["sozlesme-12"]}}  # fmt: skip
    r = _post(client_factory, make_user, project, suite_id, run_id, body)
    assert r.status_code == 201, r.text
    (item,) = langfuse.items
    assert TC not in json.dumps(item)
    token = item["input"]["message"].split()[1]
    assert token.startswith("<<PII_")
    expected = item["expected_output"]
    assert expected["answer"] == f"{token} için 90 gün"
    assert expected["must_contain"] == ["90", token]
    assert expected["must_cite"] == ["sozlesme-12"]  # nothing to mask: kept as given
    # r2 MINOR-3: the answer names what was masked.
    assert r.json()["masked_fields"] == ["message", "answer", "must_contain"]


def test_09_2_r1_masking_says_how_the_item_was_masked(
    pg, project, langfuse, client_factory, make_user
):
    # Live probe (accepted behaviour): with GUARDRAIL_EGRESS_NER=false only the regex
    # categories are masked; the answer says so, the console shows it.
    suite_id = _suite(pg, project)
    run_id = _run(pg, project, question="soru")
    r = _post(client_factory, make_user, project, suite_id, run_id)
    assert r.status_code == 201, r.text
    assert r.json()["masking"] == "regex"


def test_09_2_r1_minor5_refused_from_run_is_audited_with_its_code(
    pg, project, langfuse, client_factory, make_user, monkeypatch
):
    from ffcore.guardrails import engine

    async def block(text, stage, policy, *, ctx):
        return engine.Decision(action="block", text_out="", message="blocked", reference_id="r",
                               events=[])  # fmt: skip

    monkeypatch.setattr(engine, "evaluate", block)
    suite_id = _suite(pg, project)
    run_id = _run(pg, project, question=f"TC {TC}")
    r = _post(client_factory, make_user, project, suite_id, run_id)
    assert r.status_code == 422
    ((_, outcome, after),) = audit_rows(pg, "eval_item_from_run", project=project)
    assert outcome == "error" and TC not in json.dumps(after)
    assert after == {"suite_id": str(suite_id), "run_id": str(run_id),
                     "error_code": "run_input_blocked"}  # fmt: skip


@pytest.mark.parametrize(
    "error,status,code",
    [
        ("config", 422, "rule_type_unsupported"),
        ("ner_config", 503, "ner_not_configured"),
        ("too_long", 422, "text_too_long"),
    ],
)
def test_09_2_r1_minor8_guardrail_errors_are_coded(
    pg, project, langfuse, client_factory, make_user, monkeypatch, error, status, code
):
    from ffcore.guardrails import engine
    from ffcore.guardrails.recognizers.ner import NerConfigError
    from ffcore.guardrails.schemas import GuardrailConfigError

    raised = {
        "config": GuardrailConfigError("rule_type_unsupported", "Rule type 'x' is unsupported."),
        "ner_config": NerConfigError("ner_not_configured", "NER_MODEL is not set."),
        "too_long": engine.TextTooLong("text has 999999 characters"),
    }[error]

    async def fail(text, stage, policy, *, ctx):
        raise raised

    monkeypatch.setattr(engine, "evaluate", fail)
    suite_id = _suite(pg, project)
    run_id = _run(pg, project, question="soru")
    r = _post(client_factory, make_user, project, suite_id, run_id)
    assert (r.status_code, r.json()["error"]["code"]) == (status, code), r.text
    assert langfuse.items == []
    ((_, outcome, after),) = audit_rows(pg, "eval_item_from_run", project=project)
    assert outcome == "error" and after["error_code"] == code


# --- 09-2 r2 MINOR-2/3 (KARARLAR "09-2 r2 ekleri") --------------------------------------------


@pytest.mark.parametrize("field", ["sql_result", "must_cite", "regex"])
def test_09_2_r2_minor3_expectation_a_mask_would_change_is_refused(
    pg, project, langfuse, client_factory, make_user, field
):
    # These are compared with real rows, ids or text: a placeholder could never match, so the
    # item would always fail. Refused loudly instead of saved to fail silently.
    value = {"sql_result": [["Ad", TC]], "must_cite": [f"kayit-{TC}"], "regex": f"{TC}|90"}[field]
    suite_id = _suite(pg, project)
    run_id = _run(pg, project, question="soru")
    body = {**BODY, "expected": {"answer": "90 gün", field: value}}
    r = _post(client_factory, make_user, project, suite_id, run_id, body)
    assert r.status_code == 422, r.text
    err = r.json()["error"]
    assert err["code"] == "expected_would_be_masked" and field in err["message"]
    assert TC not in r.text and langfuse.items == []
    ((_, outcome, after),) = audit_rows(pg, "eval_item_from_run", project=project)
    assert outcome == "error" and after["error_code"] == "expected_would_be_masked"


def test_09_2_r2_minor3_nothing_masked_lists_no_field(
    pg, project, langfuse, client_factory, make_user
):
    suite_id = _suite(pg, project)
    run_id = _run(pg, project, question="soru")
    r = _post(client_factory, make_user, project, suite_id, run_id)
    assert r.status_code == 201, r.text
    assert r.json()["masked_fields"] == []


def _stored_default_policy(admin, project, mode):
    r = admin.post(
        f"{P.format(project)}/guardrail-policies",
        json={"key": "default", "name": "Default", "mode": mode,
              "rules": [{"type": "pii", "stages": ["egress"], "pii_policy_key": "default"}]},
    )  # fmt: skip
    assert r.status_code == 201, r.text


@pytest.mark.parametrize("mode,masking,masked", [("monitor", "none", False),
                                                  ("off", "none", False),
                                                  ("enforce", "regex", True)])  # fmt: skip
def test_09_2_r2_minor2_masking_follows_the_stored_policy(
    pg, project, langfuse, client_factory, make_user, mode, masking, masked
):
    # A stored policy in monitor (or off) masks nothing at egress: the answer says `none`, and
    # the item really is unmasked; the field never claims a masking that did not happen.
    _, admin_email = make_user(memberships={project: ("admin", "edit")})
    _stored_default_policy(client_factory(admin_email), project, mode)
    suite_id = _suite(pg, project)
    run_id = _run(pg, project, question=f"TC {TC} için süre?")
    r = _post(client_factory, make_user, project, suite_id, run_id)
    assert r.status_code == 201, r.text
    assert r.json()["masking"] == masking
    (item,) = langfuse.items
    assert (TC not in item["input"]["message"]) is masked
