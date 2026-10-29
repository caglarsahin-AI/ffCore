"""05a (K-05a-0005): core/auth.unverified_on_behalf_of_claims is a routing read, never a trust
decision. It returns a plain dict (not OnBehalfOfClaims, which only verification produces),
reads a forged token the verifier refuses, and is used only by the relaying MCP services."""

from pathlib import Path

import jwt
import pytest

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


def test_05a_unverified_read_is_not_verified_claims():
    token = auth.sign_on_behalf_of(
        user_id="u", project_id="p", audience=["mcp-search", "ffcore-backend"], settings=SETTINGS
    )
    claims = auth.unverified_on_behalf_of_claims(token)
    assert type(claims) is dict and not isinstance(claims, auth.OnBehalfOfClaims)


def test_05a_forged_token_is_read_but_never_accepted():
    forged = jwt.encode(
        {"sub": "admin", "project_id": "p", "aud": "ffcore-backend", "iat": 0, "exp": 2**31},
        "dummy-not-secret-wrong-signing-key-0123456789",
        algorithm="HS256",
    )
    assert auth.unverified_on_behalf_of_claims(forged)["sub"] == "admin"
    with pytest.raises(auth.OnBehalfOfError) as err:
        auth.verify_on_behalf_of(forged, audience="ffcore-backend", settings=SETTINGS)
    assert err.value.status_code == 401


def test_05a_unverified_read_used_only_by_relaying_services():
    users = sorted(
        str(path.relative_to(PACKAGE))
        for path in PACKAGE.rglob("*.py")
        if "unverified_on_behalf_of_claims" in path.read_text(encoding="utf-8")
    )
    assert users == ["core/auth.py", "services/mcp_server_common.py"]


def test_05a_routing_read_never_grants():
    """Review r1 MAJOR-1: inside the relaying services the routing read appears in two places
    only. CallerCheck._refusal can only refuse (it returns a refusal or None, and a None hands
    the request on to the verifier in mcp-sql). Relay.__init__ builds mcp-search's backend URL;
    the backend verifies that same token. mcp-sql takes its project from verified claims."""
    import ast

    source = (PACKAGE / "services" / "mcp_server_common.py").read_text(encoding="utf-8")
    callers = set()
    for cls in ast.walk(ast.parse(source)):
        if not isinstance(cls, ast.ClassDef):
            continue
        for fn in cls.body:
            if isinstance(fn, ast.FunctionDef | ast.AsyncFunctionDef) and any(
                isinstance(n, ast.Call) and getattr(n.func, "id", "") == "token_claims"
                for n in ast.walk(fn)
            ):
                callers.add(f"{cls.name}.{fn.name}")
    assert callers == {"CallerCheck._refusal", "Relay.__init__"}
    sql_server = (PACKAGE / "services" / "mcp_sql_server.py").read_text(encoding="utf-8")
    assert "token_claims" not in sql_server and "unverified" not in sql_server
