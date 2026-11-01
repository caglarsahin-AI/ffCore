"""06b facade test helpers: API keys made through the console API (03c-1) and an OpenAI-style
client on /v1 that comes from a fixed address (impersonating keys need allowed_cidrs)."""

import json

import pytest
from fastapi.testclient import TestClient

from tests.integration.conftest import CONSOLE_ORIGIN

CLIENT_IP = "203.0.113.10"
NET = ["203.0.113.0/24"]


@pytest.fixture
def owner(make_project, make_user, client_factory):
    """A project and its admin's console client (the admin issues the keys)."""
    project = make_project()
    _, email = make_user(memberships={project: ("admin", "edit")})
    return project, client_factory(email)


def make_key(console, project, *, scopes, **body) -> dict:
    payload = {"name": "facade", "scopes": scopes} | body
    if "impersonate" in scopes:
        payload.setdefault("allowed_cidrs", NET)
    response = console.post(f"/api/v1/projects/{project}/api-keys", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


class Facade:
    """The external client: only the base URL and the API key are FFCore's."""

    def __init__(self, app, key: str):
        self._client = TestClient(app, base_url=CONSOLE_ORIGIN, client=(CLIENT_IP, 50000))
        self._client.__enter__()
        self.key = key

    def close(self):
        self._client.__exit__(None, None, None)

    def headers(self, extra=None):
        return {"Authorization": f"Bearer {self.key}", **(extra or {})}

    def chat(self, model, content="Merhaba", *, headers=None, **body):
        payload = {"model": model, "messages": [{"role": "user", "content": content}]} | body
        return self._client.post(
            "/v1/chat/completions", json=payload, headers=self.headers(headers)
        )

    def stream(self, model, content="Merhaba", *, headers=None, **body):
        """(status, chunks, raw lines) of a streamed completion; chunks are the parsed JSON."""
        payload = {"model": model, "messages": [{"role": "user", "content": content}]} | body
        payload["stream"] = True
        with self._client.stream(
            "POST", "/v1/chat/completions", json=payload, headers=self.headers(headers)
        ) as response:
            lines = [line for line in response.iter_lines() if line]
            if response.status_code != 200:
                return response.status_code, json.loads("".join(lines)), lines
        chunks = [json.loads(line[6:]) for line in lines if line.startswith("data: {")]
        return 200, chunks, lines

    def models(self):
        return self._client.get("/v1/models", headers=self.headers())


@pytest.fixture
def facade(app):
    made = []

    def make(key: dict | str) -> Facade:
        client = Facade(app, key["key"] if isinstance(key, dict) else key)
        made.append(client)
        return client

    yield make
    for client in made:
        client.close()


def project_key(pg, project_id) -> str:
    return pg.execute("SELECT key FROM projects WHERE id = %s", (project_id,)).fetchone()[0]


def denied_rows(pg, key_id) -> list[dict]:
    rows = pg.execute(
        "SELECT after FROM audit_events WHERE action = 'impersonation_denied' AND actor_id = %s"
        " ORDER BY ts",
        (key_id,),
    ).fetchall()
    return [r[0] or {} for r in rows]
