"""Review r1 (K-03a-0007, decision A): the project in an X-On-Behalf-Of token bounds the whole
call. Project lists and memberships narrow to it, tenant administration is refused with 403
`obo_project_scope`, and superadmin rights do not carry over (MAJOR-1). Explicit null in PATCH
bodies for non-nullable fields is a 422, never a 500 (MAJOR-2). A provider used by an active model
cannot be deactivated by PATCH either (MAJOR-3)."""

import typing
import uuid

import pytest

from ffcore.api.schemas import MemberUpdate, ModelUpdate, ProjectUpdate, ProviderUpdate, UserUpdate
from ffcore.core.auth import sign_on_behalf_of
from ffcore.services import catalog_events
from tests.dummy import SERVICE_TOKEN

API = "/api/v1"


@pytest.fixture
def obo(client_factory, app_settings):
    """A client that calls as the service account for `user_id` inside `project_id`."""

    def make(user_id, project_id):
        token = sign_on_behalf_of(
            user_id=str(user_id),
            project_id=str(project_id),
            audience=app_settings.obo_audience,
            settings=app_settings,
        )
        client = client_factory()
        client.headers.update({"Authorization": f"Bearer {SERVICE_TOKEN}", "X-On-Behalf-Of": token})
        return client

    return make


@pytest.fixture
def two_projects(make_project):
    return make_project(), make_project()


def test_03a_r1_obo_project_list_narrows(two_projects, make_user, obo):
    p1, p2 = two_projects
    user_id, _ = make_user(
        superadmin="edit", memberships={p1: ("admin", "edit"), p2: ("admin", "edit")}
    )
    keys = {p["id"] for p in obo(user_id, p1).get(f"{API}/projects").json()["data"]}
    assert keys == {str(p1)}


def test_03a_r1_obo_other_project_refused(two_projects, make_user, obo):
    p1, p2 = two_projects
    user_id, _ = make_user(superadmin="edit", memberships={p2: ("admin", "edit")})
    response = obo(user_id, p1).get(f"{API}/projects/{p2}")
    assert (response.status_code, response.json()["error"]["code"]) == (403, "obo_project_scope")


@pytest.mark.parametrize(
    "path",
    ["/users", "/providers", "/provider-drivers", "/audit"],
)
def test_03a_r1_obo_tenant_endpoints_refused(two_projects, make_user, obo, path):
    p1, _ = two_projects
    user_id, _ = make_user(superadmin="edit", memberships={p1: ("admin", "edit")})
    response = obo(user_id, p1).get(f"{API}{path}")
    assert (response.status_code, response.json()["error"]["code"]) == (403, "obo_project_scope")


def test_03a_r1_obo_tenant_mutation_refused(two_projects, make_user, obo):
    p1, _ = two_projects
    user_id, _ = make_user(superadmin="edit", memberships={p1: ("admin", "edit")})
    response = obo(user_id, p1).post(f"{API}/projects", json={"key": "obo-new", "name": "x"})
    assert (response.status_code, response.json()["error"]["code"]) == (403, "obo_project_scope")


def test_03a_r1_obo_superadmin_not_elevated(two_projects, make_user, obo):
    p1, _ = two_projects
    user_id, _ = make_user(superadmin="edit")  # not a member of p1
    client = obo(user_id, p1)
    assert client.get(f"{API}/projects/{p1}").status_code == 404  # not a member (FOLLOWUP-103)
    assert client.get(f"{API}/projects").json()["data"] == []
    me = client.get(f"{API}/auth/me").json()
    assert (me["role"], me["access"], me["memberships"]) == (None, None, [])


def test_03a_r1_obo_member_works_in_its_project(two_projects, make_user, obo):
    p1, p2 = two_projects
    user_id, _ = make_user(memberships={p1: ("admin", "read"), p2: ("analyst", "edit")})
    client = obo(user_id, p1)
    assert client.get(f"{API}/projects/{p1}/members").status_code == 200
    assert client.get(f"{API}/audit", params={"project_id": str(p1)}).status_code == 200
    me = client.get(f"{API}/auth/me").json()
    assert [m["project_id"] for m in me["memberships"]] == [str(p1)]
    assert (me["role"], me["access"]) == ("admin", "read")


def test_03a_r1_session_superadmin_unaffected(two_projects, make_user, client_factory):
    _, email = make_user(superadmin="edit")
    client = client_factory(email)
    assert client.get(f"{API}/users").status_code == 200
    listed = {p["id"] for p in client.get(f"{API}/projects").json()["data"]}
    assert {str(p) for p in two_projects} <= listed


@pytest.fixture
def root(make_user, client_factory):
    _, email = make_user(superadmin="edit")
    return client_factory(email)


