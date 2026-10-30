"""FOLLOWUP-108: after its document is deleted, a run's `sources` event keeps the reference
(document id and name) and masks the breadcrumb as "[deleted]", on both read paths: the events
list and the stream replayed from Postgres. A live document keeps its breadcrumb."""

import asyncio
import os
import uuid
from dataclasses import replace

import redis.asyncio as aioredis

from tests.dummy import EMBED_DIM
from tests.integration.runs_fixtures import *  # noqa: F403 - fixtures
from tests.integration.runs_fixtures import InlineQueue, get_stream, post_run, publish
from tests.integration.runtime_support import (
    Ports,
    ScriptedModel,
    ScriptedRetriever,
    definition,
    source,
    turn,
)


def _document(pg, project_id) -> str:
    kb_id, doc_id = uuid.uuid4(), uuid.uuid4()
    pg.execute(
        "INSERT INTO knowledge_bases (id, project_id, key, name, embed_model, embed_dim,"
        " chunk_size, chunk_overlap, hybrid, rerank, rerank_model, default_top_k,"
        " normalizer_config_id, created_by) VALUES (%s, %s, %s, 'KB', 'BAAI/bge-m3', %s,"
        " 400, 0, true, true, 'BAAI/bge-reranker-v2-m3', 5, 'format-v1', 'test')",
        (kb_id, project_id, f"kb-{kb_id.hex[:8]}", EMBED_DIM),
    )
    pg.execute(
        "INSERT INTO documents (id, project_id, kb_id, filename, size, sha256, raw_path,"
        " created_by) VALUES (%s, %s, %s, 'prosedur.txt', 1, 'x', '/raw/x', 'test')",
        (doc_id, project_id, kb_id),
    )
    return str(doc_id)


def _selected(events) -> list[dict]:
    return [s for e in events if e["type"] == "sources" for s in e["payload"]["selected"]]


def _stream_sources(client, project_id, run_id) -> list[dict]:
    return [
        s
        for _, e, d in get_stream(client, project_id, run_id)
        if e == "sources"
        for s in d.get("selected") or d.get("sources") or []
    ]


def _deleted_run(analyst, pg, harness, use_queue):
    """A completed run whose only source is then deleted; the live Redis stream still exists."""
    project_id, client = analyst
    doc_id = _document(pg, project_id)
    hit = replace(source(), document_id=doc_id, document_name="prosedur.txt", breadcrumb="KB › M")
    publish(pg, project_id, definition())
    use_queue(InlineQueue(harness, Ports(ScriptedModel(turn("A [1].")), ScriptedRetriever([hit]))))
    run_id = post_run(client, project_id)[0][2]["run_id"]
    url = f"/api/v1/projects/{project_id}/runs/{run_id}/events"
    before = _selected(client.get(url).json()["items"])
    assert [s["breadcrumb"] for s in before] == ["KB › M"]
    assert [s["breadcrumb"] for s in _stream_sources(client, project_id, run_id)] == ["KB › M"]
    pg.execute("UPDATE documents SET deleted_at = now() WHERE id = %s", (doc_id,))
    return client, project_id, run_id, doc_id, url, before


def test_af_2b_deleted_source_masked_on_list_and_live_stream(analyst, pg, harness, use_queue):
    # Review r1 MAJOR-1: the Redis stream lives for RUN_EVENT_STREAM_TTL_S; it is not expired here.
    client, project_id, run_id, doc_id, url, before = _deleted_run(analyst, pg, harness, use_queue)
    gone = _selected(client.get(url).json()["items"])
    assert gone == [{**before[0], "breadcrumb": "[deleted]"}]  # reference kept, crumb masked
    live = _stream_sources(client, project_id, run_id)
    assert live and all(s["breadcrumb"] == "[deleted]" for s in live), live
    assert {s["document_id"] for s in live} == {doc_id}


def test_af_2b_deleted_source_masked_on_db_replay(analyst, pg, harness, use_queue):
    # The other stream path: after the TTL the run is replayed from run_events.
    client, project_id, run_id, doc_id, _, _ = _deleted_run(analyst, pg, harness, use_queue)

    async def expire():
        c = aioredis.from_url(os.environ["REDIS_URL"])
        await c.delete(f"run:{run_id}:events")
        await c.aclose()

    asyncio.run(expire())
    replayed = _stream_sources(client, project_id, run_id)
    assert replayed and all(
        s["breadcrumb"] == "[deleted]" and s["document_id"] == doc_id for s in replayed
    ), replayed
