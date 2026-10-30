"""Shared fixtures for the plan/18 scenario tests (stage 2 onwards).

These tests drive a running stack through its public API, the way a client would; they do not
import backend internals. They need: the compose stack up with the `test` profile (fake-llm,
ticket-desk) and `e2e.env`, and `seed.py` loaded (README.md here; K-SEN-0023/0024).
Without RUN_E2E_SCENARIOS=1 every test is skipped and reported NOT_RUN. With it, a missing
piece (seed, user, agent) fails loudly instead of being skipped: a scenario that cannot run is
NOT_RUN only by its own explicit marker, never by accident (plan/18 "Kurallar").

Values come from the environment so nothing secret is written here:
E2E_BACKEND_URL (default http://backend:8000), E2E_FAKE_LLM_URL (default http://fake-llm:9999),
E2E_PASSWORD (the seeded members' password, from the shell; never in a file).
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
# Modules that need no stack and always run (file checks only).
STACKLESS = ("test_18_env_overlay", "test_18_seed_unit")


def pytest_collection_modifyitems(config, items):
    if os.environ.get("RUN_E2E_SCENARIOS") == "1":
        return
    skip = pytest.mark.skip(reason="NOT_RUN: set RUN_E2E_SCENARIOS=1 (stack + seed.py)")
    for item in items:
        if item.module.__name__.endswith(STACKLESS):
            continue
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


def read_sse(lines, stop_after: int | None = None) -> list[dict]:
    """SSE lines → [{"id", "event", "data"}]; comment lines (keepalive) are skipped. With
    `stop_after`, returns once that many events were read (the caller drops the connection)."""
    events, ident, name, data = [], None, None, []
    for line in lines:
        if line.startswith(":"):
            continue
        if line.startswith("id:"):
            ident = line.split(":", 1)[1].strip()
        elif line.startswith("event:"):
            name = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            data.append(line.split(":", 1)[1].strip())
        elif line == "" and name:
            events.append({"id": ident, "event": name, "data": json.loads("\n".join(data) or "{}")})
            ident, name, data = None, None, []
            if stop_after is not None and len(events) >= stop_after:
                break
    return events


class Api:
    """A signed-in console user. The session cookie is Secure, so over the compose network's
    plain HTTP it is sent by hand; no Origin header (C6 refuses foreign origins only)."""

    def __init__(self, email: str, password: str):
        self.email = email
        self.http = httpx.Client(base_url=BACKEND_URL, timeout=httpx.Timeout(30, read=None))
        r = self.http.post("/api/v1/auth/login", json={"email": email, "password": password})
        if r.status_code != 200:
            pytest.fail(f"login {email}: {r.status_code} {r.text[:200]} (is seed.py loaded?)")
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
        pytest.fail(f"{self.email} is not a member of {key} (seed.py)")

    def start_run(
        self, project_id: str, agent_key: str, text: str, stop_after: int | None = None
    ) -> Run:
        """POST the run and read its SSE stream until it ends (done/error/approval/question),
        or, with `stop_after`, drop the connection after that many events (F12). The run id is
        the first `progress` event's `run_id` (06a OpenAPI)."""
        url = f"/api/v1/projects/{project_id}/agents/{agent_key}/runs"
        with self.http.stream("POST", url, json={"input": text}) as r:
            if r.status_code != 200:
                pytest.fail(f"run {agent_key}: {r.status_code} {r.read()[:200]!r}")
            events = read_sse(r.iter_lines(), stop_after)
        run_id = next(
            (
                e["data"]["run_id"]
                for e in events
                if e["event"] == "progress" and "run_id" in e["data"]
            ),
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

    def resume(
        self, project_id: str, run_id: str, decision: str, comment: str = "e2e"
    ) -> list[dict]:
        """POST /runs/{id}/resume with an approval decision; returns the SSE events."""
        url = f"/api/v1/projects/{project_id}/runs/{run_id}/resume"
        body = {"decision": decision, "comment": comment}
        with self.http.stream("POST", url, json=body) as r:
            if r.status_code != 200:
                pytest.fail(f"resume {run_id}: {r.status_code} {r.read()[:200]!r}")
            return read_sse(r.iter_lines())

    def stream(self, project_id: str, run_id: str, last_event_id: str | None) -> list[dict]:
        """GET /runs/{id}/stream, continuing after `last_event_id` (reconnect, 06a S8)."""
        headers = {"Last-Event-ID": last_event_id} if last_event_id else {}
        url = f"/api/v1/projects/{project_id}/runs/{run_id}/stream"
        with self.http.stream("GET", url, headers=headers) as r:
            assert r.status_code == 200, r.read()[:200]
            return read_sse(r.iter_lines())

    def tool_id(self, project_id: str, key: str) -> str:
        tools = self.get(f"/api/v1/projects/{project_id}/tools")
        assert tools.status_code == 200, tools.text
        found = [t["id"] for t in tools.json()["data"] if t["key"] == key]
        if not found:
            pytest.fail(f"tool {key} is not registered (seed.py)")
        return found[0]

    def kb_id(self, project_id: str, key: str) -> str:
        kbs = self.get(f"/api/v1/projects/{project_id}/knowledge-bases")
        assert kbs.status_code == 200, kbs.text
        found = [k["id"] for k in kbs.json()["data"] if k["key"] == key]
        if not found:
            pytest.fail(f"knowledge base {key} is missing (seed.py)")
        return found[0]


@pytest.fixture(scope="session")
def seed() -> dict:
    return load("projects/projects.json")


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
