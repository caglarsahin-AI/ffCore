"""FOLLOWUP-194, registration side: a provider URL (01) and a webhook URL (03c) that point at
the backend itself are refused with 400 `endpoint_is_platform` when saved, also when
ALLOWED_INTERNAL_HOSTS lets the backend be reached; nothing is stored. The call-time side is in
tests/unit/test_trj_194_platform_targets.py.
"""

import uuid

import pytest

API = "/api/v1"

INTERNAL = "http://ffcore-api.internal:8443"
PLATFORM_URLS = [f"{INTERNAL}/v1", "http://backend:9000/v1", "http://127.0.0.1:8000/v1"]


@pytest.fixture(params=[[], ["backend", "127.0.0.1", "ffcore-api.internal"]], ids=["", "allowed"])
def platform_settings(request, app, app_settings):
    from ffcore.core.config import get_settings

    # Added to the stack's own internal hosts (Langfuse, LiteLLM, ... must stay reachable).
    hosts = [*app_settings.allowed_internal_hosts, *request.param]
    update = {"internal_api_url": INTERNAL, "allowed_internal_hosts": hosts}
    s = app_settings.model_copy(update=update)
    app.dependency_overrides[get_settings] = lambda: s
    return s


@pytest.fixture
def root(make_user, client_factory):
    _, email = make_user(superadmin="edit")
    return client_factory(email)


@pytest.fixture
def admin_project(make_project, make_user, client_factory):
    project = make_project()
    _, email = make_user(memberships={project: ("admin", "edit")})
    return project, client_factory(email)


def refused(response):
    assert response.status_code == 400, response.text
    assert response.json()["error"]["code"] == "endpoint_is_platform"
    assert "backend" not in response.json()["error"]["message"]  # no URL echoed back


def provider_body(config, project, driver="ollama"):
    return {
        "key": f"prov-{uuid.uuid4().hex[:8]}",
        "label": "P",
        "driver": driver,
        "domains": ["model"],
        "config": config,
        "project_ids": [str(project)],
    }


@pytest.mark.parametrize("url", PLATFORM_URLS)
def test_trj_194_provider_create_refused(url, platform_settings, root, pg, make_project):
    body = provider_body({"base_url": url}, make_project())
    refused(root.post(f"{API}/providers", json=body))
    stored = pg.execute("SELECT count(*) FROM providers WHERE key = %s", (body["key"],))
    assert stored.fetchone()[0] == 0
    refused(root.post(f"{API}/providers/test", json=body))


def test_trj_194_azure_api_base_refused(platform_settings, root, make_project):
    config = {"api_base": PLATFORM_URLS[1], "api_key": "dummy-not-secret-0123", "api_version": "x"}
    body = provider_body(config, make_project(), "azure_openai")
    refused(root.post(f"{API}/providers", json=body))


@pytest.mark.parametrize("url", PLATFORM_URLS)
def test_trj_194_provider_update_refused(url, platform_settings, root, make_project):
    ollama = provider_body({"base_url": "http://ollama:11434"}, make_project())
    created = root.post(f"{API}/providers", json=ollama)
    assert created.status_code == 201, created.text
    provider_id = created.json()["id"]
    refused(root.patch(f"{API}/providers/{provider_id}", json={"config": {"base_url": url}}))
    kept = root.get(f"{API}/providers/{provider_id}").json()["config"]["base_url"]
    assert kept == "http://ollama:11434"


@pytest.mark.parametrize("url", [f"{u}/hook" for u in PLATFORM_URLS])
def test_trj_194_alert_rule_webhook_refused(url, platform_settings, admin_project, root):
    project, client = admin_project
    body = {"kind": "quota_warn", "channel": "webhook", "params": {"webhook_url": url}}
    refused(client.post(f"{API}/projects/{project}/alert-rules", json=body))
    refused(root.post(f"{API}/alert-rules", json=body))
    rule = client.post(
        f"{API}/projects/{project}/alert-rules", json={"kind": "quota_warn", "channel": "webhook"}
    )
    assert rule.status_code == 201, rule.text
    patch = {"params": {"webhook_url": url}}
    refused(client.patch(f"{API}/projects/{project}/alert-rules/{rule.json()['id']}", json=patch))


@pytest.mark.parametrize("url", [f"{u}/hook" for u in PLATFORM_URLS])
def test_trj_194_default_webhook_refused(url, platform_settings, admin_project):
    project, client = admin_project
    body = {"smtp": None, "default_webhook_url": url, "from_address": None}
    refused(client.put(f"{API}/projects/{project}/notification-settings", json=body))
    got = client.get(f"{API}/projects/{project}/notification-settings").json()
    assert got["default_webhook_url"] is None


def test_trj_194_other_webhook_saved(platform_settings, admin_project):
    project, client = admin_project
    url = "https://hooks.example.com/x"
    body = {"smtp": None, "default_webhook_url": url, "from_address": None}
    saved = client.put(f"{API}/projects/{project}/notification-settings", json=body)
    assert saved.status_code == 200, saved.text
