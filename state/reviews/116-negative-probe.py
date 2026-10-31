"""Reviewer's probes for fix/06a-checkpoint-sources (K-116-0004). Copied into
backend/tests/integration/ for one run, then removed. They reuse the branch's own fixtures.

1. Deleting an UNRELATED document leaves a live run alone (no false positive).
2. The live Redis stream carries no chunk text in ANY event of a finished run.
3. Measurement (no assertion on the residual): which stored event types still hold the chunk
   text after the run ends (FOLLOWUP-119)."""

import asyncio
import json
import uuid

from ffcore.runtime import checkpoints
from tests.integration.runtime_support import (
    Ports,
    ScriptedModel,
    ScriptedRetriever,
    definition,
    seed_run,
    source,
    stream,
    turn,
)
from tests.integration.test_116_checkpoint_sources import (  # noqa: F401 - fixtures and helpers
    CHUNK_TEXT,
    _deleted_at,
    _delete,
    _document,
    _hit,
    _thread_rows,
    _waiting_approval,
    world,
)
from tests.integration.runtime_support import events as stored_events


def _other_document(w) -> str:
    files = {"files": ("other.md", b"# Other\n\nunrelated-probe-text paragraph.\n", "text/markdown")}
    from tests.integration.test_116_checkpoint_sources import _kb_url, ingest, jobs

    response = w["admin"].post(_kb_url(w, f"/{w['kb']}/documents"), files=files)
    assert response.status_code == 202, response.text
    doc_id = response.json()["data"][0]["document"]["id"]

    async def drain():
        for function, *args in w["queue"].jobs:
            await ingest.ingest_document(
                uuid.UUID(args[0]),
                settings=w["settings"],
                store=jobs.get_vector_store(w["settings"]),
                embed_client=ingest.LocalEmbedClient(w["settings"]),
                convert=__import__("tests.converters", fromlist=["x"]).convert_without_weights,
            )
        w["queue"].jobs.clear()

    asyncio.run(drain())
    return doc_id


def test_rev_116_neg_1_unrelated_document_delete_leaves_waiting_run_alone(world, pg):
    shown = _document(world)
    run_id, _ = _waiting_approval(world, pg, shown)
    other = _other_document(world)
    _delete(world, other)  # a document the run never showed
    assert _deleted_at(pg, run_id)[1] is None, "unrelated delete marked a live run"
    assert _thread_rows(pg, run_id)["checkpoints"] > 0
    closed = asyncio.run(checkpoints.sweep(world["settings"]))
    assert str(run_id) not in closed["source_deleted"]


def test_rev_116_neg_2_stream_has_no_chunk_text_in_any_event(world, pg):
    d = definition(knowledge=[{"kb_key": "sozlesmeler", "mode": "tool", "top_k": 4}])
    run_id = seed_run(pg, world["project"], d)
    model = ScriptedModel(
        turn(tools=[("search_documents", {"query": "fesih", "kb_key": "sozlesmeler"})]),
        turn("30 gün [1]."),
    )
    hits = [source(text=CHUNK_TEXT)]
    assert world["harness"].run(run_id, Ports(model, ScriptedRetriever(hits))) == "completed"
    leaked = [kind for _, kind, data in stream(run_id) if CHUNK_TEXT in json.dumps(data, ensure_ascii=False)]
    assert leaked == [], leaked


def test_rev_116_neg_3_measure_stored_events_holding_chunk_text(world, pg, capsys):
    run_id = seed_run(pg, world["project"], definition())
    model = ScriptedModel(turn("Fesih süresi 30 gündür [1]."))
    hits = [source(text=CHUNK_TEXT)]
    assert world["harness"].run(run_id, Ports(model, ScriptedRetriever(hits))) == "completed"
    holding = sorted(
        {kind for _, kind, payload in stored_events(pg, run_id) if CHUNK_TEXT in json.dumps(payload, ensure_ascii=False)}
    )
    print("EVENT_TYPES_HOLDING_CHUNK_TEXT:", holding)
    assert "sources" not in holding
