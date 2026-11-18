"""05b test helpers: published MCP servers made through the console API, raw JSON-RPC calls to
`/mcp/{key}/` and the fake upstream (tests/upstream_fixture.py)."""

import uuid
from pathlib import Path

import pytest

from ffcore.core.auth import sign_on_behalf_of
from tests.dummy import SERVICE_TOKEN

API = "/api/v1"
SUPERSET = Path(__file__).resolve().parents[3] / "data" / "samples" / "openapi" / "superset.yaml"
SIX = [
    "addChartToDashboard",
    "createChart",
    "getChartData",
    "getDatasetMetrics",
    "listCharts",
    "searchDashboards",
]
UPSTREAM_TOKEN = "dummy-not-secret-superset-token-0123456789"
ACCEPT = {"Accept": "application/json, text/event-stream"}


@pytest.fixture
def settings(app, app_settings):
    """Loopback is internal for these tests only (the fixtures listen on 127.0.0.1)."""
    from ffcore.core.config import get_settings

    value = app_settings.model_copy(
        update={
            "allowed_internal_hosts": [*app_settings.allowed_internal_hosts, "127.0.0.0/8"],
            "egress_allowlist": ["superset.example.com"],
        }
    )
    app.dependency_overrides[get_settings] = lambda: value
    return value


@pytest.fixture(scope="module")
def upstream():
    from tests import upstream_fixture

    fake, uv = upstream_fixture.start()
    yield fake
    uv.should_exit = True


@pytest.fixture
def world(make_user, make_project, client_factory, settings):
    project = make_project()
    admin_id, admin = make_user(memberships={project: ("admin", "edit")})
    _, analyst = make_user(memberships={project: ("analyst", "edit")})
    _, developer = make_user(memberships={project: ("developer", "edit")})
    return {
        "project": str(project),
        "admin_id": str(admin_id),
        "admin": client_factory(admin),
        "analyst": client_factory(analyst),
        "developer": client_factory(developer),
        "anonymous": client_factory(),
    }


def servers_url(world, server_id="", suffix=""):
    base = f"{API}/projects/{world['project']}/mcp-servers"
    return f"{base}/{server_id}{suffix}" if server_id else base


def openapi_body(upstream_url, key=None, **extra):
    return {
        "key": key or f"ss-{uuid.uuid4().hex[:8]}",
        "name": "Superset",
        "source_kind": "openapi",
        "spec": SUPERSET.read_text(encoding="utf-8"),
        "upstream_base_url": upstream_url,
        "upstream_auth": {"type": "bearer", "token": UPSTREAM_TOKEN},
        **extra,
    }


def create(world, body):
    response = world["admin"].post(servers_url(world), json=body)
    assert response.status_code == 201, response.text
    return response.json()


def publish(world, upstream_url, *, key=None, exposed=SIX, **extra):
    """An active published Superset server with `exposed` operations."""
    key = key or f"ss-{uuid.uuid4().hex[:8]}"
    server = create(world, openapi_body(upstream_url, key=key, **extra))
    response = world["admin"].patch(
        servers_url(world, server["id"]),
        json={"exposed_operations": list(exposed), "status": "active"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def rpc(client, key, method, params=None, headers=None):
    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
    return client.post(f"/mcp/{key}/", json=body, headers={**ACCEPT, **(headers or {})})


def bearer(key: str) -> dict:
    return {"Authorization": f"Bearer {key}"}


def runtime_headers(settings, user_id, project_id, tool_key) -> dict:
    """What the runtime sends for a forward_user tool (05a mcp_client)."""
    token = sign_on_behalf_of(
        user_id=user_id,
        project_id=project_id,
        audience=[tool_key, settings.obo_audience],
        settings=settings,
        ttl_s=60,
    )
    return {"Authorization": f"Bearer {SERVICE_TOKEN}", "X-On-Behalf-Of": token}


def tool_names(response) -> list[str]:
    assert response.status_code == 200, response.text
    return sorted(t["name"] for t in response.json()["result"]["tools"])


def call_result(response) -> dict:
    assert response.status_code == 200, response.text
    return response.json()["result"]


def calls(pg, server_id):
    return pg.execute(
        "SELECT operation, status, error_code, actor_type, guardrail_action"
        " FROM mcp_server_calls WHERE server_id = %s ORDER BY ts",
        (server_id,),
    ).fetchall()
