"""06b S2 (K-06b-0002): a run started by an API key without a user searches with the key's
acl_role. The internal endpoint reads the role from the key row (any role in the body is
ignored), checks the key again (revoked, expired, project) and that the run is the key's."""

import uuid

from tests.dummy import SERVICE_TOKEN
from tests.integration import test_04a_api as kb_api
from tests.integration.test_04a_api import PROSE, create_kb, process_all, upload

# 04a's fixtures (fake embedder, ingest queue, users of two projects), used as they are.
queue = kb_api.queue
settings = kb_api.settings
world = kb_api.world

SERVICE = {"Authorization": f"Bearer {SERVICE_TOKEN}"}


def _key(world, **body):
    payload = {"name": "k", "scopes": ["agents"]} | body
    url = f"/api/v1/projects/{world['project']}/api-keys"
    response = world["admin"].post(url, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _search(world, kb_id, key_id, **extra):
    body = {"api_key_id": key_id, "project_id": world["project"], "query": "fesih bildirim"}
    return world["service"].post(
        f"/internal/knowledge-bases/{kb_id}/key-search", json=body | extra, headers=SERVICE
    )


def _indexed(world, settings, queue):
    kb = create_kb(world)
    upload(world, world["admin"], kb["id"], "gizli.md", PROSE * 8, acl_roles="admin")
    upload(world, world["admin"], kb["id"], "analist.md", PROSE * 8 + " analist")
    process_all(settings, queue)
    return kb


def _names(response):
    assert response.status_code == 200, response.text
    return {h["document_name"] for h in response.json()["hits"]}


def test_06b_3_key_actor_searches_with_acl_role(world, settings, queue, pg):
    kb = _indexed(world, settings, queue)
    analyst_key = _key(world)  # default acl_role analyst
    admin_key = _key(world, acl_role="admin")
    assert _names(_search(world, kb["id"], analyst_key["id"])) == {"analist.md"}
    assert _names(_search(world, kb["id"], admin_key["id"])) == {"gizli.md", "analist.md"}
    response = _search(world, kb["id"], analyst_key["id"])
    (user_id,) = pg.execute(
        "SELECT user_id FROM kb_queries WHERE id = %s", (response.json()["query_id"],)
    ).fetchone()
    assert user_id == f"api_key:{analyst_key['id']}"


def test_06b_s2_role_in_body_is_ignored(world, settings, queue):
    kb = _indexed(world, settings, queue)
    analyst_key = _key(world)
    forged = _search(world, kb["id"], analyst_key["id"], acl_role="admin", acl_roles=["admin"])
    assert _names(forged) == {"analist.md"}


def test_06b_s2_revoked_key_403(world, settings, queue):
    kb = _indexed(world, settings, queue)
    key = _key(world)
    url = f"/api/v1/projects/{world['project']}/api-keys/{key['id']}/revoke"
    assert world["admin"].post(url).status_code == 200
    response = _search(world, kb["id"], key["id"])
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "api_key_not_valid"


def test_06b_s2_other_project_403(world, settings, queue):
    kb = _indexed(world, settings, queue)
    key = _key(world)
    response = world["service"].post(
        f"/internal/knowledge-bases/{kb['id']}/key-search",
        json={"api_key_id": key["id"], "project_id": world["other"], "query": "fesih"},
        headers=SERVICE,
    )
    assert response.status_code == 403


def test_06b_s2_run_of_another_key_403(world, settings, queue, pg):
    kb = _indexed(world, settings, queue)
    mine, theirs = _key(world), _key(world)
    run_id = uuid.uuid4()
    agent_id, version_id = uuid.uuid4(), uuid.uuid4()
    pg.execute(
        "INSERT INTO agents (id, project_id, key, name, created_by) VALUES (%s, %s, 'a', 'A', 't')",
        (agent_id, world["project"]),
    )
    pg.execute(
        "INSERT INTO agent_versions (id, agent_id, version, definition, created_by)"
        " VALUES (%s, %s, 1, '{}', 't')",
        (version_id, agent_id),
    )
    pg.execute(
        "INSERT INTO runs (id, project_id, agent_id, agent_version_id, channel, trigger_type,"
        " input, status, api_key_id, created_by) VALUES (%s, %s, %s, %s, 'api', 'api', 'q',"
        " 'running', %s, 't')",
        (run_id, world["project"], agent_id, version_id, theirs["id"]),
    )
    response = _search(world, kb["id"], mine["id"], run_id=str(run_id))
    assert response.status_code == 403
    assert _names(_search(world, kb["id"], theirs["id"], run_id=str(run_id))) == {"analist.md"}


def test_06b_s2_only_the_service_account(world, settings, queue):
    kb = _indexed(world, settings, queue)
    key = _key(world)
    response = world["analyst"].post(
        f"/internal/knowledge-bases/{kb['id']}/key-search",
        json={"api_key_id": key["id"], "project_id": world["project"], "query": "fesih"},
    )
    assert response.status_code in (401, 403)
