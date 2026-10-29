"""05a review r1 MAJOR-1: POST /api/v1/internal/obo/verify.

FFCore's MCP services hold no signing key (K-05a-0002 S3), so they ask the backend to verify
a caller's token before acting on it (KARARLAR "05a review r1 kararları" item 2): signature,
the audience the service names, lifetime. Service account only.
"""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import SecretStr

from ffcore.core.auth import sign_on_behalf_of
from tests.dummy import SERVICE_TOKEN

URL = "/api/v1/internal/obo/verify"
SERVICE = {"Authorization": f"Bearer {SERVICE_TOKEN}"}
FORGED_KEY = "dummy-not-secret-forged-obo-key-0123456789abcdef"


@pytest.fixture
def client(client_factory):
    return client_factory()


def _token(settings, audience=("mcp-sql",), **kwargs):
    return sign_on_behalf_of(
        user_id="user-1",
        project_id="project-1",
        audience=[*audience, settings.obo_audience],
        settings=kwargs.pop("signer", settings),
        ttl_s=60,
        **kwargs,
    )


def _verify(client, token, audience="mcp-sql", headers=SERVICE):
    return client.post(URL, json={"token": token, "audience": audience}, headers=headers)


def test_05a_obo_verify_returns_claims(client, app_settings):
    response = _verify(client, _token(app_settings))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["sub"] == "user-1" and body["project_id"] == "project-1"
    assert body["jti"] and body["exp"] > datetime.now(UTC).timestamp()


def test_05a_obo_verify_wrong_key_401(client, app_settings):
    forger = app_settings.model_copy(update={"obo_jwt_secret": SecretStr(FORGED_KEY)})
    response = _verify(client, _token(app_settings, signer=forger))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_token"


def test_05a_obo_verify_other_tool_403(client, app_settings):
    response = _verify(client, _token(app_settings, audience=("mcp-search",)))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "audience_mismatch"


def test_05a_obo_verify_expired_401(client, app_settings):
    old = datetime.now(UTC) - timedelta(minutes=10)
    response = _verify(client, _token(app_settings, now=old))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "token_expired"


def test_05a_obo_verify_garbage_401(client):
    response = _verify(client, "not-a-token")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_token"


def test_05a_obo_verify_service_account_only(client_factory, make_user, app_settings):
    _, email = make_user(superadmin="edit")
    token = _token(app_settings)
    anonymous = _verify(client_factory(), token, headers={})
    user = _verify(client_factory(email), token, headers={})
    assert anonymous.status_code == 401
    assert user.status_code == 403 and user.json()["error"]["code"] == "service_account_required"


def test_05a_obo_verify_token_never_echoed(client, app_settings):
    token = _token(app_settings)
    assert token not in _verify(client, token).text
