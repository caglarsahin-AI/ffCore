"""Run events: durable rows in `run_events`, live delivery through a Redis Stream (K-06a-0002 S2).

The worker writes each event once: a `run_events` row with the next `seq` and, when it is shown
to the client, a stream entry with id `<seq>-0`. Tokens are live only (the final `answer` row
holds the text): they get ids `<seq>-<n>` after the last row, so the stream stays ordered and an
SSE `Last-Event-ID` points at a position in it.

A reader replays the stream from the start or after `Last-Event-ID`, then follows it live until
a terminal event. When the stream has expired (RUN_EVENT_STREAM_TTL_S) it replays from
`run_events` instead, and says so with a `progress` event: no silent gap.

Listeners: every reader refreshes `run:<id>:listening` (expiry RUN_ABANDON_GRACE_S); the worker
checks it at each step boundary, and a running run with nobody listening is `abandoned`
(K-06a-0002 S8). Closing the stream never cancels a run.
"""

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import redis.asyncio as aioredis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ffcore.core.config import Settings
from ffcore.core.errors import ApiError
from ffcore.guardrails.masking import RevealUnavailable
from ffcore.models.runs import RunEvent
from ffcore.runtime.contracts import TERMINAL_SSE, RunEventType, SseEvent

# Stored event type -> what the client sees when the run is replayed from Postgres.
REPLAY_SSE = {
    RunEventType.tool_call: SseEvent.tool_call,
    RunEventType.tool_result: SseEvent.tool_result,
    RunEventType.approval_requested: SseEvent.approval_required,
    RunEventType.question: SseEvent.question,
    RunEventType.sources: SseEvent.sources,
    RunEventType.progress: SseEvent.progress,
    RunEventType.fallback: SseEvent.fallback,
    RunEventType.answer: SseEvent.token,
    RunEventType.error: SseEvent.error,
}


def redis_client(settings: Settings):
    if settings.redis_url is None:
        raise ApiError(
            503, "api_error", "redis_unavailable", "The run event stream is not configured."
        )
    return aioredis.from_url(settings.redis_url.get_secret_value())


def stream_key(run_id) -> str:
    return f"run:{run_id}:events"


def listening_key(run_id) -> str:
    return f"run:{run_id}:listening"


@dataclass(frozen=True)
class SseMessage:
    id: str
    event: str
    data: dict[str, Any]

    def render(self) -> str:
        body = json.dumps(self.data, ensure_ascii=False, separators=(",", ":"))
        return f"id: {self.id}\nevent: {self.event}\ndata: {body}\n\n"


class RunEventWriter:
    """Used by the worker; one per run attempt. `seq` continues after rows already written (a
    resumed run keeps its numbering)."""

    def __init__(self, session: AsyncSession, redis, run_id, *, ttl_s: int) -> None:
        self._session = session
        self._redis = redis
        self._run_id = run_id
        self._ttl_s = ttl_s
        self._seq = 0
        self._token = 0

    async def start(self) -> None:
        self._seq = await self._session.scalar(
            select(func.coalesce(func.max(RunEvent.seq), 0)).where(RunEvent.run_id == self._run_id)
        )
        # An earlier attempt may have streamed tokens after the last row (`<seq>-<n>`): continue
        # after them, the stream only accepts growing ids.
        top = await self._redis.xrevrange(stream_key(self._run_id), count=1)
        if top:
            seq, token = (int(part) for part in _decode(top[0][0]).split("-"))
            if seq == self._seq:
                self._token = token

    @property
    def seq(self) -> int:
        return self._seq

    async def record(
        self,
        type_: RunEventType,
        payload: dict[str, Any],
        *,
        sse: SseEvent | None = None,
        sse_data: dict[str, Any] | None = None,
        iteration: int | None = None,
    ) -> int:
        """Write the row (committed, so readers and a crash see it) and, with `sse`, the live
        entry. `sse_data` is what the client gets; default: the payload."""
        self._seq += 1
        self._token = 0
        self._session.add(
            RunEvent(
                run_id=self._run_id,
                seq=self._seq,
                type=type_.value,
                iteration=iteration,
                payload=payload,
            )
        )
        await self._session.commit()
        if sse is not None:
            await self._publish(f"{self._seq}-0", sse, payload if sse_data is None else sse_data)
        return self._seq

    async def live(self, sse: SseEvent, data: dict[str, Any]) -> None:
        """A live-only entry (tokens, done): no row, ordered after the last row."""
        self._token += 1
        await self._publish(f"{self._seq}-{self._token}", sse, data)

    async def _publish(self, entry_id: str, sse: SseEvent, data: dict[str, Any]) -> None:
        key = stream_key(self._run_id)
        await self._redis.xadd(
            key, {"event": sse.value, "data": json.dumps(data, ensure_ascii=False)}, id=entry_id
        )
        await self._redis.expire(key, self._ttl_s)


