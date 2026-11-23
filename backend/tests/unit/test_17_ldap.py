"""17-1: the LDAP driver against an ldap3 MOCK_SYNC directory (no network), and the settings
and preflight rules for directory sign-in."""

import asyncio
import importlib.util
from pathlib import Path

import pytest

from ffcore.core.config import Settings
from ffcore.core.ldap_auth import (
    InvalidCredentials,
    LdapDirectory,
    ProviderUnavailable,
    external_id_of,
)
from tests import ldap_fixture as fx
from tests.dummy import OBO_SECRET, SERVICE_TOKEN, SETTINGS_03A


def base_settings(**changes) -> Settings:
    return Settings(
        deploy_profile="llmaas",
        offline=False,
        service_token=SERVICE_TOKEN,
        obo_jwt_secret=OBO_SECRET,
        **SETTINGS_03A,
        **changes,
    )


@pytest.fixture
def directory():
    fake = fx.FakeDirectory()
    settings = fx.ldap_settings(base_settings())
    return fake, fake.directory(settings)


def run(coro):
    return asyncio.run(coro)


def test_17_ldap_authenticate_by_account_name_email_and_upn(directory):
    fake, ldap = directory
    for login in (fake.login("user-a"), fake.email("user-a"), fake.email("user-a").upper()):
        user = run(ldap.authenticate(login, fake.password("user-a")))
        assert user.provider == "ldap"
        assert user.external_id == fake.guid("user-a")  # canonical text from AD's bytes
        assert user.email == fake.email("user-a")
        assert user.full_name == "Directory User A"
        assert user.groups == {fake.group("chat").lower()}
        assert user.active


def test_17_ldap_wrong_password_unknown_and_empty_are_invalid_credentials(directory):
    fake, ldap = directory
    reasons = []
    for login, password in (
        (fake.login("user-a"), "wrong"),
        ("nobody", "whatever"),
        (fake.login("user-a"), ""),  # an empty password would be an anonymous bind
    ):
        with pytest.raises(InvalidCredentials) as caught:
            run(ldap.authenticate(login, password))
        reasons.append(caught.value.reason)
    assert reasons == ["bind_failed", "user_not_found", "empty_credentials"]


def test_17_ldap_filter_injection_is_escaped(directory):
    fake, ldap = directory
    with pytest.raises(InvalidCredentials) as caught:
        run(ldap.authenticate("*", fake.password("user-a")))
    assert caught.value.reason == "user_not_found"
    with pytest.raises(InvalidCredentials):
        run(ldap.authenticate(f"{fake.login('user-a')})(objectClass=*", fake.password("user-a")))


def test_17_ldap_disabled_account_reported_inactive(directory):
    fake, ldap = directory
    user = run(ldap.authenticate(fake.login("user-disabled"), fake.password("user-disabled")))
    assert not user.active


def test_17_ldap_unreachable_and_service_refused_are_unavailable(directory):
    fake, ldap = directory
    fake.unreachable = True
    with pytest.raises(ProviderUnavailable) as caught:
        run(ldap.authenticate(fake.login("user-a"), fake.password("user-a")))
    assert caught.value.reason == "directory_unreachable"
    fake.unreachable = False
    wrong = fake.directory(fx.ldap_settings(base_settings(), ldap_bind_password="not-the-pw"))
    with pytest.raises(ProviderUnavailable) as caught:
        run(wrong.authenticate(fake.login("user-a"), fake.password("user-a")))
    assert caught.value.reason == "service_bind_failed"


def test_17_ldap_host_goes_through_egress_policy():
    fake = fx.FakeDirectory()
    settings = fx.ldap_settings(base_settings(), allowed_internal_hosts=[], offline=True)
    with pytest.raises(ProviderUnavailable) as caught:
        run(fake.directory(settings).authenticate(fake.login("user-a"), fake.password("user-a")))
    assert caught.value.reason == "egress_offline"


def test_17_ldap_find_by_id_and_email(directory):
    fake, ldap = directory
    found = run(ldap.find(fake.guid("user-b")))
    assert found is not None and found.email == fake.email("user-b")
    assert len(found.groups) == 3
    assert run(ldap.find_by_email(fake.email("user-b"))).external_id == fake.guid("user-b")
    fake.remove("user-b")
    assert run(ldap.find(fake.guid("user-b"))) is None


def test_17_ldap_probe(directory):
    fake, ldap = directory
    result = run(ldap.probe())
    assert result.ok and result.code is None and result.elapsed_ms >= 0
    fake.unreachable = True
    result = run(ldap.probe())
    assert not result.ok and result.code == "directory_unreachable"


