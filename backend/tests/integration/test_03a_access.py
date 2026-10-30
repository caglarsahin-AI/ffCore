"""03a acceptance 1 (role / access-mode denials, audited), 13 (one audit event per mutation),
14 (reserved roles) and the behaviour of users, projects and members."""

import uuid

import pytest

from tests.integration.conftest import audit_rows

API = "/api/v1"


@pytest.fixture
def root(make_user, client_factory):
    """Superadmin with edit access (admin_edit at tenant level)."""
    _, email = make_user(superadmin="edit")
    return client_factory(email)


def test_03a_1_analyst_edit_create_project_403(make_user, make_project, client_factory, pg):
    _, email = make_user(memberships={make_project(): ("analyst", "edit")})
    response = client_factory(email).post(f"{API}/projects", json={"key": "nope-a", "name": "N"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "insufficient_role"
    assert pg.execute("SELECT count(*) FROM projects WHERE key = 'nope-a'").fetchone()[0] == 0


def test_03a_1_admin_read_create_project_403(make_user, client_factory, pg):
    _, email = make_user(superadmin="read")
    response = client_factory(email).post(f"{API}/projects", json={"key": "nope-b", "name": "N"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "read_only_access"
    assert pg.execute("SELECT count(*) FROM projects WHERE key = 'nope-b'").fetchone()[0] == 0


def test_03a_1_denials_audited(make_user, make_project, client_factory, pg):
    analyst_id, analyst = make_user(memberships={make_project(): ("analyst", "edit")})
    reader_id, reader = make_user(superadmin="read")
    client_factory(analyst).post(f"{API}/projects", json={"key": "nope-c", "name": "N"})
    client_factory(reader).post(f"{API}/projects", json={"key": "nope-d", "name": "N"})
    denied = {row[0]: row[2]["code"] for row in audit_rows(pg, "create_project", "denied")}
    assert denied[str(analyst_id)] == "insufficient_role"
    assert denied[str(reader_id)] == "read_only_access"


def test_03a_1_project_admin_read_cannot_add_member(make_user, make_project, client_factory, pg):
    project = make_project()
    reader_id, reader = make_user(memberships={project: ("admin", "read")})
    other_id, _ = make_user()
    response = client_factory(reader).post(
        f"{API}/projects/{project}/members", json={"user_id": str(other_id), "role": "analyst"}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "read_only_access"
    row = audit_rows(pg, "add_member", "denied")[-1]
    assert row[0] == str(reader_id)


def test_03a_1_non_member_gets_404_not_data(make_user, make_project, client_factory):
    project = make_project()
    _, outsider = make_user(memberships={make_project(): ("admin", "edit")})
    response = client_factory(outsider).get(f"{API}/projects/{project}")
    assert response.status_code == 404  # FOLLOWUP-103: same answer as a missing project


@pytest.mark.parametrize("role", ["developer", "user"])
def test_03a_14_reserved_roles_rejected(role, root, make_user, make_project):
    project = make_project()
    user_id, _ = make_user()
    response = root.post(
        f"{API}/projects/{project}/members", json={"user_id": str(user_id), "role": role}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "role_reserved"
    added = root.post(
        f"{API}/projects/{project}/members", json={"user_id": str(user_id), "role": "analyst"}
    )
    assert added.status_code == 201
    changed = root.patch(f"{API}/projects/{project}/members/{user_id}", json={"role": role})
    assert changed.status_code == 422
    assert changed.json()["error"]["code"] == "role_reserved"


def test_03a_6_project_key_taken_and_immutable(root):
    first = root.post(f"{API}/projects", json={"key": "acc-key", "name": "A"})
    assert first.status_code == 201
    again = root.post(f"{API}/projects", json={"key": "acc-key", "name": "B"})
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "project_key_taken"
    pid = first.json()["id"]
    rename = root.patch(f"{API}/projects/{pid}", json={"key": "other-key"})
    assert rename.status_code == 422
    root.delete(f"{API}/projects/{pid}")
    reuse = root.post(f"{API}/projects", json={"key": "acc-key", "name": "C"})
    assert reuse.status_code == 409  # never reused, even after soft delete (C1)


def test_03a_users_projects_members_flow(root, make_user, client_factory):
    created = root.post(
        f"{API}/users",
        json={
            "email": "flow@example.test",
            "full_name": "Flow",
            "password": "dummy-not-secret-pw-01",
        },
    )
    assert created.status_code == 201, created.text
    user_id = created.json()["id"]
    assert "password" not in created.text and "password_hash" not in created.text
    dup = root.post(
        f"{API}/users",
        json={"email": "FLOW@example.test", "full_name": "F", "password": "dummy-not-secret-pw-02"},
    )
    assert dup.status_code == 409

    project = root.post(f"{API}/projects", json={"key": "flow-proj", "name": "Flow"}).json()
    pid = project["id"]
    add = root.post(f"{API}/projects/{pid}/members", json={"user_id": user_id, "role": "admin"})
    assert add.status_code == 201
    assert (
        root.get(f"{API}/projects/{pid}/members").json()["data"][0]["email"] == "flow@example.test"
    )

    member = client_factory("flow@example.test", "dummy-not-secret-pw-01")
    assert [p["key"] for p in member.get(f"{API}/projects").json()["data"]] == ["flow-proj"]
    assert (
        member.patch(f"{API}/projects/{pid}", json={"name": "Renamed"}).json()["name"] == "Renamed"
    )

    assert root.delete(f"{API}/projects/{pid}/members/{user_id}").status_code == 204
    assert member.get(f"{API}/projects/{pid}").status_code == 404  # removed: not a member

    assert root.patch(f"{API}/users/{user_id}", json={"is_active": False}).status_code == 200
    assert member.get(f"{API}/auth/me").status_code == 401
    assert root.delete(f"{API}/users/{user_id}").status_code == 204
    assert root.get(f"{API}/users/{user_id}").status_code == 404


def test_03a_superadmin_requires_access_mode(root):
    response = root.post(
        f"{API}/users",
        json={"email": "sa@example.test", "full_name": "S", "password": "dummy-not-secret-pw-03",
              "is_superadmin": True},
    )  # fmt: skip
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "superadmin_access_required"


def test_03a_missing_resources_404(root):
    missing = uuid.uuid4()
    assert root.get(f"{API}/users/{missing}").status_code == 404
    assert root.get(f"{API}/projects/{missing}").status_code == 404
    assert root.patch(f"{API}/projects/{missing}", json={"name": "x"}).status_code == 404


def test_03a_13_each_mutation_one_audit_event(root, make_user, pg):
    def count():
        return pg.execute("SELECT count(*) FROM audit_events WHERE outcome = 'success'").fetchone()[
            0
        ]

    other_id, _ = make_user()
    steps = [
        ("post", f"{API}/users", {"email": "a13@example.test", "full_name": "A",
                                  "password": "dummy-not-secret-pw-13"}),
        ("post", f"{API}/projects", {"key": "audit-13", "name": "A"}),
    ]  # fmt: skip
    ids = {}
    for method, url, body in steps:
        before = count()
        response = getattr(root, method)(url, json=body)
        assert response.status_code == 201, response.text
        ids[url] = response.json()["id"]
        assert count() == before + 1, url
    pid, uid = ids[f"{API}/projects"], ids[f"{API}/users"]
    more = [
        ("patch", f"{API}/users/{uid}", {"full_name": "B"}),
        ("patch", f"{API}/projects/{pid}", {"name": "B"}),
        ("post", f"{API}/projects/{pid}/members", {"user_id": str(other_id), "role": "analyst"}),
        ("patch", f"{API}/projects/{pid}/members/{other_id}", {"access": "read"}),
        ("delete", f"{API}/projects/{pid}/members/{other_id}", None),
        ("delete", f"{API}/projects/{pid}", None),
        ("delete", f"{API}/users/{uid}", None),
    ]
    for method, url, body in more:
        before = count()
        kwargs = {"json": body} if body is not None else {}
        response = getattr(root, method)(url, **kwargs)
        assert response.status_code in (200, 201, 204), (url, response.text)
        assert count() == before + 1, url
    rows = pg.execute(
        "SELECT resource_id, before FROM audit_events WHERE action = 'delete_user'"
        " AND outcome = 'success'"
    ).fetchall()
    assert rows and rows[-1][0] == uid  # deletions name the resource too
    assert "password_hash" not in str(rows[-1][1])
