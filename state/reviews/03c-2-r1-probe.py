"""Reviewer probes for 03c-2 r1 (not part of the PR)."""
import asyncio
import json
import uuid
from datetime import UTC, datetime

import pytest

from ffcore.core import db
from ffcore.core.egress import EgressError, check_destination
from ffcore.services import notify, retention_job
from tests.integration.runtime_support import definition, seed_run

API = "/api/v1"
NOW = datetime(2026, 10, 31, 12, 0, tzinfo=UTC)


def _part(pg, month, action="rev_probe"):
    name = pg.execute("SELECT ffcore_audit_ensure_partition(%s::date)", (month,)).fetchone()[0]
    pg.execute(
        "INSERT INTO audit_events (id, ts, actor_type, actor_id, action, resource_type, outcome)"
        " VALUES (%s, %s::date + 1, 'system', 't', %s, 'probe', 'success')",
        (uuid.uuid4(), month, action),
    )
    return name


def _ex(pg, n):
    return pg.execute("SELECT to_regclass(%s)", (n,)).fetchone()[0] is not None


def run_exec(database_url, settings, **kw):
    async def go():
        db.configure(database_url, pooled=False)
        try:
            return await retention_job.execute(
                settings, trigger="manual", actor_id="rev", now=NOW, **kw
            )
        finally:
            db.reset()

    return asyncio.run(go())


async def _direct(database_url, settings):
    db.configure(database_url, pooled=False)
    try:
        return await retention_job.audit_partitions(settings, 30, dry_run=False, now=NOW)
    finally:
        db.reset()


def test_p1_audit_floor_and_flags(pg, database_url, app_settings):
    old = _part(pg, "2025-09-01")  # month_end 2025-10-01 <= cutoff 2025-10-31
    edge = _part(pg, "2025-10-01")  # month_end 2025-11-01 > cutoff: must stay
    s_off = app_settings.model_copy(update={"retention_audit_drop_enabled": False})
    s_on = app_settings.model_copy(update={"retention_audit_drop_enabled": True})
    n_before = pg.execute("SELECT count(*) FROM audit_events").fetchone()[0]
    run_exec(database_url, s_on, dry_run=True)
    assert _ex(pg, old) and _ex(pg, edge)
    assert pg.execute("SELECT count(*) FROM audit_events").fetchone()[0] == n_before
    run_exec(database_url, s_off, dry_run=False)
    assert _ex(pg, old) and _ex(pg, edge), "flag off must not drop"
    run_exec(database_url, s_on, dry_run=False)
    assert not _ex(pg, old), "old partition should be dropped"
    assert _ex(pg, edge), "partition inside 365 days must stay"
    rec = pg.execute(
        "SELECT counts FROM retention_runs WHERE data_class='audit' AND counts->>'partition'=%s",
        (old,),
    ).fetchall()
    assert len(rec) == 1 and rec[0][0]["detached"] is True
    assert rec[0][0]["sha256"] and rec[0][0]["rows"] == 1
    ev = pg.execute(
        "SELECT actor_type FROM audit_events WHERE action='audit_partition_dropped'"
        " AND resource_id=%s",
        (old,),
    ).fetchall()
    assert len(ev) == 1 and ev[0][0] == "system"
    res = asyncio.run(_direct(database_url, s_on))
    assert _ex(pg, edge), f"keep_days=30 must not drop a partition inside 365 days: {res.counts}"


def test_p2_audit_error_isolation(pg, make_project, database_url, app_settings, monkeypatch):
    project = make_project()
    rid = seed_run(pg, project, definition(), question="iso-probe", status="completed")
    pg.execute(
        "UPDATE runs SET output='iso-probe', ended_at=now()-interval '100 days' WHERE id=%s",
        (rid,),
    )

    async def boom(*a, **k):
        raise RuntimeError("audit boom")

    monkeypatch.setattr(retention_job, "audit_partitions", boom)
    try:
        run_exec(database_url, app_settings, dry_run=False)
        outcome = "pass completed"
    except Exception as exc:  # noqa: BLE001
        outcome = f"pass raised {type(exc).__name__}"
    cleared = pg.execute("SELECT input FROM runs WHERE id=%s", (rid,)).fetchone()[0]
    print("P2", outcome, "content input after:", cleared)
    assert cleared == "[cleared]", f"other classes did not run: {outcome}"


@pytest.mark.parametrize(
    "host,port,ips",
    [
        ("127.0.0.1", 25, None),
        ("10.0.0.5", 587, None),
        ("169.254.169.254", 25, None),
        ("::1", 25, None),
        ("smtp.example.org", 22, ["93.184.216.34"]),
        ("smtp.example.org", 443, ["93.184.216.34"]),
        ("smtp.example.org", 587, ["93.184.216.34", "10.0.0.5"]),
        ("smtp.example.org", 587, ["127.0.0.1"]),
        ("smtp.example.org", 587, ["::ffff:10.0.0.5"]),
        ("smtp.example.org", 587, ["fd00::1"]),
    ],
)
def test_p3_smtp_denied(app_settings, host, port, ips):
    async def resolver(h, p):
        return ips

    s = app_settings.model_copy(update={"egress_allowlist": ["smtp.example.org"]})
    with pytest.raises(EgressError):
        asyncio.run(check_destination(s, host, port, resolver=resolver))


