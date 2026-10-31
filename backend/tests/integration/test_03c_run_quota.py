"""03c: the quota gate around a run's model call (06a adapters) and the usage_daily row.

Real LiteLLM + fake provider (01). A blocking quota stops the run before the model is called
(`failed` / `quota_exceeded`, C9 additive error code; HTTP 429 is the facade's, 06b). A finished
call is counted once per LiteLLM call id and written to usage_daily with the cost LiteLLM itself
charges (U2: models.pricing x tokens).
"""

import asyncio
import os
import uuid
from decimal import Decimal

import pytest
import redis.asyncio as aioredis

from ffcore.core import db
from ffcore.runtime.adapters import LiteLLMModel
from ffcore.runtime.contracts import JobClass
from ffcore.runtime.scheduler import BackgroundWindow, LlmSlots, SlotSettings
from ffcore.runtime.state import StopRun
from ffcore.services import usage as usage_rows
from ffcore.services.quota import QuotaEngine, QuotaGate, Subject
from tests.integration.litellm_support import fake_requests, run_reconcile

pytestmark = pytest.mark.usefixtures("clean_litellm")
ALWAYS = BackgroundWindow.parse("", weekends_all_day=False, zone="UTC")
PRICED = '{"input_per_1m": 3000000, "output_per_1m": 15000000}'
MESSAGES = [{"role": "user", "content": "hi"}]


def _quota(pg, project_id, **parts):
    import json

    pg.execute(
        "INSERT INTO quotas (id, project_id, scope_type, scope_id, label, windows, tokens, budget,"
        " action, created_by) VALUES (%s, %s, 'project', %s, 't', %s, %s, %s, %s, 'test')",
        (
            uuid.uuid4(),
            project_id,
            project_id,
            json.dumps(parts.get("windows", {})),
            json.dumps(parts.get("tokens", {})),
            json.dumps(parts.get("budget", {})),
            parts.get("action", "block"),
        ),
    )


def _run(database_url, settings, project_id, user_id, *, calls=1, gate_hook=None):
    async def go():
        db.configure(database_url, pooled=False)
        client = aioredis.from_url(os.environ["REDIS_URL"])
        prefix = f"t03c:{uuid.uuid4().hex}"
        slots = LlmSlots(client, SlotSettings(slots=1), ALWAYS, prefix=f"{prefix}:slots")
        results = []
        try:
            async with db.session_scope() as session:
                gate = QuotaGate(
                    QuotaEngine(client, lease_ttl_s=60, prefix=prefix),
                    client,
                    session,
                    Subject(project_id=str(project_id), user_id=str(user_id)),
                )
                model = LiteLLMModel(
                    settings,
                    session,
                    slots,
                    run_id=uuid.uuid4(),
                    project_id=project_id,
                    user_id=user_id,
                    model_key="chat-default",
                    job_class=JobClass.interactive,
                    quota=gate,
                )
                for _ in range(calls):
                    try:
                        results.append(
                            await model.call(MESSAGES, tools=[], max_tokens=50, on_token=None)
                        )
                    except StopRun as stop:
                        results.append(stop)
                if gate_hook is not None:
                    results.append(await gate_hook(gate, client))
        finally:
            await client.aclose()
            db.reset()
        return results

    return asyncio.run(go())


def _usage(pg, project_id):
    return pg.execute(
        "SELECT model, api_key_id, user_id, input_tokens, output_tokens, cost_usd, requests,"
        " unpriced_requests FROM usage_daily WHERE project_id = %s",
        (project_id,),
    ).fetchall()


def test_03c_22_run_blocked_by_quota(database_url, pg, catalog, llm_settings):
    project_id = catalog.project()
    catalog.model(project_id, catalog.provider([project_id]), pricing=PRICED)
    run_reconcile(database_url, llm_settings)
    _quota(pg, project_id, budget={"monthly_usd": "0"})
    before = len(fake_requests())

    (stop,) = _run(database_url, llm_settings, project_id, uuid.uuid4())

    assert isinstance(stop, StopRun)
    assert (stop.status, stop.code) == ("failed", "quota_exceeded")
    assert stop.extra["limit"] == "monthly_usd" and stop.extra["detail"].startswith("project:")
    assert len(fake_requests()) == before  # the model was never called
    assert _usage(pg, project_id) == []


def test_03c_22_budget_stops_the_call_after_it(database_url, pg, catalog, llm_settings):
    """daily_usd 50: the first call (39 USD) runs, the second (78 > 50 after it) is refused."""
    project_id = catalog.project()
    catalog.model(project_id, catalog.provider([project_id]), pricing=PRICED)
    run_reconcile(database_url, llm_settings)
    _quota(pg, project_id, budget={"daily_usd": "50"})

    first, second, third = _run(database_url, llm_settings, project_id, uuid.uuid4(), calls=3)

    assert first.content == "hello" and second.content == "hello"
    assert isinstance(third, StopRun) and third.code == "quota_exceeded"


