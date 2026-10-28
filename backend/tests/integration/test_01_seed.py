"""Package 01: seed -> tables -> reconcile -> LiteLLM answers <project>.chat-default.

The airgap seed with SEED_OLLAMA_BASE_URL pointing at the fake provider stands in for Ollama
(brief 01 Teslimatlar: curl with LITELLM_INTERNAL_KEY; the real Qwen run is `-m ollama`).
"""

import asyncio
import uuid
from pathlib import Path

import httpx2
import pytest

from ffcore.core import db
from ffcore.services.seed_models import seed
from tests.integration.litellm_support import SECRET_MARKER, run_reconcile

pytestmark = pytest.mark.usefixtures("clean_litellm")
SEED = Path(__file__).resolve().parents[3] / "deploy" / "seed"
ENV = {"SEED_OLLAMA_BASE_URL": "http://fake-llm:9999"}


def _seed(database_url, settings, key):
    async def go():
        db.configure(database_url, pooled=False)
        try:
            async with db.session_scope() as session:
                report = await seed(session, key, settings, SEED / "models.airgap.yaml", ENV)
                await session.commit()
                return report
        finally:
            db.reset()

    return asyncio.run(go())


@pytest.fixture
def airgap(llm_settings):
    llm_settings.deploy_profile = "airgap"
    llm_settings.offline = True
    llm_settings.inference_backend = "ollama"
    return llm_settings


def _key():
    return f"hastane{uuid.uuid4().hex[:6]}"


def test_01_13_seed_idempotent(database_url, pg, catalog, airgap):
    key = _key()
    project_id = catalog.project(key)

    first = _seed(database_url, airgap, key)
    second = _seed(database_url, airgap, key)

    assert first.providers_created == ["ollama"]
    assert first.models_created == ["chat-default", "memory-extract"]
    assert second.providers_created == [] and second.models_created == []
    assert second.models_existing == ["chat-default", "memory-extract"]
    count = pg.execute("SELECT count(*) FROM models WHERE project_id = %s", (project_id,))
    assert count.fetchone()[0] == 2
    seeded = pg.execute(
        "SELECT count(*) FROM audit_events WHERE action = 'catalog.seed' AND project_id = %s",
        (project_id,),
    )
    assert seeded.fetchone()[0] == 2


def test_01_seed_unknown_project_is_loud(database_url, pg, catalog, airgap):
    from ffcore.services.seed_models import SeedError

    with pytest.raises(SeedError, match="does not exist"):
        _seed(database_url, airgap, "no-such-project")


def test_01_teslimat_curl_chat_default(database_url, pg, catalog, airgap):
    key = _key()
    catalog.project(key)
    _seed(database_url, airgap, key)
    report = run_reconcile(database_url, airgap)
    assert sorted(report.created) == [f"{key}.chat-default", f"{key}.memory-extract"]

    response = httpx2.post(
        f"{airgap.litellm_url}/v1/chat/completions",
        headers={"Authorization": f"Bearer {airgap.litellm_internal_key.get_secret_value()}"},
        json={"model": f"{key}.chat-default", "messages": [{"role": "user", "content": "hi"}]},
        timeout=60,
    )

    assert response.status_code == 200, response.text
    assert response.json()["choices"][0]["message"]["content"] == "hello"
    assert SECRET_MARKER not in response.text
