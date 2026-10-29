"""06a acceptance 10: the LLM_SLOTS pool on the compose Redis (C10)."""

import asyncio
import os
import time
import uuid
from datetime import datetime

import pytest
import redis.asyncio as aioredis

from ffcore.runtime.contracts import JobClass
from ffcore.runtime.scheduler import BackgroundWindow, BackgroundWindowError, LlmSlots, SlotSettings

ALWAYS = BackgroundWindow.parse("", weekends_all_day=False, zone="UTC")


def with_redis(test):
    """No async test plugin in this project (04a pattern): each test runs its own loop."""

    def run():
        url = os.environ.get("REDIS_URL")
        if not url:
            pytest.fail("REDIS_URL is not set; run in the tools container with redis up")

        async def main():
            client = aioredis.from_url(url)
            try:
                await test(client)
            finally:
                await client.aclose()

        asyncio.run(main())

    run.__name__ = test.__name__
    return run


def _slots(redis, n=1, window=ALWAYS, **kw):
    return LlmSlots(
        redis, SlotSettings(slots=n, poll_s=0.02, **kw), window, prefix=f"t06a:{uuid.uuid4().hex}"
    )


@with_redis
async def test_06a_10a_slot_exclusive(redis):
    slots = _slots(redis, 1)
    inside, peak = 0, 0

    async def call():
        nonlocal inside, peak
        async with slots.acquire(JobClass.interactive):
            inside += 1
            peak = max(peak, inside)
            await asyncio.sleep(0.1)
            inside -= 1

    await asyncio.gather(*(call() for _ in range(4)))
    assert peak == 1


@with_redis
async def test_06a_10a_n_slots_allow_n(redis):
    slots = _slots(redis, 2)
    inside, peak = 0, 0

    async def call():
        nonlocal inside, peak
        async with slots.acquire(JobClass.interactive):
            inside += 1
            peak = max(peak, inside)
            await asyncio.sleep(0.15)
            inside -= 1

    await asyncio.gather(*(call() for _ in range(4)))
    assert peak == 2


@with_redis
async def test_06a_10b_interactive_first(redis):
    slots = _slots(redis, 1)
    order: list[str] = []

    async def call(name, cls, delay):
        await asyncio.sleep(delay)
        async with slots.acquire(cls):
            order.append(name)
            await asyncio.sleep(0.05)

    async with slots.acquire(JobClass.interactive):
        # Background and low queue up first, the interactive call arrives last.
        tasks = [
            asyncio.create_task(call("background", JobClass.background, 0)),
            asyncio.create_task(call("low", JobClass.interactive_low, 0.02)),
            asyncio.create_task(call("interactive", JobClass.interactive, 0.04)),
        ]
        await asyncio.sleep(0.2)
    await asyncio.gather(*tasks)
    assert order == ["interactive", "low", "background"]


@with_redis
async def test_06a_10c_background_waits_outside_window(redis):
    now = datetime.now(BackgroundWindow.parse("", weekends_all_day=False, zone="UTC").zone)
    closed_start = (now.hour + 2) % 24
    window = BackgroundWindow.parse(
        f"{closed_start:02d}:00-{(closed_start + 1) % 24:02d}:00",
        weekends_all_day=False,
        zone="UTC",
    )
    assert not window.is_open(now)
    slots = _slots(redis, 1, window)
    with pytest.raises(TimeoutError):
        async with asyncio.timeout(0.3):
            async with slots.acquire(JobClass.background):
                pass
    # An explicit "run now" goes in (behind interactive work, which is absent here).
    async with asyncio.timeout(1):
        async with slots.acquire(JobClass.background, run_now=True):
            pass
    status = await slots.status()
    assert status["waiting"]["background"] == 0, "a cancelled waiter must leave the line"


@with_redis
async def test_06a_10c_dead_waiter_does_not_block(redis):
    slots = _slots(redis, 1, alive_s=0.2)
    # A waiter whose process died: in the line, no alive key.
    await redis.zadd(slots._waiters, {"i:dead": 0})
    async with asyncio.timeout(2):
        async with slots.acquire(JobClass.interactive):
            pass


@with_redis
async def test_06a_10c_crashed_holder_frees_after_lease(redis):
    slots = _slots(redis, 1, lease_s=0.3)
    await redis.zadd(slots._holders, {"i:crashed": time.time() + 0.3})
    started = time.monotonic()
    async with slots.acquire(JobClass.interactive):
        pass
    assert 0.2 < time.monotonic() - started < 2


def test_06a_10c_window_parsing():
    w = BackgroundWindow.parse("19:00-07:00", weekends_all_day=True, zone="UTC")
    tz = w.zone
    assert w.is_open(datetime(2026, 10, 28, 20, 0, tzinfo=tz))  # Wednesday evening
    assert w.is_open(datetime(2026, 10, 28, 6, 59, tzinfo=tz))
    assert not w.is_open(datetime(2026, 10, 28, 12, 0, tzinfo=tz))
    assert w.is_open(datetime(2026, 10, 31, 12, 0, tzinfo=tz))  # Saturday noon
    for bad in ("19-07", "07:00-07:00", "yes"):
        with pytest.raises(BackgroundWindowError):
            BackgroundWindow.parse(bad, weekends_all_day=False, zone="UTC")