def test_03c_12_usage_row_cost_as_litellm(database_url, pg, catalog, llm_settings):
    project_id = catalog.project()
    catalog.model(project_id, catalog.provider([project_id]), pricing=PRICED)
    run_reconcile(database_url, llm_settings)
    user_id = uuid.uuid4()

    _run(database_url, llm_settings, project_id, user_id, calls=2)

    ((model, key, user, tokens_in, tokens_out, cost, requests, unpriced),) = _usage(pg, project_id)
    assert model.endswith(".chat-default") and key is None and user == str(user_id)
    assert (tokens_in, tokens_out, requests, unpriced) == (6, 4, 2, 0)
    # The U2 probe: LiteLLM charged 39.0 for one such call (x-litellm-response-cost).
    assert cost == Decimal(78)


def test_03c_12_commit_once_per_call_id(database_url, pg, catalog, llm_settings):
    project_id = catalog.project()
    catalog.model(project_id, catalog.provider([project_id]), pricing=PRICED)
    run_reconcile(database_url, llm_settings)
    _quota(pg, project_id, tokens={"tpd": 1000})
    model_id = pg.execute("SELECT id FROM models WHERE project_id = %s", (project_id,)).fetchone()[
        0
    ]
    call_id = str(uuid.uuid4())

    async def twice(gate, client):
        for _ in range(2):  # a retried commit of the same call
            await gate.commit(
                call_id=call_id,
                model_id=model_id,
                model_name="m",
                usage={"prompt_tokens": 3, "completion_tokens": 2},
            )
        return True

    _run(database_url, llm_settings, project_id, uuid.uuid4(), calls=0, gate_hook=twice)

    rows = [r for r in _usage(pg, project_id) if r[0] == "m"]
    assert len(rows) == 1 and rows[0][6] == 1 and rows[0][3:5] == (3, 2)


def test_03c_12_unpriced_call_flagged_not_zero(database_url, pg, catalog, llm_settings):
    project_id = catalog.project()
    catalog.model(project_id, catalog.provider([project_id]), pricing='{"input_per_1m": 3}')
    run_reconcile(database_url, llm_settings)

    _run(database_url, llm_settings, project_id, uuid.uuid4())

    ((*_, cost, requests, unpriced),) = _usage(pg, project_id)
    assert (requests, unpriced) == (1, 1)  # cost unknown is said, not hidden in a 0


def test_03c_12_usage_write_failure_counted(monkeypatch):
    """K-03c-0008 (2): a lost row never breaks the call and is counted."""

    class Broken:
        async def __aenter__(self):
            raise RuntimeError("db down")

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr(usage_rows.db, "session_scope", lambda: Broken())

    async def go():
        client = aioredis.from_url(os.environ["REDIS_URL"])
        try:
            before = int(await client.get(usage_rows.USAGE_WRITE_FAILED_KEY) or 0)
            ok = await usage_rows.record(
                project_id=uuid.uuid4(),
                model="m",
                api_key_id=None,
                user_id=None,
                input_tokens=1,
                output_tokens=1,
                cost_usd=Decimal(0),
                redis=client,
            )
            after = int(await client.get(usage_rows.USAGE_WRITE_FAILED_KEY) or 0)
        finally:
            await client.aclose()
        return ok, after - before

    assert asyncio.run(go()) == (False, 1)


def test_03c_12_spend_logs_store_no_prompts(database_url, pg, catalog, llm_settings, litellm_db):
    """K-03c-0004 condition 4: LiteLLM's spend log never keeps prompt or answer text."""
    from pathlib import Path

    import yaml

    config = Path(__file__).resolve().parents[3] / "deploy" / "litellm" / "config.yaml"
    general = yaml.safe_load(config.read_text(encoding="utf-8"))["general_settings"]
    assert general["store_prompts_in_spend_logs"] is False
    project_id = catalog.project()
    catalog.model(project_id, catalog.provider([project_id]), pricing=PRICED)
    run_reconcile(database_url, llm_settings)
    _run(database_url, llm_settings, project_id, uuid.uuid4())
    # LiteLLM writes spend rows in batches (r1 MINOR-1): wait for them, at most 30 s.
    import time

    deadline, rows = time.monotonic() + 30, []
    while time.monotonic() < deadline:
        rows = litellm_db.execute(
            'SELECT messages::text, response::text FROM "LiteLLM_SpendLogs"'
            ' ORDER BY "startTime" DESC LIMIT 5'
        ).fetchall()
        if rows:
            break
        time.sleep(0.5)
    assert rows, "LiteLLM wrote no spend row within 30 s (batched spend writer)"
    assert all(m in ("{}", "[]", "null", None) and r in ("{}", "null", None) for m, r in rows)
