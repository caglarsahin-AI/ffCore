"""03a session tokens and the cross-origin rule (acceptance 4 and 5, unit part)."""

from datetime import UTC, datetime, timedelta

import pytest
from starlette.requests import Request

from ffcore.core import auth
from ffcore.core.errors import ApiError
from ffcore.core.session import check_same_origin


def _request(method: str, headers: dict[str, str]) -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    return Request({"type": "http", "method": method, "headers": raw, "path": "/"})


def test_03a_4_session_token_round_trip(settings):
    token = auth.issue_session_token("u-1", 3, settings)
    assert auth.verify_session_token(token, settings) == auth.SessionClaims("u-1", 3)


def test_03a_4_expired_session_token_rejected(settings):
    old = datetime.now(UTC) - timedelta(seconds=settings.session_ttl_s + 5)
    token = auth.issue_session_token("u", 0, settings, old)
    assert auth.verify_session_token(token, settings) is None


def test_03a_4_session_and_obo_tokens_do_not_cross(settings):
    obo = auth.sign_on_behalf_of(user_id="u", project_id="p", audience="x", settings=settings)
    assert auth.verify_session_token(obo, settings) is None
    session_token = auth.issue_session_token("u", 0, settings)
    with pytest.raises(auth.OnBehalfOfError):
        auth.verify_on_behalf_of(session_token, audience="ffcore-session", settings=settings)


def test_03a_4_tampered_session_token_rejected(settings):
    token = auth.issue_session_token("u", 0, settings)
    assert auth.verify_session_token(token[:-2] + "xx", settings) is None


@pytest.mark.parametrize(
    "headers",
    [
        {"origin": "https://evil.example"},
        {"sec-fetch-site": "cross-site"},
        {"sec-fetch-site": "same-site"},
    ],
)
def test_03a_5_foreign_origin_mutation_refused(settings, headers):
    settings = settings.model_copy(update={"console_origins": ["https://console.example"]})
    with pytest.raises(ApiError) as caught:
        check_same_origin(_request("POST", headers), settings)
    assert (caught.value.status_code, caught.value.code) == (403, "cross_origin_forbidden")


def test_03a_5_own_origin_and_safe_methods_pass(settings):
    settings = settings.model_copy(update={"console_origins": ["https://console.example"]})
    check_same_origin(_request("POST", {"origin": "https://console.example/"}), settings)
    check_same_origin(_request("POST", {"sec-fetch-site": "same-origin"}), settings)
    check_same_origin(_request("GET", {"origin": "https://evil.example"}), settings)
