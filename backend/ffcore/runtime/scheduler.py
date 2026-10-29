"""Model call slot (`LLM_SLOTS`) with three classes and the background window (C10, brief 06 P7).

Every single model call of every worker goes through one Redis slot pool: on CPU one call at a
time (`LLM_SLOTS=1`), on GPU or a provider N. A free slot goes to the waiter with the best class,
then the earliest arrival: interactive, then interactive-low, then background. Background waiters
are only served inside `BACKGROUND_WINDOW` (a profile value: airgap cpu `19:00-07:00`, elsewhere
empty = always), unless the run was explicitly started with "run now". A running call is never
interrupted; the next call waits (a call is atomic).

The pool is two sorted sets: holders (score = lease expiry, a crashed worker's slot frees itself
when its lease ends; the holder renews while the call runs) and waiters (score = class rank, then
arrival). A waiter keeps a short-lived key alive while it polls; a waiter whose process died
drops out instead of blocking the line. One Lua script decides atomically.
"""

import asyncio
import contextlib
import re
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from datetime import time as dtime
from zoneinfo import ZoneInfo

from ffcore.runtime.contracts import JobClass

RANK = {JobClass.interactive: 0, JobClass.interactive_low: 1, JobClass.background: 2}
RANK_SPAN = 10**13  # ms timestamps stay below this, so the rank always dominates
WINDOW_PATTERN = re.compile(r"(\d{2}:\d{2})-(\d{2}:\d{2})")

PREFIX = "llm_slots"

_ACQUIRE = """
local holders, waiters, alive_prefix = KEYS[1], KEYS[2], KEYS[3]
local now, slots, me, lease_until, allow_bg = tonumber(ARGV[1]), tonumber(ARGV[2]), ARGV[3],
    tonumber(ARGV[4]), ARGV[5]
redis.call('ZREMRANGEBYSCORE', holders, '-inf', now)
if redis.call('ZCARD', holders) >= slots then return 0 end
for _ = 1, 64 do
  local first = redis.call('ZRANGE', waiters, 0, 0)[1]
  if not first then return 0 end
  if redis.call('EXISTS', alive_prefix .. first) == 0 then
    redis.call('ZREM', waiters, first)
  else
    if first ~= me then return 0 end
    if string.sub(me, 1, 2) == 'b:' and allow_bg ~= '1' then return 0 end
    redis.call('ZREM', waiters, me)
    redis.call('ZADD', holders, lease_until, me)
    return 1
  end
end
return 0
"""


class BackgroundWindowError(ValueError):
    pass


@dataclass(frozen=True)
class BackgroundWindow:
    """`HH:MM-HH:MM` in the given zone (may wrap midnight), optionally all day on weekends.
    No window (empty value) means background work may run any time."""

    start: dtime | None
    end: dtime | None
    weekends_all_day: bool
    zone: ZoneInfo

    @classmethod
    def parse(cls, value: str, *, weekends_all_day: bool, zone: str) -> "BackgroundWindow":
        try:
            tz = ZoneInfo(zone)
        except Exception as exc:  # noqa: BLE001 - any lookup failure is a config error
            raise BackgroundWindowError(f"unknown time zone {zone!r}") from exc
        value = value.strip()
        if not value:
            return cls(None, None, weekends_all_day, tz)
        match = WINDOW_PATTERN.fullmatch(value)
        try:
            if match is None:
                raise ValueError(value)
            start, end = dtime.fromisoformat(match[1]), dtime.fromisoformat(match[2])
        except ValueError:
            raise BackgroundWindowError(
                f"BACKGROUND_WINDOW must be HH:MM-HH:MM or empty, not {value!r}"
            ) from None
        if start == end:
            raise BackgroundWindowError("BACKGROUND_WINDOW start and end are equal")
        return cls(start, end, weekends_all_day, tz)

    def is_open(self, at: datetime | None = None) -> bool:
        if self.start is None:
            return True
        now = (at or datetime.now(self.zone)).astimezone(self.zone)
        if self.weekends_all_day and now.weekday() >= 5:
            return True
        t = now.time()
        if self.start < self.end:
            return self.start <= t < self.end
        return t >= self.start or t < self.end


@dataclass(frozen=True)
class SlotSettings:
    slots: int
    lease_s: float = 60.0
    poll_s: float = 0.1
    alive_s: float = 5.0


class LlmSlots:
    """`async with slots.acquire(JobClass.interactive): <one model call>`."""

    def __init__(
        self, redis, settings: SlotSettings, window: BackgroundWindow, *, prefix: str = PREFIX
    ) -> None:
        if settings.slots < 1:
            raise ValueError("LLM_SLOTS must be at least 1")
        self._holders, self._waiters = f"{prefix}:holders", f"{prefix}:waiters"
        self._alive = f"{prefix}:alive:"
        self._redis = redis
        self._settings = settings
        self._window = window
        self._script = redis.register_script(_ACQUIRE)

    def _member(self, job_class: JobClass) -> str:
        prefix = {JobClass.interactive: "i:", JobClass.interactive_low: "l:"}.get(job_class, "b:")
        return prefix + uuid.uuid4().hex

    @contextlib.asynccontextmanager
    async def acquire(self, job_class: JobClass, *, run_now: bool = False) -> AsyncIterator[float]:
        """Yields the seconds spent waiting. `run_now`: an admin's explicit "run now" lets a
        background job ignore the window (it still waits behind interactive work)."""
        s = self._settings
        me = self._member(job_class)
        started = time.monotonic()
        score = RANK[job_class] * RANK_SPAN + int(time.time() * 1000)
        await self._redis.set(self._alive + me, "1", px=int(s.alive_s * 1000))
        await self._redis.zadd(self._waiters, {me: score})
        try:
            while True:
                allow_bg = "1" if run_now or self._window.is_open() else "0"
                now = time.time()
                granted = await self._script(
                    keys=[self._holders, self._waiters, self._alive],
                    args=[now, s.slots, me, now + s.lease_s, allow_bg],
                )
                if granted == 1:
                    break
                await self._redis.set(self._alive + me, "1", px=int(s.alive_s * 1000))
                await asyncio.sleep(s.poll_s)
        except BaseException:
            await self._redis.zrem(self._waiters, me)
            await self._redis.delete(self._alive + me)
            raise
        await self._redis.delete(self._alive + me)
        renew = asyncio.create_task(self._renew(me))
        try:
            yield time.monotonic() - started
        finally:
            renew.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await renew
            await self._redis.zrem(self._holders, me)

    async def _renew(self, me: str) -> None:
        s = self._settings
        while True:
            await asyncio.sleep(s.lease_s / 3)
            await self._redis.zadd(self._holders, {me: time.time() + s.lease_s}, xx=True)

    async def status(self) -> dict:
        """Holders and waiters per class, for /readyz and the system status screen."""
        now = time.time()
        holders = await self._redis.zrangebyscore(self._holders, now, "+inf")
        waiters = await self._redis.zrange(self._waiters, 0, -1)
        counts = {"interactive": 0, "interactive_low": 0, "background": 0}
        names = {"i": "interactive", "l": "interactive_low", "b": "background"}
        for member in waiters:
            key = member.decode() if isinstance(member, bytes) else member
            counts[names[key[0]]] += 1
        return {
            "slots": self._settings.slots,
            "in_use": len(holders),
            "waiting": counts,
            "background_window_open": self._window.is_open(),
        }
