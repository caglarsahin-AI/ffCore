"""FOLLOWUP-104: a terminal event that reached `run_events` but not the live stream.

A writer commits the row before it publishes the stream entry (runtime/events.py); when the
publish fails (Redis error after the first event), the run is already ended in Postgres but a
reader following the live stream saw nothing. `follow()` now checks, on each empty keepalive
turn, whether the run has ended and then gives the remaining stored rows and stops.
"""

import asyncio
import json

from ffcore.runtime import events as run_events
from ffcore.runtime.contracts import SseEvent


class FakeRedis:
    """The calls `follow()` makes: a stream with fixed entries, then empty reads."""

    def __init__(self, entries):
        self.entries = entries
        self.reads = 0

    async def exists(self, key):
        return 1

    async def set(self, key, value, ex=None):
        return True

    async def xread(self, streams, block=None, count=None):
        self.reads += 1
        if self.entries:
            batch, self.entries = self.entries, []
            return [(b"run:x:events", batch)]
        return []


def _entry(entry_id, event, data):
    return (entry_id.encode(), {b"event": event.encode(), b"data": json.dumps(data).encode()})


def _collect(redis, *, finished, replay_rows, limit=20):
    async def run():
        out = []
        async for chunk in run_events.follow(
            redis,
            "x",
            after=None,
            keepalive_s=0.01,
            grace_s=60,
            replay_rows=replay_rows,
            finished=finished,
        ):
            out.append(chunk)
            if len(out) >= limit:
                break
        return out

    return asyncio.run(run())


def _replay(seen):
    async def rows(after_seq):
        seen.append(after_seq)
        yield run_events.SseMessage(
            f"{after_seq + 1}-0", SseEvent.error, {"code": "approval_expired"}
        )

    return rows


def test_07f_1_follow_ends_from_db_when_live_entry_lost():
    redis = FakeRedis([_entry("2-0", "progress", {"step": "x"})])
    seen = []

    async def finished():
        return True

    chunks = _collect(redis, finished=finished, replay_rows=_replay(seen))
    assert chunks[0].startswith("id: 2-0\nevent: progress")
    assert chunks[-1].startswith("id: 3-0\nevent: error")
    assert seen == [2]  # stored rows after the last entry the client saw
    # entry, two empty turns (the first leaves the writer time to publish), the stored error
    assert len(chunks) == 4


def test_07f_1_follow_prefers_live_entry_published_after_commit():
    # The run ended in Postgres, its entry reaches the stream one turn later: given live, once,
    # no replay.
    late = _entry("3-0", "error", {"code": "approval_expired"})
    redis = FakeRedis([])
    seen = []

    async def finished():
        redis.entries = [late]  # published right after the commit the check just saw
        return True

    chunks = _collect(redis, finished=finished, replay_rows=_replay(seen))
    assert chunks == [": keepalive\n\n", chunks[1]]
    assert chunks[1].startswith("id: 3-0\nevent: error")
    assert seen == []


def test_07f_1_follow_keeps_waiting_while_run_is_live():
    redis = FakeRedis([])
    seen = []
    calls = {"n": 0}

    async def finished():
        calls["n"] += 1
        return False

    chunks = _collect(redis, finished=finished, replay_rows=_replay(seen), limit=3)
    assert chunks == [": keepalive\n\n"] * 3
    assert seen == [] and calls["n"] >= 2  # checked after each empty turn but the last
