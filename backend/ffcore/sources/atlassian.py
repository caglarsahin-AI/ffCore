"""HTTP for the Confluence and Jira drivers (16-2): one egress road, polite and fail-loud.

Every request goes through `SafeOutboundClient` (K-16-0002 S4: no SDK, so the egress allowlist,
the forward proxy and the private-address rule apply; OFFLINE refuses the internet deployments
before they get here). Server/Data Center authenticates with a personal access token (Bearer),
Cloud with e-mail + API token (Basic). Links the source returns (`_links.next`,
`_links.download`, Jira attachment URLs) are followed only on the configured origin
(`foreign_url` otherwise): a page cannot send the sync elsewhere.

Politeness (plan/16 "hız sınırı ve nezaket"): a fixed gap between calls (PayCore measurement:
0.5 s reads, 0.1 s downloads), at most two calls in flight per source, and on 429/503 the
server's `Retry-After` (capped at 30 s) or exponential backoff 1 → 30 s, four tries, then a
coded error (`rate_limited`, `source_unavailable`). Bodies of error answers are never logged
(they can echo credentials or content); only the status code is kept.
"""

import asyncio
import base64
import json
import math
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ffcore.core.config import Settings
from ffcore.core.egress import EgressError, EgressTimeout, SafeOutboundClient
from ffcore.sources.base import SourceError

READ_GAP_S = 0.5
DOWNLOAD_GAP_S = 0.1
MAX_TRIES = 4
BACKOFF_CAP_S = 30.0
CONCURRENCY = 2
TIMEOUT = EgressTimeout(connect=10, read=60, total=300)
DOWNLOAD_TIMEOUT = EgressTimeout(connect=10, read=120, total=3600)
RETRYABLE = (429, 502, 503, 504)
# NOTE-1 (R-16-0013): a listing longer than this, or a next link / page token seen
# before, is `pagination_loop`, not a run that follows itself until the job limit.
MAX_PAGES = 100_000


