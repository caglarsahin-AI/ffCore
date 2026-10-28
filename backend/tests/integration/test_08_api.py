"""08-lite API on the compose Postgres and Redis: policies, audit, test panel, internal evaluate."""

import asyncio
import os
import subprocess
import uuid

import pytest

from tests.dummy import OBO_SECRET, SERVICE_TOKEN
from tests.integration.conftest import BACKEND, audit_rows

P = "/api/v1/projects/{}"
TC = "10000000146"
TEXT = f"TC kimlik {TC}, e-posta ayse@ornek.com"
SECRET = "anahtar sk-ant-REDACTEDREDACTEDREDACTEDREDACTED00"
SERVICE = {"Authorization": f"Bearer {SERVICE_TOKEN}"}


@pytest.fixture
def project(make_project):
    return make_project()


@pytest.fixture
def admin(client_factory, make_user, project):
    _, email = make_user(memberships={project: ("admin", "edit")})
    return client_factory(email)


@pytest.fixture
def service_client(client_factory):
    return client_factory()


def _pii(client, project, key="strict", **extra):
    body = {
        "key": key,
        "name": "Strict",
        "categories": {"TR_NATIONAL_ID": {"severity": "high"}, "EMAIL_ADDRESS": {}},
        **extra,
    }
    return client.post(P.format(project) + "/pii-policies", json=body)


def _policy(client, project, key="strict", rules=None, **extra):
    body = {
        "key": key,
        "name": "Strict",
        "rules": rules
        if rules is not None
        else [{"type": "pii", "stages": ["input.pre"], "pii_policy_key": "default"}],
        **extra,
    }
    return client.post(P.format(project) + "/guardrail-policies", json=body)


def _evaluate(client, project, text, stage="input.pre", **extra):
    body = {"project_id": str(project), "stage": stage, "text": text, **extra}
    return client.post("/api/v1/internal/guardrails/evaluate", json=body, headers=SERVICE)


def test_08_19_policy_access_audit(admin, client_factory, make_user, make_project, project, pg):
    created = _pii(admin, project)
    assert created.status_code == 201, created.text
    assert created.json()["builtin"] is False
    assert _policy(admin, project, rules=[]).status_code == 201
    assert [r[1] for r in audit_rows(pg, "create_pii_policy")] == ["success"]
    assert [r[1] for r in audit_rows(pg, "create_guardrail_policy")] == ["success"]

    _, analyst = make_user(memberships={project: ("analyst", "edit")})
    _, reader = make_user(memberships={project: ("admin", "read")})
    _, stranger = make_user(memberships={make_project(): ("admin", "edit")})
    as_analyst, as_reader = client_factory(analyst), client_factory(reader)
    assert as_analyst.get(P.format(project) + "/guardrail-policies").status_code == 200
    denied = _policy(as_analyst, project, key="other")
    assert (denied.status_code, denied.json()["error"]["code"]) == (403, "insufficient_role")
    read_only = _policy(as_reader, project, key="other")
    assert (read_only.status_code, read_only.json()["error"]["code"]) == (403, "read_only_access")
    assert client_factory(stranger).get(P.format(project) + "/pii-policies").status_code == 403
    assert len(audit_rows(pg, "create_guardrail_policy", "denied")) == 2


def test_08_s5_builtin_default_listed_until_overridden(admin, project):
    listed = admin.get(P.format(project) + "/guardrail-policies").json()["data"]
    assert [(p["key"], p["builtin"], p["mode"]) for p in listed] == [("default", True, "monitor")]
    assert listed[0]["id"] is None and listed[0]["builtin_version"] == 1
    assert _policy(admin, project, key="default", rules=[]).status_code == 201
    listed = admin.get(P.format(project) + "/guardrail-policies").json()["data"]
    assert [(p["key"], p["builtin"]) for p in listed] == [("default", False)]


def test_08_6_enforce_switch_audited(admin, project, pg):
    policy = _policy(admin, project).json()
    assert policy["mode"] == "monitor"  # a new policy starts in monitor
    url = P.format(project) + f"/guardrail-policies/{policy['id']}"
    switched = admin.patch(url, json={"mode": "enforce"})
    assert switched.status_code == 200, switched.text
    [(_, outcome, after)] = audit_rows(pg, "update_guardrail_policy")
    assert outcome == "success" and after["mode"] == "enforce"
    before = pg.execute(
        "SELECT before FROM audit_events WHERE action = 'update_guardrail_policy'"
    ).fetchone()[0]
    assert before["mode"] == "monitor"