async def mark_listening(redis, run_id, grace_s: int) -> None:
    await redis.set(listening_key(run_id), "1", ex=grace_s)


async def is_listened(redis, run_id) -> bool:
    return bool(await redis.exists(listening_key(run_id)))


def _decode(value) -> str:
    return value.decode() if isinstance(value, bytes) else value


def _reveal_unavailable(last: str) -> str:
    """C17 r1 MINOR-11: the reader's placeholders could not be reversed (token store down): the
    stream ends with a coded error (the run itself goes on; a reconnect continues after `last`)."""
    return SseMessage(
        last,
        SseEvent.error,
        {
            "code": "detokenize_unavailable",
            "status": None,
            "message": "The answer could not be prepared for this reader; reconnect to continue.",
        },
    ).render()


async def follow(
    redis,
    run_id,
    *,
    after: str | None,
    keepalive_s: float,
    grace_s: int,
    replay_rows,
    finished,
    transform=None,
) -> AsyncIterator[str]:
    """SSE text for one client. `after`: the client's Last-Event-ID. `replay_rows(after_seq)`
    returns stored rows when the live stream is gone; it ends with the run's final SSE event.

    `finished()` says whether the run has ended in Postgres. A writer commits a row before it
    publishes the live entry, so a failed publish (Redis error) leaves an ended run whose last
    events are only stored: on an empty keepalive turn of an ended run, the stored rows after
    the last entry seen are given and the stream stops (FOLLOWUP-104), never a silent wait.

    `transform(event, data)`, when given, returns the data to send for each live entry (the
    caller's read-time masks, FOLLOWUP-108); stored rows, the replay and the stored-only ending
    alike, get theirs in `replay_rows`."""
    key = stream_key(run_id)
    last = after or "0-0"
    ended_seen = False
    if not await redis.exists(key):
        after_seq = int(last.split("-")[0])
        yield SseMessage(
            f"{after_seq}-0", SseEvent.progress, {"replay": "run_events", "run_id": str(run_id)}
        ).render()
        try:
            async for message in replay_rows(after_seq):
                yield message.render()
        except RevealUnavailable:
            yield _reveal_unavailable(f"{after_seq}-0")
        return
    while True:
        await mark_listening(redis, run_id, grace_s)
        result = await redis.xread({key: last}, block=int(keepalive_s * 1000), count=100)
        if not result:
            yield ": keepalive\n\n"
            if await finished():
                if ended_seen:
                    try:
                        async for message in replay_rows(int(last.split("-")[0])):
                            yield message.render()
                    except RevealUnavailable:
                        yield _reveal_unavailable(last)
                    return
                # The writer publishes right after its commit: give it one more turn, so a
                # normal ending arrives live (tokens are not given twice by a replay).
                ended_seen = True
            continue
        for _, entries in result:
            for entry_id, fields in entries:
                last = _decode(entry_id)
                event = _decode(fields[b"event"] if b"event" in fields else fields["event"])
                raw = fields[b"data"] if b"data" in fields else fields["data"]
                data = json.loads(_decode(raw))
                if transform is not None:
                    try:
                        data = await transform(event, data)
                    except RevealUnavailable:
                        yield _reveal_unavailable(last)
                        return
                yield SseMessage(last, event, data).render()
                if event in TERMINAL_SSE:
                    return
