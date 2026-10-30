"""Fixtures for the 13b negative e2e tests: the same stack, seed and helpers as the plan/18
scenarios (tests/e2e/scenarios/conftest.py), gated the same way: without RUN_E2E_SCENARIOS=1
every test here is skipped and reported NOT_RUN."""

import os
from pathlib import Path

import httpx
import pytest
from scenarios.conftest import FAKE_LLM_URL, Api, load

HERE = Path(__file__).resolve().parent
PROJECT = "hastane-a"


def pytest_collection_modifyitems(config, items):
    if os.environ.get("RUN_E2E_SCENARIOS") == "1":
        return
    skip = pytest.mark.skip(reason="NOT_RUN: set RUN_E2E_SCENARIOS=1 (stack + seed.py)")
    for item in items:
        if HERE in Path(item.fspath).resolve().parents:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def password() -> str:
    value = os.environ.get("E2E_PASSWORD")
    if not value:
        pytest.fail("E2E_PASSWORD is not set (the seeded members' password; README.md)")
    return value


@pytest.fixture(scope="session")
def login(password):
    cache: dict[str, Api] = {}

    def _login(project_key: str, role: str, access: str) -> Api:
        email = f"{project_key}-{role}-{access}@example.test"  # data/samples/projects
        if email not in cache:
            cache[email] = Api(email, password)
        return cache[email]

    return _login


@pytest.fixture(scope="session")
def fake_llm():
    class FakeLlm:
        http = httpx.Client(base_url=FAKE_LLM_URL, timeout=10)

        def reset(self) -> None:
            assert self.http.post("/_reset").status_code in (200, 204)

        def requests(self) -> list[dict]:
            r = self.http.get("/_requests")
            assert r.status_code == 200
            return r.json()

    return FakeLlm()


@pytest.fixture(scope="session")
def answered_run(login):
    """A completed run of the contract assistant in the target project (for feedback/resume)."""
    analyst = login(PROJECT, "analyst", "edit")
    pid = analyst.project_id(PROJECT)
    item = next(i for i in load("eval/sozlesme-33.json") if i["metadata"]["answerable"])
    run = analyst.settle(pid, analyst.start_run(pid, "sozlesme-asistani", item["input"]["message"]))
    assert run.detail["status"] == "completed", run.detail
    return pid, run
