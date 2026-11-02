"""06b-2 external agent (`agents.kind = external`): an OpenAI-compatible agent elsewhere, behind
the facade (plan/06 "Connect Agent", minimum; K-06b-0002 S5, K-06b2-0002).

- Registration keeps `base_url`, the remote `model` and its `api_key` in `agents.external_config`
  (Fernet). The key is written, never read back (`***`), never exported in a manifest.
- The base URL passes the egress policy when it is registered, updated and published
  (check_base_url) and again at every connection (SafeOutboundClient's pinned backend: DNS
  rebinding is refused at the dial). Redirects are not followed: any 3xx is a failure.
- The call is not a run (K-06b2-0002 S1): the client's messages pass `input.pre` and `egress`,
  the request carries only the registered key (no user identity, no On-Behalf-Of), the answer
  is read as untrusted text: only `choices[0].message.content` is taken; tool calls and other
  fields are never executed or turned into text. The text then passes `output.pre`.
- Limits: the profile's model call timeout (`LLM_CALL_TIMEOUT_S`) for the whole call, at most
  MAX_EXTERNAL_RESPONSE_BYTES of answer; beyond either the call fails with a code, nothing
  partial reaches the client. Every call writes one audit event (host, status, time, bytes;
  never content). The call is outside token and USD quotas (S2, FOLLOWUP-144) and outside
  Langfuse (it does not go through LiteLLM).
"""

import json
import time
from dataclasses import dataclass, field
from typing import Any

import anyio
import httpx2
from pydantic import BaseModel, ConfigDict, SecretStr

from ffcore.core.config import Settings
from ffcore.core.egress import (
    EgressDenied,
    EgressError,
    EgressPolicy,
    EgressTimeout,
    EgressTimeoutError,
    Resolver,
    SafeOutboundClient,
    _parse_ip,
    system_resolver,
)
from ffcore.core.errors import ApiError
from ffcore.core.secrets import decrypt_json, encrypt_json

MAX_EXTERNAL_RESPONSE_BYTES = 65_536
# The answer's finish reasons passed on as given; any other is reported as `stop`.
FINISH_REASONS = ("stop", "length")


class ExternalConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    base_url: str
    model: str
    api_key: SecretStr

    def public(self) -> dict[str, str]:
        """What an API answer and an audit event may show."""
        return {"base_url": self.base_url, "model": self.model, "api_key": "***"}

    def encrypt(self, settings: Settings) -> bytes:
        return encrypt_json(
            {
                "base_url": self.base_url,
                "model": self.model,
                "api_key": self.api_key.get_secret_value(),
            },
            settings,
        )

    @classmethod
    def decrypt(cls, token: bytes, settings: Settings) -> "ExternalConfig":
        return cls.model_validate(decrypt_json(token, settings))


def not_this_path() -> ApiError:
    """An external agent without a configuration (kept for C11: the code stays frozen)."""
    return ApiError(
        501,
        "api_error",
        "external_agent_not_available",
        "External agents cannot be called through the facade yet.",
    )


def url_refused(code: str) -> ApiError:
    return ApiError(
        422,
        "invalid_request_error",
        "external_agent_url_refused",
        f"The base URL is refused by the egress policy ({code}).",
        param="base_url",
    )


async def check_base_url(url: str, settings: Settings, *, resolver: Resolver | None = None) -> None:
    """The egress rules for an HTTP base URL, as SafeOutboundClient applies them at connect
    time: scheme, OFFLINE, allowlist or internal host, then every resolved address (no private
    address unless the host is internal). core/egress.check_destination is SMTP-only, so the
    same public parts are composed here (K-06b2-0002 S3a)."""
    try:
        target = httpx2.URL(url)
    except httpx2.InvalidURL:
        raise url_refused("egress_invalid_url") from None
    policy = EgressPolicy(settings)
    try:
        policy.check_url(target)
        host = target.host
        port = target.port or (443 if target.scheme == "https" else 80)
        literal = _parse_ip(host)
        try:
            addresses = (
                [str(literal)]
                if literal is not None
                else await (resolver or system_resolver)(host, port)
            )
        except OSError:
            raise url_refused("egress_dns_failed") from None
        if not addresses:
            raise url_refused("egress_private_address")
        for address in addresses:
            policy.check_address(host, address, port)
    except EgressDenied as exc:
        raise url_refused(exc.code) from None


class ExternalCallFailed(ApiError):
    """A failed external call; `audit` is what the audit event records (never content)."""

    def __init__(self, status_code: int, code: str, message: str, audit: dict[str, Any]) -> None:
        super().__init__(status_code, "api_error", code, message)
        self.audit = audit


