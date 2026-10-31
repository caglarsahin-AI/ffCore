"""Package 01: a catalog change through the 03a API reaches LiteLLM without a restart (R1.4).

The application runs with its lifespan (TestClient context), so the start-up reconcile and the
catalog event listener are the real ones.
"""

import asyncio
import time

import pytest

from ffcore.core import db
from ffcore.core.config import get_settings
from ffcore.core.errors import ApiError
from ffcore.services.litellm_client import resolve_target
from tests.integration.conftest import CONSOLE_ORIGIN
from tests.integration.litellm_support import FAKE, litellm_models, project_key, run_reconcile

pytestmark = pytest.mark.usefixtures("clean_litellm")


def _wait(predicate, seconds=20):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.3)
    return False


@pytest.fixture
def console(app, client_factory, make_user, llm_settings):
    llm_settings.console_origins = [CONSOLE_ORIGIN]
    app.dependency_overrides[get_settings] = lambda: llm_settings
    _, email = make_user(superadmin="edit")
    return client_factory(email)


def test_01_5_api_change_reaches_litellm(app, console, pg, catalog, llm_settings):
    project_id = catalog.project()
    name = f"{project_key(pg, project_id)}.chat-default"
    provider = console.post(
        "/api/v1/providers",
        json={
            "key": "fake-provider",
            "label": "Fake",
            "driver": "openai_compatible",
            "domains": ["model"],
            "config": {"base_url": f"{FAKE}/v1", "api_key": "dummy-not-secret-key"},
            "project_ids": [str(project_id)],
        },
    )
    assert provider.status_code == 201, provider.text
    model = console.post(
        f"/api/v1/projects/{project_id}/models",
        json={
            "key": "chat-default",
            "display_name": "Chat",
            "provider_id": provider.json()["id"],
            "category": "llm",
            "model_id": "ok-model",
            "upstream_api": "chat",
        },
    )
    assert model.status_code == 201, model.text

    assert _wait(lambda: name in litellm_models(llm_settings)), "model did not reach LiteLLM"

    patched = console.patch(
        f"/api/v1/projects/{project_id}/models/{model.json()['id']}", json={"is_active": False}
    )
    assert patched.status_code == 200, patched.text
    assert _wait(lambda: name not in litellm_models(llm_settings)), "inactive model stayed"


def test_01_14_rollback_not_reconciled(app, console, pg, catalog, llm_settings):
    project_id = catalog.project()
    provider_id = catalog.provider([project_id])
    catalog.model(project_id, provider_id)
    scheduler = app.state.litellm_scheduler
    assert _wait(lambda: scheduler.runs >= 1 and not scheduler._dirty)
    time.sleep(0.5)
    before = scheduler.runs

    # Deactivating a provider that still serves an active model is refused (409, 03a r1); the
    # transaction rolls back and no catalog event is delivered.
    refused = console.patch(f"/api/v1/providers/{provider_id}", json={"is_active": False})

    assert refused.status_code == 409, refused.text
    time.sleep(1)
    assert scheduler.runs == before


def test_01_r1_deleted_project_leaves_litellm(
    app, console, database_url, pg, catalog, llm_settings
):
    """r1 MINOR-1: project deleted through the API -> no target, next reconcile removes it."""
    project_id = catalog.project()
    catalog.model(project_id, catalog.provider([project_id]))
    name = f"{project_key(pg, project_id)}.chat-default"
    run_reconcile(database_url, llm_settings)
    db.configure(database_url, pooled=False)  # run_reconcile resets the app's binding
    assert name in litellm_models(llm_settings)

    deleted = console.delete(f"/api/v1/projects/{project_id}")
    assert deleted.status_code == 204, deleted.text

    async def resolve():
        async with db.session_scope() as session:
            return await resolve_target(session, project_id, "chat-default")

    with pytest.raises(ApiError) as err:
        asyncio.run(resolve())
    assert err.value.status_code == 404 and err.value.code == "model_not_found"
    assert err.value.reason == "project_deleted"
    # FOLLOWUP-75 (03c): the delete publishes a catalog event, so the app's own reconcile may
    # already have removed the model; the explicit run removes it otherwise. Never left.
    run_reconcile(database_url, llm_settings)
    assert name not in litellm_models(llm_settings)