def test_p3b_smtp_allowed_returns_checked_address(app_settings):
    async def resolver(h, p):
        return ["93.184.216.34"]

    s = app_settings.model_copy(update={"egress_allowlist": ["smtp.example.org"]})
    got = asyncio.run(check_destination(s, "smtp.example.org", 587, resolver=resolver))
    assert got == "93.184.216.34"
    off = app_settings.model_copy(update={"offline": True, "egress_allowlist": ["smtp.example.org"]})
    with pytest.raises(EgressError):
        asyncio.run(check_destination(off, "smtp.example.org", 587, resolver=resolver))
    notl = app_settings.model_copy(update={"egress_allowlist": []})
    with pytest.raises(EgressError):
        asyncio.run(check_destination(notl, "smtp.example.org", 587, resolver=resolver))


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data",
        "http://127.0.0.1:8000/x",
        "http://[::1]/",
        "http://10.1.2.3/",
        "http://localhost/",
        "file:///etc/passwd",
        "http://backend:8000/",
        "http://postgres:5432/",
    ],
)
def test_p4_webhook_private_denied(app_settings, url):
    with pytest.raises(notify.NotificationError) as e:
        asyncio.run(notify.post_webhook(app_settings, url, {"k": 1}))
    print("P4", url, e.value.code)


def test_p5_api_matrix(pg, make_user, make_project, client_factory):
    pa, pb = make_project(), make_project()
    _, sa = make_user(superadmin="edit")
    _, adm_a = make_user(memberships={pa: ("admin", "edit")})
    _, adm_b = make_user(memberships={pb: ("admin", "edit")})
    _, ana_a = make_user(memberships={pa: ("analyst", "edit")})
    sup, A, B, ANA = (client_factory(e) for e in (sa, adm_a, adm_b, ana_a))
    assert sup.put(f"{API}/retention/policies/audit", json={"keep_days": 364}).status_code == 422
    assert A.put(f"{API}/retention/policies/content", json={"keep_days": 5}).status_code in (401, 403)
    assert A.post(f"{API}/retention/run").status_code in (401, 403)
    assert A.get(f"{API}/retention/runs").status_code in (401, 403)
    assert (
        sup.post(f"{API}/alert-rules", json={"kind": "ingest_error", "channel": "ui"}).status_code
        == 422
    )
    r = A.post(f"{API}/projects/{pa}/alert-rules", json={"kind": "quota_warn", "channel": "ui"})
    assert r.status_code == 201, r.text
    rid = r.json()["id"]
    assert B.patch(f"{API}/projects/{pb}/alert-rules/{rid}", json={"is_active": False}).status_code == 404
    assert B.patch(f"{API}/projects/{pa}/alert-rules/{rid}", json={"is_active": False}).status_code in (403, 404)
    assert B.delete(f"{API}/projects/{pb}/alert-rules/{rid}").status_code == 404
    assert (
        ANA.post(f"{API}/projects/{pa}/alert-rules", json={"kind": "quota_warn", "channel": "ui"}).status_code
        == 403
    )
    secret = "PROBE-SECRET-PW-123"
    body = {
        "smtp": {"host": "smtp.example.org", "port": 587, "username": "u", "password": secret},
        "from_address": "ff@example.org",
        "default_webhook_url": None,
    }
    assert A.put(f"{API}/projects/{pa}/notification-settings", json=body).status_code == 200
    got = A.get(f"{API}/projects/{pa}/notification-settings")
    assert secret not in got.text and got.json()["smtp"]["password"] == "***"
    assert ANA.get(f"{API}/projects/{pa}/notification-settings").status_code == 403
    assert B.get(f"{API}/projects/{pa}/notification-settings").status_code in (403, 404)
    dump = json.dumps(
        pg.execute(
            "SELECT * FROM audit_events WHERE action='update_notification_settings'"
        ).fetchall(),
        default=str,
    )
    assert secret not in dump
    stored = pg.execute("SELECT smtp_encrypted FROM notification_settings").fetchall()
    assert all(secret.encode() not in bytes(r[0] or b"") for r in stored)
    assert (
        A.put(f"{API}/projects/{pa}/notification-settings", json={"smtp": {"host": "x", "port": 22}}).status_code
        == 422
    )
    body["smtp"]["host"] = "169.254.169.254"
    assert A.put(f"{API}/projects/{pa}/notification-settings", json=body).status_code == 200
    t = A.post(
        f"{API}/projects/{pa}/notifications/test",
        json={"channel": "email", "recipient": "x@example.org"},
    )
    print("P5 test email private host:", t.status_code, t.text[:200])
    assert t.status_code == 422
    A.put(
        f"{API}/projects/{pa}/notification-settings",
        json={"default_webhook_url": "http://169.254.169.254/x"},
    )
    t = A.post(f"{API}/projects/{pa}/notifications/test", json={"channel": "webhook"})
    print("P5 test webhook private:", t.status_code, t.text[:200])
    assert t.status_code == 422
    assert ANA.post(f"{API}/projects/{pa}/notifications/test", json={"channel": "webhook"}).status_code == 403
    assert B.get(f"{API}/projects/{pa}/alerts").status_code in (403, 404)
