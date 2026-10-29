"""03a acceptance 7 (encrypted provider config), 8 (provider_projects never empty),
9 (connection test) and provider catalog events."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from ffcore.core.secrets import decrypt_json
from ffcore.services import catalog_events
from tests.dummy import FERNET_KEY
from tests.integration.conftest import audit_rows

API = "/api/v1"
SECRET = "dummy-not-secret-provider-key-77"


class _Provider(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path.startswith("/v1/models"):
            ok = self.headers.get("Authorization") == f"Bearer {SECRET}"
            body = json.dumps({"data": []}).encode() if ok else b"{}"
            self.send_response(200 if ok else 401)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()


@pytest.fixture(scope="module")
def fake_provider():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Provider)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


@pytest.fixture
def root(make_user, client_factory):
    _, email = make_user(superadmin="edit")
    return client_factory(email)


@pytest.fixture
def events():
    seen = []
    catalog_events.subscribe(seen.append)
    yield seen
    catalog_events.unsubscribe(seen.append)


def _vllm(project_ids, base_url="http://vllm.internal:8000", key="p-vllm"):
    return {
        "key": key,
        "label": "vLLM",
        "driver": "vllm",
        "domains": ["model"],
        "config": {"base_url": base_url, "api_key": SECRET},
        "project_ids": [str(p) for p in project_ids],
    }


def test_03a_7_provider_config_encrypted_at_rest(root, make_project, pg, app_settings):
    created = root.post(f"{API}/providers", json=_vllm([make_project()], key="enc-1"))
    assert created.status_code == 201, created.text
    stored = pg.execute("SELECT config_encrypted FROM providers WHERE key = 'enc-1'").fetchone()[0]
    assert SECRET.encode() not in bytes(stored)
    assert decrypt_json(stored, app_settings)["api_key"] == SECRET
    assert FERNET_KEY  # the test key, never a real one


def test_03a_7_api_masks_secrets(root, make_project):
    created = root.post(f"{API}/providers", json=_vllm([make_project()], key="mask-1")).json()
    assert created["config"] == {"base_url": "http://vllm.internal:8000", "api_key": "***"}
    listed = root.get(f"{API}/providers").text
    fetched = root.get(f"{API}/providers/{created['id']}").text
    assert SECRET not in listed and SECRET not in fetched


def test_03a_7_audit_masks_secrets(root, make_project, pg):
    root.post(f"{API}/providers", json=_vllm([make_project()], key="audit-1"))
    rows = audit_rows(pg, "create_provider", "success")
    assert rows and all(SECRET not in json.dumps(row[2]) for row in rows)


def test_03a_7_patch_keeps_masked_secret(root, make_project, pg, app_settings):
    pid = root.post(f"{API}/providers", json=_vllm([make_project()], key="keep-1")).json()["id"]
    response = root.patch(
        f"{API}/providers/{pid}",
        json={"config": {"base_url": "http://vllm.internal:9000", "api_key": "***"}},
    )
    assert response.status_code == 200, response.text
    stored = pg.execute("SELECT config_encrypted FROM providers WHERE id = %s", (pid,)).fetchone()
    config = decrypt_json(stored[0], app_settings)
    assert config == {"base_url": "http://vllm.internal:9000", "api_key": SECRET}


def test_03a_7_config_validated_per_driver(root, make_project):
    body = _vllm([make_project()], key="bad-1")
    body["config"] = {"api_key": SECRET}
    missing = root.post(f"{API}/providers", json=body)
    assert (missing.status_code, missing.json()["error"]["code"]) == (422, "missing_config_field")
    body["config"] = {"base_url": "http://x", "surprise": "1"}
    unknown = root.post(f"{API}/providers", json=body)
    assert unknown.json()["error"]["code"] == "unknown_config_field"
    body["config"], body["domains"] = {"base_url": "http://x"}, ["vector"]
    domain = root.post(f"{API}/providers", json=body)
    assert domain.json()["error"]["code"] == "domain_not_supported"


def test_03a_8_provider_requires_projects(root, make_project):
    empty = root.post(f"{API}/providers", json=_vllm([], key="empty-1"))
    assert empty.status_code == 422
    pid = root.post(f"{API}/providers", json=_vllm([make_project()], key="empty-2")).json()["id"]
    cleared = root.put(f"{API}/providers/{pid}/projects", json={"project_ids": []})
    assert cleared.status_code == 422
    other = make_project()
    moved = root.put(f"{API}/providers/{pid}/projects", json={"project_ids": [str(other)]})
    assert moved.status_code == 200
    assert moved.json()["project_ids"] == [str(other)]


def test_03a_8_unknown_project_rejected(root):
    body = _vllm(["00000000-0000-4000-8000-000000000000"], key="ghost-1")
    response = root.post(f"{API}/providers", json=body)
    assert (response.status_code, response.json()["error"]["code"]) == (422, "unknown_project")


def test_03a_provider_key_unique_and_delete(root, make_project, events):
    project = make_project()
    first = root.post(f"{API}/providers", json=_vllm([project], key="uniq-1"))
    again = root.post(f"{API}/providers", json=_vllm([project], key="uniq-1"))
    assert again.status_code == 409
    pid = first.json()["id"]
    assert root.delete(f"{API}/providers/{pid}").status_code == 204
    assert root.get(f"{API}/providers/{pid}").json()["is_active"] is False
    kinds = [(e.kind, e.action) for e in events if e.resource_id == pid]
    assert kinds == [("provider", "created"), ("provider", "deleted")]


def test_03a_provider_event_not_sent_on_rollback(root, make_project, events):
    # Duplicate key fails before commit: nothing may reach the reconciler.
    project = make_project()
    root.post(f"{API}/providers", json=_vllm([project], key="rb-1"))
    count = len(events)
    root.post(f"{API}/providers", json=_vllm([project], key="rb-1"))
    assert len(events) == count


@pytest.fixture
def internal_settings(app, app_settings):
    from ffcore.core.config import get_settings

    allowed = app_settings.model_copy(update={"allowed_internal_hosts": ["127.0.0.1"]})
    app.dependency_overrides[get_settings] = lambda: allowed
    return allowed


def test_03a_9_test_without_saving(root, internal_settings, fake_provider, pg):
    body = {"driver": "vllm", "config": {"base_url": fake_provider, "api_key": SECRET}}
    result = root.post(f"{API}/providers/test", json=body).json()
    assert (result["supported"], result["ok"], result["code"]) == (True, True, "ok")
    assert pg.execute("SELECT count(*) FROM providers WHERE driver = 'vllm' AND"
                      " key LIKE 'unsaved%'").fetchone()[0] == 0  # fmt: skip
    wrong = {"driver": "vllm", "config": {"base_url": fake_provider, "api_key": "wrong-key-000"}}
    failed = root.post(f"{API}/providers/test", json=wrong).json()
    assert (failed["ok"], failed["code"]) == (False, "auth_failed")
    assert "wrong-key" not in json.dumps(failed)


def test_03a_9_failed_test_does_not_block_save(root, internal_settings, make_project):
    body = _vllm([make_project()], base_url="http://127.0.0.1:9", key="down-1")
    created = root.post(f"{API}/providers", json=body)
    assert created.status_code == 201
    result = root.post(f"{API}/providers/{created.json()['id']}/test").json()
    assert result["ok"] is False and result["code"] == "connection_failed"


def test_03a_9_stored_config_test(root, internal_settings, make_project, fake_provider):
    created = root.post(f"{API}/providers", json=_vllm([make_project()], fake_provider, "live-1"))
    result = root.post(f"{API}/providers/{created.json()['id']}/test").json()
    assert result["ok"] is True


def test_03a_9_unresolvable_host_is_a_failed_test(root, app, app_settings, make_project):
    # 10a-forms (K-10af-0003): a provider host that does not resolve is a failed test (200 +
    # connection_failed), unsaved and stored, never a 500.
    from ffcore.core.config import get_settings

    host = "no-such-provider.invalid"
    allowed = app_settings.model_copy(update={"allowed_internal_hosts": [host]})
    app.dependency_overrides[get_settings] = lambda: allowed
    body = {"driver": "ollama", "config": {"base_url": f"http://{host}:11434"}}
    unsaved = root.post(f"{API}/providers/test", json=body)
    assert unsaved.status_code == 200
    assert (unsaved.json()["ok"], unsaved.json()["code"]) == (False, "connection_failed")

    created = root.post(
        f"{API}/providers",
        json={**body, "key": "dns-down-1", "label": "DNS down", "domains": ["model"],
              "project_ids": [str(make_project())]},
    )  # fmt: skip
    assert created.status_code == 201
    stored = root.post(f"{API}/providers/{created.json()['id']}/test")
    assert stored.status_code == 200
    assert (stored.json()["ok"], stored.json()["code"]) == (False, "connection_failed")


def test_03a_9_unsupported_driver_explicit(root):
    body = {"driver": "pgvector", "config": {}}
    result = root.post(f"{API}/providers/test", json=body).json()
    assert result == {
        "supported": False,
        "ok": False,
        "code": "connection_test_unsupported",
        "message": result["message"],
        "latency_ms": None,
    }
    assert result["message"]


def test_03a_9_offline_rejects_external_test(root, app, app_settings):
    from ffcore.core.config import get_settings

    offline = app_settings.model_copy(update={"offline": True})
    app.dependency_overrides[get_settings] = lambda: offline
    body = {"driver": "anthropic", "config": {"api_key": SECRET}}
    result = root.post(f"{API}/providers/test", json=body).json()
    assert (result["ok"], result["code"]) == (False, "egress_offline")


def test_03a_provider_drivers_listed(root):
    drivers = {d["driver"]: d for d in root.get(f"{API}/provider-drivers").json()["data"]}
    assert drivers["bedrock"]["supports_test"] is False
    assert drivers["local_flagembedding"]["domains"] == ["embedding"]
    secret = {f["name"] for f in drivers["azure_openai"]["fields"] if f["secret"]}
    assert secret == {"api_key"}
