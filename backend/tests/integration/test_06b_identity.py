"""06b facade identity: API key only, the scope of each path (negative matrix, K-06b-0002),
the `user` field (S1: one indistinguishable 403 for an unknown e-mail or a non-member; the
reason is only in the audit trail), and GET /v1/models limited to the key's project.

These checks run before any model or run is touched, so no LiteLLM is needed here."""

import pytest

from tests.integration.facade_support import *  # noqa: F403 - fixtures
from tests.integration.facade_support import denied_rows, make_key, project_key
from tests.integration.runs_fixtures import publish
from tests.integration.runtime_support import definition


def _error(response):
    return response.status_code, response.json()["error"]["code"]


# --- 17: every path checks its own scope ---


def test_06b_17_scope_matrix_direct_model_needs_chat_direct(owner, facade, pg):
    project, console = owner
    client = facade(make_key(console, project, scopes=["agents"]))
    response = client.chat(f"{project_key(pg, project)}.chat-default")
    assert _error(response) == (403, "scope_missing")


def test_06b_17_scope_matrix_short_name_needs_chat_direct(owner, facade):
    project, console = owner
    client = facade(make_key(console, project, scopes=["kb_search", "tools_invoke"]))
    assert _error(client.chat("chat-default")) == (403, "scope_missing")


def test_06b_17_scope_matrix_agent_needs_agents(owner, facade, pg):
    project, console = owner
    publish(pg, project, definition())
    client = facade(make_key(console, project, scopes=["chat_direct"]))
    response = client.chat(f"agent:{project_key(pg, project)}/asistan")
    assert _error(response) == (403, "scope_missing")


def test_06b_17_scope_checked_before_existence(owner, facade, pg):
    # A missing scope answers the same whether the agent exists or not: no probing.
    project, console = owner
    client = facade(make_key(console, project, scopes=["chat_direct"]))
    missing = client.chat(f"agent:{project_key(pg, project)}/yok")
    assert _error(missing) == (403, "scope_missing")


def test_06b_17_session_or_service_token_is_not_a_facade_caller(app, owner, app_settings):
    from fastapi.testclient import TestClient

    from tests.integration.conftest import CONSOLE_ORIGIN

    _, console = owner
    body = {"model": "chat-default", "messages": [{"role": "user", "content": "x"}]}
    assert _error(console.post("/v1/chat/completions", json=body)) == (401, "api_key_required")
    with TestClient(app, base_url=CONSOLE_ORIGIN) as service:
        token = app_settings.service_token.get_secret_value()
        response = service.post(
            "/v1/chat/completions", json=body, headers={"Authorization": f"Bearer {token}"}
        )
    assert _error(response) == (401, "api_key_required")


def test_06b_17_no_key_401(app):
    from fastapi.testclient import TestClient

    with TestClient(app) as anonymous:
        response = anonymous.get("/v1/models")
    assert response.status_code == 401
    assert response.json()["error"]["type"] == "authentication_error"


# --- 3 / S1: the `user` field ---


def test_06b_3_no_scope_user_field_is_label_and_audited(owner, facade, pg, make_user):
    # Without impersonate the field is only a label: the key stays the actor, the refusal is
    # recorded. The scope check after it still decides (here: no agents scope → 403 scope_missing).
    project, console = owner
    _, email = make_user(memberships={project: ("analyst", "edit")})
    key = make_key(console, project, scopes=["chat_direct"])
    response = facade(key).chat(f"agent:{project_key(pg, project)}/asistan", user=email)
    assert _error(response) == (403, "scope_missing")
    rows = denied_rows(pg, key["id"])
    assert rows and rows[-1]["reason"] == "scope_missing" and rows[-1]["header"] == "user"
    assert email not in str(rows[-1])  # the e-mail is not copied into the audit row


@pytest.mark.parametrize("case", ["unknown_email", "not_member", "inactive_user"])
def test_06b_3_refused_mapping_is_one_answer(case, owner, facade, pg, make_user, make_project):
    project, console = owner
    if case == "unknown_email":
        email = "nobody-here@example.test"
    elif case == "not_member":
        _, email = make_user(memberships={make_project(): ("admin", "edit")})
    else:
        _, email = make_user(active=False, memberships={project: ("analyst", "edit")})
    key = make_key(console, project, scopes=["impersonate", "chat_direct", "agents"])
    response = facade(key).chat("chat-default", user=email)
    assert response.status_code == 403
    assert response.json() == {
        "error": {
            "message": "This credential may not act for a user.",
            "type": "permission_error",
            "code": "impersonation_denied",
        }
    }
    reason = denied_rows(pg, key["id"])[-1]["reason"]
    assert reason == {"unknown_email": "user_not_mapped", "inactive_user": "user_not_mapped"}.get(
        case, "not_member"
    )


def test_06b_3_refused_mapping_bodies_are_byte_equal(owner, facade, make_user, make_project):
    project, console = owner
    _, outsider = make_user(memberships={make_project(): ("admin", "edit")})
    unknown = facade(make_key(console, project, scopes=["impersonate", "chat_direct"]))
    other = facade(make_key(console, project, scopes=["impersonate", "chat_direct"]))
    a = unknown.chat("chat-default", user="nobody@example.test")
    b = other.chat("chat-default", user=outsider)
    assert (a.status_code, a.content) == (b.status_code, b.content)


# --- 12: GET /v1/models ---


def test_06b_12_models_lists_project_only(owner, facade, pg, make_project):
    project, console = owner
    pk = project_key(pg, project)
    pg.execute(
        "INSERT INTO providers (id, key, label, driver, domains, config_encrypted,"
        " supports_test, is_active, created_by) VALUES (gen_random_uuid(), %s, 'P',"
        " 'openai_compatible', ARRAY['model'], decode('00', 'hex'), false, true, 't')",
        (f"prov-{pk}",),
    )
    provider = pg.execute("SELECT id FROM providers WHERE key = %s", (f"prov-{pk}",)).fetchone()[0]
    for proj, key in ((project, "chat-default"), (make_project(), "secret-model")):
        pg.execute(
            "INSERT INTO models (id, project_id, key, display_name, provider_id, category,"
            " model_id, capabilities, input_types, pricing, limits, upstream_api, request_policy,"
            " is_active, created_by) VALUES (gen_random_uuid(), %s, %s, %s, %s, 'llm', 'm', '{}',"
            " ARRAY['text'], '{}', '{}', 'chat', '{}', true, 't')",
            (proj, key, key, provider),
        )
    publish(pg, project, definition(), key="asistan")
    other = make_project()
    publish(pg, other, definition(), key="baskasi")

    both = facade(make_key(console, project, scopes=["chat_direct", "agents"])).models()
    assert both.status_code == 200
    ids = {m["id"] for m in both.json()["data"]}
    assert ids == {f"{pk}.chat-default", f"agent:{pk}/asistan"}
    assert both.json()["object"] == "list"

    only_agents = facade(make_key(console, project, scopes=["agents"])).models().json()
    assert {m["id"] for m in only_agents["data"]} == {f"agent:{pk}/asistan"}
