import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from ffcore.core.config import Settings
from ffcore.core.errors import ApiError, install_error_handlers

BASE = {
    "deploy_profile": "llmaas",
    "offline": False,
    "service_token": "dummy-not-secret-service-token-0123456789",
    "obo_jwt_secret": "dummy-not-secret-obo-jwt-secret-0123456789",
}


def test_03b_config_lists_split_on_commas(monkeypatch):
    monkeypatch.setenv("EGRESS_ALLOWLIST", "api.anthropic.com, *.openai.azure.com")
    monkeypatch.setenv("ALLOWED_INTERNAL_HOSTS", "")
    settings = Settings(**BASE)
    assert settings.egress_allowlist == ["api.anthropic.com", "*.openai.azure.com"]
    assert settings.allowed_internal_hosts == []


def test_03b_config_secrets_required(monkeypatch):
    monkeypatch.delenv("SERVICE_TOKEN", raising=False)
    monkeypatch.delenv("OBO_JWT_SECRET", raising=False)
    with pytest.raises(ValidationError):
        Settings(deploy_profile="llmaas", offline=False)


def test_03b_config_short_jwt_secret_rejected():
    with pytest.raises(ValidationError):
        Settings(**{**BASE, "obo_jwt_secret": "short"})


def test_03b_config_secrets_not_in_repr():
    text = repr(Settings(**BASE))
    assert "dummy-not-secret" not in text


def _app() -> FastAPI:
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/api-error")
    def api_error():
        raise ApiError(403, "permission_error", "audience_mismatch", "Token audience mismatch.")

    @app.get("/http-error")
    def http_error():
        raise HTTPException(status_code=401, detail="Not authenticated.")

    @app.get("/needs-int")
    def needs_int(n: int):
        return {"n": n}

    return app


@pytest.mark.parametrize(
    ("path", "status", "error_type", "code"),
    [
        ("/api-error", 403, "permission_error", "audience_mismatch"),
        ("/http-error", 401, "authentication_error", "unauthenticated"),
        ("/needs-int?n=x", 422, "invalid_request_error", "validation_error"),
        ("/missing", 404, "not_found_error", "not_found"),
    ],
)
def test_03b_7_4xx_openai_error_shape(path, status, error_type, code):
    response = TestClient(_app()).get(path)
    assert response.status_code == status
    body = response.json()
    assert set(body) == {"error"}
    assert body["error"]["type"] == error_type
    assert body["error"]["code"] == code
    assert body["error"]["message"].isascii()
