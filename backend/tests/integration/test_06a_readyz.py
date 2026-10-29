"""06a additions to /readyz (S13): published agents' context_tokens against OLLAMA_CONTEXT_LENGTH
(C13: a seed or install change that breaks a published agent is said at start), and the model
slot pool (LLM_SLOTS in use and waiting per class)."""

import asyncio
import json
import os
import uuid

import pytest
from pydantic import SecretStr

from ffcore.core import readiness
from tests.integration import test_04a_readyz
from tests.integration.test_04a_readyz import _checks

ready_app = test_04a_readyz.ready_app  # the 04a fixture, reused


def _ollama_agent(pg, project_id, context_tokens):
    provider = uuid.uuid4()
    pg.execute(
        "INSERT INTO providers (id, key, label, driver, domains, config_encrypted,"
        " supports_test, created_by) VALUES (%s, %s, 'Ollama', 'ollama', '{model}', %s, true,"
        " 'test')",
        (provider, f"ol-{provider.hex[:8]}", b"x"),
    )
    pg.execute(
        "INSERT INTO models (id, project_id, key, display_name, provider_id, category, model_id,"
        " capabilities, input_types, pricing, limits, upstream_api, request_policy, created_by)"
        " VALUES (%s, %s, 'chat-default', 'Chat', %s, 'llm', 'qwen3.5:35b', '{}', '{text}',"
        " '{}', '{}', 'chat', '{}', 'test')",
        (uuid.uuid4(), project_id, provider),
    )
    agent_id, version_id = uuid.uuid4(), uuid.uuid4()
    doc = {
        "model": "chat-default",
        "system_prompt": "S",
        "limits": {"context_tokens": context_tokens},
    }
    pg.execute(
        "INSERT INTO agents (id, project_id, key, name, created_by) VALUES (%s, %s, 'a', 'A', 't')",
        (agent_id, project_id),
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


@pytest.fixture
def published(pg, make_project):
    """The database is shared by the session: the agent is removed afterwards so 04a's own
    readiness tests see no published agent."""
    project_id = make_project()
    _ollama_agent(pg, project_id, 24000)
    yield project_id
    pg.execute("UPDATE agents SET deleted_at = now() WHERE project_id = %s", (project_id,))


def test_06a_6a_readyz_published_agent_context(client_factory, ready_app, published):
    asyncio.run(readiness.warmup(ready_app["settings"]))
    client = client_factory()
    base = ready_app["settings"].model_copy(update={"inference_backend": "ollama"})

    ready_app["settings"] = base.model_copy(update={"ollama_context_length": 16384})
    small = client.get("/readyz")
    assert small.status_code == 503
    check = _checks(small)["ollama_context"]
    assert check["code"] == "context_configuration_invalid" and "24000" in check["detail"]

    ready_app["settings"] = base.model_copy(update={"ollama_context_length": 32768})
    assert client.get("/readyz").status_code == 200


def test_06a_10_readyz_reports_the_slot_pool(client_factory, ready_app):
    asyncio.run(readiness.warmup(ready_app["settings"]))
    client = client_factory()
    ready_app["settings"] = ready_app["settings"].model_copy(update={"redis_url": None})
    no_redis = _checks(client.get("/readyz"))["llm_slots"]
    assert no_redis["status"] == "skipped"
    ready_app["settings"] = ready_app["settings"].model_copy(
        update={"redis_url": SecretStr(os.environ["REDIS_URL"]), "llm_slots": 1}
    )
    response = client.get("/readyz")
    slots = _checks(response)["llm_slots"]
    assert response.status_code == 200 and slots["status"] == "ok"
    assert slots["detail"].startswith("in_use=0/1")
