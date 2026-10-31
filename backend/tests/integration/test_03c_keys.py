"""03c API keys: create, list, change, revoke; the key resolver behind resolve_actor (C2).

The key is checked on every request (revoked_at, expires_at, allowed_cidrs); a wrong key answers
401 the same way whether its prefix exists or not; repeated failures from one address are rate
limited (K-03c-0004 condition 5). A probe route mounted for the test returns the resolved actor.
"""

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

import pytest
from fastapi import Depends, Request
from fastapi.testclient import TestClient

from tests.integration.conftest import CONSOLE_ORIGIN, audit_rows

PROBE = "/__test03c/whoami"


@pytest.fixture
def probe(app):
    """A route that only resolves the caller, so a key can be tested without a facade (06b)."""
    from ffcore.core.auth import Actor, resolve_actor
    from ffcore.services.keys import acl_role_of

    async def whoami(request: Request, actor: Annotated[Actor, Depends(resolve_actor)]):
        return {
            "actor_type": actor.actor_type,
            "actor_id": actor.actor_id,
            "project_id": actor.project_id,
            "scopes": sorted(actor.scopes),
            "acl_role": actor.acl_role,
            "via_service": actor.via_service,
        }

    app.router.add_api_route(PROBE, whoami, methods=["GET"])
    yield acl_role_of
    app.router.routes[:] = [r for r in app.router.routes if getattr(r, "path", None) != PROBE]


def _client(app, ip="203.0.113.10"):
    client = TestClient(app, base_url=CONSOLE_ORIGIN, client=(ip, 50000))
    client.__enter__()
    return client


@pytest.fixture
def owner(make_project, make_user, client_factory):
    project = make_project()
    _, email = make_user(memberships={project: ("admin", "edit")})
    return project, client_factory(email)


