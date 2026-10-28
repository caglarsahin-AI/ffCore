"""03a acceptance 4 (login, session, me), 5 (C6 cross-origin) and 18 (first superadmin CLI)."""

import io

import pytest

from ffcore import cli
from ffcore.core.session import COOKIE_NAME
from tests.integration.conftest import CONSOLE_ORIGIN, PASSWORD, audit_rows

LOGIN = "/api/v1/auth/login"
LOGOUT = "/api/v1/auth/logout"
ME = "/api/v1/auth/me"
PASSWORD_URL = "/api/v1/auth/password"


def test_03a_4_login_sets_strict_cookie(make_user, client_factory):
    _, email = make_user()
    response = client_factory().post(LOGIN, json={"email": email, "password": PASSWORD})
    assert response.status_code == 200
    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{COOKIE_NAME}=")
    for attribute in ("HttpOnly", "Secure", "SameSite=strict", "Path=/"):
        assert attribute.lower() in cookie.lower()


def test_03a_4_wrong_password_401_uniform(make_user, client_factory, pg):
    _, email = make_user()
    client = client_factory()
    wrong = client.post(LOGIN, json={"email": email, "password": "not-the-password-000"})
    unknown = client.post(LOGIN, json={"email": "nobody@example.test", "password": PASSWORD})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()
    assert wrong.json()["error"]["code"] == "invalid_credentials"
    assert COOKIE_NAME not in client.cookies
    denied = audit_rows(pg, "auth.login", "denied")
    assert len(denied) == 2
    assert all(email not in str(row) for row in denied)  # typed email is not stored


def test_03a_4_me_returns_role_and_access(make_user, make_project, client_factory):
    project = make_project()
    _, member = make_user(memberships={project: ("analyst", "read")})
    _, root = make_user(superadmin="read")

    body = client_factory(member).get(ME).json()
    assert (body["role"], body["access"]) == ("analyst", "read")
    assert body["memberships"][0]["project_id"] == str(project)
    assert body["user"]["is_superadmin"] is False

    body = client_factory(root).get(ME).json()
    assert (body["role"], body["access"], body["user"]["is_superadmin"]) == ("admin", "read", True)

    _, lonely = make_user()
    body = client_factory(lonely).get(ME).json()
    assert (body["role"], body["access"], body["memberships"]) == (None, None, [])


def test_03a_4_logout_revokes_token(make_user, client_factory, pg):
    user_id, email = make_user()
    client = client_factory(email)
    stolen = client.cookies[COOKIE_NAME]
    assert client.post(LOGOUT, headers={"Origin": CONSOLE_ORIGIN}).status_code == 204
    assert client.get(ME).status_code == 401
    replay = client_factory()
    replay.cookies.set(COOKIE_NAME, stolen)
    assert replay.get(ME).status_code == 401
    assert audit_rows(pg, "auth.logout", "success")[0][0] == str(user_id)


def test_03a_4_password_change_revokes_other_sessions(make_user, client_factory):
    _, email = make_user()
    first, second = client_factory(email), client_factory(email)
    response = first.post(
        PASSWORD_URL,
        json={"current_password": PASSWORD, "new_password": "dummy-not-secret-new-pass-01"},
    )
    assert response.status_code == 204
    assert first.get(ME).status_code == 200  # fresh cookie for the session that changed it
    assert second.get(ME).status_code == 401
    old = client_factory().post(LOGIN, json={"email": email, "password": PASSWORD})
    assert old.status_code == 401


def test_03a_4_inactive_user_401(make_user, client_factory, pg):
    user_id, email = make_user()
    client = client_factory(email)
    pg.execute("UPDATE users SET is_active = false WHERE id = %s", (user_id,))
    assert client.get(ME).status_code == 401
    retry = client_factory().post(LOGIN, json={"email": email, "password": PASSWORD})
    assert retry.status_code == 401


def test_03a_4_password_hash_is_argon2(make_user, client_factory, pg):
    client = client_factory()
    assert client.post(LOGIN, json={"email": "x@example.test", "password": "y"}).status_code == 401
    user_id, _ = make_user()
    stored = pg.execute("SELECT password_hash FROM users WHERE id = %s", (user_id,)).fetchone()[0]
    assert stored.startswith("$argon2id$")
    assert PASSWORD not in stored


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "https://evil.example"},
        {"Sec-Fetch-Site": "cross-site"},
        {"Sec-Fetch-Site": "same-site"},
    ],
)
def test_03a_5_cross_origin_cookie_mutation_403(make_user, client_factory, headers):
    _, email = make_user()
    client = client_factory(email)
    response = client.post(LOGOUT, headers=headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "cross_origin_forbidden"
    assert client.get(ME).status_code == 200  # nothing happened


def test_03a_5_same_origin_allowed(make_user, client_factory):
    _, email = make_user()
    client = client_factory(email)
    headers = {"Origin": CONSOLE_ORIGIN, "Sec-Fetch-Site": "same-origin"}
    assert client.post(LOGOUT, headers=headers).status_code == 204


def test_03a_5_no_cors_credentials(app, client_factory):
    assert not any("CORS" in type(m.cls).__name__ + m.cls.__name__ for m in app.user_middleware)
    response = client_factory().options(
        LOGIN, headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"}
    )
    assert "access-control-allow-credentials" not in response.headers
    assert "access-control-allow-origin" not in response.headers


def _run_cli(monkeypatch, password, *extra):
    monkeypatch.setattr("sys.stdin", io.StringIO(password + "\n"))
    return cli.main(["create-superadmin", "--email", "Root@Example.test", "--full-name", "Root",
                     "--password-stdin", *extra])  # fmt: skip


def test_03a_18_create_superadmin_cli(app, monkeypatch, pg, client_factory, capsys):
    assert _run_cli(monkeypatch, PASSWORD) == 0
    row = pg.execute(
        "SELECT is_superadmin, superadmin_access, password_hash FROM users"
        " WHERE lower(email) = 'root@example.test'"
    ).fetchone()
    assert row[0] is True and row[1] == "edit" and row[2].startswith("$argon2id$")
    assert audit_rows(pg, "user.create_superadmin", "success")[0][0] == "cli"
    assert client_factory("root@example.test").get(ME).json()["role"] == "admin"

    assert _run_cli(monkeypatch, PASSWORD) == 1  # same email again: explicit error
    assert "already exists" in capsys.readouterr().err


def test_03a_18_cli_rejects_short_password_and_argv_password(app, monkeypatch, pg):
    assert _run_cli(monkeypatch, "short") == 1
    with pytest.raises(SystemExit):
        cli.main(
            ["create-superadmin", "--email", "a@b.test", "--full-name", "A", "--password", "x"]
        )
    assert pg.execute("SELECT count(*) FROM users WHERE email = 'a@b.test'").fetchone()[0] == 0
