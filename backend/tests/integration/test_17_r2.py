"""17-1 r2 (K-17-0008, KARARLAR '17-1 r1 kararları'): identity_sync refuses mass deactivation,
sync-deactivated accounts reopen, the unknown-email timing, linking without a provider and the
unlink path, an unchanged password, the concurrent first sign-in."""

import asyncio
import statistics
import time
import uuid

import pytest

from tests import ldap_fixture as fx
from tests.integration.conftest import PASSWORD, audit_rows
from tests.integration.test_17_identity import (  # noqa: F401 (fixtures)
    API,
    configure,
    fake,
    login,
    root,
    user_row,
)


def _isolate(pg, fake):
    """The integration database is shared: earlier tests leave directory accounts this fake
    directory does not know. They are soft-deleted here so the sync sees this test's accounts
    only (a missing account would count against the deactivation ratio)."""
    mine = [fake.guid(name) for name in fake.users]
    pg.execute(
        "UPDATE users SET deleted_at = now() WHERE auth_source IN ('ldap', 'oidc')"
        " AND deleted_at IS NULL AND (external_id IS NULL OR NOT external_id = ANY(%s))",
        (mine,),
    )


def _sync(settings, fake, *, force=False):
    from ffcore.core import db
    from ffcore.core.identity import run_identity_sync

    async def go():
        async with db.session_scope() as session:
            return await run_identity_sync(
                session, settings, fake.directory(settings), force=force
            )

    return asyncio.run(go())


def _extra_users(fake, count):
    """More directory accounts, so one missing account stays under the 0.2 ratio."""
    names = []
    for index in range(count):
        name = f"extra-{index}"
        base = dict(fake.users["user-a"])
        tag = uuid.uuid4().hex[:6]
        base.update(
            dn=f"cn={name}-{tag},ou=people,dc=example,dc=test",
            sAMAccountName=f"{name}-{tag}",
            mail=f"{name}-{tag}@example.test",
            userPrincipalName=f"{name}-{tag}@example.test",
            objectGUID=str(uuid.uuid4()),
        )
        fake.users[name] = base
        fake.put(name, dict(base))
        names.append(name)
    return names


def _sign_in_all(fake, client_factory, names):
    for name in names:
        response = login(client_factory(), fake.login(name), fake.password(name))
        assert response.status_code == 200, (name, response.text)


def _active(pg, fake, name):
    return user_row(pg, fake.email(name))[4]


# --- MAJOR-1: mass deactivation is refused ---


