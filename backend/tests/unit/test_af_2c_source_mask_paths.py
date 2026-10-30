"""FOLLOWUP-108 review r1 MAJOR-1: one mask for every path that hands a `sources` event to a
client. The stored payload (`selected`) and the live SSE payload (`sources`) are masked by the same
function, and the Redis stream path applies it to each event it yields."""

import asyncio
import json

from ffcore.api.runs import DELETED_BREADCRUMB, masked_sources
from ffcore.runtime import events

ALIVE, GONE = "11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222"


def _hit(doc_id: str) -> dict:
    return {"n": 1, "document_id": doc_id, "document_name": "a.txt", "breadcrumb": "KB › M"}


def test_af_2c_mask_covers_stored_and_live_shapes():
    for key in ("selected", "sources"):
        payload = {key: [_hit(ALIVE), _hit(GONE)], "tool": "search"}
        out = masked_sources(payload, alive={ALIVE})
        assert [s["breadcrumb"] for s in out[key]] == ["KB › M", DELETED_BREADCRUMB]
        assert [s["document_id"] for s in out[key]] == [ALIVE, GONE]  # reference kept
        assert out["tool"] == "search"
        assert payload[key][1]["breadcrumb"] == "KB › M"  # the input is not changed


class _Stream:
    """The two Redis calls `follow` makes on a live stream, with one sources and one done entry."""

    def __init__(self, entries):
        self.entries = entries

    async def exists(self, key):
        return 1

    async def set(self, *args, **kwargs):
        return True

    async def xread(self, streams, block, count):
        entries, self.entries = self.entries, []
        return [(b"run:x:events", entries)] if entries else []


async def _never_finished() -> bool:
    return False


def test_af_2c_live_stream_events_pass_the_transform():
    sources = {"sources": [_hit(GONE)]}
    redis = _Stream(
        [
            (b"1-0", {b"event": b"sources", b"data": json.dumps(sources).encode()}),
            (b"2-0", {b"event": b"done", b"data": b"{}"}),
        ]
    )
    seen = []

    async def transform(event, data):
        seen.append(event)
        return masked_sources(data, alive=set()) if event == "sources" else data

    async def collect():
        return [
            chunk
            async for chunk in events.follow(
                redis,
                "x",
                after=None,
                keepalive_s=0.01,
                grace_s=1,
                replay_rows=None,
                finished=_never_finished,
                transform=transform,
            )
        ]

    chunks = asyncio.run(collect())
    assert seen == ["sources", "done"]
    assert DELETED_BREADCRUMB in chunks[0] and "KB › M" not in chunks[0]
