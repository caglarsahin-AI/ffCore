from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from ffcore.core import auth
from ffcore.core.auth import (
    Actor,
    OnBehalfOfError,
    resolve_actor,
    sign_on_behalf_of,
    verify_on_behalf_of,
)
from ffcore.core.config import get_settings
from ffcore.core.errors import install_error_handlers

from .conftest import OBO_SECRET, SERVICE_TOKEN

T0 = datetime(2026, 10, 28, 9, 0, tzinfo=UTC)
USER = "6d0e2f47-6f6a-4d2b-9a3e-1c2b3d4e5f60"
PROJECT = "1f2e3d4c-5b6a-4978-8695-a4b3c2d1e0f9"


# --- criterion 3 (C3): token lifetime, audience, re-signing --------------------------------


def test_03b_3_two_tokens_six_minutes_apart_distinct_aud(settings):
    first = sign_on_behalf_of(
        user_id=USER, project_id=PROJECT, audience="mcp-search", settings=settings, now=T0
    )
    later = T0 + timedelta(minutes=6)
    second = sign_on_behalf_of(
        user_id=USER, project_id=PROJECT, audience="tool:superset", settings=settings, now=later
    )
    claims_1 = verify_on_behalf_of(first, audience="mcp-search", settings=settings, now=T0)
    claims_2 = verify_on_behalf_of(second, audience="tool:superset", settings=settings, now=later)
    assert (claims_1.sub, claims_1.project_id, claims_1.aud) == (USER, PROJECT, "mcp-search")
    assert (claims_2.sub, claims_2.project_id, claims_2.aud) == (USER, PROJECT, "tool:superset")
    # The first token did not survive the six minutes: every call re-signs.
    with pytest.raises(OnBehalfOfError) as exc:
        verify_on_behalf_of(first, audience="mcp-search", settings=settings, now=later)
    assert exc.value.status_code == 401


def test_03b_3_expired_401(settings):
    token = sign_on_behalf_of(
        user_id=USER, project_id=PROJECT, audience="mcp-search", settings=settings, now=T0
    )
    with pytest.raises(OnBehalfOfError) as exc:
        verify_on_behalf_of(
            token, audience="mcp-search", settings=settings, now=T0 + timedelta(seconds=300)
        )
    assert (exc.value.status_code, exc.value.code) == (401, "token_expired")


def test_03b_3_wrong_aud_403(settings):
    token = sign_on_behalf_of(
        user_id=USER, project_id=PROJECT, audience="mcp-search", settings=settings, now=T0
    )
    with pytest.raises(OnBehalfOfError) as exc:
        verify_on_behalf_of(token, audience="ffcore-backend", settings=settings, now=T0)
    assert (exc.value.status_code, exc.value.code) == (403, "audience_mismatch")


def test_03b_3_lifetime_over_5min_rejected(settings):
    with pytest.raises(ValueError):
        sign_on_behalf_of(
            user_id=USER,
            project_id=PROJECT,
            audience="mcp-search",
            settings=settings,
            now=T0,
            ttl_s=301,
        )
    forged = jwt.encode(
        {
            "sub": USER,
            "project_id": PROJECT,
            "aud": "mcp-search",
            "iat": int(T0.timestamp()),
            "exp": int(T0.timestamp()) + 3600,
        },
        OBO_SECRET,
        algorithm="HS256",
    )
    with pytest.raises(OnBehalfOfError) as exc:
        verify_on_behalf_of(forged, audience="mcp-search", settings=settings, now=T0)
    assert (exc.value.status_code, exc.value.code) == (401, "token_lifetime_exceeded")


@pytest.mark.parametrize("missing", ["sub", "project_id", "aud", "exp", "iat"])
def test_03b_3_required_claims(settings, missing):
    claims = {
        "sub": USER,
        "project_id": PROJECT,
        "aud": "mcp-search",
        "iat": int(T0.timestamp()),
        "exp": int(T0.timestamp()) + 60,
    }
    del claims[missing]
    token = jwt.encode(claims, OBO_SECRET, algorithm="HS256")
    with pytest.raises(OnBehalfOfError) as exc:
        verify_on_behalf_of(token, audience="mcp-search", settings=settings, now=T0)
    assert exc.value.status_code == 401


