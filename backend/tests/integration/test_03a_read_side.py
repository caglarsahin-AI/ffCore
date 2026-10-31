"""03a acceptance 2 (read-only access sees the same GET data), 11 (readiness), 12 (audit list
and CSV) and 17 (every 4xx in the OpenAI error shape)."""

import csv
import io
import re
import uuid

import pytest

from ffcore.api import audit as audit_api
from tests.integration.conftest import CONSOLE_ORIGIN

API = "/api/v1"
SECRET = "dummy-not-secret-provider-key-12"


@pytest.fixture
def world(make_user, make_project, client_factory):
    """A superadmin pair (edit / read) and a project with a provider and a model."""
    _, editor = make_user(superadmin="edit")
    _, reader = make_user(superadmin="read")
    edit, read = client_factory(editor), client_factory(reader)
    project = make_project()
    provider = edit.post(
        f"{API}/providers",
        json={
            "key": f"rs-{uuid.uuid4().hex[:8]}",
            "label": "Ollama",
            "driver": "ollama",
            "domains": ["model"],
            "config": {"base_url": "http://ollama:11434"},
            "project_ids": [str(project)],
        },
    ).json()["id"]
    model = edit.post(
        f"{API}/projects/{project}/models",
        json={
            "key": "chat-default",
            "display_name": "Chat",
            "provider_id": provider,
            "category": "llm",
            "model_id": "qwen3.5:35b",
            "upstream_api": "chat",
        },
    ).json()["id"]
    user_id, _ = make_user(memberships={project: ("analyst", "edit")})
    return {
        "edit": edit,
        "read": read,
        "project_id": str(project),
        "provider_id": provider,
        "model_id": model,
        "user_id": str(user_id),
    }


def _get_paths(app):
    for path, ops in app.openapi()["paths"].items():
        if "get" in ops:
            yield path


# /auth/me describes the caller, who differs between the two clients by design. /readyz is
# process state, not user data (no role applies; 04a).
PARITY_EXEMPT = {f"{API}/auth/me", "/readyz"}
# 08: single-policy GETs need a stored policy in the world; their list routes stay checked here
# and the items have test_08_19b_read_mode_get_parity. 04a: knowledge-base GET routes need a KB
# and a document in the world; their parity is test_04a_read_mode_get_parity. 05a: the single
# tool GET needs a registered tool; its parity is test_05a_read_mode_get_parity (the list stays).
PARITY_EXEMPT_PREFIXES = (
    f"{API}/projects/{{project_id}}/pii-policies/{{policy_id}}",
    f"{API}/projects/{{project_id}}/guardrail-policies/{{policy_id}}",
    f"{API}/projects/{{project_id}}/knowledge-bases",
    f"{API}/projects/{{project_id}}/tools/{{tool_id}}",
    # 06a: single agent and run GETs need an agent, a version and a run in the world; their
    # parity is test_06a_read_mode_get_parity (the /agents and /runs lists stay checked here).
    f"{API}/projects/{{project_id}}/agents/{{agent_id}}",
    f"{API}/projects/{{project_id}}/runs/{{run_id}}",
    # 07: the single approval GET needs an approval (and a run) in the world; its parity is
    # test_07_read_mode_get_parity (the /approvals list and count stay checked here).
    f"{API}/projects/{{project_id}}/approvals/{{approval_id}}",
    # 03c: the single key and quota GETs need a key and a quota in the world; their parity is
    # test_03c_21_read_mode_get_parity (the lists and usage stay checked here).
    f"{API}/projects/{{project_id}}/api-keys/{{key_id}}",
    f"{API}/projects/{{project_id}}/quotas/{{quota_id}}",
)


def test_03a_2_read_mode_get_parity(app, world):
    checked = 0
    for path in _get_paths(app):
        if path in PARITY_EXEMPT or path.startswith(PARITY_EXEMPT_PREFIXES):
            continue
        url = re.sub(r"\{(\w+)\}", lambda m: world[m.group(1)], path)
        edit, read = world["edit"].get(url), world["read"].get(url)
        assert edit.status_code == 200, (url, edit.text)
        assert (read.status_code, read.content) == (edit.status_code, edit.content), url
        checked += 1
    assert checked >= 12  # every GET route of 03a, derived from OpenAPI


def test_03a_2_project_member_read_mode_parity(world, make_user, client_factory):
    pid = world["project_id"]
    _, editor = make_user(memberships={uuid.UUID(pid): ("admin", "edit")})
    _, reader = make_user(memberships={uuid.UUID(pid): ("admin", "read")})
    edit, read = client_factory(editor), client_factory(reader)
    for url in (f"{API}/projects/{pid}", f"{API}/projects/{pid}/members",
                f"{API}/projects/{pid}/models", f"{API}/projects/{pid}/readiness"):  # fmt: skip
        assert read.get(url).content == edit.get(url).content, url


