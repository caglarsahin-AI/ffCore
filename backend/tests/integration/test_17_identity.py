"""17-1 acceptance: directory sign-in (LDAP), JIT provisioning, group mappings, LOCAL_LOGIN,
deactivation, linking (S1), CSV import, provider status and the resolver for 15.

The directory is an ldap3 MOCK_SYNC server in process (tests/ldap_fixture.py); the API is the
real application against the test database.
"""

import asyncio
import io
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from tests import ldap_fixture as fx
from tests.integration.conftest import PASSWORD, audit_rows

API = "/api/v1"
INVALID = {
    "error": {
        "message": "Email or password is incorrect.",
        "type": "authentication_error",
        "code": "invalid_credentials",
    }
}


@pytest.fixture
def fake():
    return fx.FakeDirectory()


@pytest.fixture
def configure(app, app_settings, fake):
    """configure(**settings) switches the running app to the fake directory (or LDAP off)."""
    from ffcore.core.config import get_settings
    from ffcore.core.ldap_auth import get_ldap_directory

    def apply(ldap=True, **changes):
        if ldap:
            settings = fx.ldap_settings(app_settings, **changes)
        else:
            settings = app_settings.model_copy(update=changes)
        app.dependency_overrides[get_settings] = lambda: settings
        app.dependency_overrides[get_ldap_directory] = (
            (lambda: fake.directory(settings)) if ldap else (lambda: None)
        )
        return settings

    apply()
    return apply


@pytest.fixture
def root(make_user, client_factory):
    _, email = make_user(superadmin="edit")
    return client_factory(email)


def login(client, name_or_email, password):
    return client.post(f"{API}/auth/login", json={"email": name_or_email, "password": password})


def map_group(root, project, group, role="user", access="read", provider="ldap"):
    response = root.post(
        f"{API}/projects/{project}/identity-mappings",
        json={"provider": provider, "external_group": group, "role": role, "access": access},
    )
    assert response.status_code == 201, response.text
    return response.json()


def user_row(pg, email):
    return pg.execute(
        "SELECT id, auth_source, external_id, password_hash, is_active, token_version,"
        " must_change_password, last_login_at FROM users WHERE lower(email) = lower(%s)"
        " AND deleted_at IS NULL",
        (email,),
    ).fetchone()


def memberships(pg, user_id):
    rows = pg.execute(
        "SELECT project_id, role, access, membership_source FROM project_members"
        " WHERE user_id = %s",
        (user_id,),
    ).fetchall()
    return {r[0]: (r[1], r[2], r[3]) for r in rows}


# --- JIT + mapping + user role (acceptance 1) ---


def test_17_1_directory_user_provisioned_with_user_read(
    configure, fake, root, make_project, client_factory, pg
):
    project = make_project()
    map_group(root, project, fake.group("chat"))  # the DN as the directory spells it
    client = client_factory()
    response = login(client, fake.login("user-a"), fake.password("user-a"))
    assert response.status_code == 200, response.text
    me = response.json()
    assert me["user"]["auth_source"] == "ldap"
    assert me["role"] == "user" and me["access"] == "read"
    row = user_row(pg, fake.email("user-a"))
    assert row[1] == "ldap" and row[2] == fake.guid("user-a") and row[3] is None
    assert row[7] is not None  # last_login_at
    assert memberships(pg, row[0]) == {project: ("user", "read", "idp")}
    # chat is open, the console is not
    assert client.get(f"{API}/projects/{project}/chat/agents").status_code == 200
    denied = client.get(f"{API}/projects/{project}/agents")
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "insufficient_role"
    provisioned = [r for r in audit_rows(pg, "user_provisioned") if r[2]["provider"] == "ldap"]
    assert provisioned
    assert audit_rows(pg, "auth.login", "success")[-1][2] == {"source": "ldap"}


