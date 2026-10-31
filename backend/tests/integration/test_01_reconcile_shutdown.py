"""FOLLOWUP-90 (K-03c-0014): the app's shutdown stops its LiteLLM reconcile task, so a reconcile
cut short never leaves a connection idle in a transaction (that held catalog locks and blocked
test_03a_schema's migration round; state/evidence/03c-1-r2b-hang-activity-20261031.log).
"""

import asyncio
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import make_url

from ffcore.services import litellm_reconcile
from tests.integration.conftest import CONSOLE_ORIGIN


def _idle_in_transaction(pg, database_url) -> int:
    name = make_url(database_url).database
    return pg.execute(
        "SELECT count(*) FROM pg_stat_activity WHERE datname = %s"
        " AND state = 'idle in transaction'",
        (name,),
    ).fetchone()[0]


def test_01_shutdown_leaves_no_open_transaction(app, pg, database_url, app_settings, monkeypatch):
    if not app_settings.litellm_url:
        pytest.fail("LITELLM_URL is not set; run in the tools container with .env.test")
    started = []

    async def slow_reconcile(session, settings):
        # Like _desired: a catalog read inside the session, then a long wait (LiteLLM, retries).
        await session.execute(text("SELECT 1 FROM projects LIMIT 1"))
        started.append(True)
        await asyncio.sleep(60)

    monkeypatch.setattr(litellm_reconcile, "reconcile", slow_reconcile)
    client = TestClient(app, base_url=CONSOLE_ORIGIN)
    client.__enter__()
    deadline = time.monotonic() + 10
    while not started and time.monotonic() < deadline:
        client.get("/healthz")
        time.sleep(0.1)
    assert started, "the reconcile task did not start"
    task = app.state.litellm_scheduler._task
    client.__exit__(None, None, None)  # lifespan shutdown
    # The root cause: the task outlived the shutdown (destroyed pending with its loop, its
    # session never rolled back). After the fix it is cancelled and awaited inside lifespan.
    assert task is not None and task.done()
    time.sleep(1)
    assert _idle_in_transaction(pg, database_url) == 0


def test_01_scheduler_stop_idempotent_and_loud():
    async def go():
        async def run():
            await asyncio.sleep(60)

        scheduler = litellm_reconcile.ReconcileScheduler(run)
        await scheduler.stop()  # never started: nothing to do
        scheduler.on_change()
        await asyncio.sleep(0)
        await scheduler.stop()
        await scheduler.stop()  # twice: no error

        async def broken():
            raise RuntimeError("boom")

        failing = litellm_reconcile.ReconcileScheduler(broken, retries=1)
        failing.on_change()
        await asyncio.sleep(0.05)
        await failing.stop()  # the task logged and ended; stop only waits for it

    asyncio.run(go())
