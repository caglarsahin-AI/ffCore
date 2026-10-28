"""Package 01: reconciler against the real LiteLLM container (tables -> LiteLLM DB)."""

import httpx2
import pytest

from ffcore.services.litellm_reconcile import key_hash
from tests.integration.litellm_support import (
    SECRET_MARKER,
    litellm_models,
    master,
    project_key,
    run_reconcile,
)

pytestmark = pytest.mark.usefixtures("clean_litellm")


def test_01_8_reconcile_converges(database_url, pg, catalog, llm_settings):
    project = catalog.project()
    provider = catalog.provider([project])
    model_id = catalog.model(project, provider)

    report = run_reconcile(database_url, llm_settings)

    name = f"{project_key(pg, project)}.chat-default"
    assert report.created == [name] and not report.problems
    models = litellm_models(llm_settings)
    assert set(models) == {name}
    assert models[name]["model_info"]["id"] == str(model_id)


def test_01_8_second_run_noop(database_url, pg, catalog, llm_settings):
    project = catalog.project()
    catalog.model(project, catalog.provider([project]))
    run_reconcile(database_url, llm_settings)

    again = run_reconcile(database_url, llm_settings)

    assert not again.changed


def test_01_8_changed_row_is_updated(database_url, pg, catalog, llm_settings):
    project = catalog.project()
    model_id = catalog.model(project, catalog.provider([project]))
    run_reconcile(database_url, llm_settings)
    pg.execute("UPDATE models SET model_id = 'other-model' WHERE id = %s", (model_id,))

    report = run_reconcile(database_url, llm_settings)

    assert len(report.updated) == 1 and not report.created and not report.deleted
    (model,) = litellm_models(llm_settings).values()
    assert model["model_info"]["id"] == str(model_id)
    # The change is in LiteLLM, not only in the report (02: /model/update applied nothing).
    assert model["litellm_params"]["model"] == "openai/other-model"
    assert not run_reconcile(database_url, llm_settings).changed


def test_01_3_inactive_model_removed(database_url, pg, catalog, llm_settings):
    project = catalog.project()
    model_id = catalog.model(project, catalog.provider([project]))
    run_reconcile(database_url, llm_settings)
    pg.execute("UPDATE models SET is_active = false WHERE id = %s", (model_id,))

    report = run_reconcile(database_url, llm_settings)

    assert report.deleted == [f"{project_key(pg, project)}.chat-default"]
    assert litellm_models(llm_settings) == {}


def test_01_5_same_key_two_projects(database_url, pg, catalog, llm_settings):
    a, b = catalog.project(), catalog.project()
    provider = catalog.provider([a, b])
    catalog.model(a, provider)
    catalog.model(b, provider)

    run_reconcile(database_url, llm_settings)

    assert set(litellm_models(llm_settings)) == {
        f"{project_key(pg, a)}.chat-default",
        f"{project_key(pg, b)}.chat-default",
    }


def test_01_embedding_and_unassigned_not_written(database_url, pg, catalog, llm_settings):
    project, other = catalog.project(), catalog.project()
    provider = catalog.provider([project])
    catalog.model(project, provider, key="embed", category="embedding")
    catalog.model(other, provider, key="chat-default")

    report = run_reconcile(database_url, llm_settings)

    assert litellm_models(llm_settings) == {}
    assert [p["code"] for p in report.problems] == ["provider_not_assigned"]


def test_01_1_offline_writes_no_external_model(database_url, pg, catalog, llm_settings):
    llm_settings.offline = True
    llm_settings.egress_allowlist = ["api.anthropic.com"]
    project = catalog.project()
    external = catalog.provider(
        [project], driver="anthropic", config={"api_key": f"{SECRET_MARKER}-anthropic"}
    )
    internal = catalog.provider([project])
    catalog.model(project, external, key="chat-default")
    catalog.model(project, internal, key="memory-extract")

    report = run_reconcile(database_url, llm_settings)

    models = litellm_models(llm_settings)
    assert set(models) == {f"{project_key(pg, project)}.memory-extract"}
    assert [p["code"] for p in report.problems] == ["egress_offline"]
    # No deployment points outside the compose network.
    for model in models.values():
        assert "anthropic" not in model["litellm_params"]["model"]


def test_01_6_api_key_encrypted_at_rest(database_url, pg, catalog, llm_settings, litellm_db):
    project = catalog.project()
    catalog.model(project, catalog.provider([project]))
    run_reconcile(database_url, llm_settings)

    rows = litellm_db.execute(
        'SELECT litellm_params::text FROM "LiteLLM_ProxyModelTable"'
    ).fetchall()
    assert rows
    assert all(SECRET_MARKER not in text for (text,) in rows)
    (model,) = litellm_models(llm_settings).values()
    assert not model["litellm_params"].get("api_key")


def test_01_7_litellm_config_table_stays_empty(database_url, pg, catalog, llm_settings, litellm_db):
    project = catalog.project()
    catalog.model(project, catalog.provider([project]))
    run_reconcile(database_url, llm_settings)

    rows = litellm_db.execute(
        'SELECT param_name, param_value::text FROM "LiteLLM_Config"'
    ).fetchall()
    assert rows == []
    master_key = llm_settings.litellm_master_key.get_secret_value()
    for table in ("LiteLLM_Config", "LiteLLM_ProxyModelTable"):
        hits = litellm_db.execute(
            f'SELECT count(*) FROM "{table}" t WHERE t::text LIKE %s', (f"%{master_key}%",)
        ).fetchone()[0]
        assert hits == 0


def test_01_internal_key_registered(database_url, pg, catalog, llm_settings):
    run_reconcile(database_url, llm_settings)

    # By hash: a raw key in a URL lands in LiteLLM's access log (r1 MAJOR-1).
    key = key_hash(llm_settings.litellm_internal_key.get_secret_value())
    response = httpx2.get(
        f"{llm_settings.litellm_url}/key/info", params={"key": key}, headers=master(llm_settings)
    )
    assert response.status_code == 200


def test_01_6_api_key_encrypted_after_update(database_url, pg, catalog, llm_settings, litellm_db):
    """U2 also on the update path (PATCH /model/{id}/update, 02)."""
    from ffcore.core.secrets import encrypt_json

    project = catalog.project()
    provider = catalog.provider([project])
    catalog.model(project, provider)
    run_reconcile(database_url, llm_settings)
    new_key = f"{SECRET_MARKER}-rotated-key"
    pg.execute(
        "UPDATE providers SET config_encrypted = %s WHERE id = %s",
        (
            encrypt_json({"base_url": "http://fake-llm:9999/v1", "api_key": new_key}, llm_settings),
            provider,
        ),
    )

    assert len(run_reconcile(database_url, llm_settings).updated) == 1

    hits = litellm_db.execute(
        'SELECT count(*) FROM "LiteLLM_ProxyModelTable" t WHERE t::text LIKE %s', (f"%{new_key}%",)
    ).fetchone()[0]
    assert hits == 0
