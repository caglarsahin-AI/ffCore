"""Provider drivers: configuration fields (which are secret, which are required), domains and the
connection test. The test is one listing call through SafeOutboundClient (C5); drivers without a
safe listing call say so explicitly (KARARLAR "03a kararları", S4b).
"""

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ffcore.api.schemas import DriverField, DriverSpec, ProviderTestResult
from ffcore.core.config import Settings
from ffcore.core.egress import (
    EgressDenied,
    EgressError,
    EgressTimeout,
    EgressTimeoutError,
    SafeOutboundClient,
)
from ffcore.core.errors import ApiError

MASK = "***"
TEST_TIMEOUT = EgressTimeout(connect=5, read=10, total=15)

TestCall = Callable[[dict[str, str]], tuple[str, dict[str, str]]]


@dataclass(frozen=True)
class Field:
    name: str
    required: bool
    secret: bool
    description: str


@dataclass(frozen=True)
class Driver:
    domains: tuple[str, ...]
    fields: tuple[Field, ...] = ()
    # Builds (url, headers) of the listing call; None means the driver has no connection test.
    test_call: TestCall | None = None
    no_test_reason: str = ""
    defaults: dict[str, str] = field(default_factory=dict)


def _base(config: dict[str, str], default: str) -> str:
    return (config.get("base_url") or default).rstrip("/")