@dataclass
class Upstream:
    content: str
    finish_reason: str
    host: str
    upstream_status: int
    response_bytes: int
    duration_ms: int
    ignored_fields: list[str] = field(default_factory=list)

    def audit(self) -> dict[str, Any]:
        return {
            "host": self.host,
            "upstream_status": self.upstream_status,
            "error_code": None,
            "duration_ms": self.duration_ms,
            "response_bytes": self.response_bytes,
        }


def _failed(code: str, error_code: str, audit: dict[str, Any]) -> ExternalCallFailed:
    audit["error_code"] = error_code
    if code == "external_agent_timeout":
        return ExternalCallFailed(504, code, "The external agent did not answer in time.", audit)
    if code == "external_agent_response_too_large":
        message = f"The external agent's answer exceeds {MAX_EXTERNAL_RESPONSE_BYTES} bytes."
        return ExternalCallFailed(502, code, message, audit)
    # The reason (egress code, upstream status) is in the audit event, never the upstream body.
    return ExternalCallFailed(502, code, "The external agent call failed.", audit)


def _content(payload: Any) -> tuple[str, str, list[str]] | None:
    """(text, finish_reason, ignored field names) or None when there is no text answer."""
    try:
        choice = payload["choices"][0]
        message = choice["message"]
    except (KeyError, IndexError, TypeError):
        return None
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    if not isinstance(content, str) or not content:
        return None
    ignored = sorted(k for k, v in message.items() if k not in ("role", "content") and v)
    finish = choice.get("finish_reason")
    return content, finish if finish in FINISH_REASONS else "stop", ignored


async def call_upstream(
    config: ExternalConfig,
    messages: list[dict],
    params: dict[str, Any],
    settings: Settings,
    *,
    resolver: Resolver | None = None,
    inner_backend=None,
) -> Upstream:
    """One non-streaming chat completion at the external agent."""
    url = config.base_url.rstrip("/") + "/chat/completions"
    host = httpx2.URL(url).host
    limit = settings.llm_call_timeout_s
    audit: dict[str, Any] = {
        "host": host,
        "upstream_status": None,
        "error_code": None,
        "duration_ms": 0,
        "response_bytes": 0,
    }
    started = time.monotonic()
    body = {"model": config.model, "messages": messages, "stream": False, **params}
    headers = {"Authorization": f"Bearer {config.api_key.get_secret_value()}"}
    client = SafeOutboundClient(
        timeout=EgressTimeout(connect=min(10, limit), read=limit, total=limit),
        settings=settings,
        resolver=resolver,
        inner_backend=inner_backend,
        max_redirects=0,  # K-06b2-0002: redirects are not followed
    )
    raw = bytearray()
    try:
        try:
            with anyio.fail_after(limit):
                async with client, client.stream("POST", url, headers=headers, json=body) as resp:
                    audit["upstream_status"] = resp.status_code
                    declared = resp.headers.get("content-length")
                    if (
                        declared
                        and declared.isdigit()
                        and int(declared) > MAX_EXTERNAL_RESPONSE_BYTES
                    ):
                        audit["response_bytes"] = int(declared)
                        raise _failed("external_agent_response_too_large", "too_large", audit)
                    async for chunk in resp.aiter_bytes():
                        raw += chunk
                        if len(raw) > MAX_EXTERNAL_RESPONSE_BYTES:
                            audit["response_bytes"] = len(raw)
                            raise _failed("external_agent_response_too_large", "too_large", audit)
        except (TimeoutError, EgressTimeoutError, httpx2.TimeoutException):
            raise _failed("external_agent_timeout", "egress_timeout", audit) from None
        except EgressError as exc:
            raise _failed("external_agent_failed", exc.code, audit) from None
        except httpx2.HTTPError:
            raise _failed("external_agent_failed", "egress_request_failed", audit) from None
    finally:
        audit["duration_ms"] = int((time.monotonic() - started) * 1000)
    audit["response_bytes"] = len(raw)
    if not 200 <= audit["upstream_status"] < 300:
        raise _failed("external_agent_failed", "upstream_status", audit)
    try:
        answer = _content(json.loads(raw))
    except ValueError:
        answer = None
    if answer is None:
        raise _failed("external_agent_failed", "invalid_answer", audit)
    content, finish, ignored = answer
    return Upstream(
        content=content,
        finish_reason=finish,
        host=host,
        upstream_status=audit["upstream_status"],
        response_bytes=len(raw),
        duration_ms=audit["duration_ms"],
        ignored_fields=ignored,
    )
