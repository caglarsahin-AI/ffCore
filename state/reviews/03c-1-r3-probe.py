import asyncio, time
from ffcore.services import keys
from ffcore.services.litellm_reconcile import ReconcileScheduler

assert keys._clock is time.time, "default clock must be the real clock"
print("DEFAULT_CLOCK_IS_REAL: True")

async def caller_cancel():
    s = ReconcileScheduler.__new__(ReconcileScheduler)
    s._dirty = True
    async def slow():
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            await asyncio.sleep(0.2)
            raise
    s._task = asyncio.create_task(slow())
    outer = asyncio.create_task(s.stop())
    await asyncio.sleep(0.05)
    outer.cancel()
    try:
        await outer
    except asyncio.CancelledError:
        return "caller_cancel_reraised"
    return "caller_cancel_swallowed"

async def own_cancel_and_idempotent():
    s = ReconcileScheduler.__new__(ReconcileScheduler)
    s._dirty = True
    s._task = asyncio.create_task(asyncio.sleep(60))
    await s.stop()          # task's own cancellation swallowed
    await s.stop()          # idempotent
    return "own_cancel_swallowed_and_idempotent"

print(asyncio.run(caller_cancel()))
print(asyncio.run(own_cancel_and_idempotent()))
