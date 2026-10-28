"""Package 01: catalog events -> one background reconcile (S1, FOLLOWUP-56)."""

import asyncio
import logging

from ffcore.services.catalog_events import CatalogChanged
from ffcore.services.litellm_reconcile import ReconcileReport, ReconcileScheduler

CHANGE = CatalogChanged("model", "created", "m1", "p1")


def _scheduler(outcomes, delays=None):
    calls = []

    async def run():
        calls.append(len(calls))
        await asyncio.sleep(0.05)
        outcome = outcomes.pop(0) if outcomes else ReconcileReport()
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    return ReconcileScheduler(run, retries=3, base_delay=0.01), calls


def test_01_14_three_events_one_reconcile():
    async def go():
        scheduler, calls = _scheduler([])
        for _ in range(3):
            scheduler.on_change(CHANGE)
        await scheduler.wait_idle()
        return calls

    assert len(asyncio.run(go())) == 1


def test_01_14_event_during_run_runs_once_more():
    async def go():
        scheduler, calls = _scheduler([])
        scheduler.on_change(CHANGE)
        await asyncio.sleep(0.01)  # first run in progress
        scheduler.on_change(CHANGE)
        scheduler.on_change(CHANGE)
        await scheduler.wait_idle()
        return calls

    assert len(asyncio.run(go())) == 2


def test_01_14_failure_retried_with_backoff(caplog):
    async def go():
        scheduler, calls = _scheduler([RuntimeError("down"), ReconcileReport()])
        scheduler.on_change(CHANGE)
        await scheduler.wait_idle()
        return calls

    with caplog.at_level(logging.WARNING):
        assert len(asyncio.run(go())) == 2
    assert "litellm_reconcile_retry" in caplog.text
    assert "litellm_reconcile_failed" not in caplog.text


def test_01_14_gives_up_loudly(caplog):
    async def go():
        scheduler, calls = _scheduler([RuntimeError("down")] * 3)
        scheduler.on_change(CHANGE)
        await scheduler.wait_idle()
        return calls, scheduler.last_error

    with caplog.at_level(logging.ERROR):
        calls, last_error = asyncio.run(go())
    assert len(calls) == 3
    assert last_error == "RuntimeError"
    assert "litellm_reconcile_failed" in caplog.text


def test_01_14_listener_never_raises_without_loop(caplog):
    scheduler, calls = _scheduler([])
    with caplog.at_level(logging.ERROR):
        scheduler.on_change(CHANGE)  # no running event loop: logged, not raised
    assert calls == []
    assert "litellm_reconcile_not_scheduled" in caplog.text