def test_03a_11_readiness_three_checks(world, make_user, make_project, client_factory):
    edit = world["edit"]
    empty = make_project()
    body = edit.get(f"{API}/projects/{empty}/readiness").json()
    assert (body["passed"], body["total"]) == (0, 3)
    assert {c["key"]: c["ok"] for c in body["checks"]} == {
        "model_provider": False,
        "vector_provider": False,
        "project_admin": False,
    }
    edit.post(
        f"{API}/providers",
        json={"key": f"vec-{uuid.uuid4().hex[:6]}", "label": "pgvector", "driver": "pgvector",
              "domains": ["vector"], "config": {}, "project_ids": [str(empty)]},
    )  # fmt: skip
    make_user(memberships={empty: ("admin", "edit")})
    body = edit.get(f"{API}/projects/{empty}/readiness").json()
    checks = {c["key"]: c["ok"] for c in body["checks"]}
    assert checks == {"model_provider": False, "vector_provider": True, "project_admin": True}
    assert body["passed"] == 2


def test_03a_12_audit_list_filters(world, pg):
    edit, pid = world["edit"], world["project_id"]
    rows = edit.get(f"{API}/audit", params={"action": "create_model"}).json()
    assert rows["data"] and all(r["action"] == "create_model" for r in rows["data"])
    scoped = edit.get(f"{API}/audit", params={"project_id": pid}).json()["data"]
    assert scoped and all(r["project_id"] == pid for r in scoped)
    page = edit.get(f"{API}/audit", params={"limit": 1, "offset": 1}).json()
    assert (len(page["data"]), page["limit"], page["offset"]) == (1, 1, 1)


def test_03a_12_audit_csv(world, monkeypatch):
    edit = world["edit"]
    edit.post(
        f"{API}/providers/test",
        json={"driver": "anthropic", "config": {"api_key": SECRET}},
        headers={"Origin": CONSOLE_ORIGIN},
    )
    response = edit.get(f"{API}/audit.csv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert rows and {"ts", "actor_id", "action", "outcome", "after"} <= set(rows[0])
    assert SECRET not in response.text
    monkeypatch.setattr(audit_api, "CSV_MAX_ROWS", 1)
    too_many = edit.get(f"{API}/audit.csv")
    assert (too_many.status_code, too_many.json()["error"]["code"]) == (400, "export_too_large")


def test_03a_12_audit_requires_admin(world, make_user, client_factory):
    pid = world["project_id"]
    _, analyst = make_user(memberships={uuid.UUID(pid): ("analyst", "edit")})
    _, admin = make_user(memberships={uuid.UUID(pid): ("admin", "read")})
    analyst_client, admin_client = client_factory(analyst), client_factory(admin)
    assert analyst_client.get(f"{API}/audit", params={"project_id": pid}).status_code == 403
    assert admin_client.get(f"{API}/audit").status_code == 403  # unscoped: superadmin only
    scoped = admin_client.get(f"{API}/audit", params={"project_id": pid})
    assert scoped.status_code == 200
    assert all(r["project_id"] == pid for r in scoped.json()["data"])


def _shape(response, status):
    assert response.status_code == status, response.text
    error = response.json()["error"]
    assert set(error) == {"message", "type", "code"} and all(error.values())
    assert not re.search("[çğıöşüÇĞİÖŞÜ]", error["message"])
    return error["code"]


def test_03a_17_errors_openai_shape(world, client_factory):
    anonymous, edit, read = client_factory(), world["edit"], world["read"]
    pid = world["project_id"]
    _shape(anonymous.get(f"{API}/projects"), 401)
    _shape(anonymous.get(f"{API}/providers"), 401)
    assert _shape(read.post(f"{API}/projects", json={"key": "x-yz", "name": "x"}), 403) == (
        "read_only_access"
    )
    _shape(edit.get(f"{API}/projects/{uuid.uuid4()}"), 404)
    _shape(edit.post(f"{API}/projects", json={"key": "BAD KEY", "name": "x"}), 422)
    _shape(edit.post(f"{API}/projects/{pid}/models", json={}), 422)
    key = edit.get(f"{API}/projects/{pid}").json()["key"]
    _shape(edit.post(f"{API}/projects", json={"key": key, "name": "dup"}), 409)
    _shape(edit.get(f"{API}/audit", params={"limit": 0}), 422)
