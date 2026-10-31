"""03c alerts and notifications (R9.1): budget 80 % by e-mail and UI, service_down after 5 min,
quota warn, checkpoint_purge_overdue, rule API, SMTP through check_destination, readiness n/5,
project delete event.

A local fake SMTP server (127.0.0.1:587, allowed with ALLOWED_INTERNAL_HOSTS) records messages.
Installation-wide rules are soft-deleted after each test: they cover every project's readiness.
"""

import asyncio
import os
import socketserver
import threading
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import redis.asyncio as aioredis

from ffcore.core import db
from ffcore.core.egress import EgressDenied, check_destination
from ffcore.services import alerts, catalog_events
from ffcore.services.quota import QuotaEngine, QuotaGate, Subject

API = "/api/v1"


class _Smtp(socketserver.StreamRequestHandler):
    def handle(self):
        self.wfile.write(b"220 fake ESMTP\r\n")
        while True:
            line = self.rfile.readline()
            if not line:
                return
            verb = line.strip().split(b" ")[0].upper()
            if verb in (b"EHLO", b"HELO"):
                self.wfile.write(b"250 fake\r\n")
            elif verb == b"DATA":
                self.wfile.write(b"354 go\r\n")
                data = b""
                while not data.endswith(b"\r\n.\r\n"):
                    data += self.rfile.readline()
                self.server.messages.append(data.decode())
                self.wfile.write(b"250 queued\r\n")
            elif verb == b"QUIT":
                self.wfile.write(b"221 bye\r\n")
                return
            else:
                self.wfile.write(b"250 ok\r\n")


@pytest.fixture(scope="module")
def smtp_server():
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    server = socketserver.ThreadingTCPServer(("127.0.0.1", 587), _Smtp)
    server.messages = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()


@pytest.fixture
def settings(app, app_settings):
    from ffcore.core.config import get_settings

    hosts = [*app_settings.allowed_internal_hosts, "127.0.0.1"]
    s = app_settings.model_copy(update={"allowed_internal_hosts": hosts})
    app.dependency_overrides[get_settings] = lambda: s
    return s


@pytest.fixture
def superadmin(make_user, client_factory):
    _, email = make_user(superadmin="edit")
    return client_factory(email)


@pytest.fixture
def global_rules(superadmin):
    """Installation rules made by a test, soft-deleted afterwards."""
    made = []

    def make(**body):
        response = superadmin.post(f"{API}/alert-rules", json=body)
        assert response.status_code == 201, response.text
        made.append(response.json()["id"])
        return response.json()

    yield make
    for rule_id in made:
        superadmin.delete(f"{API}/alert-rules/{rule_id}")


def _run(database_url, coro_factory):
    """The same database the app fixture uses; not reset here (the app fixture's teardown does,
    and resetting mid-test would leave the test client without a database)."""

    async def go():
        db.configure(database_url, pooled=False)
        return await coro_factory()

    return asyncio.run(go())


@pytest.fixture
def admin_project(make_project, make_user, client_factory):
    project = make_project()
    _, email = make_user(memberships={project: ("admin", "edit")})
    return project, client_factory(email)


