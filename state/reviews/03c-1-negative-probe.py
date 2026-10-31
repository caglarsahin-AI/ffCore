"""Reviewer's probes for 03c-1 (K-03c-0009). Copied into backend/tests/integration/ for one run, then
removed. They reuse the branch's own fixtures and helpers (test_03c_keys)."""

import uuid

import pytest

from tests.integration.test_03c_keys import PROBE, _client, _create, _who, owner, probe  # noqa: F401


def _bad():
    return "ffk_deadbeef_" + "x" * 43


def _rows(pg, ip, action):
    return pg.execute(
        "SELECT count(*) FROM audit_events WHERE action = %s AND ip = %s", (action, ip)
    ).fetchone()[0]


def test_rev_03c_neg_1_blocked_requests_do_not_grow_the_audit_table_without_bound(
    app, owner, probe, app_settings, pg
):
    ip = f"192.0.2.{uuid.uuid4().int % 200 + 20}"
    for _ in range(app_settings.api_key_auth_failures_per_min):
        assert _who(app, _bad(), ip=ip).status_code == 401
    before = _rows(pg, ip, "api_key_auth_rate_limited")
    for _ in range(30):
        assert _who(app, _bad(), ip=ip).status_code == 429
    after = _rows(pg, ip, "api_key_auth_rate_limited")
    print("AUDIT_ROWS_FOR_30_BLOCKED_REQUESTS:", after - before)
    assert after - before <= 3, f"{after - before} audit rows for 30 blocked requests"


def test_rev_03c_neg_2_bare_key_cannot_manage_keys(app, owner, probe):
    project, client = owner
    created = _create(client, project)
    headers = {"Authorization": f"Bearer {created['key']}"}
    c = _client(app, "203.0.113.10")
    try:
        post = c.post(
            f"/api/v1/projects/{project}/api-keys",
            json={"name": "x", "scopes": ["chat_direct"]},
            headers=headers,
        )
        listing = c.get(f"/api/v1/projects/{project}/api-keys", headers=headers)
    finally:
        c.__exit__(None, None, None)
    print("BARE_KEY_POST:", post.status_code, "LIST:", listing.status_code)
    assert post.status_code in (401, 403, 404), post.text
    assert listing.status_code in (401, 403, 404), listing.text


def test_rev_03c_neg_3_raw_key_nowhere_in_the_audit_table(owner, pg):
    project, client = owner
    created = _create(client, project)
    key_id = created["id"]
    assert client.patch(
        f"/api/v1/projects/{project}/api-keys/{key_id}", json={"name": "renamed"}
    ).status_code == 200
    assert client.post(f"/api/v1/projects/{project}/api-keys/{key_id}/revoke").status_code == 200
    secret = created["key"].rsplit("_", 1)[-1]
    hits = pg.execute(
        "SELECT count(*) FROM audit_events WHERE row_to_json(audit_events)::text LIKE %s",
        (f"%{secret}%",),
    ).fetchone()[0]
    in_keys = pg.execute(
        "SELECT count(*) FROM api_keys WHERE row_to_json(api_keys)::text LIKE %s", (f"%{secret}%",)
    ).fetchone()[0]
    assert (hits, in_keys) == (0, 0)


def test_rev_03c_neg_4_forwarded_for_cannot_satisfy_a_cidr(app, owner, probe):
    project, client = owner
    created = _create(client, project, allowed_cidrs=["203.0.113.0/24"])
    spoofed = _who(
        app,
        created["key"],
        ip="198.51.100.9",
        headers={"X-Forwarded-For": "203.0.113.10", "X-Real-IP": "203.0.113.10"},
    )
    assert spoofed.status_code == 403, spoofed.text
    assert spoofed.json()["error"]["code"] == "ip_not_allowed"
    assert _who(app, created["key"], ip="203.0.113.10").status_code == 200


def test_rev_03c_neg_5_unreachable_redis_never_accepts_a_key(app, owner, probe, monkeypatch):
    import redis.asyncio as aioredis

    project, client = owner
    created = _create(client, project)
    monkeypatch.setattr(
        "ffcore.services.keys._redis", lambda settings: aioredis.from_url("redis://127.0.0.1:1")
    )
    try:
        status = _who(app, created["key"]).status_code
    except Exception as exc:  # the test client re-raises an unhandled server error
        print("REDIS_DOWN_EXCEPTION:", type(exc).__name__)
        status = 500
    print("REDIS_DOWN_STATUS:", status)
    assert status != 200
