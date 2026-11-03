"""06b-2 external agent configuration (`agents.external_config`) and its base URL policy: what
the registration routes (api/agents.py) and the call path (services/facade_external.py) share.
It imports nothing from ffcore.api, so either side can be imported first (review r1 MINOR-6)."""

import httpx2
from pydantic import BaseModel, ConfigDict, SecretStr

from ffcore.core.config import Settings
from ffcore.core.egress import (
    EgressError,
    Resolver,
    _parse_ip,
    check_http_destination,
    system_resolver,
)
from ffcore.core.errors import ApiError
from ffcore.core.secrets import decrypt_json, encrypt_json


class ExternalConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    base_url: str
    model: str
    # None after the base URL moved to another origin without a new key (review r1 MINOR-4):
    # the agent cannot be published or called until a key is given again.
    api_key: SecretStr | None

    def public(self) -> dict[str, str | None]:
        """What an API answer and an audit event may show."""
        masked = "***" if self.api_key is not None else None
        return {"base_url": self.base_url, "model": self.model, "api_key": masked}

    def encrypt(self, settings: Settings) -> bytes:
        return encrypt_json(
            {
                "base_url": self.base_url,
                "model": self.model,
                "api_key": self.api_key.get_secret_value() if self.api_key else None,
            },
            settings,
        )

    @classmethod
    def decrypt(cls, token: bytes, settings: Settings) -> "ExternalConfig":
        return cls.model_validate(decrypt_json(token, settings))


def origin(url: str) -> str:
    """scheme://host:port of a base URL (the default port written out)."""
    target = httpx2.URL(url)
    port = target.port or (443 if target.scheme == "https" else 80)
    return f"{target.scheme}://{(target.host or '').lower().rstrip('.')}:{port}"


# Review r1 MINOR-1 (K-06b2-0008, decision A): the platform's own services are never an external
# agent's target, even when ALLOWED_INTERNAL_HOSTS lets them be reached; wrapping LiteLLM or
# Ollama as an "external agent" would take the platform's own model outside quota and tracing.
# Every compose service is a host name on the platform network (tests/contract checks the list
# against deploy/docker-compose*.yml); host.docker.internal is airgap Ollama on the host (seed).
# Other internal hosts stay valid targets (KARARLAR:172).
RESERVED_HOSTS = frozenset(
    {
        "agent-worker",
        "agent-worker-bg",
        "backend",
        "e2e",
        "fake-llm",
        "frontend",
        "langfuse-clickhouse",
        "langfuse-minio",
        "langfuse-postgres",
        "langfuse-redis",
        "langfuse-web",
        "langfuse-worker",
        "litellm",
        "mcp-search",
        "mcp-sql",
        "migrate",
        "ollama",
        "postgres",
        "qdrant",
        "redis",
        "ticket-desk",
        "vllm",
        "tools",
        "worker",
        "host.docker.internal",
    }
)
# The port the backend listens on in its container (compose maps BACKEND_PORT to it): a loopback
# address on it is the backend itself.
BACKEND_CONTAINER_PORT = 8000


def _host(url: str) -> str:
    """A host as compared here: lower case, without the root dot (r2 NOTE-2)."""
    return (httpx2.URL(url).host or "").lower().rstrip(".")


def _reserved(host: str, port: int, settings: Settings) -> bool:
    configured = {_host(url) for url in (settings.litellm_url, settings.langfuse_host) if url}
    if host in RESERVED_HOSTS or host in configured:
        return True
    literal = _parse_ip(host)
    loopback = host == "localhost" or (literal is not None and literal.is_loopback)
    return loopback and port == BACKEND_CONTAINER_PORT


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
    address unless the host is internal), through core/egress.check_http_destination
    (FOLLOWUP-147), plus what a base URL adds: no credentials, query or fragment, and none of
    the platform's own hosts."""
    try:
        target = httpx2.URL(url)
    except httpx2.InvalidURL:
        raise url_refused("egress_invalid_url") from None
    if target.userinfo:
        # Credentials in the URL would leave as Basic auth beside the registered key, and appear
        # wherever the URL is shown; the key field is the only credential (K-06b2-0003).
        raise url_refused("egress_userinfo")
    if "?" in url or "#" in url:
        # Review r1 MINOR-2: scheme, host, port and path only. A query would carry a credential
        # (`?api-key=`) into every place the URL is shown and choose the upstream path.
        raise ApiError(
            422,
            "invalid_request_error",
            "base_url_query_not_allowed",
            "The base URL takes scheme, host, port and path only (no query, no fragment).",
            param="base_url",
        )
    if target.port is not None and not 0 < target.port < 65536:
        # httpx2 parses any number as a port; the dial would fail later and less clearly.
        raise url_refused("egress_invalid_port")
    port = target.port or (443 if target.scheme == "https" else 80)
    if _reserved((target.host or "").lower().rstrip("."), port, settings):
        raise ApiError(
            422,
            "invalid_request_error",
            "external_agent_host_reserved",
            "The base URL names one of the platform's own services; it cannot be an external "
            "agent.",
            param="base_url",
        )
    try:
        # The scheme, host and address rules are egress's own (FOLLOWUP-147); the checks above
        # are what a base URL adds to them.
        await check_http_destination(settings, url, resolver=resolver or system_resolver)
    except EgressError as exc:
        raise url_refused(exc.code) from None