def _smtp_settings(client, base):
    response = client.put(
        f"{base}/notification-settings",
        json={
            "smtp": {
                "host": "127.0.0.1",
                "port": 587,
                # The fake server offers no AUTH: no username, so no login; the password is
                # still stored and must stay masked.
                "username": None,
                "password": "dummy-not-secret-smtp-0123",
                "starttls": False,
            },
            "from_address": "ffcore@example.test",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_03c_1_budget_80_alert_email_and_ui(admin_project, pg, database_url, settings, smtp_server):
    project, client = admin_project
    base = f"{API}/projects/{project}"
    _smtp_settings(client, base)
    assert (
        client.post(
            f"{base}/quotas",
            json={"scope_type": "project", "label": "month", "budget": {"monthly_usd": "100"}},
        ).status_code
        == 201
    )
    for channel, extra in (("email", {"recipients": ["ops@example.test"]}), ("ui", {})):
        created = client.post(
            f"{base}/alert-rules", json={"kind": "budget_threshold", "channel": channel, **extra}
        )
        assert created.status_code == 201, created.text
    pg.execute(
        "INSERT INTO usage_daily (project_id, date, model, cost_usd, requests)"
        " VALUES (%s, current_date, 'p.chat-default', 80, 4)",
        (project,),
    )
    before = len(smtp_server.messages)

    first = _run(database_url, lambda: alerts.evaluate(settings))
    again = _run(database_url, lambda: alerts.evaluate(settings))

    mine = client.get(f"{base}/alerts").json()["data"]
    thresholds = sorted(a["payload"]["threshold_percent"] for a in mine)
    assert thresholds == [50, 50, 80, 80]  # two rules, each 50 % and 80 %, not 100 %
    email = [a for a in mine if a["payload"].get("delivery", {}).get("channel") == "email"]
    assert len(email) == 2 and {a["payload"]["delivery"]["status"] for a in email} == {"sent"}
    assert len([a for a in mine if "delivery" not in a["payload"]]) == 2  # ui: the row itself
    emails = smtp_server.messages[before:]
    assert len(emails) == 2 and all("budget_threshold" in m for m in emails)
    assert "dummy-not-secret-smtp" not in "".join(emails)
    assert len(first) >= 4 and not [a for a in again if a in first]
    assert client.get(f"{base}/alerts/count").json() == {"open": 4}


def test_03c_1_service_down_after_5min(database_url, settings, global_rules, superadmin):
    global_rules(kind="service_down", channel="ui")
    now = datetime(2026, 10, 31, 12, 0, tzinfo=UTC)
    state = {"ok": False}

    async def readiness():
        return state["ok"], ["vector_store"]

    async def at(seconds):
        client = aioredis.from_url(os.environ["REDIS_URL"])
        try:
            return await alerts.evaluate(
                settings, now=now + timedelta(seconds=seconds), readiness=readiness, redis=client
            )
        finally:
            await client.aclose()

    async def flow():
        client = aioredis.from_url(os.environ["REDIS_URL"])
        await client.delete(alerts.SERVICE_DOWN_KEY)
        await client.aclose()
        results = [await at(0), await at(200), await at(301), await at(400)]
        state["ok"] = True
        results.append(await at(500))
        return results

    first, early, fired, repeat, recovered = _run(database_url, flow)
    assert [s for r in (first, early) for s in r if s in fired] == []
    service = [a for a in fired]
    assert len(service) >= 1 and repeat == [] and recovered == []
    listed = superadmin.get(f"{API}/alerts").json()["data"]
    assert any(a["kind"] == "service_down" and a["severity"] == "critical" for a in listed)


def test_03c_1_warn_quota_emits_alert(admin_project, database_url, settings, pg):
    project, client = admin_project
    base = f"{API}/projects/{project}"
    assert (
        client.post(f"{base}/alert-rules", json={"kind": "quota_warn", "channel": "ui"}).status_code
        == 201
    )
    assert (
        client.post(
            f"{base}/quotas",
            json={"scope_type": "project", "label": "w", "action": "warn", "windows": {"rpm": 1}},
        ).status_code
        == 201
    )

    async def flow():
        redis = aioredis.from_url(os.environ["REDIS_URL"])
        try:
            async with db.session_scope() as session:
                gate = QuotaGate(
                    QuotaEngine(redis, lease_ttl_s=60, prefix=f"t03c:{uuid.uuid4().hex}"),
                    redis,
                    session,
                    Subject(project_id=str(project)),
                    settings=settings,
                )

                async def priced(_):
                    return {"input_per_1m": 1, "output_per_1m": 1}

                gate._pricing = priced
                return [await gate.check(uuid.uuid4(), input_tokens=1) for _ in range(3)]
        finally:
            await redis.aclose()

    decisions = _run(database_url, flow)
    assert [d.action for d in decisions] == ["allow", "warn", "warn"]  # never blocked
    kinds = [a["kind"] for a in client.get(f"{base}/alerts").json()["data"]]
    assert kinds == ["quota_warn"]  # once per quota, window and day


def test_03c_16_purge_overdue_emits_alert(
    database_url, settings, global_rules, superadmin, pg, make_project, monkeypatch
):
    from ffcore.runtime import checkpoints
    from tests.integration.runtime_support import definition, seed_run

    global_rules(kind="checkpoint_purge_overdue", channel="ui")
    run_id = seed_run(pg, make_project(), definition(), status="completed")
    pg.execute("UPDATE runs SET ended_at = now() - interval '25 hours' WHERE id = %s", (run_id,))

    async def failing_purge(session, settings, run):
        return False

    monkeypatch.setattr(checkpoints, "purge", failing_purge)
    _run(database_url, lambda: checkpoints.sweep(settings))
    listed = superadmin.get(f"{API}/alerts").json()["data"]
    assert any(
        a["kind"] == "checkpoint_purge_overdue" and a["payload"]["run_id"] == str(run_id)
        for a in listed
    )


def test_03c_17_alert_rule_crud_ack_count(admin_project, pg):
    project, client = admin_project
    base = f"{API}/projects/{project}"
    unavailable = client.post(f"{base}/alert-rules", json={"kind": "sync_error", "channel": "ui"})
    assert unavailable.status_code == 422
    assert unavailable.json()["error"]["code"] == "alert_kind_unavailable"
    kinds = client.get(f"{API}/alert-kinds").json()["kinds"]
    assert "sync_error" not in kinds and "checkpoint_purge_overdue" in kinds
    no_to = client.post(f"{base}/alert-rules", json={"kind": "quota_warn", "channel": "email"})
    assert no_to.json()["error"]["code"] == "recipients_required"
    rule = client.post(f"{base}/alert-rules", json={"kind": "quota_warn", "channel": "ui"}).json()
    patched = client.patch(f"{base}/alert-rules/{rule['id']}", json={"is_active": False})
    assert patched.status_code == 200 and patched.json()["is_active"] is False
    alert_id = uuid.uuid4()
    pg.execute(
        "INSERT INTO alerts (id, rule_id, project_id, kind, dedupe_key) VALUES"
        " (%s, %s, %s, 'quota_warn', 'x')",
        (alert_id, rule["id"], project),
    )
    assert client.get(f"{base}/alerts/count").json() == {"open": 1}
    acked = client.post(f"{base}/alerts/{alert_id}/ack")
    assert acked.status_code == 200 and acked.json()["acked_at"] is not None
    assert client.get(f"{base}/alerts/count").json() == {"open": 0}
    assert client.delete(f"{base}/alert-rules/{rule['id']}").status_code == 204


def test_03c_17_webhook_private_ip_rejected(admin_project, database_url, app_settings):
    project, client = admin_project
    base = f"{API}/projects/{project}"
    client.post(
        f"{base}/alert-rules",
        json={
            "kind": "quota_warn",
            "channel": "webhook",
            "params": {"webhook_url": "http://10.1.2.3/hook"},
        },
    )
    _run(
        database_url,
        lambda: alerts.emit(
            # Allowlisted, so the address rule is what refuses it.
            app_settings.model_copy(update={"egress_allowlist": ["10.1.2.3"]}),
            "quota_warn",
            {"q": 1},
            project_id=project,
            dedupe_key="hook",
        ),
    )
    alert = client.get(f"{base}/alerts").json()["data"][0]
    assert alert["payload"]["delivery"] == {
        "channel": "webhook",
        "status": "egress_private_address",
    }


def test_03c_18_smtp_secret_encrypted_masked(admin_project, pg):
    project, client = admin_project
    base = f"{API}/projects/{project}"
    shown = _smtp_settings(client, base)
    assert shown["smtp"]["password"] == "***"
    stored = pg.execute(
        "SELECT smtp_encrypted FROM notification_settings WHERE project_id = %s", (project,)
    ).fetchone()[0]
    assert b"dummy-not-secret-smtp" not in bytes(stored)
    kept = client.put(
        f"{base}/notification-settings",
        json={"smtp": {**shown["smtp"], "password": "***"}, "from_address": "x@example.test"},
    )
    assert kept.status_code == 200
    audit = pg.execute(
        "SELECT string_agg(after::text, '') FROM audit_events WHERE project_id = %s"
        " AND action = 'update_notification_settings'",
        (project,),
    ).fetchone()[0]
    assert "dummy-not-secret-smtp" not in audit


def test_03c_18_notification_test_sends(admin_project, settings, smtp_server):
    project, client = admin_project
    base = f"{API}/projects/{project}"
    _smtp_settings(client, base)
    before = len(smtp_server.messages)
    sent = client.post(
        f"{base}/notifications/test", json={"channel": "email", "recipient": "a@example.test"}
    )
    assert sent.status_code == 200, sent.text
    assert len(smtp_server.messages) == before + 1


@pytest.mark.parametrize(
    ("host", "port", "update", "code"),
    [
        ("10.0.0.5", 587, {"egress_allowlist": ["10.0.0.5"]}, "egress_private_address"),
        ("smtp.example.com", 587, {"offline": True}, "egress_offline"),
        ("smtp.example.com", 2525, {}, "egress_port_not_allowed"),
    ],
)
def test_03c_18_check_destination(app_settings, host, port, update, code):
    settings = app_settings.model_copy(update={"egress_allowlist": ["smtp.example.com"]} | update)

    async def resolver(name, p):
        return ["10.9.9.9"]  # the allowlisted name resolves to a private address

    with pytest.raises(EgressDenied) as caught:
        asyncio.run(check_destination(settings, host, port, resolver=resolver))
    assert caught.value.code == code


def test_03c_18_check_destination_rebinding(app_settings):
    """An allowlisted name whose answer is private is refused (the checked address is dialled)."""
    settings = app_settings.model_copy(update={"egress_allowlist": ["smtp.example.com"]})

    async def resolver(name, p):
        return ["93.184.216.34", "10.0.0.1"]

    with pytest.raises(EgressDenied):
        asyncio.run(check_destination(settings, "smtp.example.com", 465, resolver=resolver))


def test_03c_19_readiness_five_checks(admin_project, pg):
    project, client = admin_project
    base = f"{API}/projects/{project}"
    globals_exist = pg.execute(
        "SELECT count(*) FROM alert_rules WHERE project_id IS NULL AND is_active"
        " AND deleted_at IS NULL"
    ).fetchone()[0]
    body = client.get(f"{base}/readiness").json()
    checks = {c["key"]: c["ok"] for c in body["checks"]}
    assert body["total"] == 5 and checks["limits"] is False
    assert checks["alert_rules"] is bool(globals_exist)
    client.post(
        f"{base}/quotas", json={"scope_type": "project", "label": "l", "windows": {"rpm": 9}}
    )
    client.post(f"{base}/alert-rules", json={"kind": "quota_warn", "channel": "ui"})
    checks = {c["key"]: c["ok"] for c in client.get(f"{base}/readiness").json()["checks"]}
    assert checks["limits"] is True and checks["alert_rules"] is True


def test_03c_20_project_delete_publishes_event(superadmin, make_project):
    project = make_project()
    seen = []
    catalog_events.subscribe(seen.append)
    try:
        assert superadmin.delete(f"{API}/projects/{project}").status_code == 204
    finally:
        catalog_events._listeners.remove(seen.append)
    assert [(e.kind, e.action, e.project_id) for e in seen] == [
        ("project", "deleted", str(project))
    ]


def test_03c_15_audit_partition_cron_idempotent(database_url, pg):
    from ffcore.runtime.worker import audit_partitions

    async def twice():
        await audit_partitions({})
        await audit_partitions({})

    _run(database_url, twice)
    month = datetime.now(UTC).strftime("%Y_%m")
    assert pg.execute("SELECT to_regclass(%s)", (f"audit_events_{month}",)).fetchone()[0]


def test_03c_cron_jobs_registered():
    from ffcore.runtime.contracts import JobClass
    from ffcore.runtime.worker import (
        audit_partitions,
        clear_source_deleted,
        cron_jobs_for,
        evaluate_alerts,
        run_retention,
    )

    jobs = {j.coroutine for j in cron_jobs_for(JobClass.background)}
    assert {evaluate_alerts, clear_source_deleted, audit_partitions, run_retention} <= jobs
    assert cron_jobs_for(JobClass.interactive) == []
