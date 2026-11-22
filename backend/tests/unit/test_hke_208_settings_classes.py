"""K-HKE-0010: every settings class handed to the egress client carries EGRESS_PROXY_URL.

The main gate found mcp-sql answering 500 on every call: SafeOutboundClient read
`settings.egress_proxy_url` from McpServiceSettings, which did not declare it. The field is
declared explicitly (no getattr default: a missing field must fail loudly, here, in a test).
"""

import importlib
import inspect
import pkgutil
import re

import pytest
from pydantic import ValidationError
from pydantic_settings import BaseSettings

import ffcore
from ffcore.core import egress as egress_module
from ffcore.core.config import get_settings
from ffcore.core.egress import EgressTimeout, SafeOutboundClient, policy_http_client
from ffcore.services.mcp_server_common import McpServiceSettings

TIMEOUT = EgressTimeout(connect=1, read=1, total=2)
SERVICE_TOKEN = "dummy-not-secret-service-token-0123456789"


def _mcp_settings(**values):
    return McpServiceSettings(service_token=SERVICE_TOKEN, offline=False, **values)


def test_hke_mcp_service_settings_build_the_egress_clients():
    settings = _mcp_settings()
    assert settings.egress_proxy_url == ""
    SafeOutboundClient(timeout=TIMEOUT, settings=settings)
    policy_http_client(timeout=TIMEOUT, settings=settings)


def test_hke_mcp_service_settings_read_the_proxy_from_the_environment(monkeypatch):
    monkeypatch.setenv("EGRESS_PROXY_URL", "http://egress-proxy:3128")
    settings = _mcp_settings()
    assert settings.egress_proxy_url == "http://egress-proxy:3128"
    client = SafeOutboundClient(timeout=TIMEOUT, settings=settings)
    assert client._transport._proxy is not None


def test_hke_mcp_service_settings_validate_the_proxy_like_the_backend():
    with pytest.raises(ValidationError, match="egress_proxy_url_invalid"):
        _mcp_settings(egress_proxy_url="https://user:pw@egress-proxy:3128/x")


# FOLLOWUP-215: modules that may not import in the test image, with the reason. A module that
# drops out and is not listed here fails the test (its settings class would go unchecked); a
# listed module that imports again fails it too, so the list never goes stale. Empty today:
# ffcore.knowledge.worker dropped out only where REDIS_URL was unset (a bare `docker run`; the
# compose tools service sets it), so the walk gives it a dummy URL (parsed, never connected).
EXPECTED_IMPORT_FAILURES: dict[str, str] = {}
IMPORT_ENV = {"REDIS_URL": "redis://:dummy-not-secret@redis:6379/0"}

# Every field core/egress.py reads from the settings object it is handed (drift-checked below).
EGRESS_FIELDS = frozenset(
    {
        "allowed_internal_hosts",
        "egress_allowlist",
        "egress_proxy_url",
        "internal_api_url",
        "offline",
    }
)


def _settings_classes():
    with pytest.MonkeyPatch.context() as mp:
        for name, value in IMPORT_ENV.items():
            mp.setenv(name, value)
        get_settings.cache_clear()
        try:
            return _walk()
        finally:
            get_settings.cache_clear()


def _walk():
    found, failed = set(), {}
    for module in pkgutil.walk_packages(ffcore.__path__, "ffcore."):
        try:
            loaded = importlib.import_module(module.name)
        except Exception as exc:  # noqa: BLE001 - collected and compared with the list above
            failed[module.name] = f"{type(exc).__name__}: {exc}"
            continue
        for _, obj in inspect.getmembers(loaded, inspect.isclass):
            if issubclass(obj, BaseSettings) and obj.__module__.startswith("ffcore."):
                found.add(obj)
    return found, failed


def test_hke_215_import_failures_are_the_expected_ones():
    _, failed = _settings_classes()
    assert set(failed) == set(EXPECTED_IMPORT_FAILURES), failed


def test_hke_215_egress_fields_match_what_the_egress_client_reads():
    source = inspect.getsource(egress_module)
    read = set(re.findall(r"\bsettings\.([a-z_]+)", source))
    assert read == EGRESS_FIELDS


def test_hke_every_egress_settings_class_declares_the_proxy():
    # egress_allowlist marks a class the egress client reads; it needs every egress field
    classes, _ = _settings_classes()
    egress = [c for c in classes if "egress_allowlist" in c.model_fields]
    assert {c.__name__ for c in egress} >= {"Settings", "McpServiceSettings"}
    missing = {
        c.__name__: sorted(EGRESS_FIELDS - set(c.model_fields))
        for c in egress
        if EGRESS_FIELDS - set(c.model_fields)
    }
    assert missing == {}
