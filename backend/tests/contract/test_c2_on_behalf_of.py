"""C2 (freezes at M2): on-behalf-of claim names and the single verification point."""

from pathlib import Path

import jwt

from ffcore.core import auth
from ffcore.core.config import Settings
from tests.dummy import SETTINGS_03A

PACKAGE = Path(auth.__file__).resolve().parents[1]
SETTINGS = Settings(
    deploy_profile="llmaas",
    offline=False,
    service_token="dummy-not-secret-service-token-0123456789",
    obo_jwt_secret="dummy-not-secret-obo-jwt-secret-0123456789",
    **SETTINGS_03A,
)


def test_c2_obo_claim_names_and_header():
    token = auth.sign_on_behalf_of(
        user_id="u", project_id="p", audience="mcp-search", settings=SETTINGS
    )
    claims = jwt.decode(token, options={"verify_signature": False})
    assert {"sub", "project_id", "exp", "aud", "iat"} <= set(claims)
    assert claims["exp"] - claims["iat"] <= 300
    assert auth.OBO_HEADER == "X-On-Behalf-Of"
    assert auth.OBO_MAX_LIFETIME_S == 300


def test_c2_resolve_actor_is_single_verification_point():
    offenders = []
    for path in PACKAGE.rglob("*.py"):
        if path.name == "auth.py" and path.parent.name == "core":
            continue
        source = path.read_text(encoding="utf-8")
        if "jwt.decode" in source or "service_token.get_secret_value" in source:
            offenders.append(str(path.relative_to(PACKAGE)))
    assert offenders == []
