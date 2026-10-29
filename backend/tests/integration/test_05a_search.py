"""05a slice 4: mcp-search end to end, no stubs in the chain.

mcp_client -> mcp-search (ffcore.services.mcp_search_server, 127.0.0.1) -> the real backend
app served over HTTP -> 04a search with its ACL. Acceptance 4 (ACL), 7 (forward_user: two
users at once, expired token 401, replay to another tool 403) and the C7 signature.
"""

import asyncio
import socket
import threading
import time
from datetime import UTC, datetime, timedelta

import httpx2
import pytest
import uvicorn

from ffcore.core.auth import sign_on_behalf_of
from ffcore.services import mcp_client, mcp_search_server
from ffcore.services.mcp_client import Caller, ToolCallError, ToolTarget
from tests.dummy import SERVICE_TOKEN
from tests.integration.test_04a_api import (  # noqa: F401 - fixtures
    PROSE,
    create_kb,
    process_all,
    queue,
    upload,
)

TOOL_KEY = "mcp-search"


def _serve(app) -> tuple[str, uvicorn.Server]:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    deadline = time.monotonic() + 10
    while not server.started:
        assert time.monotonic() < deadline, "server did not start"
        time.sleep(0.05)
    return f"127.0.0.1:{port}", server


@pytest.fixture
def settings(app, app_settings, tmp_path):
    from ffcore.core.config import get_settings

    value = app_settings.model_copy(
        update={
            "fake_embed": True,
            "knowledge_storage_dir": str(tmp_path / "storage"),
            "allowed_internal_hosts": [*app_settings.allowed_internal_hosts, "127.0.0.0/8"],
        }
    )
    app.dependency_overrides[get_settings] = lambda: value
    return value


@pytest.fixture
def chain(app, settings):
    backend_host, backend = _serve(app)
    search_settings = settings.model_copy(update={"internal_api_url": f"http://{backend_host}"})
    search_host, search = _serve(
        mcp_search_server.build_app(
            search_settings, tool_key=TOOL_KEY, allowed_hosts=["127.0.0.1:*"]
        )
    )
    yield f"http://{search_host}/mcp"
    search.should_exit = backend.should_exit = True


@pytest.fixture
def world(make_user, make_project, client_factory, settings, queue):  # noqa: F811
    project = make_project()
    admin_id, admin = make_user(memberships={project: ("admin", "edit")})
    analyst_id, analyst = make_user(memberships={project: ("analyst", "edit")})
    return {
        "project": str(project),
        "admin": client_factory(admin),
        "admin_id": str(admin_id),
        "analyst_id": str(analyst_id),
    }


@pytest.fixture
def kb(world, settings, queue):  # noqa: F811
    kb = create_kb(world, key="contracts")
    upload(
        world, world["admin"], kb["id"], "secret.md", "# Gizli\n\n" + PROSE * 8, acl_roles="admin"
    )
    upload(world, world["admin"], kb["id"], "open.md", "# Açık\n\n" + PROSE * 8, acl_open="true")
    process_all(settings, queue)
    return kb


def _target(url):
    return ToolTarget(key=TOOL_KEY, endpoint_url=url, auth_type="forward_user", auth={})


def _search(url, settings, user, project, kb_key="contracts"):
    return mcp_client.call(
        _target(url),
        "search_documents",
        {"query": "fesih bildirim süresi", "kb_key": kb_key},
        settings,
        caller=Caller(user, project),
    )


def _names(text):
    return {
        line.split(". ", 1)[1].split(" (p.")[0] for line in text.splitlines() if ". " in line[:4]
    }


def test_05a_c7_search_documents_signature(chain, settings, world):
    actions = asyncio.run(
        mcp_client.discover(
            _target(chain), settings, caller=Caller(world["admin_id"], world["project"])
        )
    )
    assert [a.name for a in actions] == ["search_documents"]
    schema = actions[0].input_schema
    assert set(schema["required"]) == {"query", "kb_key"}
    assert schema["properties"]["top_k"]["default"] == 5


def test_05a_4_search_documents_applies_acl(chain, settings, world, kb):
    analyst = asyncio.run(_search(chain, settings, world["analyst_id"], world["project"]))
    admin = asyncio.run(_search(chain, settings, world["admin_id"], world["project"]))
    assert not analyst.is_error and not admin.is_error, (analyst.text, admin.text)
    assert _names(analyst.text) == {"open.md"}
    assert _names(admin.text) == {"secret.md", "open.md"}
    assert analyst.text.startswith("1. ")


def test_05a_7_forward_user_concurrent_acl_isolated(chain, settings, world, kb):
    async def rounds():
        calls = []
        for _ in range(3):
            calls += [
                _search(chain, settings, world["analyst_id"], world["project"]),
                _search(chain, settings, world["admin_id"], world["project"]),
            ]
        return await asyncio.gather(*calls)

    results = asyncio.run(rounds())
    for i, result in enumerate(results):
        expected = {"open.md"} if i % 2 == 0 else {"secret.md", "open.md"}
        assert _names(result.text) == expected, (i, result.text)


def test_05a_unknown_kb_key_is_a_coded_tool_error(chain, settings, world, kb):
    result = asyncio.run(_search(chain, settings, world["admin_id"], world["project"], "nope"))
    assert result.is_error and "kb_not_found" in result.text


def _post(url, headers):
    body = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
    accept = {"accept": "application/json, text/event-stream", "content-type": "application/json"}
    return httpx2.post(url, json=body, headers={**accept, **headers})


def _token(settings, world, audience, now=None):
    return sign_on_behalf_of(
        user_id=world["analyst_id"],
        project_id=world["project"],
        audience=audience,
        settings=settings,
        now=now,
        ttl_s=60,
    )


def test_05a_7_expired_token_401(chain, settings, world):
    old = datetime.now(UTC) - timedelta(minutes=10)
    token = _token(settings, world, [TOOL_KEY, settings.obo_audience], now=old)
    response = _post(chain, {"Authorization": f"Bearer {SERVICE_TOKEN}", "X-On-Behalf-Of": token})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "token_expired"


def test_05a_7_replay_to_another_tool_403(chain, settings, world):
    token = _token(settings, world, ["mcp-sql", settings.obo_audience])
    response = _post(chain, {"Authorization": f"Bearer {SERVICE_TOKEN}", "X-On-Behalf-Of": token})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "audience_mismatch"


def test_05a_7_service_bearer_required(chain, settings, world):
    token = _token(settings, world, [TOOL_KEY, settings.obo_audience])
    no_bearer = _post(chain, {"X-On-Behalf-Of": token})
    no_token = _post(chain, {"Authorization": f"Bearer {SERVICE_TOKEN}"})
    assert no_bearer.status_code == 401 and no_token.status_code == 401


def test_05a_7_expired_token_through_client_is_coded(chain, settings, world, monkeypatch):
    # The client always signs a fresh token; a stale clock on its side shows as a coded 401.
    real = mcp_client.sign_on_behalf_of

    def stale(**kwargs):
        return real(**kwargs, now=datetime.now(UTC) - timedelta(minutes=10))

    monkeypatch.setattr(mcp_client, "sign_on_behalf_of", stale)
    with pytest.raises(ToolCallError) as err:
        asyncio.run(_search(chain, settings, world["analyst_id"], world["project"]))
    assert err.value.code == "tool_auth_failed"