def test_08_14_pii_policy_reference(admin, project):
    missing = _policy(admin, project, rules=[
        {"type": "pii", "stages": ["input.pre"], "pii_policy_key": "nope"}
    ])
    assert (missing.status_code, missing.json()["error"]["code"]) == (422, "pii_policy_not_found")
    pii = _pii(admin, project).json()
    used = _policy(admin, project, rules=[
        {"type": "pii", "stages": ["input.pre"], "pii_policy_key": "strict"}
    ])
    assert used.status_code == 201
    deleted = admin.delete(P.format(project) + f"/pii-policies/{pii['id']}")
    assert (deleted.status_code, deleted.json()["error"]["code"]) == (409, "pii_policy_in_use")
    admin.delete(P.format(project) + f"/guardrail-policies/{used.json()['id']}")
    assert admin.delete(P.format(project) + f"/pii-policies/{pii['id']}").status_code == 204


def test_08_15_unsupported_rejected_by_api(admin, project):
    person = _pii(admin, project, categories={"PERSON": {}})
    assert person.json()["error"]["code"] == "category_unsupported"
    ner = _pii(admin, project, key="ner", engine="ner")
    assert ner.json()["error"]["code"] == "engine_unsupported"
    later = _policy(admin, project, rules=[
        {"type": "injection", "action": "block", "stages": ["input.pre"]}
    ])
    assert (later.status_code, later.json()["error"]["code"]) == (422, "rule_type_unsupported")
    patched = admin.patch(
        P.format(project) + f"/guardrail-policies/{_policy(admin, project).json()['id']}",
        json={"rules": [{"type": "secrets", "stages": ["input.pre"]}]},
    )
    assert patched.json()["error"]["code"] == "rule_action_required"


def test_08_16_test_panel_evidence(admin, client_factory, make_user, project, pg):
    _, reader = make_user(memberships={project: ("analyst", "read")})
    panel = client_factory(reader)  # a dry run: read-only access may use it
    result = panel.post(
        P.format(project) + "/guardrails/test", json={"text": TEXT, "action": "redact"}
    )
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["text_out"] == "TC kimlik [TR_NATIONAL_ID], e-posta [EMAIL_ADDRESS]"
    assert body["builtin"] is True
    tc = body["findings"][0]
    assert tc["category"] == "TR_NATIONAL_ID" and (tc["start"], tc["end"]) == (10, 21)
    assert tc["evidence"].startswith("checksum valid") and "context word" in tc["evidence"]
    assert tc["value"] == "*******0146"
    assert all(f["evidence"] for f in body["findings"])
    detect = panel.post(P.format(project) + "/guardrails/test", json={"text": TEXT,
                                                                       "action": "detect"})
    assert detect.json()["text_out"] == TEXT and len(detect.json()["findings"]) == 2
    tokenized = panel.post(P.format(project) + "/guardrails/test", json={"text": TEXT,
                                                                          "action": "tokenize"})
    assert tokenized.json()["text_out"] == "TC kimlik <<PII_1>>, e-posta <<PII_2>>"
    # The built-in policy is monitor, but the panel shows what enforce would do.
    policy = panel.post(P.format(project) + "/guardrails/test", json={"text": SECRET})
    assert (policy.json()["action"], policy.json()["policy_mode"]) == ("block", "monitor")
    assert pg.execute("SELECT count(*) FROM guardrail_events").fetchone()[0] == 0


def test_08_17_internal_service_only(admin, client_factory, service_client, project, pg):
    body = {"project_id": str(project), "stage": "input.pre", "text": TEXT}
    url = "/api/v1/internal/guardrails/evaluate"
    assert client_factory().post(url, json=body).status_code == 401
    as_user = admin.post(url, json=body)
    assert (as_user.status_code, as_user.json()["error"]["code"]) == (
        403,
        "service_account_required",
    )
    from ffcore.core.auth import sign_on_behalf_of
    from ffcore.core.config import Settings
    from tests.dummy import SETTINGS_03A

    settings = Settings(
        deploy_profile="llmaas",
        offline=False,
        service_token=SERVICE_TOKEN,
        obo_jwt_secret=OBO_SECRET,
        **SETTINGS_03A,
    )
    obo = sign_on_behalf_of(
        user_id=str(uuid.uuid4()),
        project_id=str(project),
        audience=settings.obo_audience,
        settings=settings,
    )
    as_obo = service_client.post(url, json=body, headers={**SERVICE, "X-On-Behalf-Of": obo})
    assert as_obo.status_code == 403
    ok = _evaluate(service_client, project, TEXT, source="chat")
    assert ok.status_code == 200, ok.text
    decision = ok.json()
    # Built-in default is monitor: recorded, not applied.
    assert (decision["action"], decision["text_out"], decision["builtin"]) == ("allow", TEXT, True)
    rows = pg.execute(
        "SELECT rule, mode, source, action_taken FROM guardrail_events ORDER BY rule"
    ).fetchall()
    assert rows == [("pii#1", "monitor", "chat", "redact"), ("secrets#0", "monitor", "chat", "log")]
    unknown = _evaluate(service_client, uuid.uuid4(), TEXT)
    assert unknown.status_code == 404
    missing_policy = _evaluate(service_client, project, TEXT, policy_key="nope")
    assert missing_policy.json()["error"]["code"] == "guardrail_policy_not_found"


