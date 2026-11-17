"""05b S3 (FOLLOWUP-159, tool side) and the upstream rules of published servers.

- A tool may point at the backend itself only as `<INTERNAL_API_URL>/mcp/<key>/` with
  forward_user (self-consumption of a published server); any other backend URL is refused,
  even when ALLOWED_INTERNAL_HOSTS lists the backend.
- The self endpoint is reachable at call time without adding the backend to
  ALLOWED_INTERNAL_HOSTS (call settings widen only for that exact target).
- A published server's upstream is never a platform service (RESERVED_HOSTS, the backend).
"""

import pytest

from ffcore.core.config import Settings
from ffcore.core.errors import ApiError
from ffcore.services import mcp_client, mcp_tools
from ffcore.services.mcp_publish import check_upstream_url
from tests.dummy import OBO_SECRET, SERVICE_TOKEN, SETTINGS_03A


def _settings(**extra) -> Settings:
    base = {
        "deploy_profile": "llmaas",
        "offline": False,
        "service_token": SERVICE_TOKEN,
        "obo_jwt_secret": OBO_SECRET,
        **SETTINGS_03A,
        "internal_api_url": "http://backend:8000",
        "allowed_internal_hosts": ["mcp-search"],
        "egress_allowlist": ["superset.example.com"],
    }
    return Settings(**(base | extra))


def _code(call) -> str:
    with pytest.raises(ApiError) as caught:
        call()
    return caught.value.code


def test_05b_self_endpoint_is_the_published_path():
    assert mcp_tools.self_endpoint(_settings(), "superset") == "http://backend:8000/mcp/superset/"


def test_05b_self_endpoint_registers_with_forward_user():
    settings = _settings()
    mcp_tools.check_endpoint("http://backend:8000/mcp/superset/", "forward_user", settings)


@pytest.mark.parametrize(
    "url, auth",
    [
        ("http://backend:8000/mcp/superset/", "none"),
        ("http://backend:8000/mcp/superset/", "bearer"),
        ("http://backend:8000/api/v1/projects", "forward_user"),
        ("http://backend:8000/mcp/", "forward_user"),
        ("http://backend:8000/mcp/Bad_Key/", "forward_user"),
        ("http://backend:8000/mcp/a/../../api/", "forward_user"),
        ("http://backend:9000/mcp/superset/", "forward_user"),
        ("http://127.0.0.1:8000/mcp/superset/", "forward_user"),
    ],
)
def test_05b_other_backend_targets_are_refused(url, auth):
    # Even with the backend (and loopback) listed as internal (FOLLOWUP-159).
    settings = _settings(allowed_internal_hosts=["backend", "127.0.0.0/8"])
    assert _code(lambda: mcp_tools.check_endpoint(url, auth, settings)) == "endpoint_is_platform"


def test_05b_ordinary_internal_tools_still_register():
    mcp_tools.check_endpoint("http://mcp-search:8000/mcp", "forward_user", _settings())


def test_05b_call_settings_widen_only_for_the_self_endpoint():
    settings = _settings()
    own = mcp_client.ToolTarget("superset", "http://backend:8000/mcp/superset/", "forward_user", {})
    other = mcp_client.ToolTarget("x", "http://mcp-search:8000/mcp", "forward_user", {})
    widened = mcp_client.call_settings(own, settings)
    assert "backend" in widened.allowed_internal_hosts
    assert "backend" not in settings.allowed_internal_hosts
    assert mcp_client.call_settings(other, settings) is settings
    wrong_auth = mcp_client.ToolTarget("s", "http://backend:8000/mcp/s/", "none", {})
    assert mcp_client.call_settings(wrong_auth, settings) is settings


@pytest.mark.parametrize(
    "url, code",
    [
        ("http://backend:8000", "upstream_url_refused"),
        ("http://litellm:4000", "upstream_url_refused"),
        ("http://mcp-search:8000", "upstream_url_refused"),
        ("http://postgres:5432", "upstream_url_refused"),
        ("http://127.0.0.1:8000", "upstream_url_refused"),
        ("http://user:pw@superset.example.com", "endpoint_url_not_allowed"),
        ("http://superset.example.com?x=1", "endpoint_url_not_allowed"),
        ("http://not-listed.example.com", "egress_not_allowlisted"),
        ("ftp://superset.example.com", "egress_invalid_url"),
    ],
)
def test_05b_upstream_url_rules(url, code):
    settings = _settings(allowed_internal_hosts=["mcp-search", "127.0.0.0/8"])
    assert _code(lambda: check_upstream_url(url, settings)) == code


def test_05b_upstream_url_accepts_an_allowlisted_host():
    check_upstream_url("https://superset.example.com/base", _settings())
