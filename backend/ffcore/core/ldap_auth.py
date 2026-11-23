"""LDAP / Active Directory sign-in (17): service-account search, then a bind as the user.

ldap3 is synchronous; every directory call runs in a worker thread with LDAP_TIMEOUT_S on the
connection and on each answer. The directory host goes through the egress policy (OFFLINE,
allowlist, ALLOWED_INTERNAL_HOSTS) before any connection. The service password and the user's
password never reach a log, an exception text or an audit row.

Tests pass an `endpoint_factory` that returns an ldap3 MOCK_SYNC server (no network).
"""

import asyncio
import ssl
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any
from urllib.parse import urlsplit

from fastapi import Depends

from ffcore.core.config import Settings, get_settings
from ffcore.core.egress import EgressError, EgressPolicy


class DirectoryError(Exception):
    """Base of the directory outcomes; `reason` is for the audit row, never for the caller."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class InvalidCredentials(DirectoryError):
    """Unknown login, ambiguous login, empty or wrong password: all answer 401 alike."""


class ProviderUnavailable(DirectoryError):
    """The directory cannot be asked (network, timeout, service account refused): 503."""


@dataclass(frozen=True)
class DirectoryUser:
    provider: str
    external_id: str
    email: str | None
    full_name: str | None
    # LDAP group DNs lower-cased (AD compares DNs case-insensitively); OIDC values as given.
    groups: frozenset[str]
    active: bool


@dataclass(frozen=True)
class ProbeResult:
    ok: bool
    elapsed_ms: int
    code: str | None = None


@dataclass(frozen=True)
class LdapEndpoint:
    server: Any
    strategy: str


EndpointFactory = Callable[[Settings], LdapEndpoint]

# userAccountControl ACCOUNTDISABLE (Active Directory).
_UAC_DISABLED = 0x2
_ATTRIBUTES = ("mail", "userPrincipalName", "displayName", "cn", "userAccountControl")


def default_endpoint(settings: Settings) -> LdapEndpoint:
    from ldap3 import NONE, SYNC, Server, Tls

    parts = urlsplit(settings.ldap_url)
    secure = parts.scheme.lower() == "ldaps"
    tls = None
    if secure:
        tls = Tls(
            validate=ssl.CERT_REQUIRED,
            ca_certs_file=settings.ldap_ca_file,
            version=ssl.PROTOCOL_TLS_CLIENT,
        )
    server = Server(
        parts.hostname,
        port=parts.port or (636 if secure else 389),
        use_ssl=secure,
        tls=tls,
        get_info=NONE,
        connect_timeout=settings.ldap_timeout_s,
    )
    return LdapEndpoint(server=server, strategy=SYNC)


def _first(attributes: dict, name: str) -> Any:
    values = attributes.get(name)
    if isinstance(values, list):
        return values[0] if values else None
    return values


def _text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def external_id_of(raw: Any, id_attr: str) -> str | None:
    """objectGUID arrives as 16 little-endian bytes: the canonical UUID text is stored, so the
    id reads the same in the directory tools and here. Other attributes (entryUUID) as text."""
    if isinstance(raw, list):
        raw = raw[0] if raw else None
    value = raw
    if value in (None, b"", ""):
        return None
    if isinstance(value, bytes) and len(value) == 16 and id_attr.lower() == "objectguid":
        return str(uuid.UUID(bytes_le=value))
    text = _text(value).strip()
    if id_attr.lower() == "objectguid":
        try:
            return str(uuid.UUID(text.strip("{}")))
        except ValueError:
            return text
    return text


def _id_filter_value(external_id: str, id_attr: str) -> str:
    from ldap3.utils.conv import escape_bytes, escape_filter_chars

    if id_attr.lower() == "objectguid":
        try:
            return escape_bytes(uuid.UUID(external_id).bytes_le)
        except ValueError:
            pass
    return escape_filter_chars(external_id)


class LdapDirectory:
    provider = "ldap"

    def __init__(self, settings: Settings, endpoint_factory: EndpointFactory | None = None):
        if not settings.ldap_enabled:
            raise ValueError("LDAP is not configured (LDAP_URL)")
        self.settings = settings
        self._endpoint_factory = endpoint_factory or default_endpoint

    # --- public, async ---

    async def authenticate(self, login: str, password: str) -> DirectoryUser:
        self._check_egress()
        return await self._in_thread(self._authenticate, login, password)

    async def find(self, external_id: str) -> DirectoryUser | None:
        self._check_egress()
        return await self._in_thread(self._find, external_id)

    async def find_by_email(self, email: str) -> DirectoryUser | None:
        self._check_egress()
        return await self._in_thread(self._find_by_email, email)

    async def probe(self) -> ProbeResult:
        started = time.monotonic()
        try:
            self._check_egress()
            await self._in_thread(self._probe)
        except DirectoryError as exc:
            return ProbeResult(False, int((time.monotonic() - started) * 1000), exc.reason)
        return ProbeResult(True, int((time.monotonic() - started) * 1000))

    # --- internals ---

    def _check_egress(self) -> None:
        parts = urlsplit(self.settings.ldap_url)
        host = parts.hostname or ""
        try:
            EgressPolicy(self.settings).check_host(host, f"{host}:{parts.port or ''}")
        except EgressError as exc:
            raise ProviderUnavailable(exc.code) from None

    async def _in_thread(self, func, *args):
        timeout = self.settings.ldap_timeout_s * 3
        try:
            return await asyncio.wait_for(asyncio.to_thread(func, *args), timeout)
        except TimeoutError:
            raise ProviderUnavailable("directory_timeout") from None

    def _connection(self, user: str, password: str):
        from ldap3 import SIMPLE, Connection

        endpoint = self._endpoint_factory(self.settings)
        return Connection(
            endpoint.server,
            user=user,
            password=password,
            authentication=SIMPLE,
            client_strategy=endpoint.strategy,
            receive_timeout=self.settings.ldap_timeout_s,
            raise_exceptions=False,
            auto_bind=False,
        )

    def _bind(self, user: str, password: str, *, service: bool):
        from ldap3.core.exceptions import LDAPException

        conn = self._connection(user, password)
        try:
            bound = conn.bind()
        except LDAPException:
            raise ProviderUnavailable("directory_unreachable") from None
        if bound:
            return conn
        code = (conn.result or {}).get("result")
        conn.unbind()
        if code == 49 and not service:
            raise InvalidCredentials("bind_failed")
        if service:
            raise ProviderUnavailable("service_bind_failed")
        raise ProviderUnavailable("directory_error")

    def _service(self):
        return self._bind(
            self.settings.ldap_bind_dn,
            self.settings.ldap_bind_password.get_secret_value(),
            service=True,
        )

    def _search(self, conn, search_filter: str) -> list[dict]:
        from ldap3 import SUBTREE
        from ldap3.core.exceptions import LDAPException

        attributes = [*_ATTRIBUTES, self.settings.ldap_group_attr, self.settings.ldap_id_attr]
        try:
            conn.search(
                self.settings.ldap_user_base,
                search_filter,
                SUBTREE,
                attributes=attributes,
                size_limit=2,
            )
        except LDAPException:
            raise ProviderUnavailable("directory_unreachable") from None
        code = (conn.result or {}).get("result")
        # 0 success, 4 size limit exceeded (more than one match), 32 no such object (empty base)
        if code not in (0, 4, 32):
            raise ProviderUnavailable("directory_error")
        return [item for item in conn.response or [] if item.get("type") == "searchResEntry"]

    def _user(self, item: dict) -> DirectoryUser:
        raw = item.get("raw_attributes", {})
        attributes = item.get("attributes", {})
        external_id = external_id_of(
            raw.get(self.settings.ldap_id_attr), self.settings.ldap_id_attr
        )
        if external_id is None:
            raise ProviderUnavailable("directory_id_missing")
        uac = _first(attributes, "userAccountControl")
        try:
            disabled = uac is not None and int(uac) & _UAC_DISABLED
        except (TypeError, ValueError):
            disabled = False
        groups = attributes.get(self.settings.ldap_group_attr) or []
        if not isinstance(groups, list):
            groups = [groups]
        return DirectoryUser(
            provider=self.provider,
            external_id=external_id,
            email=_text(_first(attributes, "mail")),
            full_name=_text(_first(attributes, "displayName") or _first(attributes, "cn")),
            groups=frozenset(_text(g).lower() for g in groups if g),
            active=not disabled,
        )

    def _authenticate(self, login: str, password: str) -> DirectoryUser:
        from ldap3.utils.conv import escape_filter_chars

        # An empty password is an unauthenticated bind, which many directories accept.
        if not password or not login.strip():
            raise InvalidCredentials("empty_credentials")
        service = self._service()
        try:
            found = self._search(
                service,
                self.settings.ldap_user_filter.replace(
                    "{login}", escape_filter_chars(login.strip())
                ),
            )
        finally:
            service.unbind()
        if not found:
            raise InvalidCredentials("user_not_found")
        if len(found) > 1:
            raise InvalidCredentials("login_ambiguous")
        user = self._user(found[0])
        self._bind(found[0]["dn"], password, service=False).unbind()
        return user

    def _find_one(self, search_filter: str) -> DirectoryUser | None:
        service = self._service()
        try:
            found = self._search(service, search_filter)
        finally:
            service.unbind()
        if len(found) != 1:
            return None
        return self._user(found[0])

    def _find(self, external_id: str) -> DirectoryUser | None:
        attr = self.settings.ldap_id_attr
        return self._find_one(f"({attr}={_id_filter_value(external_id, attr)})")

    def _find_by_email(self, email: str) -> DirectoryUser | None:
        from ldap3.utils.conv import escape_filter_chars

        value = escape_filter_chars(email.strip())
        return self._find_one(f"(|(mail={value})(userPrincipalName={value}))")

    def _probe(self) -> None:
        self._service().unbind()


def get_ldap_directory(
    settings: Annotated[Settings, Depends(get_settings)],
) -> LdapDirectory | None:
    """FastAPI dependency: the configured directory, or None when LDAP is off."""
    if not settings.ldap_enabled:
        return None
    return LdapDirectory(settings)
