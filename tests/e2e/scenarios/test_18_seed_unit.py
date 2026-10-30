"""seed.ensure_superadmin (review r1 MINOR-2): decided by the API's error code, not by CLI text.
Login first; only 401 `invalid_credentials` leads to `create-superadmin`; any other refusal, or
a failing CLI, stops the seed. Runs without a stack (fakes for login and the CLI)."""

import json
import subprocess

import httpx
import pytest

from . import seed


class FakeLogin:
    """Stands in for seed.Client: refuses with the queued errors, then signs in."""

    def __init__(self, *refusals):
        self.refusals = list(refusals)
        self.calls = 0

    def __call__(self, email, password):
        self.calls += 1
        if self.refusals:
            raise self.refusals.pop(0)
        return f"client:{email}"


def fake_cli(returncode=0, stderr=""):
    calls = []

    def run(*args, stdin=None):
        calls.append(args)
        return subprocess.CompletedProcess(args, returncode, "", stderr)

    run.calls = calls
    return run


def refused(status, code):
    return seed.LoginRefused("e2e-admin@example.test", status, code)


def test_18_seed_1_existing_admin_signs_in_without_cli():
    login, run = FakeLogin(), fake_cli()
    assert seed.ensure_superadmin("a@example.test", "pw", login=login, run=run) == (
        "client:a@example.test"
    )
    assert run.calls == [] and login.calls == 1


def test_18_seed_2_unknown_admin_is_created_then_signs_in():
    login, run = FakeLogin(refused(401, "invalid_credentials")), fake_cli()
    seed.ensure_superadmin("a@example.test", "pw", login=login, run=run)
    assert run.calls[0][0] == "create-superadmin" and login.calls == 2


@pytest.mark.parametrize(("status", "code"), [(403, "account_disabled"), (500, "api_error")])
def test_18_seed_3_other_login_refusals_stop_the_seed(status, code):
    login, run = FakeLogin(refused(status, code)), fake_cli()
    with pytest.raises(seed.LoginRefused):
        seed.ensure_superadmin("a@example.test", "pw", login=login, run=run)
    assert run.calls == []


def test_18_seed_4_failing_cli_stops_the_seed_whatever_it_says():
    login = FakeLogin(refused(401, "invalid_credentials"))
    run = fake_cli(1, "a user with this email already exists")  # wrong password, existing user
    with pytest.raises(seed.SeedError, match="create-superadmin"):
        seed.ensure_superadmin("a@example.test", "pw", login=login, run=run)


class FakeApi:
    """A tiny in-memory backend for Client (review r2 MAJOR-1: Client.call/create/find had
    slipped into ensure_superadmin's body; main() failed on the first admin.call)."""

    def __init__(self):
        self.projects = [{"id": "p-1", "key": "hastane-a", "name": "A"}]
        self.seen = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.seen.append((request.method, request.url.path))
        path = request.url.path.removeprefix("/api/v1")
        if path == "/auth/login":
            return httpx.Response(200, json={}, headers={"set-cookie": "ffcore_session=s1"})
        assert request.headers.get("cookie") == "ffcore_session=s1"
        if (request.method, path) == ("GET", "/projects"):
            return httpx.Response(200, json={"data": self.projects})
        if (request.method, path) == ("POST", "/projects"):
            key = json.loads(request.content)["key"]
            if any(p["key"] == key for p in self.projects):
                return httpx.Response(409, json={"error": {"code": "project_key_taken"}})
            self.projects.append({"id": f"p-{len(self.projects) + 1}", "key": key, "name": key})
            return httpx.Response(201, json=self.projects[-1])
        return httpx.Response(500, json={"error": {"code": "unexpected"}})


@pytest.fixture
def fake_api(monkeypatch):
    api = FakeApi()
    real = httpx.Client

    def client(**kw):
        return real(transport=httpx.MockTransport(api), **kw)

    monkeypatch.setattr(seed.httpx, "Client", client)
    return api


def test_18_seed_5_client_methods_against_a_fake_api(fake_api):
    admin = seed.Client("a@example.test", "pw")
    assert admin.call("GET", "/projects").json()["data"][0]["key"] == "hastane-a"
    assert admin.find("/projects", "hastane-a")["id"] == "p-1"
    projects = {"projects": [{"key": "hastane-a", "name": "A"}, {"key": "klinik-b", "name": "B"}]}
    ids = seed.seed_projects(admin, projects)  # what main() calls first after sign-in
    assert ids == {"hastane-a": "p-1", "klinik-b": "p-2"}  # 409 looked up, new one created
    with pytest.raises(seed.SeedError, match="500"):
        admin.call("GET", "/nowhere")
