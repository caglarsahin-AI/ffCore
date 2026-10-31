"""Alerts (03c, R9.1): rule CRUD, alert list, ack and count; project and installation level.

Project rules and alerts: analyst reads, admin changes rules, analyst+edit acks. Installation
rules (no project: service_down, checkpoint_purge_overdue) and their alerts: superadmin.
A rule of a kind nothing emits yet is refused (`alert_kind_unavailable`); `GET /alert-kinds`
lists the usable kinds (10c).
"""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from ffcore.api.common import ERROR_RESPONSES, SessionDep, invalid, not_found, path_resource
from ffcore.api.schemas import Patch, Strict
from ffcore.core.audit import audited
from ffcore.core.auth import Actor, require_role, require_superadmin, resolve_actor
from ffcore.models.alerts import ALERT_KINDS, Alert, AlertRule
from ffcore.services.alerts import EMITTED_KINDS

router = APIRouter(tags=["alerts"], responses=ERROR_RESPONSES)

ProjectReader = Annotated[Actor, Depends(require_role("analyst"))]
ProjectAdmin = Annotated[Actor, Depends(require_role("admin", write=True))]
ProjectAcker = Annotated[Actor, Depends(require_role("analyst", write=True))]
TenantReader = Annotated[Actor, Depends(require_superadmin())]
TenantWriter = Annotated[Actor, Depends(require_superadmin(write=True))]
RuleIdDep = Annotated[str, Depends(path_resource("rule_id"))]

AlertKind = StrEnum("AlertKind", {k: k for k in ALERT_KINDS})


class AlertChannel(StrEnum):
    email = "email"
    webhook = "webhook"
    ui = "ui"


class AlertRuleCreate(Strict):
    kind: AlertKind
    channel: AlertChannel
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="budget_threshold: thresholds (percent list, default 50/80/100); webhook: "
        "webhook_url (else the notification settings' default).",
    )
    recipients: list[str] = Field(default_factory=list, description="E-mail addresses.")
    is_active: bool = True


class AlertRuleUpdate(Patch):
    params: dict[str, Any] = Field(default=None)
    recipients: list[str] = Field(default=None)
    is_active: bool = Field(default=None)


class AlertRuleOut(BaseModel):
    id: UUID
    project_id: UUID | None
    kind: AlertKind
    channel: AlertChannel
    params: dict[str, Any]
    recipients: list[str]
    is_active: bool
    created_by: str
    created_at: datetime


class AlertRuleList(BaseModel):
    data: list[AlertRuleOut]


class AlertOut(BaseModel):
    id: UUID
    rule_id: UUID
    project_id: UUID | None
    kind: AlertKind
    fired_at: datetime
    severity: str
    payload: dict[str, Any] = Field(
        description="Facts of the alert; `delivery` its channel status."
    )
    acked_by: str | None
    acked_at: datetime | None


class AlertList(BaseModel):
    data: list[AlertOut]


class AlertCount(BaseModel):
    open: int = Field(description="Alerts not acked yet (console badge).")


class AlertKinds(BaseModel):
    kinds: list[AlertKind] = Field(description="Kinds a rule may use: something emits them.")


def rule_out(r: AlertRule) -> AlertRuleOut:
    return AlertRuleOut(
        id=r.id,
        project_id=r.project_id,
        kind=r.kind,
        channel=r.channel,
        params=r.params or {},
        recipients=list(r.recipients or []),
        is_active=r.is_active,
        created_by=r.created_by,
        created_at=r.created_at,
    )


def alert_out(a: Alert) -> AlertOut:
    return AlertOut(
        id=a.id,
        rule_id=a.rule_id,
        project_id=a.project_id,
        kind=a.kind,
        fired_at=a.fired_at,
        severity=a.severity,
        payload=a.payload or {},
        acked_by=a.acked_by,
        acked_at=a.acked_at,
    )