def test_17_1_login_by_email_and_upn_finds_same_account(configure, fake, client_factory, pg):
    first = login(client_factory(), fake.login("user-a"), fake.password("user-a"))
    second = login(client_factory(), fake.email("user-a").upper(), fake.password("user-a"))
    assert first.status_code == second.status_code == 200
    assert first.json()["user"]["id"] == second.json()["user"]["id"]


def test_17_1_unmapped_group_member_enters_without_project(configure, fake, client_factory, pg):
    response = login(client_factory(), fake.login("user-b"), fake.password("user-b"))
    assert response.status_code == 200
    assert response.json()["role"] is None and response.json()["memberships"] == []


def test_17_1_default_project_gives_user_read(configure, fake, make_project, client_factory, pg):
    project = make_project()
    key = pg.execute("SELECT key FROM projects WHERE id = %s", (project,)).fetchone()[0]
    configure(default_project_for_new_users=key)
    response = login(client_factory(), fake.login("user-b"), fake.password("user-b"))
    assert response.status_code == 200
    row = user_row(pg, fake.email("user-b"))
    assert memberships(pg, row[0]) == {project: ("user", "read", "idp")}


def test_17_1_default_project_missing_fails_loud(configure, fake, client_factory):
    configure(default_project_for_new_users="no-such-project")
    response = login(client_factory(), fake.login("user-b"), fake.password("user-b"))
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "default_project_missing"


def test_17_1_several_groups_highest_role_and_edit(
    configure, fake, root, make_project, client_factory, pg
):
    project = make_project()
    map_group(root, project, fake.group("chat"), "user", "edit")
    map_group(root, project, fake.group("analysts"), "analyst", "read")
    login(client_factory(), fake.login("user-b"), fake.password("user-b"))
    row = user_row(pg, fake.email("user-b"))
    assert memberships(pg, row[0]) == {project: ("analyst", "edit", "idp")}


# --- group change, manual memberships (acceptance 2, S2) ---


def test_17_2_left_group_loses_idp_membership_manual_stays(
    configure, fake, root, make_project, client_factory, pg
):
    mapped, manual = make_project(), make_project()
    map_group(root, mapped, fake.group("editors"), "analyst", "edit")
    login(client_factory(), fake.login("user-b"), fake.password("user-b"))
    user_id = user_row(pg, fake.email("user-b"))[0]
    added = root.post(
        f"{API}/projects/{manual}/members", json={"user_id": str(user_id), "role": "user"}
    )
    assert added.status_code == 201
    # the same project mapped too: the manual row is authoritative and untouched
    map_group(root, manual, fake.group("editors"), "admin", "edit")
    fake.set_groups("user-b", ["chat"])
    assert login(client_factory(), fake.login("user-b"), fake.password("user-b")).status_code == 200
    assert memberships(pg, user_id) == {manual: ("user", "edit", "manual")}
    synced = [r for r in audit_rows(pg, "membership_synced") if str(mapped) in r[2]["removed"]]
    assert synced


def test_17_2_admin_edit_of_idp_membership_becomes_manual(
    configure, fake, root, make_project, client_factory, pg
):
    project = make_project()
    map_group(root, project, fake.group("chat"))
    login(client_factory(), fake.login("user-a"), fake.password("user-a"))
    user_id = user_row(pg, fake.email("user-a"))[0]
    changed = root.patch(f"{API}/projects/{project}/members/{user_id}", json={"access": "edit"})
    assert changed.status_code == 200
    fake.set_groups("user-a", [])
    login(client_factory(), fake.login("user-a"), fake.password("user-a"))
    assert memberships(pg, user_id) == {project: ("user", "edit", "manual")}


