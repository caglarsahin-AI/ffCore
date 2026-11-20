"""K-HKE-0010: every settings class handed to the egress client carries EGRESS_PROXY_URL.

The main gate found mcp-sql answering 500 on every call: SafeOutboundClient read
`settings.egress_proxy_url` from McpServiceSettings, which did not declare it. The field is
declared explicitly (no getattr default: a missing field must fail loudly, here, in a test).
"""

import importlib
import inspect
import pkgutil

import pytest
from pydantic import ValidationError
from pydantic_settings import BaseSettings

import ffcore
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


def _settings_classes():
    found = set()
    for module in pkgutil.walk_packages(ffcore.__path__, "ffcore."):
        try:
            loaded = importlib.import_module(module.name)
        except Exception:  # noqa: BLE001 - optional runtime deps; listed below if any
            continue
        for _, obj in inspect.getmembers(loaded, inspect.isclass):
            if issubclass(obj, BaseSettings) and obj.__module__.startswith("ffcore."):
                found.add(obj)
    return found


def test_hke_every_egress_settings_class_declares_the_proxy():
    # egress_allowlist marks a class the egress client reads; it needs every egress field
    egress = [c for c in _settings_classes() if "egress_allowlist" in c.model_fields]
    assert {c.__name__ for c in egress} >= {"Settings", "McpServiceSettings"}
    missing = [c.__name__ for c in egress if "egress_proxy_url" not in c.model_fields]
    assert missing == []
