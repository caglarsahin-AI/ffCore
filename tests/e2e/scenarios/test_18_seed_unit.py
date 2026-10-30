"""seed.ensure_superadmin (review r1 MINOR-2): decided by the API's error code, not by CLI text.
Login first; only 401 `invalid_credentials` leads to `create-superadmin`; any other refusal, or
a failing CLI, stops the seed. Runs without a stack (fakes for login and the CLI)."""

import subprocess

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