def test_17_2_mapping_change_applies_at_next_login(
    configure, fake, root, make_project, client_factory, pg
):
    project = make_project()
    mapping = map_group(root, project, fake.group("chat"))
    login(client_factory(), fake.login("user-a"), fake.password("user-a"))
    user_id = user_row(pg, fake.email("user-a"))[0]
    assert project in memberships(pg, user_id)
    gone = root.delete(f"{API}/projects/{project}/identity-mappings/{mapping['id']}")
    assert gone.status_code == 204
    login(client_factory(), fake.login("user-a"), fake.password("user-a"))
    assert memberships(pg, user_id) == {}


# --- refusals (acceptance 3) ---


def test_17_3_bad_credentials_one_body_reason_in_audit(configure, fake, client_factory, pg):
    wrong = login(client_factory(), fake.login("user-a"), "wrong-password")
    unknown = login(client_factory(), "nobody-here", "whatever")
    empty = login(client_factory(), fake.login("user-a"), " ")
    for response in (wrong, unknown, empty):
        assert response.status_code == 401
        assert response.json() == INVALID
    reasons = [r[2]["reason"] for r in audit_rows(pg, "auth.login", "denied")[-3:]]
    assert reasons == ["bind_failed", "user_not_found", "bind_failed"]
    assert all("nobody-here" not in str(r[2]) for r in audit_rows(pg, "auth.login", "denied"))


def test_17_3_directory_down_503_no_local_fallback(configure, fake, make_user, client_factory, pg):
    login(client_factory(), fake.login("user-a"), fake.password("user-a"))  # account exists
    fake.unreachable = True
    for name in (fake.login("user-a"), fake.email("user-a"), "someone-new"):
        response = login(client_factory(), name, "anything")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "identity_provider_unavailable"
    # a local account keeps working: its path is local, the directory is not asked
    _, local = make_user()
    assert login(client_factory(), local, PASSWORD).status_code == 200
    assert audit_rows(pg, "auth.login", "error")[-1][2]["reason"] == "directory_unreachable"


def test_17_3_directory_account_while_ldap_off_is_503(configure, fake, client_factory):
    login(client_factory(), fake.login("user-a"), fake.password("user-a"))
    configure(ldap=False)
    response = login(client_factory(), fake.email("user-a"), fake.password("user-a"))
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "identity_provider_unavailable"


@pytest.mark.parametrize("policy", ["off", "superadmin_only"])
def test_17_3_local_login_policy_keeps_superadmin(policy, configure, make_user, client_factory):
    configure(local_login=policy)
    _, superadmin = make_user(superadmin="edit")
    _, member = make_user()
    assert login(client_factory(), superadmin, PASSWORD).status_code == 200
    refused = login(client_factory(), member, PASSWORD)
    assert refused.status_code == 403
    assert refused.json()["error"]["code"] == "local_login_disabled"
    # the policy is not an oracle: a wrong password is still the plain 401
    assert login(client_factory(), member, "wrong-password-0000").json() == INVALID


def test_17_3_disabled_directory_account_403(configure, fake, client_factory, pg):
    response = login(client_factory(), fake.login("user-disabled"), fake.password("user-disabled"))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "user_inactive"


def test_17_3_directory_account_without_email_refused(configure, fake, client_factory):
    response = login(client_factory(), fake.login("user-nomail"), fake.password("user-nomail"))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "identity_email_missing"