def _bearer(config: dict[str, str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {config['api_key']}"} if config.get("api_key") else {}


BASE_URL = Field("base_url", True, False, "Base URL of the server, e.g. http://ollama:11434.")
OPTIONAL_BASE_URL = Field("base_url", False, False, "Override of the provider's public URL.")
API_KEY = Field("api_key", True, True, "API key.")
OPTIONAL_API_KEY = Field("api_key", False, True, "API key, if the server requires one.")

DRIVERS: dict[str, Driver] = {
    "ollama": Driver(
        domains=("model", "embedding"),
        fields=(BASE_URL,),
        test_call=lambda c: (f"{_base(c, '')}/api/tags", {}),
    ),
    "vllm": Driver(
        domains=("model", "embedding"),
        fields=(BASE_URL, OPTIONAL_API_KEY),
        test_call=lambda c: (f"{_base(c, '')}/v1/models", _bearer(c)),
    ),
    "anthropic": Driver(
        domains=("model",),
        fields=(API_KEY, OPTIONAL_BASE_URL),
        test_call=lambda c: (
            f"{_base(c, 'https://api.anthropic.com')}/v1/models",
            {"x-api-key": c["api_key"], "anthropic-version": "2023-06-01"},
        ),
    ),
    "openai": Driver(
        domains=("model", "embedding"),
        fields=(API_KEY, OPTIONAL_BASE_URL),
        test_call=lambda c: (f"{_base(c, 'https://api.openai.com/v1')}/models", _bearer(c)),
    ),
    "azure_openai": Driver(
        domains=("model", "embedding"),
        fields=(
            API_KEY,
            Field("api_base", True, False, "Resource endpoint in the agreed region (EU)."),
            Field("api_version", True, False, "API version, e.g. 2024-10-21."),
        ),
        test_call=lambda c: (
            f"{c['api_base'].rstrip('/')}/openai/models?api-version={c['api_version']}",
            {"api-key": c["api_key"]},
        ),
    ),
    "bedrock": Driver(
        domains=("model", "embedding"),
        fields=(
            Field("aws_access_key_id", True, True, "Access key id."),
            Field("aws_secret_access_key", True, True, "Secret access key."),
            Field("region", True, False, "AWS region in the agreed area, e.g. eu-central-1."),
        ),
        no_test_reason="Bedrock requests need AWS SigV4 signing; no connection test.",
    ),
    "openai_compatible": Driver(
        domains=("model", "embedding"),
        fields=(BASE_URL, OPTIONAL_API_KEY),
        test_call=lambda c: (f"{_base(c, '')}/models", _bearer(c)),
    ),
    "local_flagembedding": Driver(
        domains=("embedding",),
        no_test_reason="Runs inside the API process; its health is part of /readyz.",
    ),
    "pgvector": Driver(
        domains=("vector",),
        no_test_reason="Uses the application database; no separate connection.",
    ),
    "qdrant": Driver(
        domains=("vector",),
        fields=(
            Field("url", True, False, "Qdrant URL, e.g. http://qdrant:6333."),
            Field("api_key", False, True, "API key, if Qdrant requires one."),
        ),
        test_call=lambda c: (
            f"{c['url'].rstrip('/')}/collections",
            {"api-key": c["api_key"]} if c.get("api_key") else {},
        ),
    ),
    "local_fs": Driver(
        domains=("file",),
        fields=(Field("path", True, False, "Directory inside the backend container."),),
        no_test_reason="Local directory; no connection to test.",
    ),
}


def driver(name: str) -> Driver:
    return DRIVERS[name]


def specs() -> list[DriverSpec]:
    return [
        DriverSpec(
            driver=name,
            domains=list(d.domains),
            supports_test=d.test_call is not None,
            fields=[DriverField(**vars(f)) for f in d.fields],
        )
        for name, d in DRIVERS.items()
    ]


def _invalid(code: str, message: str) -> ApiError:
    return ApiError(422, "invalid_request_error", code, message)


def validate_domains(name: str, domains: list[str]) -> None:
    unsupported = sorted(set(domains) - set(DRIVERS[name].domains))
    if unsupported:
        raise _invalid("domain_not_supported", f"Driver {name} does not serve: {unsupported}.")


def validate_config(name: str, config: dict[str, Any]) -> dict[str, str]:
    spec = DRIVERS[name]
    known = {f.name for f in spec.fields}
    unknown = sorted(set(config) - known)
    if unknown:
        raise _invalid("unknown_config_field", f"Unknown configuration fields: {unknown}.")
    clean: dict[str, str] = {}
    for f in spec.fields:
        value = config.get(f.name)
        if value is None or value == "":
            if f.required:
                raise _invalid("missing_config_field", f"Configuration field {f.name} is required.")
            continue
        if not isinstance(value, str):
            raise _invalid("invalid_config_field", f"Configuration field {f.name} must be text.")
        if f.secret and value == MASK:
            raise _invalid("invalid_config_field", f"Configuration field {f.name} is masked.")
        clean[f.name] = value
    return clean


def merge_config(name: str, stored: dict[str, str], update: dict[str, Any]) -> dict[str, str]:
    """A secret field sent back as "***" keeps its stored value (the API never returns it)."""
    secret = {f.name for f in DRIVERS[name].fields if f.secret}
    merged = dict(update)
    for key, value in update.items():
        if key in secret and value == MASK:
            if key not in stored:
                raise _invalid("invalid_config_field", f"Configuration field {key} is masked.")
            merged[key] = stored[key]
    return validate_config(name, merged)


def mask_config(name: str, config: dict[str, str]) -> dict[str, str]:
    secret = {f.name for f in DRIVERS[name].fields if f.secret}
    return {key: MASK if key in secret else value for key, value in config.items()}


async def test_connection(
    name: str, config: dict[str, str], settings: Settings, **client_options
) -> ProviderTestResult:
    """Never raises for connection problems: the outcome is the result (a failed test does not
    block saving). Messages carry no URL path, header or key."""
    spec = DRIVERS[name]
    if spec.test_call is None:
        return ProviderTestResult(
            supported=False,
            ok=False,
            code="connection_test_unsupported",
            message=spec.no_test_reason,
        )
    url, headers = spec.test_call(config)
    started = time.monotonic()
    try:
        async with SafeOutboundClient(
            timeout=TEST_TIMEOUT, settings=settings, **client_options
        ) as client:
            response = await client.request("GET", url, headers=headers)
    except EgressDenied as exc:
        return _failed(exc.code, f"Refused by the outbound policy ({exc.code}).")
    except EgressTimeoutError:
        return _failed("egress_timeout", "The provider did not answer in time.")
    except EgressError:
        return _failed("connection_failed", "Could not connect to the provider.")
    latency = int((time.monotonic() - started) * 1000)
    if response.status_code in (401, 403):
        return _failed("auth_failed", "The provider refused the credentials.", latency)
    if response.status_code >= 400:
        code = f"http_{response.status_code}"
        return _failed(code, f"The provider answered {response.status_code}.", latency)
    return ProviderTestResult(
        supported=True, ok=True, code="ok", message="Connection works.", latency_ms=latency
    )


def _failed(code: str, message: str, latency: int | None = None) -> ProviderTestResult:
    return ProviderTestResult(
        supported=True, ok=False, code=code, message=message, latency_ms=latency
    )
