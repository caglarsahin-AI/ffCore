"""03c-1 review r1 (K-03c-0013): unauthenticated or refused callers cannot grow audit_events
without bound. Rate-limited key attempts and refused X-On-Behalf-Of headers write at most one
row per address and 60 s (the next window's first row carries how many were held back), all
addresses together at most AUDIT_GLOBAL_CAP rows a minute (then one `audit_rate_capped`).
Without Redis a key cannot be checked: 503 `auth_backend_unavailable`, and nothing is written.
"""

import asyncio
import random
import time
import uuid

from fastapi.testclient import TestClient
from pydantic import SecretStr

from ffcore.core import audit, db
from tests.integration import test_03c_keys as keys_tests
from tests.integration.conftest import CONSOLE_ORIGIN
from tests.integration.test_03c_keys import PROBE, _create

# 03c keys fixtures: a project admin's console client, and the route that resolves the caller.
owner = keys_tests.owner
probe = keys_tests.probe


def _ip() -> str:
    return f"10.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"


def _rows(pg, action, ip):
    return pg.execute(
        "SELECT after FROM audit_events WHERE action = %s AND ip = %s ORDER BY ts", (action, ip)
    ).fetchall()


def _client(app, ip):
    client = TestClient(app, base_url=CONSOLE_ORIGIN, client=(ip, 50000))
    client.__enter__()
    return client


def test_03c_6_blocked_requests_one_audit_row_per_window(app, owner, probe, app_settings, pg):
    ip = _ip()
    client = _client(app, ip)
    try:
        wrong = {"Authorization": "Bearer ffk_deadbeef_" + "x" * 43}
        for _ in range(app_settings.api_key_auth_failures_per_min):
            assert client.get(PROBE, headers=wrong).status_code == 401
        for _ in range(30):
            assert client.get(PROBE, headers=wrong).status_code == 429
    finally:
        client.__exit__(None, None, None)
    rows = _rows(pg, "api_key_auth_rate_limited", ip)
    assert len(rows) == 1
    assert rows[0][0]["failures_at_block"] >= app_settings.api_key_auth_failures_per_min


def test_03c_6_impersonation_denied_throttled(app, probe, pg, app_settings):
    """FOLLOWUP-125: the 03b path (no credential, X-On-Behalf-Of) is held to the same rule."""
    ip = _ip()
    client = _client(app, ip)
    try:
        for _ in range(30):
            response = client.get(PROBE, headers={"X-On-Behalf-Of": "not-a-token"})
            assert response.status_code == 401
    finally:
        client.__exit__(None, None, None)
    assert len(_rows(pg, "impersonation_denied", ip)) == 1


def _entry(ip, action="probe_03c_throttle"):
    return audit.AuditEntry(
        action=action,
        resource_type="auth",
        outcome="denied",
        actor_type="system",
        actor_id="anonymous",
        after={"path": "/x"},
        ip=ip,
    )


def _throttled(database_url, settings, calls):
    async def go():
        db.configure(database_url, pooled=False)
        try:
            return [
                await audit.write_event_throttled(e, settings=settings, **kw) for e, kw in calls
            ]
        finally:
            db.reset()

    return asyncio.run(go())


def test_03c_6_next_window_reports_held_back(database_url, app_settings, pg):
    ip, scope = _ip(), f"t03c:{uuid.uuid4().hex}"
    calls = [(_entry(ip), {"key": ip, "window_s": 1, "scope": scope}) for _ in range(6)]
    first = _throttled(database_url, app_settings, calls)
    time.sleep(1.2)
    later = _throttled(database_url, app_settings, calls[:1])
    assert first == [True, False, False, False, False, False] and later == [True]
    rows = _rows(pg, "probe_03c_throttle", ip)
    assert len(rows) == 2 and rows[1][0]["blocked_in_previous_window"] == 5


def test_03c_6_global_audit_cap(database_url, app_settings, pg):
    scope = f"t03c:{uuid.uuid4().hex}"
    ips = [_ip() for _ in range(200)]
    calls = [
        # One fixed minute (r2: 200 calls may straddle a minute boundary otherwise).
        (_entry(ip, "probe_03c_cap"), {"key": ip, "scope": scope, "global_cap": 100, "now": 0.0})
        for ip in ips
    ]
    written = _throttled(database_url, app_settings, calls)
    assert sum(written) == 100
    rows = pg.execute(
        "SELECT count(*) FROM audit_events WHERE action = 'probe_03c_cap' AND ip = ANY(%s::inet[])",
        (ips,),
    ).fetchone()[0]
    capped = pg.execute(
        "SELECT count(*) FROM audit_events WHERE action = 'audit_rate_capped'"
        " AND after->>'scope' = %s",
        (scope,),
    ).fetchone()[0]
    assert (rows, capped) == (100, 1)


def test_03c_6_redis_down_503_no_audit(app, owner, probe, app_settings, pg):
    from ffcore.core.config import get_settings

    project, console = owner
    created = _create(console, project)
    down = app_settings.model_copy(update={"redis_url": SecretStr("redis://127.0.0.1:1/0")})
    app.dependency_overrides[get_settings] = lambda: down
    ip = _ip()
    client = _client(app, ip)
    try:
        response = client.get(PROBE, headers={"Authorization": f"Bearer {created['key']}"})
    finally:
        client.__exit__(None, None, None)
        app.dependency_overrides[get_settings] = lambda: app_settings
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "auth_backend_unavailable"
    assert pg.execute("SELECT count(*) FROM audit_events WHERE ip = %s", (ip,)).fetchone() == (0,)