def test_03b_3_bad_signature_and_alg_none_401(settings):
    good = sign_on_behalf_of(
        user_id=USER, project_id=PROJECT, audience="mcp-search", settings=settings, now=T0
    )
    tampered = good[:-2] + ("AA" if not good.endswith("AA") else "BB")
    unsigned = jwt.encode(
        jwt.decode(good, options={"verify_signature": False}), key=None, algorithm="none"
    )
    for token in (tampered, unsigned, "not-a-jwt"):
        with pytest.raises(OnBehalfOfError) as exc:
            verify_on_behalf_of(token, audience="mcp-search", settings=settings, now=T0)
        assert exc.value.status_code == 401


# --- criterion 1 (R2.5): resolve_actor and X-On-Behalf-Of ----------------------------------


@pytest.fixture
def client(settings, monkeypatch):
    denied: list[tuple[str, Actor | None]] = []

    async def record(request, actor):
        denied.append((request.url.path, actor))

    monkeypatch.setattr(auth, "_audit_impersonation_denied", record)
    app = FastAPI()
    install_error_handlers(app)
    app.dependency_overrides[get_settings] = lambda: settings

    @app.get("/whoami")
    async def whoami(actor: Annotated[Actor, Depends(resolve_actor)]):
        return {
            "type": actor.actor_type,
            "id": actor.actor_id,
            "project_id": actor.project_id,
            "via_service": actor.via_service,
        }

    test_client = TestClient(app)
    test_client.denied = denied
    return test_client


def _obo(settings, audience="ffcore-backend", now=None):
    return sign_on_behalf_of(
        user_id=USER, project_id=PROJECT, audience=audience, settings=settings, now=now
    )


def test_03b_1_unknown_caller_401(client):
    for headers in ({}, {"Authorization": "Bearer dummy-not-secret-wrong-token-0000000000"}):
        response = client.get("/whoami", headers=headers)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "unauthenticated"


def test_03b_1_service_token_is_system_actor(client):
    response = client.get("/whoami", headers={"Authorization": f"Bearer {SERVICE_TOKEN}"})
    assert response.status_code == 200
    assert response.json() == {
        "type": "system",
        "id": "service",
        "project_id": None,
        "via_service": False,
    }


def test_03b_1_valid_obo_actor_is_user(client, settings):
    response = client.get(
        "/whoami",
        headers={"Authorization": f"Bearer {SERVICE_TOKEN}", "X-On-Behalf-Of": _obo(settings)},
    )
    assert response.status_code == 200
    assert response.json() == {
        "type": "user",
        "id": USER,
        "project_id": PROJECT,
        "via_service": True,
    }
    assert client.denied == []


def test_03b_1_obo_without_service_token_is_ignored_and_audited(client, settings):
    response = client.get("/whoami", headers={"X-On-Behalf-Of": _obo(settings)})
    assert response.status_code == 401
    assert client.denied == [("/whoami", None)]


def test_03b_1_obo_ignored_for_non_impersonating_credential(client, settings):
    # Stand-in for a 03c API key without the `impersonate` scope (and for a 03a user session).
    async def api_key_resolver(request, _settings):
        if request.headers.get("authorization") == "Bearer dummy-not-secret-api-key":
            return Actor(actor_type="api_key", actor_id="key-1", project_id=PROJECT)
        return None

    auth.register_credential_resolver(api_key_resolver)
    try:
        response = client.get(
            "/whoami",
            headers={
                "Authorization": "Bearer dummy-not-secret-api-key",
                "X-On-Behalf-Of": _obo(settings),
            },
        )
    finally:
        auth.unregister_credential_resolver(api_key_resolver)
    assert response.status_code == 200
    assert response.json()["type"] == "api_key"
    assert response.json()["id"] == "key-1"
    assert len(client.denied) == 1 and client.denied[0][1].actor_id == "key-1"


def test_03b_1_invalid_obo_with_service_token_fails_loud(client, settings):
    for token, status in (
        (_obo(settings, audience="mcp-search"), 403),
        (_obo(settings, now=datetime.now(UTC) - timedelta(minutes=10)), 401),
    ):
        response = client.get(
            "/whoami",
            headers={"Authorization": f"Bearer {SERVICE_TOKEN}", "X-On-Behalf-Of": token},
        )
        assert response.status_code == status
        assert "dummy-not-secret" not in response.text
