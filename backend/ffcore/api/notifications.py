"""Notification settings (03c): one SMTP account, default webhook and sender per project, or one
for the installation. Admin only. The SMTP password is stored encrypted (Fernet) and answered
as "***"; sending "***" back keeps the stored value. `POST .../notifications/test` sends a test
e-mail or webhook with the current settings.
"""

from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from ffcore.api.common import ERROR_RESPONSES, SessionDep, invalid
from ffcore.api.schemas import Strict
from ffcore.core.audit import audited
from ffcore.core.auth import Actor, require_role, require_superadmin
from ffcore.core.config import Settings, get_settings
from ffcore.core.errors import ApiError
from ffcore.core.secrets import decrypt_json, encrypt_json
from ffcore.models.alerts import NotificationSettings
from ffcore.services import notify

router = APIRouter(tags=["notifications"], responses=ERROR_RESPONSES)

ProjectReader = Annotated[Actor, Depends(require_role("admin"))]
ProjectWriter = Annotated[Actor, Depends(require_role("admin", write=True))]
TenantReader = Annotated[Actor, Depends(require_superadmin())]
TenantWriter = Annotated[Actor, Depends(require_superadmin(write=True))]
SettingsDep = Annotated[Settings, Depends(get_settings)]
MASK = "***"


class SmtpSettings(Strict):
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(description="25, 465 (TLS) or 587 (STARTTLS).")
    username: str | None = None
    password: str | None = Field(default=None, description='Answered as "***".')
    starttls: bool = True


class NotificationSettingsIn(Strict):
    smtp: SmtpSettings | None = None
    default_webhook_url: str | None = None
    from_address: str | None = None


class NotificationSettingsOut(BaseModel):
    project_id: UUID | None
    smtp: SmtpSettings | None
    default_webhook_url: str | None
    from_address: str | None
    updated_at: datetime | None
    updated_by: str | None


class TestChannel(StrEnum):
    email = "email"
    webhook = "webhook"


class NotificationTest(Strict):
    channel: TestChannel
    recipient: str | None = Field(default=None, description="E-mail address for the test mail.")


class NotificationTestResult(BaseModel):
    channel: TestChannel
    status: str = Field(description="sent")


async def _row(session, project_id) -> NotificationSettings | None:
    return await session.scalar(
        select(NotificationSettings).where(
            NotificationSettings.project_id == project_id
            if project_id
            else NotificationSettings.project_id.is_(None)
        )
    )


def _out(row: NotificationSettings | None, project_id, settings) -> NotificationSettingsOut:
    if row is None:
        return NotificationSettingsOut(
            project_id=project_id,
            smtp=None,
            default_webhook_url=None,
            from_address=None,
            updated_at=None,
            updated_by=None,
        )
    smtp = decrypt_json(row.smtp_encrypted, settings) if row.smtp_encrypted else None
    if smtp and smtp.get("password"):
        smtp["password"] = MASK
    return NotificationSettingsOut(
        project_id=row.project_id,
        smtp=SmtpSettings(**smtp) if smtp else None,
        default_webhook_url=row.default_webhook_url,
        from_address=row.from_address,
        updated_at=row.updated_at,
        updated_by=row.updated_by,
    )


async def _put(session, project_id, body: NotificationSettingsIn, actor, settings):
    if body.smtp is not None and body.smtp.port not in (25, 465, 587):
        raise invalid("smtp_port_not_allowed", "SMTP port must be 25, 465 or 587.")
    row = await _row(session, project_id)
    if row is None:
        row = NotificationSettings(project_id=project_id, updated_by=actor.actor_id)
        session.add(row)
    smtp = body.smtp.model_dump() if body.smtp else None
    if smtp and smtp.get("password") == MASK:
        old = decrypt_json(row.smtp_encrypted, settings) if row.smtp_encrypted else {}
        smtp["password"] = old.get("password")
    row.smtp_encrypted = encrypt_json(smtp, settings) if smtp else None
    row.default_webhook_url = body.default_webhook_url
    row.from_address = body.from_address
    row.updated_by = actor.actor_id
    await session.flush()
    await session.refresh(row)
    return _out(row, project_id, settings)


async def _test(session, project_id, body: NotificationTest, settings) -> NotificationTestResult:
    smtp, row = await notify.settings_for(session, settings, project_id)
    try:
        if body.channel == TestChannel.email:
            await notify.send_email(
                settings,
                smtp,
                row.from_address if row else None,
                [body.recipient] if body.recipient else [],
                "[FFCore] test",
                "This is a test message from FFCore.",
            )
        else:
            await notify.post_webhook(
                settings, row.default_webhook_url if row else None, {"kind": "test"}
            )
    except notify.NotificationError as exc:
        raise ApiError(422, "invalid_request_error", "notification_failed", exc.code) from None
    return NotificationTestResult(channel=body.channel, status="sent")


P = "/projects/{project_id}"


@router.get(
    P + "/notification-settings",
    response_model=NotificationSettingsOut,
    summary="The project's notification settings",
)
async def get_project_settings(
    project_id: UUID, actor: ProjectReader, session: SessionDep, settings: SettingsDep
):
    return _out(await _row(session, project_id), project_id, settings)


@router.put(
    P + "/notification-settings",
    response_model=NotificationSettingsOut,
    summary="Set the project's notification settings",
)
@audited("update_notification_settings", "notification_settings", redact_fields=["smtp"])
async def put_project_settings(
    project_id: UUID,
    body: NotificationSettingsIn,
    request: Request,
    actor: ProjectWriter,
    session: SessionDep,
    settings: SettingsDep,
):
    return await _put(session, project_id, body, actor, settings)


@router.post(
    P + "/notifications/test",
    response_model=NotificationTestResult,
    summary="Send a test e-mail or webhook",
)
@audited("test_notification", "notification_settings")
async def test_project_notification(
    project_id: UUID,
    body: NotificationTest,
    request: Request,
    actor: ProjectWriter,
    session: SessionDep,
    settings: SettingsDep,
):
    return await _test(session, project_id, body, settings)


@router.get(
    "/notification-settings",
    response_model=NotificationSettingsOut,
    summary="Installation notification settings",
)
async def get_settings_(actor: TenantReader, session: SessionDep, settings: SettingsDep):
    return _out(await _row(session, None), None, settings)


@router.put(
    "/notification-settings",
    response_model=NotificationSettingsOut,
    summary="Set the installation notification settings",
)
@audited("update_notification_settings", "notification_settings", redact_fields=["smtp"])
async def put_settings(
    body: NotificationSettingsIn,
    request: Request,
    actor: TenantWriter,
    session: SessionDep,
    settings: SettingsDep,
):
    return await _put(session, None, body, actor, settings)


@router.post(
    "/notifications/test",
    response_model=NotificationTestResult,
    summary="Send a test with the installation settings",
)
@audited("test_notification", "notification_settings")
async def test_notification(
    body: NotificationTest,
    request: Request,
    actor: TenantWriter,
    session: SessionDep,
    settings: SettingsDep,
):
    return await _test(session, None, body, settings)
