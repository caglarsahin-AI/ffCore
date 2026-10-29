"""Shared fixtures for the plan/18 scenario tests (stage 2 onwards).

These tests drive a running stack through its public API, the way a client would; they do not
import backend internals. They need: the compose stack up with the `test` profile (fake-llm),
06a merged, and 13b's seed loaded (projects, users and agents from data/samples/projects/).
Without RUN_E2E_SCENARIOS=1 every test is skipped and reported NOT_RUN. With it, a missing
piece (seed, user, agent) fails loudly instead of being skipped: a scenario that cannot run is
NOT_RUN only by its own explicit marker, never by accident (plan/18 "Kurallar").

Values come from the environment so nothing secret is written here:
E2E_BACKEND_URL (default http://backend:8000), E2E_FAKE_LLM_URL (default http://fake-llm:9999),
E2E_PASSWORD (the seeded users' password; 13b's seed sets it from .env.test).
"""

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import pytest

REPO = Path(__file__).resolve().parents[3]
SAMPLES = REPO / "data" / "samples"
BACKEND_URL = os.environ.get("E2E_BACKEND_URL", "http://backend:8000")
FAKE_LLM_URL = os.environ.get("E2E_FAKE_LLM_URL", "http://fake-llm:9999")
TERMINAL = {"completed", "failed", "cancelled", "abandoned"}
WAITING = {"waiting_approval", "waiting_user"}
RUN_TIMEOUT_S = float(os.environ.get("E2E_RUN_TIMEOUT_S", "900"))  # airgap cpu run limit (C2)


def pytest_collection_modifyitems(config, items):
    if os.environ.get("RUN_E2E_SCENARIOS") == "1":
        return
    skip = pytest.mark.skip(reason="NOT_RUN: set RUN_E2E_SCENARIOS=1 (stack + 06a + 13b seed)")
    for item in items:
        item.add_marker(skip)


def load(rel: str):
    path = SAMPLES / rel
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass
class Run:
    id: str
    events: list[dict] = field(default_factory=list)  # SSE events: {"event", "data"}
    detail: dict = field(default_factory=dict)  # GET /runs/{id} once settled

    def names(self) -> list[str]:
        return [e["event"] for e in self.events]


class Api:
    """A signed-in console user. The session cookie is Secure, so over the compose network's
    plain HTTP it is sent by hand; no Origin header (C6 refuses foreign origins only)."""

    def __init__(self, email: str, password: str):
        self.email = email
        self.http = httpx.Client(base_url=BACKEND_URL, timeout=httpx.Timeout(30, read=None))
        r = self.http.post("/api/v1/auth/login", json={"email": email, "password": password})
        if r.status_code != 200:
            pytest.fail(f"login {email}: {r.status_code} {r.text[:200]} (is 13b's seed loaded?)")
        cookie = r.cookies.get("ffcore_session")
        if not cookie:
            pytest.fail(f"login {email}: no ffcore_session cookie")
        self.http.headers["cookie"] = f"ffcore_session={cookie}"
        self.me = r.json()

    def get(self, path: str, **kw) -> httpx.Response:
        return self.http.get(path, **kw)

    def post(self, path: str, **kw) -> httpx.Response:
        return self.http.post(path, **kw)

    def project_id(self, key: str) -> str:
        for m in self.me.get("memberships", []):
            if m.get("project_key") == key:
                return m["project_id"]
        pytest.fail(f"{self.email} is not a member of {key} (13b seed)")

    def start_run(self, project_id: str, agent_key: str, text: str) -> Run:
        """POST the run and read its SSE stream until it ends (done/error/approval/question).
        The run id is the first `progress` event's `run_id` (06a OpenAPI)."""
        url = f"/api/v1/projects/{project_id}/agents/{agent_key}/runs"
        events, name, data = [], None, []
        with self.http.stream("POST", url, json={"input": text}) as r:
            if r.status_code != 200:
                pytest.fail(f"run {agent_key}: {r.status_code} {r.read()[:200]!r}")
            for line in r.iter_lines():
                if line.startswith("event:"):
                    name = line.split(":", 1)[1].strip()
                elif line.startswith("data:"):
                    data.append(line.split(":", 1)[1].strip())
                elif line == "" and name:
                    events.append({"event": name, "data": json.loads("\n".join(data) or "{}")})
                    name, data = None, []
        run_id = next(
            (e["data"]["run_id"] for e in events if e["event"] == "progress" and "run_id" in e["data"]),
            None,
        )
        if run_id is None:
            pytest.fail(f"run {agent_key}: no run_id in the stream: {events[:3]}")
        return Run(run_id, events)

    def settle(self, project_id: str, run: Run) -> Run:
        """Poll the run until it is terminal or waiting on a human; the stream may end first."""
        deadline = time.monotonic() + RUN_TIMEOUT_S
        while True:
            r = self.get(f"/api/v1/projects/{project_id}/runs/{run.id}")
            assert r.status_code == 200, r.text
            run.detail = r.json()
            if run.detail["status"] in TERMINAL | WAITING:
                return run
            if time.monotonic() > deadline:
                pytest.fail(f"run {run.id} still {run.detail['status']} after {RUN_TIMEOUT_S} s")
            time.sleep(2)

    def run_events(self, project_id: str, run_id: str) -> list[dict]:
        r = self.get(f"/api/v1/projects/{project_id}/runs/{run_id}/events")
        assert r.status_code == 200, r.text
        return r.json()["items"]


@pytest.fixture(scope="session")
def seed() -> dict:
    return load("projects/projects.json")


@pytest.fixture(scope="session")
def password() -> str:
    value = os.environ.get("E2E_PASSWORD")
    if not value:
        pytest.fail("E2E_PASSWORD is not set (the seeded users' password, from .env.test)")
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
    """01's fake provider records every request body LiteLLM sends it (S1 A, K-SEN-0002)."""

    class FakeLlm:
        http = httpx.Client(base_url=FAKE_LLM_URL, timeout=10)

        def reset(self) -> None:
            assert self.http.post("/_reset").status_code in (200, 204)

        def requests(self) -> list[dict]:
            r = self.http.get("/_requests")
            assert r.status_code == 200
            return r.json()

    return FakeLlm()