def test_17_r2_moved_base_refuses_and_changes_nothing(
    configure, fake, root, client_factory, pg
):
    """The reviewer's S4: the directory answers, but under a wrong base nobody is found."""
    settings = configure()
    names = ["user-a", "user-b", *_extra_users(fake, 3)]
    _sign_in_all(fake, client_factory, names)
    _isolate(pg, fake)
    rule = root.post(f"{API}/alert-rules", json={"kind": "identity_sync_refused", "channel": "ui"})
    assert rule.status_code == 201, rule.text
    moved = fx.ldap_settings(settings, ldap_user_base="ou=moved,dc=example,dc=test")
    report = _sync(moved, fake)
    assert report.error in ("identity_sync_refused", "directory_base_missing")
    assert report.deactivated == []
    assert all(_active(pg, fake, name) for name in names)
    last = pg.execute(
        "SELECT outcome, after FROM audit_events WHERE action = 'identity.sync'"
        " ORDER BY ts DESC LIMIT 1"
    ).fetchone()
    assert last[0] == "error"
    if report.error == "identity_sync_refused":
        alert = pg.execute(
            "SELECT payload FROM alerts WHERE kind = 'identity_sync_refused'"
            " ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        assert alert is not None and alert[0]["missing"] == len(names)


def test_17_r2_ratio_over_limit_refused_under_limit_applies(
    configure, fake, client_factory, pg
):
    settings = configure()
    names = ["user-a", "user-b", *_extra_users(fake, 3)]  # five accounts
    _sign_in_all(fake, client_factory, names)
    _isolate(pg, fake)
    fake.remove("extra-0")
    fake.remove("extra-1")  # 2/5 = 0.4 > 0.2
    refused = _sync(settings, fake)
    assert refused.error == "identity_sync_refused" and refused.deactivated == []
    assert _active(pg, fake, "extra-0") and _active(pg, fake, "extra-1")
    fake.put("extra-1", dict(fake.users["extra-1"]))  # back: 1/5 = 0.2, not over the limit
    applied = _sync(settings, fake)
    assert applied.error is None
    assert not _active(pg, fake, "extra-0")
    assert _active(pg, fake, "extra-1")
    row = pg.execute(
        "SELECT deactivated_by FROM users WHERE lower(email) = lower(%s)",
        (fake.email("extra-0"),),
    ).fetchone()
    assert row[0] == "identity_sync"


def test_17_r2_force_overrides_the_ratio(configure, fake, client_factory, pg):
    settings = configure()
    names = ["user-a", "user-b"]
    _sign_in_all(fake, client_factory, names)
    _isolate(pg, fake)
    fake.remove("user-a")
    assert _sync(settings, fake).error == "identity_sync_refused"  # 1/2
    forced = _sync(settings, fake, force=True)
    assert forced.error is None and not _active(pg, fake, "user-a")
    after = pg.execute(
        "SELECT after FROM audit_events WHERE action = 'identity.sync'"
        " ORDER BY ts DESC LIMIT 1"
    ).fetchone()[0]
    assert after["forced"] is True


def test_17_r2_sync_deactivated_account_reopens_at_sign_in(
    configure, fake, client_factory, pg
):
    settings = configure()
    names = ["user-a", "user-b", *_extra_users(fake, 3)]
    _sign_in_all(fake, client_factory, names)
    _isolate(pg, fake)
    fake.disable("user-a")  # disabled, not missing: no ratio involved
    assert _sync(settings, fake).error is None
    assert not _active(pg, fake, "user-a")
    fake.put("user-a", {**fake.users["user-a"], "userAccountControl": 512})
    response = login(client_factory(), fake.login("user-a"), fake.password("user-a"))
    assert response.status_code == 200, response.text
    assert _active(pg, fake, "user-a")
    assert any(r[2]["reason"] == "directory_sign_in" for r in audit_rows(pg, "user_reactivated"))


def test_17_r2_sync_reopens_an_account_seen_again(configure, fake, client_factory, pg):
    settings = configure()
    names = ["user-a", "user-b", *_extra_users(fake, 3)]
    _sign_in_all(fake, client_factory, names)
    _isolate(pg, fake)
    fake.disable("user-b")
    _sync(settings, fake)
    assert not _active(pg, fake, "user-b")
    fake.put("user-b", {**fake.users["user-b"], "userAccountControl": 512})
    report = _sync(settings, fake)
    assert report.error is None and _active(pg, fake, "user-b")
    assert any(r[2]["reason"] == "identity_sync" for r in audit_rows(pg, "user_reactivated"))


def test_17_r2_admin_deactivation_is_not_reopened(configure, fake, root, client_factory, pg):
    configure()
    login(client_factory(), fake.login("user-a"), fake.password("user-a"))
    user_id = user_row(pg, fake.email("user-a"))[0]
    assert root.patch(f"{API}/users/{user_id}", json={"is_active": False}).status_code == 200
    refused = login(client_factory(), fake.login("user-a"), fake.password("user-a"))
    assert refused.status_code == 403
    assert refused.json()["error"]["code"] == "user_inactive"
    row = pg.execute("SELECT deactivated_by FROM users WHERE id = %s", (user_id,)).fetchone()
    assert row[0] == "admin"
    assert root.patch(f"{API}/users/{user_id}", json={"is_active": True}).status_code == 200
    row = pg.execute("SELECT deactivated_by FROM users WHERE id = %s", (user_id,)).fetchone()
    assert row[0] is None


# --- MINOR-1: an unknown email takes as long as a wrong password ---


def test_17_r2_unknown_email_timing(configure, make_user, client_factory):
    configure(ldap=False)
    _, known = make_user()
    client = client_factory()

    def median(email):
        samples = []
        for _ in range(8):
            started = time.perf_counter()
            response = login(client, email, "wrong-password-0000")
            samples.append(time.perf_counter() - started)
            assert response.status_code == 401
        return statistics.median(samples)

    login(client, known, "warm-up-0000000")
    unknown = median(f"nobody-{uuid.uuid4().hex[:8]}@example.test")
    existing = median(known)
    assert max(unknown, existing) / min(unknown, existing) < 1.5, (unknown, existing)


# --- MINOR-4: linking needs a configured provider; unlink before the first sign-in ---


def test_17_r2_link_needs_a_configured_provider(configure, root, make_user, pg):
    configure(ldap=False)
    user_id, _ = make_user()
    for source in ("oidc", "ldap"):
        refused = root.patch(f"{API}/users/{user_id}", json={"auth_source": source})
        assert refused.status_code == 422, source
        assert refused.json()["error"]["code"] == "identity_provider_not_configured"
    assert pg.execute(
        "SELECT password_hash IS NOT NULL FROM users WHERE id = %s", (user_id,)
    ).fetchone()[0]


def test_17_r2_unlink_before_binding_then_not_after(
    configure, fake, root, make_user, client_factory, pg
):
    configure()
    user_id, email = make_user(fake.email("user-a"))
    assert root.patch(f"{API}/users/{user_id}", json={"auth_source": "ldap"}).status_code == 200
    back = root.patch(f"{API}/users/{user_id}", json={"auth_source": "local"})
    assert back.status_code == 200, back.text
    body = back.json()
    assert body["auth_source"] == "local" and body["must_change_password"] is True
    temporary = body["temporary_password"]
    assert temporary and len(temporary) >= 16
    assert root.get(f"{API}/users/{user_id}").json().get("temporary_password") is None
    unlinked = audit_rows(pg, "user_identity_unlinked")[-1][2]
    assert temporary not in str(unlinked)
    assert login(client_factory(), email, temporary).status_code == 200
    # linked and bound: no way back
    assert root.patch(f"{API}/users/{user_id}", json={"auth_source": "ldap"}).status_code == 200
    assert login(client_factory(), fake.login("user-a"), fake.password("user-a")).status_code == 200
    refused = root.patch(f"{API}/users/{user_id}", json={"auth_source": "local"})
    assert refused.status_code == 422
    assert refused.json()["error"]["code"] == "auth_source_change_invalid"


# --- NOTE-3: the same password is not a change ---


def test_17_r2_unchanged_password_refused(configure, make_user, client_factory):
    configure(ldap=False)
    _, email = make_user()
    client = client_factory(email)
    response = client.post(
        f"{API}/auth/password", json={"current_password": PASSWORD, "new_password": PASSWORD}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "password_unchanged"


# --- NOTE-5: two first sign-ins at once make one account ---


def test_17_r2_concurrent_first_provision_rereads(configure, fake):
    from ffcore.core import db
    from ffcore.core.identity import provision
    from ffcore.core.ldap_auth import DirectoryUser

    settings = configure()
    found = DirectoryUser(
        provider="ldap",
        external_id=str(uuid.uuid4()),
        email=f"race-{uuid.uuid4().hex[:6]}@example.test",
        full_name="Race",
        groups=frozenset(),
        active=True,
    )

    async def go():
        first = db.session_scope()
        second = db.session_scope()
        async with first as one, second as two:
            winner = await provision(one, found, settings)
            racing = asyncio.create_task(provision(two, found, settings))
            await asyncio.sleep(0.5)  # the second insert waits on the first's row lock
            await one.commit()
            loser = await racing
            await two.commit()
            return winner.id, loser.id

    winner, loser = asyncio.run(go())
    assert winner == loser


@pytest.mark.parametrize("value", ["identity_sync", "admin", None])
def test_17_r2_deactivated_by_values(value, pg):
    user_id = uuid.uuid4()
    pg.execute(
        "INSERT INTO users (id, email, password_hash, full_name, is_active, deactivated_by)"
        " VALUES (%s, %s, 'x', 'D', false, %s)",
        (user_id, f"d-{user_id.hex[:8]}@example.test", value),
    )
