"""Reviewer's negative probe for fix/04a-06a-followups (K-AF-0004). Copied into backend/tests/integration/
for one run, then removed. Same setup as test_af_2b, but the Redis stream is NOT expired: a client that
reconnects while the live stream still exists must not get the deleted document's breadcrumb."""

import uuid
from dataclasses import replace

from tests.integration.runs_fixtures import InlineQueue, get_stream, post_run, publish
from tests.integration.runtime_support import Ports, ScriptedModel, ScriptedRetriever, definition, source, turn
from tests.integration.test_af_2b_deleted_source_breadcrumb import _document, _selected
from tests.integration.runs_fixtures import *  # noqa: F403 - fixtures


def test_rev_af_neg_1_deleted_source_masked_on_live_stream(analyst, pg, harness, use_queue):
    project_id, client = analyst
    doc_id = _document(pg, project_id)
    hit = replace(source(), document_id=doc_id, document_name="prosedur.txt", breadcrumb="KB › M")
    publish(pg, project_id, definition())
    use_queue(InlineQueue(harness, Ports(ScriptedModel(turn("A [1].")), ScriptedRetriever([hit]))))
    run_id = post_run(client, project_id)[0][2]["run_id"]
    pg.execute("UPDATE documents SET deleted_at = now() WHERE id = %s", (doc_id,))

    replayed = [
        s
        for _, e, d in get_stream(client, project_id, run_id)
        if e == "sources"
        for s in d.get("selected") or d.get("sources") or []
    ]
    assert replayed, "no sources event on the stream"
    assert all(s["breadcrumb"] == "[deleted]" for s in replayed), [s["breadcrumb"] for s in replayed]
