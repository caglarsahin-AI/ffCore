"""Delivery of alerts and test messages (03c): e-mail over SMTP and webhooks.

Webhooks go through SafeOutboundClient (C5). E-mail uses the standard library (`smtplib`, no new
dependency, K-03c-0004 S4-A): the server name passes `check_destination` (OFFLINE, allowlist,
every resolved address, SMTP ports only) and the connection dials that checked address while
TLS still verifies the server name (K-03c-0011 condition 2). The SMTP password lives encrypted in
`notification_settings` and never reaches a log, an API answer or an audit row.
"""

import asyncio
import logging
import smtplib
import socket
import ssl
from email.message import EmailMessage

from sqlalchemy import select

from ffcore.core.config import Settings
from ffcore.core.egress import (
    EgressError,
    EgressTimeout,
    SafeOutboundClient,
    check_destination,
)
from ffcore.core.secrets import decrypt_json
from ffcore.models.alerts import NotificationSettings

log = logging.getLogger("ffcore.notify")
SMTP_TIMEOUT_S = 15
WEBHOOK_TIMEOUT = EgressTimeout(connect=5, read=10, total=15)


class NotificationError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class _PinnedSMTP(smtplib.SMTP):
    """Dials the checked address; `connect(host)` keeps the name for EHLO and STARTTLS SNI."""

    def __init__(self, address: str, **kw):
        self._address = address
        super().__init__(**kw)

    def _get_socket(self, host, port, timeout):
        return socket.create_connection((self._address, port), timeout)


class _PinnedSMTPSSL(smtplib.SMTP_SSL):
    def __init__(self, address: str, **kw):
        self._address = address
        super().__init__(**kw)

    def _get_socket(self, host, port, timeout):
        raw = socket.create_connection((self._address, port), timeout)
        return self.context.wrap_socket(raw, server_hostname=host)


def _send_mail(address: str, smtp: dict, message: EmailMessage) -> None:
    host, port = smtp["host"], int(smtp["port"])
    context = ssl.create_default_context()
    if port == 465:
        client = _PinnedSMTPSSL(address, timeout=SMTP_TIMEOUT_S, context=context)
    else:
        client = _PinnedSMTP(address, timeout=SMTP_TIMEOUT_S)
    with client:
        client.connect(host, port)
        if port != 465 and smtp.get("starttls", True):
            client.starttls(context=context)
        if smtp.get("username"):
            client.login(smtp["username"], smtp.get("password") or "")
        client.send_message(message)


async def settings_for(
    session, settings: Settings, project_id
) -> tuple[dict | None, NotificationSettings | None]:
    """The project's notification settings, else the installation's (project_id NULL)."""
    rows = list(
        await session.scalars(
            select(NotificationSettings).where(
                (NotificationSettings.project_id == project_id)
                | NotificationSettings.project_id.is_(None)
            )
        )
    )
    row = next((r for r in rows if r.project_id is not None), None) or next(iter(rows), None)
    if row is None:
        return None, None
    smtp = decrypt_json(row.smtp_encrypted, settings) if row.smtp_encrypted else None
    return smtp, row


async def send_email(
    settings: Settings,
    smtp: dict | None,
    from_address: str | None,
    to: list[str],
    subject: str,
    body: str,
) -> None:
    if not smtp or not from_address:
        raise NotificationError("smtp_not_configured")
    if not to:
        raise NotificationError("no_recipients")
    try:
        address = await check_destination(settings, smtp["host"], int(smtp["port"]))
    except EgressError as exc:
        raise NotificationError(exc.code) from None
    message = EmailMessage()
    message["From"], message["To"], message["Subject"] = from_address, ", ".join(to), subject
    message.set_content(body)
    try:
        await asyncio.to_thread(_send_mail, address, smtp, message)
    except (OSError, smtplib.SMTPException) as exc:
        # The server's text may carry the address or account; the type only.
        raise NotificationError(f"smtp_failed:{type(exc).__name__}") from None


async def post_webhook(settings: Settings, url: str | None, payload: dict) -> None:
    if not url:
        raise NotificationError("webhook_not_configured")
    try:
        async with SafeOutboundClient(timeout=WEBHOOK_TIMEOUT, settings=settings) as client:
            response = await client.request("POST", url, json=payload)
    except EgressError as exc:
        raise NotificationError(exc.code) from None
    if response.status_code >= 400:
        raise NotificationError(f"webhook_http_{response.status_code}")