class AtlassianSecret(BaseModel):
    """Server/Data Center: `token` (personal access token). Cloud: `email` + `api_token`.
    Plain strings: the API encrypts the dump (Fernet) and masks it in every answer (16-1)."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    token: str | None = Field(default=None, min_length=1, max_length=4096, repr=False)
    email: str | None = Field(default=None, max_length=320)
    api_token: str | None = Field(default=None, min_length=1, max_length=4096, repr=False)

    @model_validator(mode="after")
    def _one_scheme(self) -> "AtlassianSecret":
        pat = self.token is not None
        basic = self.email is not None and self.api_token is not None
        if pat == basic:
            raise ValueError(
                "give either token (Server/Data Center) or email and api_token (Cloud)"
            )
        return self


class BaseUrl(BaseModel):
    base_url: str = Field(
        description="https://wiki.example.org[/context] or https://site.atlassian.net"
    )

    @field_validator("base_url")
    @classmethod
    def _url(cls, value: str) -> str:
        parts = urlsplit(value.strip())
        if parts.scheme not in ("https", "http") or not parts.hostname:
            raise ValueError("base_url must be an http(s) URL")
        if parts.username or parts.password or parts.query or parts.fragment:
            raise ValueError("base_url must not carry credentials, a query or a fragment")
        return value.strip().rstrip("/")


def check_secret(deployment: str | None, secret: dict | None) -> None:
    """The credential matches the deployment (422 secret_invalid at registration)."""
    if not secret:
        raise SourceError("secret_required", "Atlassian sources need credentials")
    has_token = bool(secret.get("token"))
    if deployment == "server" and not has_token:
        raise SourceError("secret_invalid", "Server/Data Center needs a personal access token")
    if deployment == "cloud" and has_token:
        raise SourceError("secret_invalid", "Cloud needs email and api_token, not a token")


def auth_header(deployment: str | None, secret: dict) -> str:
    if deployment == "server":
        return f"Bearer {secret['token']}"
    pair = f"{secret['email']}:{secret['api_token']}".encode()
    return "Basic " + base64.b64encode(pair).decode("ascii")


class AtlassianHttp:
    def __init__(
        self,
        base_url: str,
        authorization: str,
        settings: Settings,
        *,
        client: SafeOutboundClient | None = None,
        sleep=asyncio.sleep,
        read_gap: float = READ_GAP_S,
        download_gap: float = DOWNLOAD_GAP_S,
    ) -> None:
        self.base = base_url.rstrip("/")
        self._origin = _origin(self.base)
        self._headers = {"Authorization": authorization, "Accept": "application/json"}
        self._settings = settings
        # One client per timeout class (a 500 MB download outlives a listing call's limit).
        self._clients: dict[str, SafeOutboundClient] = (
            {"read": client, "download": client} if client is not None else {}
        )
        self._own_clients = client is None
        self._sleep = sleep
        self._gaps = {"read": read_gap, "download": download_gap}
        self._last = 0.0
        self._lock = asyncio.Lock()
        self._slots = asyncio.Semaphore(CONCURRENCY)
        self.requests = 0

    def _http(self, kind: str) -> SafeOutboundClient:
        if kind not in self._clients:
            timeout = TIMEOUT if kind == "read" else DOWNLOAD_TIMEOUT
            self._clients[kind] = SafeOutboundClient(
                timeout=timeout, settings=self._settings, max_redirects=0
            )
        return self._clients[kind]

    def url(self, link: str) -> str:
        """A path relative to the API base, or an absolute URL on the configured origin."""
        target = (
            link if "://" in link else self.base + (link if link.startswith("/") else "/" + link)
        )
        if _origin(target) != self._origin:
            raise SourceError("foreign_url", "the source linked to another host; not followed")
        return target

    async def _pace(self, kind: str) -> None:
        async with self._lock:
            wait = self._last + self._gaps[kind] - time.monotonic()
            if wait > 0 and self.requests:
                await self._sleep(wait)
            self._last = time.monotonic()
            self.requests += 1

    async def get_json(self, link: str, params: dict | None = None) -> dict:
        url = self.url(link)
        for attempt in range(1, MAX_TRIES + 1):
            async with self._slots:
                await self._pace("read")
                try:
                    response = await self._http("read").request(
                        "GET", url, headers=self._headers, params=params
                    )
                except EgressError as exc:
                    raise SourceError(exc.code, "the source could not be reached") from None
            if response.status_code in RETRYABLE and attempt < MAX_TRIES:
                await self._sleep(_retry_after(response, attempt))
                continue
            _raise_for(response.status_code)
            try:
                return json.loads(response.content)
            except ValueError:
                raise SourceError("source_bad_response", "the source answered no JSON") from None
        raise AssertionError("unreachable")

    @asynccontextmanager
    async def stream(self, link: str) -> AsyncIterator[AsyncIterator[bytes]]:
        url = self.url(link)
        for attempt in range(1, MAX_TRIES + 1):
            async with self._slots:
                await self._pace("download")
                try:
                    async with self._http("download").stream(
                        "GET", url, headers={**self._headers, "Accept": "*/*"}
                    ) as response:
                        if response.status_code in RETRYABLE and attempt < MAX_TRIES:
                            delay = _retry_after(response, attempt)
                        else:
                            if response.status_code == 404:
                                raise SourceError("attachment_gone", "the source has no such file")
                            if not 200 <= response.status_code < 300:
                                # R-16-0013 MINOR-2: a 3xx without Location (or any other
                                # answer) is never streamed as the file.
                                raise SourceError(
                                    "attachment_download_failed",
                                    f"the source answered {response.status_code} to a download",
                                )
                            yield response.aiter_bytes()
                            return
                except EgressError as exc:
                    raise SourceError(exc.code, "the source could not be reached") from None
            await self._sleep(delay)
        raise SourceError("rate_limited", "the source kept refusing the download")

    async def aclose(self) -> None:
        if self._own_clients:
            for client in self._clients.values():
                await client.aclose()
        self._clients = {}


def _origin(url: str) -> tuple[str, str, int | None]:
    parts = urlsplit(url)
    port = parts.port or (443 if parts.scheme == "https" else 80)
    return (parts.scheme, (parts.hostname or "").lower(), port)


def _retry_after(response, attempt: int) -> float:
    """The server's wait in seconds, capped; a value that is not a finite number of seconds
    (an HTTP date, `nan`, `inf`, negative) falls back to the exponential default (NOTE-6)."""
    default = min(2.0 ** (attempt - 1), BACKOFF_CAP_S)
    value = response.headers.get("Retry-After")
    if value is None:
        return default
    try:
        seconds = float(value)
    except ValueError:
        return default
    if not math.isfinite(seconds) or seconds < 0:
        return default
    return min(seconds, BACKOFF_CAP_S)


class PageGuard:
    """NOTE-1: refuses a next link or page token seen before, and a listing over MAX_PAGES."""

    def __init__(self) -> None:
        self._seen: set[str] = set()

    def next(self, marker: str) -> None:
        if marker in self._seen or len(self._seen) >= MAX_PAGES:
            raise SourceError("pagination_loop", "the source kept returning pages already read")
        self._seen.add(marker)


def _raise_for(status: int) -> None:
    if status < 400:
        return
    if status in (401, 403):
        raise SourceError("source_auth_failed", f"the source refused the credentials ({status})")
    if status == 404:
        raise SourceError("source_not_found", "the source has no such resource (404)")
    if status == 429:
        raise SourceError("rate_limited", "the source kept answering 429")
    if status == 400:
        raise SourceError("source_query_refused", "the source refused the query (400)")
    raise SourceError("source_unavailable", f"the source answered {status}")
