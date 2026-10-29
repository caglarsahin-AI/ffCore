"""06a run API fixtures shared by the run and feedback tests: the app with Redis settings, the
test harness, an inline queue that runs each attempt in the request, SSE parsing."""

import json
import os
import uuid

import pytest
from pydantic import SecretStr

from tests.integration.runtime_support import Harness, Ports, setup

__all__ = [
    "InlineQueue",
    "analyst",
    "get_stream",
    "harness",
    "parse_sse",
    "post_run",
    "publish",
    "settings",
    "use_queue",
]


class InlineQueue:
    """Runs each attempt right away, inside the request, with the test's ports."""

    def __init__(self, harness: Harness, ports: Ports, run_now: bool = True) -> None:
        self.harness, self.ports, self.run_now = harness, ports, run_now
        self.jobs: list[tuple[str, dict | None]] = []

    async def enqueue(self, run_id, resume=None):
        self.jobs.append((run_id, resume))
        if self.run_now:
            await self.harness.attempt(run_id, self.ports, resume)
        return f"job-{len(self.jobs)}"


@pytest.fixture
def settings(app, app_settings, database_url):
    from ffcore.core.config import get_settings

    s = app_settings.model_copy(
        update={
            "database_url": SecretStr(database_url),
            "redis_url": SecretStr(os.environ["REDIS_URL"]),
            "sse_keepalive_s": 0.2,
        }
    )
    app.dependency_overrides[get_settings] = lambda: s
    return s


@pytest.fixture
def harness(database_url, settings):
    setup(database_url)
    return Harness(database_url, settings)


@pytest.fixture
def use_queue(app):
    from ffcore.api.runs import queue_dependency

    def install(queue):
        app.dependency_overrides[queue_dependency] = lambda: queue
        return queue

    return install


def publish(pg, project_id, doc, key="asistan"):
    agent_id, version_id = uuid.uuid4(), uuid.uuid4()
    pg.execute(
        "INSERT INTO agents (id, project_id, key, name, created_by) VALUES (%s, %s, %s, 'A', 't')",
        (agent_id, project_id, key),
    )
    pg.execute(
        "INSERT INTO agent_versions (id, agent_id, version, definition, created_by, published_at)"
        " VALUES (%s, %s, 1, %s, 't', now())",
        (version_id, agent_id, json.dumps(doc)),
    )
    pg.execute(
        "UPDATE agents SET status = 'published', current_version_id = %s WHERE id = %s",
        (version_id, agent_id),
    )
    return agent_id


def parse_sse(lines) -> list[tuple[str, str, dict]]:
    out, current = [], {}
    for line in lines:
        if line.startswith("id: "):
            current["id"] = line[4:]
        elif line.startswith("event: "):
            current["event"] = line[7:]
        elif line.startswith("data: "):
            out.append((current["id"], current["event"], json.loads(line[6:])))
            current = {}
    return out


def post_run(client, project_id, key="asistan", **body):
    with client.stream(
        "POST",
        f"/api/v1/projects/{project_id}/agents/{key}/runs",
        json={"input": "Fesih süresi nedir?", **body},
    ) as response:
        assert response.status_code == 200, response.read()
        assert response.headers["content-type"].startswith("text/event-stream")
        return parse_sse(response.iter_lines())


def get_stream(client, project_id, run_id, last=None):
    headers = {"Last-Event-ID": last} if last else {}
    with client.stream(
        "GET", f"/api/v1/projects/{project_id}/runs/{run_id}/stream", headers=headers
    ) as response:
        assert response.status_code == 200
        return parse_sse(response.iter_lines())


@pytest.fixture
def analyst(make_project, make_user, client_factory):
    project_id = make_project()
    _, email = make_user(memberships={project_id: ("analyst", "edit")})
    return project_id, client_factory(email)