@pytest.fixture
def patch_targets(root, make_project, make_user):
    """URL of one live resource per PATCH schema."""
    project = make_project()
    member_id, _ = make_user()
    root.post(
        f"{API}/projects/{project}/members", json={"user_id": str(member_id), "role": "analyst"}
    )
    provider = root.post(
        f"{API}/providers",
        json={"key": f"null-{uuid.uuid4().hex[:6]}", "label": "P", "driver": "ollama",
              "domains": ["model"], "config": {"base_url": "http://ollama:11434"},
              "project_ids": [str(project)]},
    ).json()["id"]  # fmt: skip
    model = root.post(
        f"{API}/projects/{project}/models",
        json={"key": "chat", "display_name": "C", "provider_id": provider, "category": "llm",
              "model_id": "qwen3.5:35b", "upstream_api": "chat"},
    ).json()["id"]  # fmt: skip
    return {
        UserUpdate: f"{API}/users/{member_id}",
        ProjectUpdate: f"{API}/projects/{project}",
        MemberUpdate: f"{API}/projects/{project}/members/{member_id}",
        ProviderUpdate: f"{API}/providers/{provider}",
        ModelUpdate: f"{API}/projects/{project}/models/{model}",
    }


def _nullable(schema, field) -> bool:
    return type(None) in typing.get_args(schema.model_fields[field].annotation)


def test_03a_r1_patch_explicit_null_is_422(root, patch_targets):
    # Every non-nullable field of every PATCH schema (taken from the schema, not a hand list).
    checked = 0
    for schema, url in patch_targets.items():
        for field in schema.model_fields:
            if _nullable(schema, field):
                continue
            response = root.patch(url, json={field: None})
            assert response.status_code == 422, (url, field, response.text)
            assert response.json()["error"]["code"] == "validation_error"
            checked += 1
    assert checked >= 20


def test_03a_r1_patch_null_allowed_where_nullable(root, patch_targets):
    nullable = {
        (schema, field)
        for schema in patch_targets
        for field in schema.model_fields
        if _nullable(schema, field)
    }
    assert nullable == {
        (UserUpdate, "superadmin_access"),
        (ProjectUpdate, "description"),
        (ProviderUpdate, "description"),
        (ModelUpdate, "reasoning_default"),
    }
    for schema, field in nullable:
        response = root.patch(patch_targets[schema], json={field: None})
        assert response.status_code == 200, (schema.__name__, field, response.text)
        assert response.json()[field] is None


def test_03a_r1_patch_omitted_fields_kept(root, patch_targets):
    url = patch_targets[ProjectUpdate]
    before = root.get(url).json()
    after = root.patch(url, json={"description": "new"}).json()
    assert after["name"] == before["name"] and after["description"] == "new"


def _used_provider(root, make_project):
    project = make_project()
    provider = root.post(
        f"{API}/providers",
        json={"key": f"used-{uuid.uuid4().hex[:6]}", "label": "P", "driver": "ollama",
              "domains": ["model"], "config": {"base_url": "http://ollama:11434"},
              "project_ids": [str(project)]},
    ).json()["id"]  # fmt: skip
    model = root.post(
        f"{API}/projects/{project}/models",
        json={"key": "chat", "display_name": "C", "provider_id": provider, "category": "llm",
              "model_id": "qwen3.5:35b", "upstream_api": "chat"},
    ).json()["id"]  # fmt: skip
    return project, provider, model


@pytest.fixture
def events():
    seen = []
    catalog_events.subscribe(seen.append)
    yield seen
    catalog_events.unsubscribe(seen.append)


def test_03a_r1_deactivating_used_provider_409(root, make_project, events, pg):
    project, provider, model = _used_provider(root, make_project)
    count = len(events)
    response = root.patch(f"{API}/providers/{provider}", json={"is_active": False})
    assert (response.status_code, response.json()["error"]["code"]) == (409, "provider_in_use")
    assert pg.execute("SELECT is_active FROM providers WHERE id = %s", (provider,)).fetchone()[0]
    assert len(events) == count  # nothing published for the refused change

    off = root.patch(f"{API}/projects/{project}/models/{model}", json={"is_active": False})
    assert off.status_code == 200
    allowed = root.patch(f"{API}/providers/{provider}", json={"is_active": False})
    assert (allowed.status_code, allowed.json()["is_active"]) == (200, False)


def test_03a_r1_other_provider_changes_allowed_while_used(root, make_project):
    _, provider, _ = _used_provider(root, make_project)
    response = root.patch(f"{API}/providers/{provider}", json={"label": "Renamed"})
    assert (response.status_code, response.json()["label"]) == (200, "Renamed")


def test_03a_r1_delete_uses_same_guard(root, make_project):
    project, provider, model = _used_provider(root, make_project)
    assert root.delete(f"{API}/providers/{provider}").status_code == 409
    root.patch(f"{API}/projects/{project}/models/{model}", json={"is_active": False})
    assert root.delete(f"{API}/providers/{provider}").status_code == 204
