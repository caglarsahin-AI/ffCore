"""FOLLOWUP-194 (FOLLOWUP-159's other half, state/pr/05b.md): the backend itself is never the
target of a provider base_url (01) or a webhook (03c), whatever ALLOWED_INTERNAL_HOSTS says.

One rule, `core.egress.is_platform_target` (05b's mcp_client uses the same function): the
INTERNAL_API_URL origin, the `backend` service name on any port, loopback on the backend's
container port. Here: the call-time paths (connection test, LiteLLM reconcile, webhook post),
each refused before any connection. The registration paths are in
tests/integration/test_trj_194_platform_registration.py.
"""

import asyncio
from types import SimpleNamespace

import pytest

from ffcore.core import egress
from ffcore.core.errors import ApiError
from ffcore.services import mcp_client, notify
from ffcore.services import providers as drivers
from ffcore.services.litellm_reconcile import ReconcileProblem, desired_model

INTERNAL = "http://ffcore-api.internal:8443"
PLATFORM_URLS = [
    f"{INTERNAL}/v1",  # the INTERNAL_API_URL origin
    "http://backend:9000/v1",  # the service name, any port
    "http://127.0.0.1:8000/v1",  # loopback on the container port
]


@pytest.fixture(params=[[], ["backend", "127.0.0.1", "ffcore-api.internal"]], ids=["", "allowed"])
def platform_settings(request, settings):
    """Both with and without the backend in ALLOWED_INTERNAL_HOSTS: the rule does not care."""
    return settings.model_copy(
        update={"internal_api_url": INTERNAL, "allowed_internal_hosts": request.param}
    )


class NoClient:
    def __init__(self, *_, **__):
        raise AssertionError("a platform target must be refused before any connection")


@pytest.mark.parametrize("url", PLATFORM_URLS)
def test_trj_194_rule_is_shared(url, platform_settings):
    assert egress.is_platform_target(url, platform_settings)
    assert mcp_client.is_platform_target is egress.is_platform_target


@pytest.mark.parametrize(
    "url", ["http://ollama:11434", "https://api.example.com/v1", "http://127.0.0.1:11434"]
)
def test_trj_194_other_internal_hosts_pass(url, platform_settings):
    assert not egress.is_platform_target(url, platform_settings)


@pytest.mark.parametrize("url", PLATFORM_URLS)
def test_trj_194_connection_test_refuses(url, platform_settings, monkeypatch):
    monkeypatch.setattr(drivers, "SafeOutboundClient", NoClient)
    result = asyncio.run(drivers.test_connection("ollama", {"base_url": url}, platform_settings))
    assert (result.ok, result.code) == (False, "endpoint_is_platform")


@pytest.mark.parametrize("field", ["base_url", "api_base", "url"])
@pytest.mark.parametrize("url", PLATFORM_URLS)
def test_trj_194_saved_address_fields_refused(field, url, platform_settings):
    """Every driver's address field is checked when saved, the qdrant driver's `url` too
    (review r1 NOTE-1): saving and the connection test give the same answer."""
    with pytest.raises(ApiError) as err:
        drivers.refuse_platform_urls({field: url}, platform_settings)
    assert (err.value.status_code, err.value.code) == (400, "endpoint_is_platform")
    assert "://" not in err.value.message


def test_trj_194_url_fields_cover_every_driver_address():
    names = {f.name for d in drivers.DRIVERS.values() for f in d.fields}
    address = {n for n in names if "url" in n or n == "api_base"}
    assert address == {"base_url", "api_base", "url"}
    assert address <= set(drivers.URL_FIELDS), address


@pytest.mark.parametrize("url", PLATFORM_URLS)
def test_trj_194_qdrant_connection_test_refuses(url, platform_settings, monkeypatch):
    monkeypatch.setattr(drivers, "SafeOutboundClient", NoClient)
    result = asyncio.run(drivers.test_connection("qdrant", {"url": url}, platform_settings))
    assert (result.ok, result.code) == (False, "endpoint_is_platform")


@pytest.mark.parametrize("url", PLATFORM_URLS)
def test_trj_194_reconcile_refuses(url, platform_settings):
    model = SimpleNamespace(
        key="chat-default",
        model_id="qwen3.5:35b",
        upstream_api="chat",
        request_policy={},
        limits={},
        pricing={},
        capabilities={},
        input_types=["text"],
        category="llm",
        id="00000000-0000-0000-0000-000000000001",
    )
    provider = SimpleNamespace(driver="ollama", config={"base_url": url})
    with pytest.raises(ReconcileProblem) as err:
        desired_model("hastane", model, provider, platform_settings)
    assert err.value.code == "endpoint_is_platform"


@pytest.mark.parametrize("url", [f"{u}/hook" for u in PLATFORM_URLS])
def test_trj_194_webhook_post_refuses(url, platform_settings, monkeypatch):
    monkeypatch.setattr(notify, "SafeOutboundClient", NoClient)
    with pytest.raises(notify.NotificationError) as err:
        asyncio.run(notify.post_webhook(platform_settings, url, {"kind": "test"}))
    assert err.value.code == "endpoint_is_platform"
