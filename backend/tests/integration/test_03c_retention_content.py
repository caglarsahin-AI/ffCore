"""03c FOLLOWUP-119: the text a run left behind is cleared, place by place (tip tablosu,
K-03c-0004 condition 3), by a document delete and by the content class's 30 days."""

import asyncio
import json
import uuid

import pytest

from ffcore.core import db
from ffcore.services import retention
from tests.integration.runtime_support import definition, seed_run

DOC, OTHER_DOC = str(uuid.uuid4()), str(uuid.uuid4())
SECRET = "Madde 7 - fesih bildirimi 30 gün önce yazılı yapılır"


def _event(pg, run_id, seq, kind, payload):
    pg.execute(
        "INSERT INTO run_events (run_id, seq, type, payload) VALUES (%s, %s, %s, %s)",
        (run_id, seq, kind, json.dumps(payload)),
    )


def _finished_run(pg, project_id, document_id, *, status="completed"):
    run_id = seed_run(pg, project_id, definition(), question=f"Soru: {SECRET}", status=status)
    pg.execute(
        "UPDATE runs SET output = %s, ended_at = now() - interval '1 hour' WHERE id = %s",
        (f"Cevap: {SECRET}", run_id),
    )
    sources = {"selected": [{"n": 1, "document_id": document_id, "chunk_id": "c1"}]}
    _event(pg, run_id, 1, "sources", sources)
    _event(pg, run_id, 2, "llm_call", {"model": "m", "request_messages": [{"content": SECRET}]})
    _event(pg, run_id, 3, "question", {"question": f"{SECRET}?"})
    _event(pg, run_id, 4, "user_answer", {"tool_call_id": "t1"})
    _event(pg, run_id, 5, "tool_call", {"tool_call_id": "t2", "arguments": {"q": SECRET}})
    _event(pg, run_id, 6, "approval_requested", {"tool_call_id": "t2", "arguments": {"q": SECRET}})
    _event(pg, run_id, 7, "tool_result", {"tool_call_id": "t2", "chars": 120})
    _event(pg, run_id, 8, "answer", {"text": f"Cevap: {SECRET}", "outcome_label": "answered"})
    conversation = uuid.uuid4()
    pg.execute(
        "INSERT INTO conversations (id, project_id, agent_id, user_id, created_by)"
        " SELECT %s, project_id, agent_id, NULL, 't' FROM runs WHERE id = %s",
        (conversation, run_id),
    )
    pg.execute("UPDATE runs SET conversation_id = %s WHERE id = %s", (conversation, run_id))
    for role in ("user", "assistant"):
        pg.execute(
            "INSERT INTO messages (id, conversation_id, run_id, role, content)"
            " VALUES (%s, %s, %s, %s, %s)",
            (uuid.uuid4(), conversation, run_id, role, SECRET),
        )
    pg.execute(
        "INSERT INTO approvals (id, project_id, run_id, tool_call_id, action, arguments,"
        " args_hash, status, assigned_role, expires_at, resolved_at, created_by)"
        " SELECT %s, project_id, id, 't2', 'sql__run_sql', %s, %s, 'approved', 'analyst',"
        " now(), now(), 't' FROM runs WHERE id = %s",
        (uuid.uuid4(), json.dumps({"q": SECRET}), "a" * 64, run_id),
    )
    return run_id


def _clear(database_url, document_ids):
    async def go():
        db.configure(database_url, pooled=False)
        try:
            async with db.session_scope() as session:
                counts = await retention.clear_document_content(session, document_ids)
                await session.commit()
                return counts
        finally:
            db.reset()

    return asyncio.run(go())


def _payloads(pg, run_id):
    rows = pg.execute(
        "SELECT type, payload FROM run_events WHERE run_id = %s ORDER BY seq", (run_id,)
    ).fetchall()
    return dict(rows)


@pytest.fixture
def runs(pg, make_project, database_url):
    project = make_project()
    hit = _finished_run(pg, project, DOC)
    miss = _finished_run(pg, project, OTHER_DOC)
    counts = _clear(database_url, [DOC])
    return hit, miss, counts


