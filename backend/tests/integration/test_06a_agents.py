"""06a acceptance 14 (agent lifecycle, read-only 403, audit) and 6a (context_tokens, C13)."""

import json
import uuid

import pytest

from tests.integration.conftest import audit_rows

TEMPLATE = {
    "model": "chat-default",
    "system_prompt": "Answer from the documents.",
    "knowledge": [{"kb_key": "sozlesmeler", "mode": "always", "top_k": 8}],
    "limits": {"context_tokens": 16000},
}


def _model(pg, project_id, *, driver="ollama", window=None, key="chat-default"):
    provider = uuid.uuid4()
    pg.execute(
        "INSERT INTO providers (id, key, label, driver, domains, config_encrypted,"
        " supports_test, created_by) VALUES (%s, %s, 'P', %s, '{model}', %s, true, 'test')",
        (provider, f"pr-{provider.hex[:8]}", driver, b"x"),
    )
    limits = {"context_window": window} if window else {}
    pg.execute(
        "INSERT INTO models (id, project_id, key, display_name, provider_id, category, model_id,"
        " capabilities, input_types, pricing, limits, upstream_api, request_policy, created_by)"
        " VALUES (%s, %s, %s, 'Chat', %s, 'llm', 'm', '{}', '{text}', '{}', %s, 'chat', '{}',"
        " 'test')",
        (uuid.uuid4(), project_id, key, provider, json.dumps(limits)),
    )


@pytest.fixture
def project(make_project, pg, app_settings):
    project_id = make_project()
    _model(pg, project_id)
    return project_id


@pytest.fixture
def ollama_32k(app, app_settings):
    from ffcore.core.config import get_settings

    settings = app_settings.model_copy(
        update={"inference_backend": "ollama", "ollama_context_length": 32768}
    )
    app.dependency_overrides[get_settings] = lambda: settings
    return settings


def _base(project_id):
    return f"/api/v1/projects/{project_id}/agents"


def test_06a_14_agent_lifecycle(client_factory, make_user, project, ollama_32k, pg):
    _, email = make_user(memberships={project: ("analyst", "edit")})
    client = client_factory(email)
    base = _base(project)

    created = client.post(
        base, json={"key": "sozlesme-asistani", "name": "Contracts", "model": "chat-default"}
    )
    assert created.status_code == 201, created.text
    agent = created.json()
    assert agent["status"] == "draft" and agent["latest_version"] == 1
    assert agent["current_version_id"] is None
    url = f"{base}/{agent['id']}"

    dup = client.post(base, json={"key": "sozlesme-asistani", "name": "X", "model": "chat-default"})
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "agent_key_taken"

    put = client.put(f"{url}/versions/1", json={"definition": TEMPLATE})
    assert put.status_code == 200, put.text
    assert put.json()["definition"]["knowledge"][0]["kb_key"] == "sozlesmeler"

    published = client.post(f"{url}/publish", json={"version": 1})
    assert published.status_code == 200, published.text
    assert published.json()["status"] == "published"
    v1_id = published.json()["current_version_id"]

    # A published version is never edited; a new draft is opened from it.
    locked = client.put(f"{url}/versions/1", json={"definition": TEMPLATE})
    assert locked.status_code == 409 and locked.json()["error"]["code"] == "version_published"
    v2 = client.post(f"{url}/versions", json={})
    assert v2.status_code == 201 and v2.json()["version"] == 2
    assert client.post(f"{url}/publish", json={"version": 2}).status_code == 200

    never = client.post(f"{url}/rollback", json={"version": 3})
    assert never.status_code == 404
    back = client.post(f"{url}/rollback", json={"version": 1})
    assert back.status_code == 200 and back.json()["current_version_id"] == v1_id

    assert [v["version"] for v in client.get(f"{url}/versions").json()["items"]] == [1, 2]
    assert client.delete(url).status_code == 204
    assert client.get(url).status_code == 404
    assert client.get(base).json()["items"] == []

    for action in (
        "create_agent",
        "update_agent_version",
        "publish_agent",
        "create_agent_version",
        "rollback_agent",
        "delete_agent",
    ):
        assert audit_rows(pg, action, "success"), action


def test_06a_14_read_only_gets_403_and_sees_the_same(
    client_factory, make_user, project, ollama_32k, pg
):
    _, writer = make_user(memberships={project: ("analyst", "edit")})
    _, reader = make_user(memberships={project: ("analyst", "read")})
    w, r = client_factory(writer), client_factory(reader)
    base = _base(project)
    agent = w.post(base, json={"key": "a1", "name": "A", "model": "chat-default"}).json()

    denied = r.post(base, json={"key": "a2", "name": "B", "model": "chat-default"})
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "read_only_access"
    assert (
        r.put(f"{base}/{agent['id']}/versions/1", json={"definition": TEMPLATE}).status_code == 403
    )
    assert r.get(f"{base}/{agent['id']}").json() == w.get(f"{base}/{agent['id']}").json()
    assert audit_rows(pg, "create_agent", "denied")


def test_06a_14_other_project_agent_is_404(client_factory, make_user, make_project, project, pg):
    other = make_project()
    _model(pg, other)
    _, email = make_user(memberships={project: ("analyst", "edit"), other: ("analyst", "edit")})
    client = client_factory(email)
    agent = client.post(_base(other), json={"key": "x", "name": "X", "model": "chat-default"})
    assert agent.status_code == 201, agent.text
    assert client.get(f"{_base(project)}/{agent.json()['id']}").status_code == 404


def test_06a_6a_context_tokens_rejected(client_factory, make_user, project, ollama_32k):
    _, email = make_user(memberships={project: ("analyst", "edit")})
    client = client_factory(email)
    base = _base(project)
    agent = client.post(base, json={"key": "big", "name": "B", "model": "chat-default"}).json()
    too_big = {**TEMPLATE, "limits": {"context_tokens": 40000}}
    response = client.put(f"{base}/{agent['id']}/versions/1", json={"definition": too_big})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "context_configuration_invalid"


def test_06a_6a_context_tokens_against_model_window(
    client_factory, make_user, make_project, pg, app
):
    project_id = make_project()
    _model(pg, project_id, driver="openai", window=8000)
    _, email = make_user(memberships={project_id: ("analyst", "edit")})
    client = client_factory(email)
    base = _base(project_id)
    agent = client.post(base, json={"key": "w", "name": "W", "model": "chat-default"})
    # The first draft's default budget (16000) already exceeds the 8000 window: refused early.
    assert agent.status_code == 400
    assert agent.json()["error"]["code"] == "context_configuration_invalid"


def test_06a_6a_unknown_model_is_400(client_factory, make_user, project, ollama_32k):
    _, email = make_user(memberships={project: ("analyst", "edit")})
    client = client_factory(email)
    response = client.post(_base(project), json={"key": "m", "name": "M", "model": "nope"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "model_not_found"


def test_06a_15_unknown_definition_field_is_422(client_factory, make_user, project, ollama_32k):
    _, email = make_user(memberships={project: ("analyst", "edit")})
    client = client_factory(email)
    base = _base(project)
    agent = client.post(base, json={"key": "u", "name": "U", "model": "chat-default"}).json()
    response = client.put(
        f"{base}/{agent['id']}/versions/1",
        json={"definition": {**TEMPLATE, "webhook_url": "http://example.test"}},
    )
    assert response.status_code == 422
