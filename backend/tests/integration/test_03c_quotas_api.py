"""03c quotas API: one form (scope, windows, tokens, budget, activation), admin writes, audit;
FOLLOWUP-69: no USD budget while an active model of the project has no price."""

import uuid

import pytest

from tests.integration.conftest import audit_rows

LIMITS = {"windows": {"rpm": 60}, "tokens": {"tpd": 100000}}


@pytest.fixture
def admin(make_project, make_user, client_factory):
    project = make_project()
    user_id, email = make_user(memberships={project: ("admin", "edit")})
    return project, user_id, client_factory(email)


def _model(pg, project, pricing):
    provider = uuid.uuid4()
    pg.execute(
        "INSERT INTO providers (id, key, label, driver, domains, config_encrypted, supports_test,"
        " is_active, created_by) VALUES (%s, %s, 'P', 'openai_compatible', ARRAY['model'],"
        " '\\x00', true, true, 'test')",
        (provider, f"prov-{provider.hex[:8]}"),
    )
    pg.execute(
        "INSERT INTO models (id, project_id, key, display_name, provider_id, category, model_id,"
        " capabilities, input_types, pricing, limits, upstream_api, request_policy, is_active,"
        " created_by) VALUES (%s, %s, %s, 'm', %s, 'llm', 'x', '{}', ARRAY['text'], %s, '{}',"
        " 'chat', '{}', true, 'test')",
        (uuid.uuid4(), project, f"m-{uuid.uuid4().hex[:6]}", provider, pricing),
    )


def test_03c_10_quota_crud_and_audit(admin, pg):
    project, _, client = admin
    created = client.post(
        f"/api/v1/projects/{project}/quotas",
        json={"scope_type": "project", "label": "base", **LIMITS},
    )
    assert created.status_code == 201, created.text
    quota = created.json()
    assert quota["scope_id"] == str(project) and quota["action"] == "block"
    assert quota["windows"]["rpm"] == 60 and quota["windows"]["rph"] is None
    url = f"/api/v1/projects/{project}/quotas/{quota['id']}"
    patched = client.patch(url, json={"action": "warn", "budget": {"daily_usd": "5"}})
    assert patched.status_code == 200, patched.text
    assert patched.json()["action"] == "warn" and patched.json()["windows"]["rpm"] == 60
    assert client.delete(url).status_code == 204
    assert client.get(url).status_code == 404
    for action in ("create_quota", "update_quota", "delete_quota"):
        assert len(audit_rows(pg, action, "success", project)) == 1, action


def test_03c_10_scope_validation(admin, make_project, make_user):
    project, user_id, client = admin
    base = f"/api/v1/projects/{project}/quotas"
    empty = client.post(base, json={"scope_type": "project", "label": "x"})
    assert empty.status_code == 422 and empty.json()["error"]["code"] == "quota_empty"
    no_id = client.post(base, json={"scope_type": "user", "label": "x", **LIMITS})
    assert no_id.json()["error"]["code"] == "scope_id_required"
    stranger, _ = make_user(memberships={make_project(): ("admin", "edit")})
    foreign = client.post(
        base, json={"scope_type": "user", "scope_id": str(stranger), "label": "x", **LIMITS}
    )
    assert foreign.json()["error"]["code"] == "scope_id_invalid"
    mine = client.post(
        base, json={"scope_type": "user", "scope_id": str(user_id), "label": "x", **LIMITS}
    )
    assert mine.status_code == 201
    group = client.post(base, json={"scope_type": "group", "label": "x", **LIMITS})
    assert group.status_code == 422  # C20: no group/model/provider scope


def test_03c_10_key_quota_needs_project_key(admin):
    project, _, client = admin
    key = client.post(
        f"/api/v1/projects/{project}/api-keys", json={"name": "k", "scopes": ["chat_direct"]}
    ).json()
    response = client.post(
        f"/api/v1/projects/{project}/quotas",
        json={
            "scope_type": "api_key",
            "scope_id": key["id"],
            "label": "k",
            "budget": {"daily_usd": "1"},
        },
    )
    assert response.status_code == 201, response.text


def test_03c_11_budget_rule_rejected_pricing_missing(admin, pg):
    project, _, client = admin
    _model(pg, project, '{"input_per_1m": 3}')  # output price missing (llmaas seed, 01 S3)
    base = f"/api/v1/projects/{project}/quotas"
    refused = client.post(
        base, json={"scope_type": "project", "label": "b", "budget": {"monthly_usd": "100"}}
    )
    assert refused.status_code == 422
    assert refused.json()["error"]["code"] == "pricing_missing"
    # Limits without money are fine on an unpriced model.
    assert client.post(base, json={"scope_type": "project", "label": "w", **LIMITS}).status_code
    pg.execute(
        'UPDATE models SET pricing = \'{"input_per_1m": 3, "output_per_1m": 15}\''
        " WHERE project_id = %s",
        (project,),
    )
    accepted = client.post(
        base, json={"scope_type": "project", "label": "b", "budget": {"monthly_usd": "100"}}
    )
    assert accepted.status_code == 201, accepted.text


def test_03c_21_quota_writes_need_admin_edit(make_project, make_user, client_factory):
    project = make_project()
    _, analyst = make_user(memberships={project: ("analyst", "edit")})
    _, reader = make_user(memberships={project: ("admin", "read")})
    base = f"/api/v1/projects/{project}/quotas"
    body = {"scope_type": "project", "label": "x", **LIMITS}
    a, r = client_factory(analyst), client_factory(reader)
    assert a.post(base, json=body).json()["error"]["code"] == "insufficient_role"
    assert r.post(base, json=body).json()["error"]["code"] == "read_only_access"
    assert a.get(base).status_code == 200 and r.get(base).status_code == 200
