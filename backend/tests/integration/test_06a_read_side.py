"""06a read-only access: every GET under an agent or a run answers a superadmin in `read` mode
exactly as in `edit` mode (brief 03 acceptance 2, the 06a part; test_03a_2 exempts these)."""

import re

from tests.integration.runtime_support import (
    Harness,
    Ports,
    ScriptedModel,
    ScriptedRetriever,
    definition,
    seed_run,
    setup,
    source,
    turn,
)

API = "/api/v1"


def test_06a_read_mode_get_parity(
    app, database_url, app_settings, pg, make_project, make_user, client_factory
):
    import os

    from pydantic import SecretStr

    project_id = make_project()
    run_id = seed_run(pg, project_id, definition())
    setup(database_url)
    settings = app_settings.model_copy(
        update={
            "database_url": SecretStr(database_url),
            "redis_url": SecretStr(os.environ["REDIS_URL"]),
        }
    )
    Harness(database_url, settings).run(
        run_id, Ports(ScriptedModel(turn("A [1].")), ScriptedRetriever([source()]))
    )
    agent_id = pg.execute("SELECT agent_id FROM runs WHERE id = %s", (run_id,)).fetchone()[0]
    world = {
        "project_id": str(project_id),
        "agent_id": str(agent_id),
        "run_id": str(run_id),
        "version": "1",
    }
    # 06b-2: GET .../agents/{agent_id}/external reads an external agent (a native one is 409
    # `agent_not_external`), so that route gets an external agent of its own.
    import uuid

    from ffcore.services.facade_external import ExternalConfig

    external_id = uuid.uuid4()
    config = ExternalConfig(
        base_url="https://agent.example/v1", model="m", api_key="dummy-not-secret-parity-key"
    )
    pg.execute(
        "INSERT INTO agents (id, project_id, key, name, kind, external_config, created_by)"
        " VALUES (%s, %s, 'dis-parite', 'Dış', 'external', %s, 'test')",
        (external_id, project_id, config.encrypt(app_settings)),
    )

    from ffcore.core.config import get_settings

    app.dependency_overrides[get_settings] = lambda: settings
    _, editor = make_user(superadmin="edit")
    _, reader = make_user(superadmin="read")
    edit, read = client_factory(editor), client_factory(reader)
    checked = 0
    for path, ops in app.openapi()["paths"].items():
        if "get" not in ops or not (
            path.startswith(f"{API}/projects/{{project_id}}/agents/{{agent_id}}")
            or path.startswith(f"{API}/projects/{{project_id}}/runs/{{run_id}}")
        ):
            continue
        here = dict(world, agent_id=str(external_id)) if path.endswith("/external") else world
        url = re.sub(r"\{(\w+)\}", lambda m, here=here: here[m.group(1)], path)
        a, b = edit.get(url), read.get(url)
        assert a.status_code == 200, (url, a.text)
        assert (b.status_code, b.content) == (a.status_code, a.content), url
        checked += 1
    # agent, versions, version, manifest (06b), external agent (06b-2), run, events, stream
    assert checked == 8
