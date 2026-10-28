"""Package 02 / fix(01): an existing LiteLLM model is updated once, then the cost is the price."""

import asyncio
import dataclasses

import httpx2
import pytest

from ffcore.core.egress import EgressTimeout
from ffcore.services.litellm_client import litellm_settings
from ffcore.services.litellm_reconcile import LiteLLMAdmin, desired_state
from tests.integration.litellm_support import litellm_models, project_key, run_reconcile

pytestmark = pytest.mark.usefixtures("clean_litellm")
COST_KEYS = ("input_cost_per_token", "output_cost_per_token", "cache_read_input_token_cost")


def _write_pre_fix_deployment(database_url, settings):
    """What 01 wrote before the fix: prices only in model_info, the old hash."""
    from ffcore.core import db

    async def go():
        db.configure(database_url, pooled=False)
        try:
            async with db.session_scope() as session:
                (desired,), _ = await desired_state(session, settings)
        finally:
            db.reset()
        params = {k: v for k, v in desired.litellm_params.items() if k not in COST_KEYS}
        info = {**desired.model_info, "ffcore_hash": "pre-fix"}
        old = dataclasses.replace(desired, litellm_params=params, model_info=info)
        async with LiteLLMAdmin(litellm_settings(settings), settings) as admin:
            await admin.model_new(old)

    asyncio.run(go())


def test_02_7_existing_model_updated_once_then_cost_is_price(
    database_url, pg, catalog, llm_settings
):
    project_id = catalog.project()
    catalog.model(
        project_id,
        catalog.provider([project_id]),
        pricing='{"input_per_1m": 3, "output_per_1m": 15}',
    )
    _write_pre_fix_deployment(database_url, llm_settings)
    name = f"{project_key(pg, project_id)}.chat-default"
    assert litellm_models(llm_settings)[name]["model_info"]["ffcore_hash"] == "pre-fix"

    first = run_reconcile(database_url, llm_settings)
    second = run_reconcile(database_url, llm_settings)

    assert first.updated == [name] and not first.created and not first.deleted
    assert not second.changed
    response = httpx2.post(
        f"{llm_settings.litellm_url}/v1/chat/completions",
        headers={"Authorization": f"Bearer {llm_settings.litellm_internal_key.get_secret_value()}"},
        json={"model": name, "messages": [{"role": "user", "content": "hi"}]},
        timeout=EgressTimeout(connect=5, read=30, total=30).total,
    )
    assert response.status_code == 200, response.text
    # fake-llm usage: 3 prompt + 2 completion tokens; 3 * 3e-6 + 2 * 15e-6.
    assert float(response.headers["x-litellm-response-cost"]) == pytest.approx(3.9e-05)
