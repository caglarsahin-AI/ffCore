"""04a slice 4: POST /internal/embed (service account only) and the local_flagembedding probe."""

import uuid

import pytest

from tests.dummy import EMBED_DIM, SERVICE_TOKEN


@pytest.fixture
def fake_settings(app, app_settings):
    from ffcore.core.config import get_settings

    settings = app_settings.model_copy(update={"fake_embed": True})
    app.dependency_overrides[get_settings] = lambda: settings
    return settings


def test_04a_internal_embed_returns_dense_and_sparse(client_factory, fake_settings):
    client = client_factory()
    response = client.post(
        "/internal/embed",
        json={"texts": ["fesih bildirim süresi", "bakım"]},
        headers={"Authorization": f"Bearer {SERVICE_TOKEN}"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["dim"] == EMBED_DIM and body["model"] == fake_settings.embed_model
    assert len(body["dense"]) == 2 and len(body["dense"][0]) == EMBED_DIM
    assert body["sparse"][0] and body["truncated"] == [False, False]


def test_04a_internal_embed_refuses_users_and_anonymous(client_factory, make_user, fake_settings):
    _, email = make_user(superadmin="edit")
    anonymous = client_factory().post("/internal/embed", json={"texts": ["x"]})
    user = client_factory(email).post("/internal/embed", json={"texts": ["x"]})
    assert anonymous.status_code == 401
    assert user.status_code == 403 and user.json()["error"]["code"] == "service_account_required"


def test_04a_5_embed_dim_mismatch_rejected_through_probe(
    client_factory, make_user, make_project, fake_settings
):
    """03a's model registration measures the dimension with the 04a probe; a model whose
    measured dimension is not EMBED_DIM is refused with 400 and never activated."""
    from ffcore.knowledge import embed as embed_module

    _, email = make_user(superadmin="edit")
    client = client_factory(email)
    project = make_project()
    provider = client.post(
        "/api/v1/providers",
        json={
            "key": f"emb-{uuid.uuid4().hex[:8]}",
            "label": "In-process embedding",
            "driver": "local_flagembedding",
            "domains": ["embedding"],
            "config": {},
            "project_ids": [str(project)],
        },
    )
    assert provider.status_code == 201, provider.text
    body = {
        "key": "embed-default",
        "display_name": "Embedding",
        "provider_id": provider.json()["id"],
        "category": "embedding",
        "model_id": fake_settings.embed_model,
        "upstream_api": "chat",
    }
    ok = client.post(f"/api/v1/projects/{project}/models", json=body)
    assert ok.status_code == 201, ok.text
    assert ok.json()["embed_dim"] == EMBED_DIM

    original = embed_module.FakeEmbedder.encode

    def short_vectors(self, texts):
        result = original(self, texts)
        return type(result)([v[:512] for v in result.dense], result.sparse, result.truncated)

    embed_module.FakeEmbedder.encode = short_vectors
    try:
        bad = client.post(f"/api/v1/projects/{project}/models", json={**body, "key": "embed-short"})
    finally:
        embed_module.FakeEmbedder.encode = original
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "embed_dim_mismatch"
    listed = client.get(f"/api/v1/projects/{project}/models").json()["data"]
    assert "embed-short" not in {m["key"] for m in listed}


def test_04a_probe_refuses_a_second_embedding_model(
    client_factory, make_user, make_project, fake_settings
):
    _, email = make_user(superadmin="edit")
    client = client_factory(email)
    project = make_project()
    provider = client.post(
        "/api/v1/providers",
        json={
            "key": f"emb-{uuid.uuid4().hex[:8]}",
            "label": "In-process embedding",
            "driver": "local_flagembedding",
            "domains": ["embedding"],
            "config": {},
            "project_ids": [str(project)],
        },
    ).json()["id"]
    response = client.post(
        f"/api/v1/projects/{project}/models",
        json={
            "key": "e5",
            "display_name": "e5",
            "provider_id": provider,
            "category": "embedding",
            "model_id": "intfloat/multilingual-e5-large",
            "upstream_api": "chat",
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "embed_model_mismatch"