def test_08_4_block_decision_through_internal_endpoint(admin, service_client, project, pg):
    _policy(
        admin,
        project,
        key="default",
        mode="enforce",
        rules=[{"type": "secrets", "action": "block", "stages": ["input.pre"]}],
        block_message={"en": "Blocked.", "tr": "Engellendi."},
    )
    decision = _evaluate(service_client, project, SECRET, locale="tr").json()
    assert decision["action"] == "block" and decision["text_out"] == ""
    assert decision["message"] == "Engellendi." and decision["reference_id"]
    row = pg.execute("SELECT status, action_taken, reference_id FROM guardrail_events").fetchone()
    assert row == ("failed", "block", decision["reference_id"])


def test_08_20_events_masked_in_database(service_client, project, pg):
    _evaluate(service_client, project, TEXT + " " + SECRET)
    dump = str(pg.execute("SELECT input_preview, findings, matches FROM guardrail_events").fetchall())
    assert TC not in dump and "ayse@ornek.com" not in dump and "REDACTEDREDACTED" not in dump
    assert "[TR_NATIONAL_ID]" in dump


def test_08_3b_tokenize_redis_ttl(admin, service_client, project):
    _policy(
        admin,
        project,
        key="default",
        mode="enforce",
        rules=[
            {"type": "pii", "action": "tokenize", "stages": ["egress"], "pii_policy_key": "default"}
        ],
    )
    run_id = uuid.uuid4()
    decision = _evaluate(service_client, project, TEXT, stage="egress", run_id=str(run_id)).json()
    assert decision["text_out"] == "TC kimlik <<PII_1>>, e-posta <<PII_2>>"
    again = _evaluate(service_client, project, f"tekrar {TC}", stage="egress",
                      run_id=str(run_id)).json()
    assert again["text_out"] == "tekrar <<PII_1>>"  # same value, same placeholder in the run

    async def check():
        from redis.asyncio import Redis

        from ffcore.guardrails.masking import RedisTokenStore, detokenize

        client = Redis.from_url(os.environ["REDIS_URL"])
        try:
            ttl = await client.ttl(f"ffcore:pii:{run_id}")
            restored = await detokenize(
                decision["text_out"], store=RedisTokenStore(client, 1800), scope=str(run_id)
            )
            return ttl, restored
        finally:
            await client.aclose()

    ttl, (restored, unresolved) = asyncio.run(check())
    assert 0 < ttl <= 1800
    assert restored == TEXT and unresolved == []


def test_08_18_egress_flag_from_environment(service_client, project, monkeypatch):
    from ffcore.guardrails.settings import get_guardrail_settings

    monkeypatch.setenv("GUARDRAIL_EGRESS_ENABLED", "false")
    get_guardrail_settings.cache_clear()
    try:
        refused = _evaluate(service_client, project, TEXT, stage="egress")
        assert (refused.status_code, refused.json()["error"]["code"]) == (
            409,
            "egress_stage_disabled",
        )
    finally:
        monkeypatch.undo()
        get_guardrail_settings.cache_clear()
    assert _evaluate(service_client, project, TEXT, stage="egress").status_code == 200


def test_08_23_migration_roundtrip(database_url, pg):
    env = {**os.environ, "DATABASE_URL": database_url}

    def alembic(*args):
        return subprocess.run(["alembic", *args], cwd=BACKEND, env=env, capture_output=True)

    def tables():
        rows = pg.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        return {r[0] for r in rows.fetchall()}

    ours = {"pii_policies", "guardrail_policies", "guardrail_events"}
    assert ours <= tables()
    assert alembic("downgrade", "08@-1").returncode == 0
    assert not ours & tables()
    assert {"projects", "users", "audit_events"} <= tables()
    assert alembic("upgrade", "heads").returncode == 0
    assert ours <= tables()
    heads = alembic("heads").stdout.decode()
    assert "08_0001" in heads