def test_17_external_id_formats():
    import uuid

    value = uuid.uuid4()
    assert external_id_of([value.bytes_le], "objectGUID") == str(value)
    assert external_id_of([b"{" + str(value).encode() + b"}"], "objectGUID") == str(value)
    assert external_id_of([b"0b7c-entry-uuid"], "entryUUID") == "0b7c-entry-uuid"
    assert external_id_of([], "objectGUID") is None


# --- settings ---


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"ldap_url": "ldap://dir.example.test"}, "ldap_plaintext_forbidden"),
        ({"ldap_url": "http://dir.example.test"}, "ldap_url_invalid"),
        ({"ldap_url": "ldaps://dir.example.test"}, "ldap_incomplete"),
        (
            {
                "ldap_url": "ldaps://dir.example.test",
                "ldap_bind_dn": "cn=x",
                "ldap_bind_password": "y",
                "ldap_user_base": "dc=x",
                "ldap_user_filter": "(mail=*)",
            },
            "ldap_filter_invalid",
        ),
        (
            {
                "ldap_url": "ldaps://dir.example.test",
                "ldap_bind_dn": "cn=x",
                "ldap_bind_password": "y",
                "ldap_user_base": "dc=x",
                "ldap_ca_file": "/nonexistent/ca.pem",
            },
            "ldap_ca_file_missing",
        ),
    ],
)
def test_17_settings_refuse_incoherent_ldap(changes, code):
    with pytest.raises(ValueError) as caught:
        base_settings(**changes)
    assert code in str(caught.value)
    assert "dummy-not-secret-bind-pw" not in str(caught.value)


def test_17_settings_plaintext_allowed_explicitly_and_defaults():
    settings = base_settings(
        ldap_url="ldap://dir.example.test",
        ldap_allow_plaintext=True,
        ldap_bind_dn="cn=x",
        ldap_bind_password="y",
        ldap_user_base="dc=x",
    )
    assert settings.ldap_enabled
    plain = base_settings()
    assert not plain.ldap_enabled
    assert plain.local_login == "all"
    assert not plain.auto_provision_from_channels
    assert plain.ldap_id_attr == "objectGUID"
    with pytest.raises(ValueError):
        base_settings(local_login="maybe")


def test_17_directory_requires_configuration():
    with pytest.raises(ValueError):
        LdapDirectory(base_settings())


# --- preflight ---

REPO = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location(
    "compose_preflight_17", REPO / "scripts" / "compose_preflight.py"
)
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)

PREFLIGHT_BASE = {
    "DEPLOY_PROFILE": "llmaas",
    "INFERENCE_BACKEND": "ollama",
    "COMPOSE_PROFILES": "",
    "COMPOSE_FILE": "",
    "APP_DB_USER": "ffcore_app",
    "APP_DB_PASSWORD": "dummy-not-secret",
}
LDAP_ENV = {
    "LDAP_URL": "ldaps://dir.example.test",
    "LDAP_BIND_DN": "cn=svc",
    "LDAP_BIND_PASSWORD": "dummy-not-secret-bind-pw",
    "LDAP_USER_BASE": "dc=example,dc=test",
}


def preflight_error(**changes):
    with pytest.raises(preflight.PreflightError) as caught:
        preflight.check({**PREFLIGHT_BASE, **changes})
    return caught.value.code


def test_17_preflight_local_only_and_ldaps():
    lines = preflight.check(PREFLIGHT_BASE)
    assert "identity: local accounts only (LOCAL_LOGIN=all)" in lines
    lines = preflight.check({**PREFLIGHT_BASE, **LDAP_ENV, "LOCAL_LOGIN": "superadmin_only"})
    assert "identity: ldap (ldaps), LOCAL_LOGIN=superadmin_only" in lines
    assert not any("dummy-not-secret-bind-pw" in line for line in lines)


def test_17_preflight_refuses_plaintext_incomplete_and_bad_policy():
    plain = {**LDAP_ENV, "LDAP_URL": "ldap://dir.example.test"}
    assert preflight_error(**plain) == "ldap_plaintext_forbidden"
    assert preflight_error(**{**LDAP_ENV, "LDAP_BIND_PASSWORD": ""}) == "ldap_incomplete"
    assert preflight_error(LOCAL_LOGIN="nobody") == "local_login_invalid"
    lines = preflight.check(
        {**PREFLIGHT_BASE, **LDAP_ENV, "LDAP_URL": "ldap://d", "LDAP_ALLOW_PLAINTEXT": "true"}
    )
    assert any(line.startswith("warning: LDAP_URL is plaintext") for line in lines)