def test_17_3_external_account_cannot_change_password(configure, fake, client_factory):
    client = client_factory()
    login(client, fake.login("user-a"), fake.password("user-a"))
    response = client.post(
        f"{API}/auth/password",
        json={"current_password": fake.password("user-a"), "new_password": "x" * 16},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "external_identity"


# --- conflict and linking (S1), superadmin is local ---


def test_17_s1_same_email_local_account_conflict_then_link(
    configure, fake, root, make_user, make_project, client_factory, pg
):
    project = make_project()
    local_id, _ = make_user(fake.email("user-a"), memberships={project: ("analyst", "edit")})
    refused = login(client_factory(), fake.login("user-a"), fake.password("user-a"))
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "identity_conflict"
    assert audit_rows(pg, "auth.login", "denied")[-1][2]["reason"] == "email_taken_by_local"
    linked = root.patch(f"{API}/users/{local_id}", json={"auth_source": "ldap"})
    assert linked.status_code == 200, linked.text
    assert linked.json()["auth_source"] == "ldap"
    row = user_row(pg, fake.email("user-a"))
    assert row[3] is None and row[2] is None
    assert audit_rows(pg, "user_identity_linked")[-1][2] == {
        "auth_source": "ldap",
        "password_deleted": True,
    }
    # the old password no longer signs in locally; the directory does, and binds the id
    assert login(client_factory(), fake.email("user-a"), PASSWORD).status_code == 401
    ok = login(client_factory(), fake.login("user-a"), fake.password("user-a"))
    assert ok.status_code == 200
    assert ok.json()["user"]["id"] == str(local_id)
    row = user_row(pg, fake.email("user-a"))
    assert row[2] == fake.guid("user-a")
    assert memberships(pg, local_id) == {project: ("analyst", "edit", "manual")}


def test_17_s1_superadmin_must_stay_local(configure, fake, root, make_user, client_factory, pg):
    super_id, _ = make_user(superadmin="read")
    refused = root.patch(f"{API}/users/{super_id}", json={"auth_source": "ldap"})
    assert refused.status_code == 422
    assert refused.json()["error"]["code"] == "superadmin_must_be_local"
    login(client_factory(), fake.login("user-a"), fake.password("user-a"))
    ldap_id = user_row(pg, fake.email("user-a"))[0]
    promote = root.patch(
        f"{API}/users/{ldap_id}", json={"is_superadmin": True, "superadmin_access": "edit"}
    )
    assert promote.status_code == 422
    assert promote.json()["error"]["code"] == "superadmin_must_be_local"
    back = root.patch(f"{API}/users/{ldap_id}", json={"auth_source": "oidc"})
    assert back.status_code == 422
    assert back.json()["error"]["code"] == "auth_source_change_invalid"


def test_17_s1_database_refuses_external_superadmin(pg):
    with pytest.raises(Exception) as caught:
        pg.execute(
            "INSERT INTO users (id, email, password_hash, full_name, is_superadmin,"
            " superadmin_access, auth_source) VALUES (%s, %s, NULL, 'X', true, 'edit', 'ldap')",
            (uuid.uuid4(), f"x-{uuid.uuid4().hex[:6]}@example.test"),
        )
    assert "superadmin_is_local" in str(caught.value)
    with pytest.raises(Exception) as caught:
        pg.execute(
            "INSERT INTO users (id, email, password_hash, full_name, auth_source)"
            " VALUES (%s, %s, NULL, 'X', 'local')",
            (uuid.uuid4(), f"x-{uuid.uuid4().hex[:6]}@example.test"),
        )
    assert "password_only_local" in str(caught.value)


# --- identity_sync (acceptance 2: deactivation) ---


def _sync(settings, fake, now=None):
    from ffcore.core import db
    from ffcore.core.identity import run_identity_sync

    async def go():
        async with db.session_scope() as session:
            return await run_identity_sync(
                session,
                settings,
                fake.directory(settings) if settings.ldap_enabled else None,
                now=now,
            )

    return asyncio.run(go())


def test_17_2_identity_sync_deactivates_and_drops_session(configure, fake, client_factory, pg):
    settings = configure()
    client = client_factory()
    login(client, fake.login("user-a"), fake.password("user-a"))
    login(client_factory(), fake.login("user-b"), fake.password("user-b"))
    assert client.get(f"{API}/auth/me").status_code == 200
    fake.remove("user-a")
    fake.disable("user-b")
    report = _sync(settings, fake)
    assert report.error is None
    for name in ("user-a", "user-b"):
        row = user_row(pg, fake.email(name))
        assert row[4] is False
    assert client.get(f"{API}/auth/me").status_code == 401  # the open session dropped
    reasons = {r[2]["reason"] for r in audit_rows(pg, "user_deactivated")}
    assert {"directory_missing", "directory_disabled"} <= reasons
    again = login(client_factory(), fake.email("user-b"), fake.password("user-b"))
    assert again.status_code in (401, 403)


def test_17_2_identity_sync_directory_down_changes_nothing(configure, fake, client_factory, pg):
    settings = configure()
    login(client_factory(), fake.login("user-a"), fake.password("user-a"))
    fake.remove("user-a")
    fake.unreachable = True
    report = _sync(settings, fake)
    assert report.error == "directory_unreachable"
    assert user_row(pg, fake.email("user-a"))[4] is True
    last = pg.execute(
        "SELECT outcome, after FROM audit_events WHERE action = 'identity.sync'"
        " ORDER BY ts DESC LIMIT 1"
    ).fetchone()
    assert last[0] == "error" and last[1]["error"] == "directory_unreachable"


def test_17_2_identity_sync_oidc_idle_accounts(configure, app_settings, fake, pg):
    settings = configure(ldap=False)
    idle, fresh = uuid.uuid4(), uuid.uuid4()
    old = datetime.now(UTC) - timedelta(days=settings.oidc_inactive_after_days + 1)
    for user_id, last in ((idle, old), (fresh, datetime.now(UTC))):
        pg.execute(
            "INSERT INTO users (id, email, password_hash, full_name, auth_source, external_id,"
            " last_login_at) VALUES (%s, %s, NULL, 'O', 'oidc', %s, %s)",
            (user_id, f"o-{user_id.hex[:8]}@example.test", f"sub-{user_id.hex}", last),
        )
    _sync(settings, fake)
    active = dict(
        pg.execute("SELECT id, is_active FROM users WHERE id IN (%s, %s)", (idle, fresh)).fetchall()
    )
    assert active == {idle: False, fresh: True}


# --- mappings API ---


def test_17_mappings_project_admin_scope_and_validation(
    configure, fake, root, make_user, make_project, client_factory, pg
):
    own, other = make_project(), make_project()
    _, admin = make_user(memberships={own: ("admin", "edit")})
    client = client_factory(admin)
    created = map_group(client, own, fake.group("chat"))
    assert created["external_group"] == fake.group("chat").lower()  # DN stored lower-case
    assert (
        client.get(f"{API}/projects/{own}/identity-mappings").json()["data"][0]["id"]
        == (created["id"])
    )
    foreign = client.post(
        f"{API}/projects/{other}/identity-mappings",
        json={"provider": "ldap", "external_group": "cn=x", "role": "user"},
    )
    assert foreign.status_code == 404
    duplicate = client.post(
        f"{API}/projects/{own}/identity-mappings",
        json={"provider": "ldap", "external_group": fake.group("chat").upper(), "role": "user"},
    )
    assert duplicate.status_code == 409
    reserved = client.post(
        f"{API}/projects/{own}/identity-mappings",
        json={"provider": "ldap", "external_group": "cn=y", "role": "developer"},
    )
    assert reserved.status_code == 422
    assert client.get(f"{API}/identity-mappings").status_code == 403  # tenant list: superadmin
    listed = root.get(f"{API}/identity-mappings").json()
    assert any(m["id"] == created["id"] for m in listed["data"])
    assert audit_rows(pg, "create_identity_mapping", "success")


def test_17_mappings_read_only_admin_cannot_change(
    configure, make_user, make_project, client_factory
):
    project = make_project()
    _, reader = make_user(memberships={project: ("admin", "read")})
    response = client_factory(reader).post(
        f"{API}/projects/{project}/identity-mappings",
        json={"provider": "ldap", "external_group": "cn=z", "role": "user"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "read_only_access"


# --- user role in the matrix (user_edit / user_read) ---


@pytest.mark.parametrize("access", ["edit", "read"])
def test_17_user_role_matrix(access, configure, root, make_user, make_project, client_factory):
    project = make_project()
    added_id, email = make_user()
    added = root.post(
        f"{API}/projects/{project}/members",
        json={"user_id": str(added_id), "role": "user", "access": access},
    )
    assert added.status_code == 201  # `user` is assignable now
    client = client_factory(email)
    assert client.get(f"{API}/auth/me").json()["role"] == "user"
    assert client.get(f"{API}/projects/{project}/chat/agents").status_code == 200
    assert client.get(f"{API}/projects/{project}/conversations").status_code == 200
    assert client.get(f"{API}/projects/{project}/memories").status_code == 200
    for path in ("/agents", "/knowledge-bases", "/tools", "/members"):
        denied = client.get(f"{API}/projects/{project}{path}")
        assert denied.status_code == 403, path
        assert denied.json()["error"]["code"] == "insufficient_role"
    assert client.get(f"{API}/users").status_code == 403
    assert client.post(f"{API}/projects", json={"key": "nope-u", "name": "N"}).status_code == 403


# --- CSV import ---


def _csv(*lines):
    return io.BytesIO(("email,full_name,role,access,project_keys\n" + "\n".join(lines)).encode())


def test_17_import_dry_run_then_apply(
    configure, fake, root, make_user, make_project, client_factory, pg
):
    project = make_project()
    key = pg.execute("SELECT key FROM projects WHERE id = %s", (project,)).fetchone()[0]
    _, existing = make_user()
    login(client_factory(), fake.login("user-a"), fake.password("user-a"))
    tag = uuid.uuid4().hex[:6]
    body = [
        f"new-{tag}@example.test,New Person,user,read,{key}",
        f"{existing},Renamed Person,analyst,edit,{key}",
        "not-an-email,X,user,read,",
        f"bad-role-{tag}@example.test,X,developer,read,",
        f"unknown-{tag}@example.test,X,user,read,no-such-key",
        f"{fake.email('user-a')},X,user,read,",
        f"new-{tag}@example.test,Again,user,read,",
    ]
    preview = root.post(f"{API}/users/import", files={"file": ("u.csv", _csv(*body), "text/csv")})
    assert preview.status_code == 200, preview.text
    report = preview.json()
    assert report["dry_run"] is True
    assert report["summary"] == {"create": 1, "update": 1, "error": 5}
    codes = {r["line"]: r["code"] for r in report["rows"] if r["action"] == "error"}
    assert codes == {
        4: "invalid_email",
        5: "invalid_role",
        6: "unknown_project",
        7: "external_identity",
        8: "duplicate_email",
    }
    assert user_row(pg, f"new-{tag}@example.test") is None  # nothing written
    applied = root.post(
        f"{API}/users/import?dry_run=false", files={"file": ("u.csv", _csv(*body), "text/csv")}
    ).json()
    created = [r for r in applied["rows"] if r["action"] == "create"]
    assert len(created) == 1 and len(created[0]["temporary_password"]) >= 16
    temp = created[0]["temporary_password"]
    row = user_row(pg, f"new-{tag}@example.test")
    assert row[1] == "local" and row[6] is True
    assert memberships(pg, row[0]) == {project: ("user", "read", "manual")}
    # once: the password is in no audit row
    for audit in audit_rows(pg, "user_imported"):
        assert temp not in str(audit[2])
    me = login(client_factory(), f"new-{tag}@example.test", temp).json()
    assert me["user"]["must_change_password"] is True
    client = client_factory(f"new-{tag}@example.test", temp)
    # the temporary password opens only the password screen
    blocked = client.get(f"{API}/projects/{project}/chat/agents")
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "password_change_required"
    assert client.get(f"{API}/auth/me").status_code == 200
    changed = client.post(
        f"{API}/auth/password", json={"current_password": temp, "new_password": "y" * 16}
    )
    assert changed.status_code == 204
    assert user_row(pg, f"new-{tag}@example.test")[6] is False
    assert client.get(f"{API}/projects/{project}/chat/agents").status_code == 200


def test_17_import_header_and_permissions(configure, root, make_user, client_factory):
    bad = root.post(
        f"{API}/users/import",
        files={"file": ("u.csv", io.BytesIO(b"mail,name\nx,y\n"), "text/csv")},
    )
    assert bad.status_code == 422
    assert bad.json()["error"]["code"] == "import_header_invalid"
    _, reader = make_user(superadmin="read")
    denied = client_factory(reader).post(
        f"{API}/users/import", files={"file": ("u.csv", _csv(), "text/csv")}
    )
    assert denied.status_code == 403


# --- providers, status, secrets ---


def test_17_providers_and_status_without_secrets(configure, fake, root, client_factory, pg):
    settings = configure(local_login="superadmin_only")
    anonymous = client_factory()
    assert anonymous.get(f"{API}/auth/providers").json() == {
        "local": True,
        "ldap": True,
        "oidc": False,
    }
    status = root.get(f"{API}/identity-providers")
    assert status.status_code == 200
    body = status.json()
    assert body["local_login"] == "superadmin_only"
    ldap = next(p for p in body["providers"] if p["provider"] == "ldap")
    assert ldap["enabled"] and ldap["transport"] == "ldaps"
    tested = root.post(f"{API}/identity-providers/ldap/test")
    assert tested.status_code == 200 and tested.json()["ok"] is True
    fake.unreachable = True
    failed = root.post(f"{API}/identity-providers/ldap/test").json()
    assert failed["ok"] is False and failed["code"] == "directory_unreachable"
    secret = settings.ldap_bind_password.get_secret_value()
    for text in (status.text, tested.text, str(failed)):
        assert secret not in text
        assert fx.SERVICE_DN not in text
    configure(ldap=False, local_login="off")
    assert anonymous.get(f"{API}/auth/providers").json() == {
        "local": False,
        "ldap": False,
        "oidc": False,
    }


def test_17_no_credentials_in_logs_or_audit(configure, fake, client_factory, pg, caplog):
    caplog.set_level("DEBUG")
    login(client_factory(), fake.login("user-a"), fake.password("user-a"))
    login(client_factory(), fake.login("user-a"), "wrong-pw-for-scan")
    fake.unreachable = True
    login(client_factory(), fake.login("user-a"), fake.password("user-a"))
    secrets = (fx.SERVICE_PASSWORD, fake.password("user-a"), "wrong-pw-for-scan")
    for secret in secrets:
        assert secret not in caplog.text
    rows = pg.execute(
        "SELECT before::text, after::text FROM audit_events WHERE ts > now() - interval '1 min'"
    ).fetchall()
    for before, after in rows:
        for secret in secrets:
            assert secret not in (before or "") and secret not in (after or "")


# --- the resolver for 15 ---


def test_17_resolve_external_identity(configure, app_settings, fake, make_user, pg):
    from ffcore.core import db
    from ffcore.core.identity import resolve_external_identity

    settings = configure()
    _, email = make_user()

    async def resolve(value, auto):
        cfg = settings.model_copy(update={"auto_provision_from_channels": auto})
        async with db.session_scope() as session:
            user = await resolve_external_identity(
                session, email=value, settings=cfg, directory=fake.directory(cfg)
            )
            await session.commit()
            return user

    assert asyncio.run(resolve(email.upper(), False)).email == email
    assert asyncio.run(resolve(fake.email("user-b"), False)) is None
    assert user_row(pg, fake.email("user-b")) is None  # off: no account appears
    created = asyncio.run(resolve(fake.email("user-b"), True))
    assert created is not None and created.auth_source == "ldap"
    assert user_row(pg, fake.email("user-b"))[2] == fake.guid("user-b")
    assert asyncio.run(resolve("nobody@example.test", True)) is None