@pytest.mark.parametrize(
    ("kind", "key", "cleared"),
    [
        ("llm_call", "request_messages", "[cleared]"),
        ("answer", "text", "[cleared]"),
        ("question", "question", "[cleared]"),
        ("tool_call", "arguments", {"_cleared": True}),
        ("approval_requested", "arguments", {"_cleared": True}),
    ],
)
def test_03c_13_event_text_cleared(pg, runs, kind, key, cleared):
    hit, _, counts = runs
    payload = _payloads(pg, hit)[kind]
    assert payload[key] == cleared
    assert counts[f"run_events.{kind}"] >= 1


def test_03c_13_metrics_and_textless_events_kept(pg, runs):
    hit, _, _ = runs
    payloads = _payloads(pg, hit)
    assert payloads["llm_call"]["model"] == "m"
    assert payloads["answer"]["outcome_label"] == "answered"
    assert payloads["tool_result"] == {"tool_call_id": "t2", "chars": 120}
    assert payloads["user_answer"] == {"tool_call_id": "t1"}
    assert payloads["sources"]["selected"][0]["document_id"] == DOC


def test_03c_13_run_message_approval_text_cleared(pg, runs):
    hit, _, _ = runs
    output, question, stamped = pg.execute(
        "SELECT output, input, content_cleared_at FROM runs WHERE id = %s", (hit,)
    ).fetchone()
    assert output == "[cleared]" and stamped is not None
    assert SECRET in question  # the user's own words go with the 30-day class, not here
    contents = dict(
        pg.execute("SELECT role, content FROM messages WHERE run_id = %s", (hit,)).fetchall()
    )
    assert contents == {"assistant": "[cleared]", "user": SECRET}
    arguments = pg.execute("SELECT arguments FROM approvals WHERE run_id = %s", (hit,)).fetchone()
    assert arguments == ({"_cleared": True},)


def test_03c_13_unrelated_runs_untouched(pg, runs):
    _, miss, _ = runs
    payloads = _payloads(pg, miss)
    assert payloads["answer"]["text"] == f"Cevap: {SECRET}"
    assert payloads["llm_call"]["request_messages"] == [{"content": SECRET}]
    assert pg.execute("SELECT content_cleared_at FROM runs WHERE id = %s", (miss,)).fetchone() == (
        None,
    )


def test_03c_13_no_text_left_anywhere(pg, runs):
    hit, _, _ = runs
    dump = pg.execute(
        "SELECT string_agg(payload::text, ' ') FROM run_events WHERE run_id = %s", (hit,)
    ).fetchone()[0]
    assert SECRET not in dump
    assert SECRET not in pg.execute("SELECT output FROM runs WHERE id = %s", (hit,)).fetchone()[0]


def test_03c_13_live_runs_left_to_116(pg, make_project, database_url):
    """A waiting run is not cleared here: 116 closes it source_deleted, then the sweep clears."""
    project = make_project()
    waiting = _finished_run(pg, project, DOC, status="waiting_user")
    _clear(database_url, [DOC])
    assert _payloads(pg, waiting)["answer"]["text"] == f"Cevap: {SECRET}"
    pg.execute(
        "UPDATE runs SET status = 'failed', error_code = 'source_deleted',"
        " source_deleted_at = now() WHERE id = %s",
        (waiting,),
    )

    async def sweep():
        db.configure(database_url, pooled=False)
        try:
            async with db.session_scope() as session:
                n = await retention.sweep_source_deleted(session)
                await session.commit()
                return n
        finally:
            db.reset()

    assert asyncio.run(sweep()) >= 1
    assert _payloads(pg, waiting)["answer"]["text"] == "[cleared]"


def test_03c_13_approval_audit_keeps_args_hash(database_url, pg, make_project):
    """K-03c-0011 (2): retention clears approvals.arguments; the decision's audit row keeps the
    hash of what was approved."""
    from tests.integration.test_07_decide import _audit, _decide
    from tests.integration.test_07_schema import _insert

    project = make_project()
    row = _insert(pg, project)
    _decide(database_url, project, row["id"])
    [(_, outcome, after)] = _audit(pg, row["id"], "approval.approved")
    stored = pg.execute("SELECT args_hash FROM approvals WHERE id = %s", (row["id"],)).fetchone()
    assert outcome == "success" and after["args_hash"] == stored[0]