def _create(client, project, **body):
    payload = {"name": "ci", "scopes": ["chat_direct"]} | body
    response = client.post(f"/api/v1/projects/{project}/api-keys", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _who(app, key, ip="203.0.113.10", headers=None):
    client = _client(app, ip)
    try:
        return client.get(PROBE, headers={"Authorization": f"Bearer {key}", **(headers or {})})
    finally:
        client.__exit__(None, None, None)


# --- 3: no raw key in the database; verified by hash; raw value returned once ---


def test_03c_3_raw_key_not_stored(owner, pg):
    project, client = owner
    created = _create(client, project)
    raw = created["key"]
    rows = pg.execute("SELECT key_prefix, key_hash FROM api_keys WHERE id = %s", (created["id"],))
    prefix, key_hash = rows.fetchone()
    assert raw.startswith(prefix) and raw != prefix
    assert key_hash == hashlib.sha256(raw.encode()).hexdigest()
    dump = pg.execute("SELECT row_to_json(k)::text FROM api_keys k WHERE id = %s", (created["id"],))
    assert raw not in dump.fetchone()[0]


def test_03c_3_key_verified_by_hash(app, owner, probe):
    project, client = owner
    created = _create(client, project, scopes=["chat_direct", "kb_search"])
    response = _who(app, created["key"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["actor_type"] == "api_key" and body["actor_id"] == created["id"]
    assert body["project_id"] == str(project)
    assert body["scopes"] == ["chat_direct", "kb_search"]
    # One changed character is a different key.
    tampered = created["key"][:-1] + ("A" if created["key"][-1] != "A" else "B")
    assert _who(app, tampered).status_code == 401


def test_03c_3_raw_key_returned_once(owner):
    project, client = owner
    created = _create(client, project)
    listed = client.get(f"/api/v1/projects/{project}/api-keys").json()["data"]
    assert [k["id"] for k in listed] == [created["id"]]
    assert "key" not in listed[0] and listed[0]["key_prefix"] == created["key_prefix"]
    one = client.get(f"/api/v1/projects/{project}/api-keys/{created['id']}").json()
    assert "key" not in one


# --- 6: allowed_cidrs, revoked_at and expires_at on every request; uniform 401 ---


def test_03c_6_cidr_denied_openai_shape(app, owner, probe):
    project, client = owner
    created = _create(client, project, allowed_cidrs=["198.51.100.0/24"])
    assert _who(app, created["key"], ip="198.51.100.7").status_code == 200
    response = _who(app, created["key"], ip="203.0.113.10")
    assert response.status_code == 403
    assert response.json() == {
        "error": {
            "message": response.json()["error"]["message"],
            "type": "permission_error",
            "code": "ip_not_allowed",
        }
    }


def test_03c_6_revoked_key_next_request_401(app, owner, probe):
    project, client = owner
    created = _create(client, project)
    assert _who(app, created["key"]).status_code == 200
    revoked = client.post(f"/api/v1/projects/{project}/api-keys/{created['id']}/revoke")
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["revoked_at"] is not None
    response = _who(app, created["key"])
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_api_key"


def test_03c_6_expired_key_401(app, owner, probe, pg):
    project, client = owner
    created = _create(client, project)
    pg.execute(
        "UPDATE api_keys SET expires_at = %s WHERE id = %s",
        (datetime.now(UTC) - timedelta(seconds=1), created["id"]),
    )
    assert _who(app, created["key"]).json()["error"]["code"] == "invalid_api_key"


def test_03c_6_unknown_prefix_same_answer(app, owner, probe):
    project, client = owner
    created = _create(client, project)
    unknown = "ffk_00000000_" + created["key"].split("_", 2)[2]
    a, b = _who(app, unknown, ip="203.0.113.21"), _who(app, created["key"] + "x", ip="203.0.113.21")
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()


def test_03c_6_auth_failures_rate_limited(app, owner, probe, app_settings, pg):
    project, client = owner
    created = _create(client, project)
    ip = f"192.0.2.{uuid.uuid4().int % 200 + 20}"
    limit = app_settings.api_key_auth_failures_per_min
    for _ in range(limit):
        assert _who(app, "ffk_deadbeef_" + "x" * 43, ip=ip).status_code == 401
    blocked = _who(app, "ffk_deadbeef_" + "x" * 43, ip=ip)
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "too_many_auth_failures"
    # A valid key from the blocked address waits too: the limit is per address, not per key.
    assert _who(app, created["key"], ip=ip).status_code == 429
    rows = pg.execute(
        "SELECT actor_type, actor_id, outcome FROM audit_events"
        " WHERE action = 'api_key_auth_rate_limited' AND ip = %s",
        (ip,),
    ).fetchall()
    # No actor is known: the 03b convention for that (impersonation_denied) is system/anonymous;
    # audit_events.actor_type stays user|api_key|system (C2 ActorType).
    assert rows and set(rows) == {("system", "anonymous", "denied")}


def test_03c_6_last_used_at_buffered(app, owner, probe, pg):
    project, client = owner
    created = _create(client, project)
    _who(app, created["key"])
    first = pg.execute("SELECT last_used_at FROM api_keys WHERE id = %s", (created["id"],))
    stamp = first.fetchone()[0]
    assert stamp is not None
    _who(app, created["key"])
    second = pg.execute("SELECT last_used_at FROM api_keys WHERE id = %s", (created["id"],))
    assert second.fetchone()[0] == stamp  # within API_KEY_LAST_USED_FLUSH_S: not rewritten


# --- 7: acl_role; a key never reaches console project routes (_grant unchanged) ---


def test_03c_7_key_acl_role_without_impersonate(app, owner, probe):
    project, client = owner
    created = _create(client, project, acl_role="developer")
    assert _who(app, created["key"]).json()["acl_role"] == "developer"
    assert created["acl_role"] == "developer"


def test_03c_7_default_acl_role_is_analyst(owner):
    project, client = owner
    assert _create(client, project)["acl_role"] == "analyst"


def test_03c_7_key_not_a_console_member(app, owner, make_project):
    project, client = owner
    created = _create(client, project)
    api = _client(app)
    try:
        auth = {"Authorization": f"Bearer {created['key']}"}
        own = api.get(f"/api/v1/projects/{project}/approvals", headers=auth)
        other = api.get(f"/api/v1/projects/{make_project()}/approvals", headers=auth)
    finally:
        api.__exit__(None, None, None)
    # _grant: a non-user actor has no membership (403 insufficient_role), as before 03c.
    assert own.status_code == 403 and own.json()["error"]["code"] == "insufficient_role"
    assert other.status_code == 403


ACL_PROBE = "/__test03c/projects/{project_id}/acl"
NET = ["203.0.113.0/24"]


@pytest.fixture
def acl_probe(app, probe):
    """A project route behind require_role, as KB search is: the grant decides the ACL role."""
    from ffcore.core.auth import Actor, require_role
    from ffcore.services.keys import acl_role_of

    async def acl(
        project_id: str,
        request: Request,
        actor: Annotated[Actor, Depends(require_role("analyst"))],
    ):
        return {
            "actor_type": actor.actor_type,
            "actor_id": actor.actor_id,
            "via_key_id": actor.via_key_id,
            "acl_role": acl_role_of(actor, request.state.grant),
        }

    app.router.add_api_route(ACL_PROBE, acl, methods=["GET"])
    yield
    app.router.routes[:] = [r for r in app.router.routes if getattr(r, "path", None) != ACL_PROBE]


def _token(settings, user_id, project, **kw):
    from ffcore.core.auth import sign_on_behalf_of

    return sign_on_behalf_of(
        user_id=str(user_id),
        project_id=str(project),
        audience=kw.pop("audience", settings.obo_audience),
        settings=settings,
        **kw,
    )


def _as(app, key, token, path):
    client = _client(app)
    try:
        headers = {"Authorization": f"Bearer {key}", "X-On-Behalf-Of": token}
        return client.get(path, headers=headers)
    finally:
        client.__exit__(None, None, None)


@pytest.fixture
def impersonator(owner):
    project, client = owner
    created = _create(
        client, project, scopes=["impersonate", "chat_direct"], acl_role="admin", allowed_cidrs=NET
    )
    return project, created


def test_03c_7a_other_project_token_403(
    app, impersonator, acl_probe, make_project, make_user, app_settings, pg
):
    """K-03c-0006 (a): project A's key with project B's token → 403, nothing runs as B's user."""
    project_a, key = impersonator
    project_b = make_project()
    user_id, _ = make_user(memberships={project_b: ("admin", "edit")})
    token = _token(app_settings, user_id, project_b)
    response = _as(app, key["key"], token, ACL_PROBE.format(project_id=project_b))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "impersonation_denied"
    assert str(project_b) not in response.text and str(project_a) not in response.text
    row = pg.execute(
        "SELECT actor_type, actor_id, after FROM audit_events"
        " WHERE action = 'impersonation_denied' AND actor_id = %s",
        (key["id"],),
    ).fetchone()
    assert row[0] == "api_key"
    assert row[2]["reason"] == "obo_project_scope"
    assert row[2]["token_project_id"] == str(project_b)


def test_03c_7b_impersonate_uses_member_role(app, impersonator, acl_probe, make_user, app_settings):
    """(b) Same project, the user is a member: the user acts, ACL is the user's role."""
    project, key = impersonator
    user_id, _ = make_user(memberships={project: ("analyst", "edit")})
    token = _token(app_settings, user_id, project)
    body = _as(app, key["key"], token, ACL_PROBE.format(project_id=project)).json()
    assert body["actor_type"] == "user" and body["actor_id"] == str(user_id)
    assert body["via_key_id"] == key["id"]
    assert body["acl_role"] == "analyst"  # not the key's admin acl_role


def test_03c_7c_impersonated_non_member_404(app, impersonator, acl_probe, make_user, app_settings):
    """(c) The user is not a member of the key's project: _grant's 404."""
    project, key = impersonator
    user_id, _ = make_user()
    token = _token(app_settings, user_id, project)
    response = _as(app, key["key"], token, ACL_PROBE.format(project_id=project))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "project_not_found"


def test_03c_7d_no_scope_key_with_obo_403(app, owner, probe, make_user, app_settings, pg):
    """(d) A key without impersonate that sends X-On-Behalf-Of fails loud (K-03c-0006 item 2)."""
    project, client = owner
    created = _create(client, project)
    user_id, _ = make_user(memberships={project: ("analyst", "edit")})
    response = _as(app, created["key"], _token(app_settings, user_id, project), PROBE)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "impersonation_denied"
    rows = pg.execute(
        "SELECT actor_type FROM audit_events WHERE action = 'impersonation_denied'"
        " AND actor_id = %s",
        (created["id"],),
    ).fetchall()
    assert rows == [("api_key",)]


def test_03c_7e_bad_key_never_impersonates(app, impersonator, probe, make_user, app_settings, pg):
    """(e) A revoked key with a valid token: 401, and no impersonation is attempted."""
    project, key = impersonator
    user_id, _ = make_user(memberships={project: ("analyst", "edit")})
    pg.execute("UPDATE api_keys SET revoked_at = now() WHERE id = %s", (key["id"],))
    response = _as(app, key["key"], _token(app_settings, user_id, project), PROBE)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_api_key"
    outside = _who(
        app,
        key["key"],
        ip="198.51.100.9",
        headers={"X-On-Behalf-Of": _token(app_settings, user_id, project)},
    )
    assert outside.status_code in (401, 403)


def test_03c_7f_bad_token_rejected(app, impersonator, probe, make_user, app_settings):
    """(f) Wrong audience 403 audience_mismatch, expired 401 token_expired (03b rules)."""
    project, key = impersonator
    user_id, _ = make_user(memberships={project: ("analyst", "edit")})
    wrong = _as(app, key["key"], _token(app_settings, user_id, project, audience="other"), PROBE)
    assert wrong.status_code == 403 and wrong.json()["error"]["code"] == "audience_mismatch"
    old = datetime.now(UTC) - timedelta(minutes=10)
    expired = _as(app, key["key"], _token(app_settings, user_id, project, now=old), PROBE)
    assert expired.status_code == 401 and expired.json()["error"]["code"] == "token_expired"


def test_03c_7g_service_token_any_project_unchanged(
    app, acl_probe, make_project, make_user, app_settings
):
    """(g) Regression: the service account may act for a user of any project."""
    project_b = make_project()
    user_id, _ = make_user(memberships={project_b: ("analyst", "edit")})
    client = _client(app)
    try:
        response = client.get(
            ACL_PROBE.format(project_id=project_b),
            headers={
                "Authorization": f"Bearer {app_settings.service_token.get_secret_value()}",
                "X-On-Behalf-Of": _token(app_settings, user_id, project_b),
            },
        )
    finally:
        client.__exit__(None, None, None)
    assert response.status_code == 200, response.text
    assert response.json()["actor_id"] == str(user_id)
    assert response.json()["via_key_id"] is None


def test_03c_7h_no_superadmin_under_obo(app, impersonator, acl_probe, make_user, app_settings):
    """(h) A superadmin reached through a key is only a project member (no superadmin rights)."""
    project, key = impersonator
    user_id, _ = make_user(superadmin="edit")
    response = _as(
        app,
        key["key"],
        _token(app_settings, user_id, project),
        ACL_PROBE.format(project_id=project),
    )
    assert response.status_code == 404


def test_03c_7i_impersonate_requires_cidrs(owner):
    """K-03c-0006 item 4: the strongest scope is never usable from anywhere."""
    project, client = owner
    response = client.post(
        f"/api/v1/projects/{project}/api-keys",
        json={"name": "x", "scopes": ["impersonate"]},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "cidrs_required_for_impersonate"
    created = _create(client, project, scopes=["chat_direct"])
    patched = client.patch(
        f"/api/v1/projects/{project}/api-keys/{created['id']}", json={"scopes": ["impersonate"]}
    )
    assert patched.status_code == 422


def test_03c_7_audit_impersonated_mutation_has_via_key(
    app, impersonator, make_user, app_settings, pg
):
    """K-03c-0006 item 3: a mutation done through an impersonating key is the user's, with the
    key's id beside it."""
    project, key = impersonator
    user_id, _ = make_user(memberships={project: ("admin", "edit")})
    token = _token(app_settings, user_id, project)
    client = _client(app)
    try:
        response = client.post(
            f"/api/v1/projects/{project}/api-keys",
            json={"name": "child", "scopes": ["chat_direct"]},
            headers={"Authorization": f"Bearer {key['key']}", "X-On-Behalf-Of": token},
        )
    finally:
        client.__exit__(None, None, None)
    assert response.status_code == 201, response.text
    row = pg.execute(
        "SELECT actor_type, actor_id, via_key_id FROM audit_events"
        " WHERE action = 'create_api_key' AND resource_id = %s",
        (response.json()["id"],),
    ).fetchone()
    assert row == ("user", str(user_id), uuid.UUID(key["id"]))


def test_03c_7_impersonate_needs_admin(make_project, make_user, client_factory):
    project = make_project()
    _, email = make_user(memberships={project: ("analyst", "edit")})
    client = client_factory(email)
    response = client.post(
        f"/api/v1/projects/{project}/api-keys", json={"name": "x", "scopes": ["impersonate"]}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "scope_not_allowed"
    higher = client.post(
        f"/api/v1/projects/{project}/api-keys",
        json={"name": "x", "scopes": ["chat_direct"], "acl_role": "admin"},
    )
    assert higher.status_code == 403
    assert higher.json()["error"]["code"] == "scope_not_allowed"


# --- 8: audit actor_type=api_key; key mutations audited, raw key never in audit ---


def test_03c_8_key_mutations_audited_masked(owner, pg):
    project, client = owner
    created = _create(client, project)
    key_id = created["id"]
    patched = client.patch(
        f"/api/v1/projects/{project}/api-keys/{key_id}", json={"scopes": ["agents", "kb_search"]}
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["scopes"] == ["agents", "kb_search"]
    client.post(f"/api/v1/projects/{project}/api-keys/{key_id}/revoke")
    for action in ("create_api_key", "update_api_key", "revoke_api_key"):
        rows = audit_rows(pg, action, "success", project)
        assert len([r for r in rows if r[2] and r[2].get("id") == key_id]) == 1, action
    dump = pg.execute(
        "SELECT string_agg(after::text, '') FROM audit_events WHERE project_id = %s", (project,)
    ).fetchone()[0]
    assert created["key"] not in dump
    update = audit_rows(pg, "update_api_key", "success", project)[-1]
    assert update[2]["scopes"] == ["agents", "kb_search"]  # scope change visible in the trail


def test_03c_8_audit_actor_api_key(app, owner, probe, make_user, pg, app_settings):
    """The key as actor reaches audit through resolve_actor (impersonation_denied path)."""
    from ffcore.core.auth import sign_on_behalf_of

    project, client = owner
    created = _create(client, project)
    user_id, _ = make_user()
    token = sign_on_behalf_of(
        user_id=str(user_id),
        project_id=str(project),
        audience=app_settings.obo_audience,
        settings=app_settings,
    )
    _who(app, created["key"], headers={"X-On-Behalf-Of": token})
    actor_types = pg.execute(
        "SELECT DISTINCT actor_type FROM audit_events WHERE actor_id = %s", (created["id"],)
    ).fetchall()
    assert actor_types == [("api_key",)]


# --- 9: everyone lists only their own keys; admin lists all ---


def test_03c_9_list_own_keys_only(make_project, make_user, client_factory):
    project = make_project()
    _, a_mail = make_user(memberships={project: ("analyst", "edit")})
    _, b_mail = make_user(memberships={project: ("analyst", "edit")})
    a, b = client_factory(a_mail), client_factory(b_mail)
    mine = _create(a, project)
    _create(b, project)
    listed = a.get(f"/api/v1/projects/{project}/api-keys").json()["data"]
    assert [k["id"] for k in listed] == [mine["id"]]
    assert a.get(f"/api/v1/projects/{project}/api-keys?all=true").status_code == 403
    other = b.get(f"/api/v1/projects/{project}/api-keys").json()["data"][0]["id"]
    assert a.get(f"/api/v1/projects/{project}/api-keys/{other}").status_code == 404
    assert a.post(f"/api/v1/projects/{project}/api-keys/{other}/revoke").status_code == 404


def test_03c_9_admin_lists_all(make_project, make_user, client_factory):
    project = make_project()
    _, admin_mail = make_user(memberships={project: ("admin", "edit")})
    _, user_mail = make_user(memberships={project: ("analyst", "edit")})
    admin, user = client_factory(admin_mail), client_factory(user_mail)
    _create(admin, project)
    theirs = _create(user, project)
    listed = admin.get(f"/api/v1/projects/{project}/api-keys?all=true").json()["data"]
    assert len(listed) == 2
    revoked = admin.post(f"/api/v1/projects/{project}/api-keys/{theirs['id']}/revoke")
    assert revoked.status_code == 200


def test_03c_21_read_mode_403(make_project, make_user, client_factory):
    project = make_project()
    _, email = make_user(memberships={project: ("admin", "read")})
    client = client_factory(email)
    response = client.post(
        f"/api/v1/projects/{project}/api-keys", json={"name": "x", "scopes": ["chat_direct"]}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "read_only_access"
    assert client.get(f"/api/v1/projects/{project}/api-keys").status_code == 200


def test_03c_7_via_key_id_in_new_partitions(pg):
    """K-03c-0007 (2): a partition made after 03c_0001 has the column too (PARTITION OF)."""
    name = pg.execute("SELECT ffcore_audit_ensure_partition(date '2031-03-01')").fetchone()[0]
    columns = pg.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = %s", (name,)
    ).fetchall()
    assert ("via_key_id",) in columns
    key_id = uuid.uuid4()
    pg.execute(
        "INSERT INTO audit_events (id, ts, actor_type, actor_id, action, resource_type, outcome,"
        " via_key_id) VALUES (%s, '2031-03-05', 'user', 'u', 'probe_03c', 'probe', 'success', %s)",
        (uuid.uuid4(), key_id),
    )
    row = pg.execute(
        "SELECT via_key_id FROM audit_events WHERE action = 'probe_03c' AND ts = '2031-03-05'"
    ).fetchone()
    assert row == (key_id,)
    # Append-only stays as it was (03b trigger).
    with pytest.raises(Exception, match="append-only"):
        pg.execute("UPDATE audit_events SET via_key_id = NULL WHERE action = 'probe_03c'")
