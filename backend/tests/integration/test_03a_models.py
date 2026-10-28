"""03a acceptance 6 (C1 through the API), 10 (embed_dim measured, P5), 15 (catalog loader) and
the model endpoints."""

import uuid
from pathlib import Path

import anyio
import pytest

from ffcore.services import catalog_events, catalog_loader, providers
from tests.dummy import EMBED_DIM

API = "/api/v1"
SEED = Path(__file__).resolve().parents[3] / "deploy" / "seed" / "model_catalog.yaml"


@pytest.fixture
def root(make_user, client_factory):
    _, email = make_user(superadmin="edit")
    return client_factory(email)


@pytest.fixture
def events():
    seen = []
    catalog_events.subscribe(seen.append)
    yield seen
    catalog_events.unsubscribe(seen.append)


@pytest.fixture
def probe():
    """Stands in for 04a's in-process probe; answers a fixed dimension per model id."""
    dims = {"BAAI/bge-m3": EMBED_DIM, "tiny-embed": 384}

    async def measure(config, model_id, settings):
        return dims[model_id]

    providers.register_embedding_probe("local_flagembedding", measure)
    yield
    providers.unregister_embedding_probe("local_flagembedding")


def _provider(root, project_ids, driver="ollama", domains=("model",), config=None):
    body = {
        "key": f"prov-{uuid.uuid4().hex[:8]}",
        "label": "P",
        "driver": driver,
        "domains": list(domains),
        "config": config if config is not None else {"base_url": "http://ollama:11434"},
        "project_ids": [str(p) for p in project_ids],
    }
    response = root.post(f"{API}/providers", json=body)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _model(provider_id, key="chat-default", category="llm", model_id="qwen3.5:35b"):
    return {
        "key": key,
        "display_name": "Chat",
        "provider_id": provider_id,
        "category": category,
        "model_id": model_id,
        "upstream_api": "chat",
        "request_policy": {"extra_body": {"reasoning_effort": "none"}},
    }


def test_03a_6_same_model_key_two_projects_and_litellm_name(root, make_project, pg):
    keys = [f"proj-{uuid.uuid4().hex[:6]}", f"proj-{uuid.uuid4().hex[:6]}"]
    projects = [make_project(key) for key in keys]
    provider = _provider(root, projects)
    for project, key in zip(projects, keys, strict=True):
        created = root.post(f"{API}/projects/{project}/models", json=_model(provider))
        assert created.status_code == 201, created.text
        assert created.json()["litellm_name"] == f"{key}.chat-default"
    again = root.post(f"{API}/projects/{projects[0]}/models", json=_model(provider))
    assert (again.status_code, again.json()["error"]["code"]) == (409, "model_key_taken")


def test_03a_model_needs_assigned_provider_and_domain(root, make_project):
    mine, other = make_project(), make_project()
    foreign = _provider(root, [other])
    response = root.post(f"{API}/projects/{mine}/models", json=_model(foreign))
    assert (response.status_code, response.json()["error"]["code"]) == (
        422,
        "provider_not_assigned",
    )
    vector = _provider(root, [mine], driver="pgvector", domains=("vector",), config={})
    response = root.post(f"{API}/projects/{mine}/models", json=_model(vector, key="vector-chat"))
    assert response.json()["error"]["code"] == "provider_domain_mismatch"


def test_03a_model_upstream_api_is_explicit(root, make_project):
    project = make_project()
    body = _model(_provider(root, [project]))
    del body["upstream_api"]
    response = root.post(f"{API}/projects/{project}/models", json=body)
    assert response.status_code == 422  # never detected (ARCH-10)


def test_03a_10_embed_dim_mismatch_400(root, make_project, probe, pg):
    project = make_project()
    provider = _provider(root, [project], "local_flagembedding", ("embedding",), {})
    body = _model(provider, key="embed-small", category="embedding", model_id="tiny-embed")
    response = root.post(f"{API}/projects/{project}/models", json=body)
    assert (response.status_code, response.json()["error"]["code"]) == (400, "embed_dim_mismatch")
    assert "384" in response.json()["error"]["message"]
    assert pg.execute("SELECT count(*) FROM models WHERE key = 'embed-small'").fetchone()[0] == 0


