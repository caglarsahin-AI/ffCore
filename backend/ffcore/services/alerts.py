"""Alerts (03c, R9.1): one emit point for every package, one evaluator, three channels.

Packages call `emit(kind, payload, project_id=, dedupe_key=)`; they never choose a channel. Every
active rule of that kind for the project (or installation-wide) gets one `alerts` row per
dedupe key (a repeated condition fires once), delivered by its channel: `ui` (the row is the
alert), `email`, `webhook`. A delivery failure is kept in `payload.delivery` and logged, never
silent. The evaluator (arq cron, once a minute, background worker; C9) checks the conditions
nobody else emits: `budget_threshold` (month's spend in usage_daily against the project's
monthly_usd quota, 50/80/100 %) and `service_down` (/readyz failing for ALERT_SERVICE_DOWN_S).

Kinds without an emitter yet are refused when a rule is created (`alert_kind_unavailable`,
K-03c-0011 S8-A): a rule that can never fire is a promise the screen would not keep.
"""

import json
import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from ffcore.core.config import Settings
from ffcore.models.alerts import Alert, AlertRule
from ffcore.models.quota import Quota, UsageDaily

log = logging.getLogger("ffcore.alerts")

# Kinds something emits today; the others are refused at rule creation (GET /alert-kinds).
EMITTED_KINDS = (
    "budget_threshold",
    "service_down",
    "quota_warn",
    "approval_pending_age",
    "checkpoint_purge_overdue",
)
SEVERITY = {"service_down": "critical", "budget_threshold": "warning"}
DEFAULT_THRESHOLDS = (50, 80, 100)
SERVICE_DOWN_KEY = "ffcore:alerts:service_down_since"


async def _rules(session, kind: str, project_id) -> list[AlertRule]:
    query = select(AlertRule).where(
        AlertRule.kind == kind, AlertRule.is_active, AlertRule.deleted_at.is_(None)
    )
    if project_id is None:
        query = query.where(AlertRule.project_id.is_(None))
    else:
        query = query.where(
            (AlertRule.project_id == uuid.UUID(str(project_id))) | AlertRule.project_id.is_(None)
        )
    return list(await session.scalars(query))


async def emit(
    settings: Settings,
    kind: str,
    payload: dict[str, Any],
    *,
    project_id=None,
    dedupe_key: str,
    severity: str | None = None,
) -> list[str]:
    """Record and deliver; returns the new alert ids (empty when every rule already fired for
    this dedupe key, or no rule wants this kind). Never raises for a delivery problem."""
    from ffcore.core import db

    created: list[tuple[AlertRule, str]] = []
    async with db.session_scope() as session:
        for rule in await _rules(session, kind, project_id):
            alert_id = await session.scalar(
                insert(Alert)
                .values(
                    id=uuid.uuid4(),
                    rule_id=rule.id,
                    project_id=uuid.UUID(str(project_id)) if project_id else None,
                    kind=kind,
                    dedupe_key=dedupe_key,
                    payload=payload,
                    severity=severity or SEVERITY.get(kind, "warning"),
                )
                .on_conflict_do_nothing(index_elements=["rule_id", "dedupe_key"])
                .returning(Alert.id)
            )
            if alert_id is not None:
                created.append((rule, str(alert_id)))
        await session.commit()
    for rule, alert_id in created:
        await _deliver(settings, rule, alert_id, kind, payload, project_id)
    if created:
        log.warning("alert_fired kind=%s count=%s project_id=%s", kind, len(created), project_id)
    return [alert_id for _, alert_id in created]


async def _deliver(settings, rule: AlertRule, alert_id: str, kind, payload, project_id) -> None:
    from ffcore.core import db
    from ffcore.services import notify

    if rule.channel == "ui":
        return
    status = "sent"
    try:
        async with db.session_scope() as session:
            smtp, row = await notify.settings_for(session, settings, project_id)
        if rule.channel == "email":
            await notify.send_email(
                settings,
                smtp,
                row.from_address if row else None,
                list(rule.recipients),
                f"[FFCore] {kind}",
                "\n".join(f"{k}: {v}" for k, v in sorted(payload.items())),
            )
        else:
            url = (rule.params or {}).get("webhook_url") or (
                row.default_webhook_url if row else None
            )
            await notify.post_webhook(
                settings, url, {"alert_id": alert_id, "kind": kind, "payload": payload}
            )
    except notify.NotificationError as exc:
        status = exc.code
        log.error(
            "alert_delivery_failed alert_id=%s channel=%s code=%s", alert_id, rule.channel, status
        )
    async with db.session_scope() as session:
        alert = await session.get(Alert, uuid.UUID(alert_id))
        alert.payload = {**alert.payload, "delivery": {"channel": rule.channel, "status": status}}
        await session.commit()


# --- Evaluator (arq cron, once a minute) ---


