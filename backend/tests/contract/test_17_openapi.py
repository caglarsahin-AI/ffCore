"""17: the committed OpenAPI draft (`backend/openapi/17.yaml`) equals what the app serves; the
03a additions are additive and no identity schema carries a secret."""

from pathlib import Path

import yaml

from ffcore.api.openapi_export import render

DRAFT = Path(__file__).resolve().parents[2] / "openapi" / "17.yaml"
REGENERATE = "python -m ffcore.api.openapi_export 17 > openapi/17.yaml"
M = "/api/v1/projects/{project_id}/identity-mappings"

EXPECTED = {
    "/api/v1/auth/providers": {"get"},
    "/api/v1/identity-mappings": {"get"},
    M: {"get", "post"},
    M + "/{mapping_id}": {"delete"},
    "/api/v1/identity-providers": {"get"},
    "/api/v1/identity-providers/ldap/test": {"post"},
    "/api/v1/users/import": {"post"},
}


def test_17_openapi_draft_matches_app():
    assert DRAFT.exists(), f"missing {DRAFT}; regenerate with: {REGENERATE}"
    assert DRAFT.read_text(encoding="utf-8") == render("17"), f"draft drifted; run: {REGENERATE}"


def test_17_openapi_paths():
    spec = yaml.safe_load(render("17"))
    assert {p: set(m) for p, m in spec["paths"].items()} == EXPECTED


def test_17_03a_draft_gains_identity_fields_only_additively():
    schemas = yaml.safe_load(render("03a"))["components"]["schemas"]
    for name in ("CurrentUser", "UserOut"):
        props = schemas[name]["properties"]
        assert "auth_source" in props and "must_change_password" in props
        assert "auth_source" not in schemas[name].get("required", [])
    assert "last_login_at" in schemas["UserOut"]["properties"]
    # r2: `local` takes a link back before the first directory sign-in
    assert set(schemas["UserUpdate"]["properties"]["auth_source"]["enum"]) == {
        "ldap",
        "oidc",
        "local",
    }
    assert "temporary_password" in schemas["UserOut"]["properties"]
    assert "/api/v1/auth/providers" not in yaml.safe_load(render("03a"))["paths"]


def test_17_no_secret_fields_in_identity_schemas():
    schemas = yaml.safe_load(render("17"))["components"]["schemas"]
    for name in ("IdentityProvidersOut", "ProviderStatus", "ProviderTestOut", "SignInProviders"):
        for prop in schemas[name]["properties"]:
            assert not any(word in prop for word in ("password", "secret", "bind_dn", "url")), (
                name,
                prop,
            )