def test_03a_10_probe_unavailable_409(root, make_project):
    project = make_project()
    provider = _provider(root, [project], "local_flagembedding", ("embedding",), {})
    body = _model(provider, key="embed", category="embedding", model_id="BAAI/bge-m3")
    response = root.post(f"{API}/projects/{project}/models", json=body)
    assert (response.status_code, response.json()["error"]["code"]) == (
        409,
        "embedding_probe_unavailable",
    )


def test_03a_10_embedding_not_for_litellm(root, make_project, probe, events):
    project = make_project()
    provider = _provider(root, [project], "local_flagembedding", ("embedding",), {})
    body = _model(provider, key="embed", category="embedding", model_id="BAAI/bge-m3")
    created = root.post(f"{API}/projects/{project}/models", json=body)
    assert created.status_code == 201, created.text
    assert created.json()["embed_dim"] == EMBED_DIM
    chat = root.post(f"{API}/projects/{project}/models", json=_model(_provider(root, [project])))
    model_events = {e.resource_id: e for e in events if e.kind == "model"}
    assert model_events[created.json()["id"]].litellm is False
    assert model_events[chat.json()["id"]].litellm is True
    assert model_events[chat.json()["id"]].project_id == str(project)


def test_03a_model_update_and_delete(root, make_project, events):
    project = make_project()
    provider = _provider(root, [project])
    mid = root.post(f"{API}/projects/{project}/models", json=_model(provider)).json()["id"]
    updated = root.patch(
        f"{API}/projects/{project}/models/{mid}",
        json={"pricing": {"input_per_1m": "0", "output_per_1m": "0"}, "is_active": False},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["is_active"] is False
    assert root.delete(f"{API}/projects/{project}/models/{mid}").status_code == 204
    assert root.get(f"{API}/projects/{project}/models/{mid}").status_code == 404
    actions = [e.action for e in events if e.resource_id == mid]
    assert actions == ["created", "updated", "deleted"]
    # Provider is free again once the model is gone.
    assert root.delete(f"{API}/providers/{provider}").status_code == 204


def test_03a_provider_in_use_409(root, make_project):
    project = make_project()
    provider = _provider(root, [project])
    root.post(f"{API}/projects/{project}/models", json=_model(provider))
    response = root.delete(f"{API}/providers/{provider}")
    assert (response.status_code, response.json()["error"]["code"]) == (409, "provider_in_use")


def test_03a_15_catalog_loader_idempotent(app, pg, tmp_path):
    first = anyio.run(catalog_loader.load, SEED)
    second = anyio.run(catalog_loader.load, SEED)
    assert first.upserted >= 2 and second.upserted == first.upserted
    rows = pg.execute("SELECT count(*) FROM model_catalog").fetchone()[0]
    assert rows == first.upserted
    bge = pg.execute(
        "SELECT embed_dim, category, source FROM model_catalog WHERE model_id = 'BAAI/bge-m3'"
    ).fetchone()
    assert bge[0] == EMBED_DIM and bge[1] == "embedding" and bge[2]

    smaller = tmp_path / "catalog.yaml"
    smaller.write_text(SEED.read_text(encoding="utf-8").split("\n  - driver: local_flag")[0] + "\n")
    result = anyio.run(catalog_loader.load, smaller)
    assert result.removed >= 1  # the file is the source; rows not in it are gone


def test_03a_15_catalog_loader_rejects_bad_file(app, tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("version: 1\nentries:\n  - driver: ollama\n    model_id: x\n")
    with pytest.raises(catalog_loader.CatalogFileError):
        anyio.run(catalog_loader.load, bad)
    with pytest.raises(catalog_loader.CatalogFileError):
        anyio.run(catalog_loader.load, tmp_path / "missing.yaml")


def test_03a_15_catalog_endpoint_for_any_user(app, make_user, make_project, client_factory):
    anyio.run(catalog_loader.load, SEED)
    _, analyst = make_user(memberships={make_project(): ("analyst", "read")})
    client = client_factory(analyst)
    data = client.get(f"{API}/model-catalog", params={"driver": "ollama"}).json()["data"]
    assert [entry["model_id"] for entry in data] == ["qwen3.5:35b"]
    assert client.get(f"{API}/model-catalog", params={"model_id": "nope"}).json()["data"] == []