async def evaluate(settings: Settings, *, now: datetime | None = None, readiness=None, redis=None):
    """budget_threshold and service_down; `readiness` and `redis` are injectable for tests."""
    now = now or datetime.now(UTC)
    fired = await _budget_thresholds(settings, now)
    if readiness is not None and redis is not None:
        fired += await _service_down(settings, now, readiness, redis)
    return fired


async def _budget_thresholds(settings: Settings, now: datetime) -> list[str]:
    from ffcore.core import db

    month = now.strftime("%Y-%m")
    first = now.date().replace(day=1)
    fired: list[str] = []
    async with db.session_scope() as session:
        rules = await _rules_of_kind(session, "budget_threshold")
        budgets = {}
        for quota in await session.scalars(
            select(Quota).where(
                Quota.scope_type == "project", Quota.is_active, Quota.deleted_at.is_(None)
            )
        ):
            monthly = (quota.budget or {}).get("monthly_usd")
            if monthly is not None and Decimal(str(monthly)) > 0:
                budgets[quota.project_id] = min(
                    Decimal(str(monthly)), budgets.get(quota.project_id, Decimal(monthly))
                )
        spend = dict(
            (
                await session.execute(
                    select(UsageDaily.project_id, func.sum(UsageDaily.cost_usd))
                    .where(UsageDaily.date >= first)
                    .group_by(UsageDaily.project_id)
                )
            ).all()
        )
    for project_id, budget in budgets.items():
        if not any(r.project_id in (None, project_id) for r in rules):
            continue
        used = Decimal(spend.get(project_id) or 0)
        percent = used / budget * 100
        thresholds = _thresholds(rules, project_id)
        for threshold in thresholds:
            if percent >= threshold:
                fired += await emit(
                    settings,
                    "budget_threshold",
                    {
                        "threshold_percent": threshold,
                        "spent_usd": str(used),
                        "monthly_usd": str(budget),
                        "month": month,
                    },
                    project_id=project_id,
                    dedupe_key=f"{month}:{threshold}",
                    severity="critical" if threshold >= 100 else "warning",
                )
    return fired


async def _rules_of_kind(session, kind: str) -> list[AlertRule]:
    return list(
        await session.scalars(
            select(AlertRule).where(
                AlertRule.kind == kind, AlertRule.is_active, AlertRule.deleted_at.is_(None)
            )
        )
    )


def _thresholds(rules, project_id) -> list[int]:
    chosen = set()
    for rule in rules:
        if rule.project_id in (None, project_id):
            chosen.update((rule.params or {}).get("thresholds") or DEFAULT_THRESHOLDS)
    return sorted(int(t) for t in chosen)


async def _service_down(settings: Settings, now: datetime, readiness, redis) -> list[str]:
    """/readyz failing continuously for ALERT_SERVICE_DOWN_S (default 300) fires once per
    outage (dedupe: the outage's start)."""
    ok, failed = await readiness()
    if ok:
        await redis.delete(SERVICE_DOWN_KEY)
        return []
    stamp = int(now.timestamp())
    await redis.set(SERVICE_DOWN_KEY, stamp, nx=True)
    since = int(await redis.get(SERVICE_DOWN_KEY))
    if stamp - since < settings.alert_service_down_s:
        return []
    return await emit(
        settings,
        "service_down",
        {"since": datetime.fromtimestamp(since, UTC).isoformat(), "failed_checks": failed},
        dedupe_key=f"outage:{since}",
    )


async def readyz_probe(settings: Settings):
    """The API process's /readyz over HTTP (the worker runs no models, so its own readiness
    would always read "warming"): (ok, names of failed checks). Unreachable is a failure."""
    from ffcore.core.egress import EgressError, EgressTimeout, SafeOutboundClient

    try:
        async with SafeOutboundClient(
            timeout=EgressTimeout(connect=3, read=10, total=15), settings=settings
        ) as client:
            response = await client.request("GET", f"{settings.internal_api_url}/readyz")
    except EgressError as exc:
        return False, [f"unreachable:{exc.code}"]
    try:
        checks = json.loads(response.content).get("checks", [])
    except ValueError:
        checks = []
    failed = [c.get("name") for c in checks if c.get("status") == "failed"]
    return response.status_code == 200 and not failed, failed


async def retention_executor(session, project_id, overridden, cutoff, dry_run, batch) -> dict:
    """`alerts` retention class: alerts fired before the cutoff."""
    from ffcore.services.retention_job import _delete_where, _scope

    n = await _delete_where(
        session,
        Alert.__table__,
        Alert.id,
        (Alert.fired_at < cutoff) & _scope(Alert.project_id, project_id, overridden),
        dry_run,
        batch,
    )
    return {"alerts": n}


def _register() -> None:
    from ffcore.services import retention_job

    retention_job.register("alerts", retention_executor)


_register()
