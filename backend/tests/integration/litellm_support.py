"""Package 01 integration fixtures: the real LiteLLM container and the fake provider.

Needs `docker compose --profile test up -d postgres litellm fake-llm`; tests run in the tools
container (compose network). LiteLLM's database is shared by the tests of one run: every test
starts from an empty model list, because each reconcile removes what its tables do not hold.
"""

import asyncio
import os
import uuid

import httpx2
import psycopg
import pytest
from sqlalchemy.engine import make_url

from ffcore.core.config import Settings
from ffcore.core.secrets import encrypt_json
from tests.dummy import OBO_SECRET, SERVICE_TOKEN, SETTINGS_03A

FAKE = "http://fake-llm:9999"
SECRET_MARKER = "dummy-not-secret"


def _env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        pytest.fail(f"{name} is not set; run in the tools container with .env.test")
    return value


@pytest.fixture
def llm_settings() -> Settings:
    return Settings(
        deploy_profile=os.environ.get("DEPLOY_PROFILE", "llmaas"),
        offline=False,
        service_token=SERVICE_TOKEN,
        obo_jwt_secret=OBO_SECRET,
        allowed_internal_hosts=["litellm", "fake-llm", "langfuse-web"],  # 02: LANGFUSE_HOST
        egress_allowlist=[],
        litellm_url=_env("LITELLM_URL"),
        litellm_master_key=_env("LITELLM_MASTER_KEY"),
        litellm_internal_key=_env("LITELLM_INTERNAL_KEY"),
        llm_call_timeout_s=20,
        **SETTINGS_03A,
    )


@pytest.fixture
def litellm_db():
    """psycopg connection to LiteLLM's own database (same server, database `litellm`)."""
    url = make_url(_env("DATABASE_URL")).set(drivername="postgresql", database="litellm")
    with psycopg.connect(url.render_as_string(hide_password=False), autocommit=True) as conn:
        yield conn


def master(settings: Settings) -> dict[str, str]:
    return {"Authorization": f"Bearer {settings.litellm_master_key.get_secret_value()}"}


def litellm_models(settings: Settings) -> dict[str, dict]:
    response = httpx2.get(f"{settings.litellm_url}/model/info", headers=master(settings))
    response.raise_for_status()
    return {m["model_name"]: m for m in response.json()["data"]}


def fake_requests() -> list[dict]:
    return httpx2.get(f"{FAKE}/_requests").json()


@pytest.fixture
def clean_litellm(llm_settings):
    """Empty LiteLLM model list and fake provider log before the test."""
    for model in litellm_models(llm_settings).values():
        httpx2.post(
            f"{llm_settings.litellm_url}/model/delete",
            headers=master(llm_settings),
            json={"id": model["model_info"]["id"]},
        ).raise_for_status()
    httpx2.post(f"{FAKE}/_reset", json={}).raise_for_status()
    yield


@pytest.fixture
def catalog(pg, make_project, llm_settings):
    """Insert providers and models straight into the test database. The database is shared by
    the session, so the catalog tables start empty: the reconciler reads all of them."""
    pg.execute("DELETE FROM models")
    pg.execute("DELETE FROM provider_projects")
    pg.execute("DELETE FROM providers")

    class Catalog:
        def provider(self, project_ids, driver="openai_compatible", config=None, active=True):
            provider_id = uuid.uuid4()
            config = config or {"base_url": f"{FAKE}/v1", "api_key": f"{SECRET_MARKER}-key-x"}
            pg.execute(
                "INSERT INTO providers (id, key, label, driver, domains, config_encrypted,"
                " supports_test, is_active, created_by) VALUES (%s, %s, 'P', %s,"
                " ARRAY['model'], %s, true, %s, 'test')",
                (
                    provider_id,
                    f"prov-{provider_id.hex[:8]}",
                    driver,
                    encrypt_json(config, llm_settings),
                    active,
                ),
            )
            for project_id in project_ids:
                pg.execute(
                    "INSERT INTO provider_projects (provider_id, project_id) VALUES (%s, %s)",
                    (provider_id, project_id),
                )
            return provider_id

        def model(self, project_id, provider_id, key="chat-default", model_id="ok-model", **over):
            model_id_ = uuid.uuid4()
            values = {
                "category": "llm",
                "is_active": True,
                "request_policy": '{"extra_body": {"reasoning_effort": "none"}}',
                "pricing": '{"input_per_1m": 0, "output_per_1m": 0}',
            }
            values.update(over)
            pg.execute(
                "INSERT INTO models (id, project_id, key, display_name, provider_id, category,"
                " model_id, capabilities, input_types, pricing, limits, upstream_api,"
                " request_policy, is_active, created_by) VALUES (%s, %s, %s, %s, %s, %s, %s,"
                " '{}', ARRAY['text'], %s, '{}', 'chat', %s, %s, 'test')",
                (
                    model_id_,
                    project_id,
                    key,
                    key,
                    provider_id,
                    values["category"],
                    model_id,
                    values["pricing"],
                    values["request_policy"],
                    values["is_active"],
                ),
            )
            return model_id_

        def project(self, key=None):
            return make_project(key or f"p{uuid.uuid4().hex[:8]}")

    return Catalog()


def run_reconcile(database_url: str, settings: Settings):
    from ffcore.core import db
    from ffcore.services.litellm_reconcile import reconcile

    async def go():
        db.configure(database_url, pooled=False)
        try:
            async with db.session_scope() as session:
                return await reconcile(session, settings)
        finally:
            db.reset()

    return asyncio.run(go())


def project_key(pg, project_id) -> str:
    return pg.execute("SELECT key FROM projects WHERE id = %s", (project_id,)).fetchone()[0]
