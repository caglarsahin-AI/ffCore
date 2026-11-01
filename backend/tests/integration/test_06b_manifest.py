"""06b manifest: export an agent version as JSON or YAML and import it (dry run validates and
writes nothing); an import makes a new agent or the next draft version, never publishes;
writing needs edit access and is audited; an older definition without schema_version is read."""

import uuid

import yaml

from tests.integration.conftest import audit_rows


def _model(pg, project):
    provider = uuid.uuid4()
    pg.execute(
        "INSERT INTO providers (id, key, label, driver, domains, config_encrypted, supports_test,"
        " is_active, created_by) VALUES (%s, %s, 'P', 'openai_compatible', ARRAY['model'],"
        " decode('00', 'hex'), false, true, 't')",
        (provider, f"prov-{provider.hex[:8]}"),
    )
    pg.execute(
        "INSERT INTO provider_projects (provider_id, project_id) VALUES (%s, %s)",
        (provider, project),
    )
    pg.execute(
        "INSERT INTO models (id, project_id, key, display_name, provider_id, category, model_id,"
        " capabilities, input_types, pricing, limits, upstream_api, request_policy, is_active,"
        " created_by) VALUES (gen_random_uuid(), %s, 'chat-default', 'c', %s, 'llm', 'm', '{}',"
        " ARRAY['text'], '{}', '{}', 'chat', '{}', true, 't')",
        (project, provider),
    )


def _projects(make_project, make_user, client_factory, pg):
    a, b = make_project(), make_project()
    for p in (a, b):
        _model(pg, p)
    _, email = make_user(memberships={a: ("analyst", "edit"), b: ("analyst", "edit")})
    return a, b, client_factory(email)


def _agent(client, project):
    created = client.post(
        f"/api/v1/projects/{project}/agents",
        json={"key": "sozlesme", "name": "Sözleşme Asistanı", "model": "chat-default"},
    )
    assert created.status_code == 201, created.text
    agent = created.json()
    edited = client.put(
        f"/api/v1/projects/{project}/agents/{agent['id']}/versions/1",
        json={
            "definition": {
                "model": "chat-default",
                "system_prompt": "Answer from {{kb}}.",
                "variables": [{"key": "kb", "label": "KB", "default": "docs"}],
            }
        },
    )
    assert edited.status_code == 200, edited.text
    return agent


def _count(pg, project):
    return pg.execute(
        "SELECT (SELECT count(*) FROM agents WHERE project_id = %s),"
        " (SELECT count(*) FROM agent_versions v JOIN agents a ON a.id = v.agent_id"
        " WHERE a.project_id = %s)",
        (project, project),
    ).fetchone()


def test_06b_14_manifest_round_trip(make_project, make_user, client_factory, pg):
    a, b, client = _projects(make_project, make_user, client_factory, pg)
    agent = _agent(client, a)
    exported = client.get(f"/api/v1/projects/{a}/agents/{agent['id']}/manifest")
    assert exported.status_code == 200, exported.text
    manifest = exported.json()
    assert manifest["manifest_version"] == 1 and manifest["agent"]["key"] == "sozlesme"
    assert manifest["definition"]["system_prompt"] == "Answer from {{kb}}."

    url = f"/api/v1/projects/{b}/agents/import"
    imported = client.post(url, json=manifest)
    assert imported.status_code == 200, imported.text
    result = imported.json()
    assert (result["action"], result["version"], result["dry_run"]) == ("create", 1, False)
    copy = client.get(f"/api/v1/projects/{b}/agents/{result['id']}/versions/1").json()
    assert copy["definition"] == manifest["definition"]
    status = client.get(f"/api/v1/projects/{b}/agents/{result['id']}").json()["status"]
    assert status == "draft"  # an import never publishes

    # YAML both ways; the same key again is the next draft version.
    text = client.get(
        f"/api/v1/projects/{a}/agents/{agent['id']}/manifest", params={"format": "yaml"}
    )
    assert text.headers["content-type"].startswith("application/yaml")
    assert yaml.safe_load(text.text) == manifest
    again = client.post(url, content=text.text, headers={"Content-Type": "application/yaml"})
    assert again.status_code == 200, again.text
    assert (again.json()["action"], again.json()["version"]) == ("new_version", 2)
    assert [r[1] for r in audit_rows(pg, "import_agent", project=b)] == ["success", "success"]


def test_06b_14_import_dry_run_writes_nothing(make_project, make_user, client_factory, pg):
    a, b, client = _projects(make_project, make_user, client_factory, pg)
    manifest = client.get(f"/api/v1/projects/{a}/agents/{_agent(client, a)['id']}/manifest").json()
    before = _count(pg, b)
    dry = client.post(
        f"/api/v1/projects/{b}/agents/import", params={"dry_run": "true"}, json=manifest
    )
    assert dry.status_code == 200, dry.text
    assert dry.json()["dry_run"] is True and dry.json()["action"] == "create"
    assert dry.json()["id"] is None
    assert _count(pg, b) == before


def test_06b_14_old_schema_version_is_read(make_project, make_user, client_factory, pg):
    a, _, client = _projects(make_project, make_user, client_factory, pg)
    manifest = {
        "agent": {"key": "eski", "name": "Old"},
        "definition": {"model": "chat-default", "system_prompt": "x"},  # no schema_version
    }
    response = client.post(f"/api/v1/projects/{a}/agents/import", json=manifest)
    assert response.status_code == 200, response.text
    assert response.json()["definition"]["schema_version"] == 1


def test_06b_14_import_refuses_what_it_cannot_run(make_project, make_user, client_factory, pg):
    a, _, client = _projects(make_project, make_user, client_factory, pg)
    url = f"/api/v1/projects/{a}/agents/import"
    bad = client.post(url, json={"agent": {"key": "x", "name": "x"}, "definition": {"nope": 1}})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "manifest_invalid"
    unknown_model = client.post(
        url,
        json={
            "agent": {"key": "y", "name": "y"},
            "definition": {"model": "yok", "system_prompt": "x"},
        },
    )
    assert unknown_model.status_code == 400
    assert unknown_model.json()["error"]["code"] == "model_not_found"
    external = client.post(
        url,
        json={
            "agent": {"key": "z", "name": "z", "kind": "external"},
            "definition": {"model": "chat-default"},
        },
    )
    assert external.status_code == 422
    assert external.json()["error"]["code"] == "external_agent_not_available"
    assert _count(pg, a)[0] == 0  # nothing was turned into a native agent
    garbage = client.post(
        url, content=b"::: not yaml", headers={"Content-Type": "application/yaml"}
    )
    assert garbage.status_code == 422 and garbage.json()["error"]["code"] == "manifest_invalid"


def test_06b_14_import_needs_write(make_project, make_user, client_factory, pg):
    a, _, _ = _projects(make_project, make_user, client_factory, pg)
    _, reader = make_user(memberships={a: ("admin", "read")})
    response = client_factory(reader).post(
        f"/api/v1/projects/{a}/agents/import",
        json={"agent": {"key": "r", "name": "r"}, "definition": {"model": "chat-default"}},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "read_only_access"