def _validate(kind: str, channel: str, recipients: list[str], params: dict) -> None:
    if kind not in EMITTED_KINDS:
        raise invalid("alert_kind_unavailable", f"Nothing emits {kind} yet; see /alert-kinds.")
    if channel == "email" and not recipients:
        raise invalid("recipients_required", "An e-mail rule needs recipients.")
    thresholds = params.get("thresholds")
    if thresholds is not None and (
        not isinstance(thresholds, list)
        or not all(isinstance(t, int) and 0 < t <= 1000 for t in thresholds)
    ):
        raise invalid("thresholds_invalid", "thresholds is a list of percentages (1..1000).")


@router.get("/alert-kinds", response_model=AlertKinds, summary="Alert kinds a rule may use")
async def alert_kinds(actor: Annotated[Actor, Depends(resolve_actor)]):
    return AlertKinds(kinds=list(EMITTED_KINDS))


async def _rule(session, project_id, rule_id) -> AlertRule:
    query = select(AlertRule).where(AlertRule.id == rule_id, AlertRule.deleted_at.is_(None))
    query = query.where(
        AlertRule.project_id == project_id if project_id else AlertRule.project_id.is_(None)
    )
    row = await session.scalar(query)
    if row is None:
        raise not_found("alert_rule")
    return row


async def _list_rules(session, project_id) -> AlertRuleList:
    query = select(AlertRule).where(AlertRule.deleted_at.is_(None))
    query = query.where(
        AlertRule.project_id == project_id if project_id else AlertRule.project_id.is_(None)
    )
    rows = await session.scalars(query.order_by(AlertRule.created_at, AlertRule.id))
    return AlertRuleList(data=[rule_out(r) for r in rows])


