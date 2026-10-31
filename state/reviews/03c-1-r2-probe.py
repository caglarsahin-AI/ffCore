"""Reviewer's delta probes for 03c-1 r2 (K-03c-0016). Copied into backend/tests/integration/ for one run,
then removed."""

import asyncio
import uuid

from tests.integration.test_03c_keys import _create, _who, owner, probe  # noqa: F401


def _bad():
    return "ffk_deadbeef_" + "x" * 43


def _rows(pg, ip, action):
    return pg.execute(
        "SELECT count(*) FROM audit_events WHERE action = %s AND ip = %s", (action, ip)
    ).fetchone()[0]


def test_rev_03c2_neg_1_blocked_requests_write_at_most_one_row(app, owner, probe, app_settings, pg):
    ip = f"10.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250 + 1}"
    for _ in range(app_settings.api_key_auth_failures_per_min):
        assert _who(app, _bad(), ip=ip).status_code == 401
    for _ in range(30):
        assert _who(app, _bad(), ip=ip).status_code == 429
    rows = _rows(pg, ip, "api_key_auth_rate_limited")
    print("AUDIT_ROWS_FOR_30_BLOCKED:", rows)
    assert rows <= 1, rows


def test_rev_03c2_neg_2_unreachable_redis_is_503_and_writes_no_audit(
    app, owner, probe, pg, monkeypatch
):
    import redis.asyncio as aioredis

    project, client = owner
    created = _create(client, project)
    monkeypatch.setattr(
        "ffcore.services.keys._redis", lambda settings: aioredis.from_url("redis://127.0.0.1:1")
    )
    ip = f"10.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250 + 1}"
    before = pg.execute("SELECT count(*) FROM audit_events").fetchone()[0]
    for key in (created["key"], _bad()):
        r = _who(app, key, ip=ip)
        print("REDIS_DOWN:", r.status_code, r.json().get("error", {}).get("code"))
        assert r.status_code == 503 and r.json()["error"]["code"] == "auth_backend_unavailable"
    after = pg.execute("SELECT count(*) FROM audit_events").fetchone()[0]
    assert after == before, (before, after)


def test_rev_03c2_neg_3_reconcile_stop_does_not_swallow_the_callers_cancellation():
    from ffcore.services.litellm_reconcile import ReconcileScheduler

    async def main():
        scheduler = ReconcileScheduler.__new__(ReconcileScheduler)
        scheduler._dirty = True

        async def forever():
            await asyncio.sleep(3600)

        scheduler._task = asyncio.create_task(forever())
        outer = asyncio.create_task(scheduler.stop())
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        outer.cancel()
        try:
            await outer
        except asyncio.CancelledError:
            return "cancelled"
        return "swallowed"

    result = asyncio.run(main())
    print("STOP_CALLER_CANCEL:", result)
    assert result == "cancelled"