async def _create_rule(session, project_id, body: AlertRuleCreate, actor) -> AlertRuleOut:
    _validate(body.kind.value, body.channel.value, body.recipients, body.params)
    row = AlertRule(
        project_id=project_id,
        kind=body.kind.value,
        channel=body.channel.value,
        params=body.params,
        recipients=body.recipients,
        is_active=body.is_active,
        created_by=actor.actor_id,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return rule_out(row)


async def _update_rule(session, project_id, rule_id, body: AlertRuleUpdate) -> AlertRuleOut:
    row = await _rule(session, project_id, rule_id)
    changes = body.model_dump(exclude_unset=True)
    _validate(
        row.kind,
        row.channel,
        changes.get("recipients", list(row.recipients or [])),
        changes.get("params", row.params or {}),
    )
    for name, value in changes.items():
        setattr(row, name, value)
    await session.flush()
    await session.refresh(row)
    return rule_out(row)


async def _alerts(session, project_id) -> AlertList:
    query = select(Alert).where(
        Alert.project_id == project_id if project_id else Alert.project_id.is_(None)
    )
    rows = await session.scalars(query.order_by(Alert.fired_at.desc(), Alert.id).limit(500))
    return AlertList(data=[alert_out(a) for a in rows])


async def _count(session, project_id) -> AlertCount:
    open_alerts = await session.scalar(
        select(func.count())
        .select_from(Alert)
        .where(
            Alert.acked_at.is_(None),
            Alert.project_id == project_id if project_id else Alert.project_id.is_(None),
        )
    )
    return AlertCount(open=open_alerts)


async def _ack(session, project_id, alert_id, actor) -> AlertOut:
    row = await session.scalar(
        select(Alert).where(
            Alert.id == alert_id,
            Alert.project_id == project_id if project_id else Alert.project_id.is_(None),
        )
    )
    if row is None:
        raise not_found("alert")
    if row.acked_at is None:
        row.acked_at, row.acked_by = func.now(), actor.actor_id
        await session.flush()
        await session.refresh(row)
    return alert_out(row)


# --- Project level ---

P = "/projects/{project_id}"


@router.get(P + "/alert-rules", response_model=AlertRuleList, summary="List alert rules")
async def list_project_rules(project_id: UUID, actor: ProjectReader, session: SessionDep):
    return await _list_rules(session, project_id)


@router.post(
    P + "/alert-rules", response_model=AlertRuleOut, status_code=201, summary="Create an alert rule"
)
@audited("create_alert_rule", "alert_rule")
async def create_project_rule(
    project_id: UUID,
    body: AlertRuleCreate,
    request: Request,
    actor: ProjectAdmin,
    session: SessionDep,
):
    return await _create_rule(session, project_id, body, actor)


async def _project_rule_before(project_id, rule_id, session, **_):
    return rule_out(await _rule(session, project_id, rule_id))


@router.patch(
    P + "/alert-rules/{rule_id}", response_model=AlertRuleOut, summary="Change an alert rule"
)
@audited("update_alert_rule", "alert_rule", load_before=_project_rule_before)
async def update_project_rule(
    project_id: UUID,
    rule_id: UUID,
    body: AlertRuleUpdate,
    request: Request,
    actor: ProjectAdmin,
    session: SessionDep,
):
    return await _update_rule(session, project_id, rule_id, body)


@router.delete(
    P + "/alert-rules/{rule_id}", status_code=204, summary="Delete an alert rule (soft delete)"
)
@audited("delete_alert_rule", "alert_rule", load_before=_project_rule_before)
async def delete_project_rule(
    project_id: UUID,
    rule_id: UUID,
    request: Request,
    actor: ProjectAdmin,
    session: SessionDep,
    resource_id: RuleIdDep,
) -> None:
    row = await _rule(session, project_id, rule_id)
    row.deleted_at = func.now()


@router.get(P + "/alerts", response_model=AlertList, summary="The project's alerts, newest first")
async def list_project_alerts(project_id: UUID, actor: ProjectReader, session: SessionDep):
    return await _alerts(session, project_id)


@router.get(P + "/alerts/count", response_model=AlertCount, summary="Open alerts (badge)")
async def count_project_alerts(project_id: UUID, actor: ProjectReader, session: SessionDep):
    return await _count(session, project_id)


@router.post(P + "/alerts/{alert_id}/ack", response_model=AlertOut, summary="Acknowledge an alert")
@audited("ack_alert", "alert")
async def ack_project_alert(
    project_id: UUID, alert_id: UUID, request: Request, actor: ProjectAcker, session: SessionDep
):
    return await _ack(session, project_id, alert_id, actor)


# --- Installation level (no project) ---


@router.get("/alert-rules", response_model=AlertRuleList, summary="Installation alert rules")
async def list_rules(actor: TenantReader, session: SessionDep):
    return await _list_rules(session, None)


@router.post(
    "/alert-rules",
    response_model=AlertRuleOut,
    status_code=201,
    summary="Create an installation alert rule",
)
@audited("create_alert_rule", "alert_rule")
async def create_rule(
    body: AlertRuleCreate, request: Request, actor: TenantWriter, session: SessionDep
):
    return await _create_rule(session, None, body, actor)


async def _rule_before(rule_id, session, **_):
    return rule_out(await _rule(session, None, rule_id))


@router.patch(
    "/alert-rules/{rule_id}",
    response_model=AlertRuleOut,
    summary="Change an installation alert rule",
)
@audited("update_alert_rule", "alert_rule", load_before=_rule_before)
async def update_rule(
    rule_id: UUID,
    body: AlertRuleUpdate,
    request: Request,
    actor: TenantWriter,
    session: SessionDep,
):
    return await _update_rule(session, None, rule_id, body)


@router.delete(
    "/alert-rules/{rule_id}", status_code=204, summary="Delete an installation alert rule"
)
@audited("delete_alert_rule", "alert_rule", load_before=_rule_before)
async def delete_rule(
    rule_id: UUID,
    request: Request,
    actor: TenantWriter,
    session: SessionDep,
    resource_id: RuleIdDep,
) -> None:
    row = await _rule(session, None, rule_id)
    row.deleted_at = func.now()


@router.get("/alerts", response_model=AlertList, summary="Installation alerts")
async def list_alerts(actor: TenantReader, session: SessionDep):
    return await _alerts(session, None)


@router.get("/alerts/count", response_model=AlertCount, summary="Open installation alerts")
async def count_alerts(actor: TenantReader, session: SessionDep):
    return await _count(session, None)


@router.post(
    "/alerts/{alert_id}/ack", response_model=AlertOut, summary="Acknowledge an installation alert"
)
@audited("ack_alert", "alert")
async def ack_alert(alert_id: UUID, request: Request, actor: TenantWriter, session: SessionDep):
    return await _ack(session, None, alert_id, actor)
