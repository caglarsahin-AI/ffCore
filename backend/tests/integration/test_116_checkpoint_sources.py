"""FOLLOWUP-116 (K-116-0002): chunk text does not outlive a run in the LangGraph checkpoint.

A finished run's checkpoint thread is deleted (at the end, and by the sweep for ends outside
the runner); a live run whose source document is deleted ends `failed` / `source_deleted`
instead of going on with the deleted text. Real graph, runner, Postgres checkpointer and Redis;
the document is deleted through the 04a API.
"""

import asyncio
import json
import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import SecretStr

from ffcore.api.knowledge import queue_dependency
from ffcore.knowledge import ingest, jobs
from ffcore.runtime import checkpoints
from ffcore.runtime.state import ToolOutcome
from tests.converters import convert_without_weights
from tests.integration.runtime_support import (
    Harness,
    Ports,
    ScriptedModel,
    ScriptedRetriever,
    ScriptedTools,
    definition,
    events,
    run_row,
    seed_run,
    setup,
    source,
    stream,
    turn,
)

API = "/api/v1"
CHUNK_TEXT = "gizli-parca-116 fesih bildirimi otuz gun"
SQL_TOOL = "mcp-sql__run_sql"
SQL_SCHEMA = [
    {"type": "function", "function": {"name": SQL_TOOL, "parameters": {"type": "object"}}}
]
TABLES = ("checkpoints", "checkpoint_blobs", "checkpoint_writes")


class FakeQueue:
    def __init__(self):
        self.jobs = []

    async def enqueue(self, function, *args):
        self.jobs.append((function, *args))
        return f"job-{len(self.jobs)}"


@pytest.fixture
def world(app, app_settings, database_url, tmp_path, make_user, make_project, client_factory):
    from ffcore.core.config import get_settings

    settings = app_settings.model_copy(
        update={
            "fake_embed": True,
            "knowledge_storage_dir": str(tmp_path / "storage"),
            "database_url": SecretStr(database_url),
            "redis_url": SecretStr(os.environ["REDIS_URL"]),
        }
    )
    app.dependency_overrides[get_settings] = lambda: settings
    queue = FakeQueue()
    app.dependency_overrides[queue_dependency] = lambda: queue
    setup(database_url)
    project = make_project()
    _, admin = make_user(memberships={project: ("admin", "edit")})
    w = {"settings": settings, "queue": queue, "project": project, "admin": client_factory(admin)}
    kb = w["admin"].post(_kb_url(w), json={"key": "sozlesmeler", "name": "Sözleşmeler"})
    assert kb.status_code == 201, kb.text
    w["kb"] = kb.json()["id"]
    w["harness"] = Harness(database_url, settings)
    return w


def _kb_url(w, suffix=""):
    return f"{API}/projects/{w['project']}/knowledge-bases" + suffix


def _document(w) -> str:
    files = {"files": ("fesih.md", f"# Fesih\n\n{CHUNK_TEXT}\n".encode(), "text/markdown")}
    response = w["admin"].post(_kb_url(w, f"/{w['kb']}/documents"), files=files)
    assert response.status_code == 202, response.text
    doc_id = response.json()["data"][0]["document"]["id"]

    async def drain():
        for function, *args in w["queue"].jobs:
            assert function == "ingest_document_job"
            await ingest.ingest_document(
                uuid.UUID(args[0]),
                settings=w["settings"],
                store=jobs.get_vector_store(w["settings"]),
                embed_client=ingest.LocalEmbedClient(w["settings"]),
                convert=convert_without_weights,
            )
        w["queue"].jobs.clear()

    asyncio.run(drain())
    return doc_id


def _delete(w, doc_id):
    response = w["admin"].delete(_kb_url(w, f"/{w['kb']}/documents/{doc_id}"))
    assert response.status_code == 204, response.text


def _hit(doc_id):
    hit = source(text=CHUNK_TEXT)
    hit.document_id = doc_id
    return hit


def _thread_rows(pg, run_id) -> dict[str, int]:
    return {
        t: pg.execute(
            f"SELECT count(*) FROM checkpoints.{t} WHERE thread_id = %s", (str(run_id),)
        ).fetchone()[0]
        for t in TABLES
    }


def _no_rows(pg, run_id):
    assert _thread_rows(pg, run_id) == dict.fromkeys(TABLES, 0)


def _deleted_at(pg, run_id):
    return pg.execute(
        "SELECT checkpoint_deleted_at, source_deleted_at FROM runs WHERE id = %s", (run_id,)
    ).fetchone()


def _sql_ports(model, hits):
    tools = ScriptedTools(
        schema=SQL_SCHEMA,
        approval={SQL_TOOL},
        results={SQL_TOOL: ToolOutcome("rows: 3", False, 7, False, 12)},
    )
    return Ports(model, ScriptedRetriever(hits), tools=tools)


APPROVAL_DEFINITION = definition(
    tools=[{"tool_key": "mcp-sql", "actions": ["run_sql"]}],
    approval={"actions": ["mcp-sql.run_sql"], "assign_to": "analyst"},
    limits={"max_tool_calls": 1},
)


def _waiting_approval(w, pg, doc_id):
    run_id = seed_run(pg, w["project"], APPROVAL_DEFINITION)
    model = ScriptedModel(
        turn(tools=[(SQL_TOOL, {"sql": "select 1", "reason": "r"})]), turn("Tamam [1].")
    )
    ports = _sql_ports(model, [_hit(doc_id)])
    assert w["harness"].run(run_id, ports) == "waiting_approval"
    return run_id, ports


def test_116_1_finished_run_leaves_no_checkpoint(world, pg):
    run_id = seed_run(pg, world["project"], definition())
    model = ScriptedModel(turn("Fesih süresi 30 gündür [1]."))
    hits = [source(text=CHUNK_TEXT)]
    assert world["harness"].run(run_id, Ports(model, ScriptedRetriever(hits))) == "completed"
    assert CHUNK_TEXT in model.calls[0][-1]["content"]  # the model still saw the passage
    _no_rows(pg, run_id)
    assert _deleted_at(pg, run_id)[0] is not None


def test_116_2_tool_search_leaves_no_checkpoint_and_events_carry_no_text(world, pg):
    d = definition(knowledge=[{"kb_key": "sozlesmeler", "mode": "tool", "top_k": 4}])
    run_id = seed_run(pg, world["project"], d)
    model = ScriptedModel(
        turn(tools=[("search_documents", {"query": "fesih", "kb_key": "sozlesmeler"})]),
        turn("30 gün [1]."),
    )
    hits = [source(text=CHUNK_TEXT)]
    assert world["harness"].run(run_id, Ports(model, ScriptedRetriever(hits))) == "completed"
    _no_rows(pg, run_id)
    for _, kind, payload in events(pg, run_id):
        if kind in ("sources", "tool_result"):
            assert CHUNK_TEXT not in json.dumps(payload, ensure_ascii=False)
    for _, kind, data in stream(run_id):
        if kind in ("sources", "tool_result"):
            assert CHUNK_TEXT not in json.dumps(data, ensure_ascii=False)


def test_116_3_resume_after_document_delete_fails_loud(world, pg):
    doc_id = _document(world)
    run_id, ports = _waiting_approval(world, pg, doc_id)
    # While the run waits its checkpoint exists, but the sources it keeps have no text.
    assert _thread_rows(pg, run_id)["checkpoints"] > 0
    state = asyncio.run(checkpoints.latest_state(world["settings"], run_id))
    assert state["sources"] and all("text" not in s for s in state["sources"])

    _delete(world, doc_id)
    assert _deleted_at(pg, run_id)[1] is not None  # the delete marked the waiting run

    resumed = world["harness"].run(run_id, ports, {"decision": "approved", "comment": None})
    assert resumed == "failed"
    row = run_row(pg, run_id)
    assert row["error_code"] == "source_deleted"
    assert ports.tools.called == []  # the approved action did not run on deleted evidence
    assert len(ports.model.calls) == 1  # no model call after the delete
    errors = [p for _, t, p in events(pg, run_id) if t == "error"]
    assert errors[-1]["code"] == "source_deleted"
    _no_rows(pg, run_id)
    listed = world["admin"].get(f"{API}/projects/{world['project']}/runs/{run_id}/events")
    sources = [e["payload"] for e in listed.json()["items"] if e["type"] == "sources"]
    assert sources[0]["selected"][0]["breadcrumb"] == "[deleted]"


def test_116_4_sweep_closes_waiting_user_run_with_deleted_source(world, pg):
    doc_id = _document(world)
    d = definition(ask_user=True)
    run_id = seed_run(pg, world["project"], d)
    model = ScriptedModel(turn(tools=[("ask_user_question", {"question": "Hangi sözleşme?"})]))
    ports = Ports(model, ScriptedRetriever([_hit(doc_id)]))
    assert world["harness"].run(run_id, ports) == "waiting_user"
    _delete(world, doc_id)

    closed = asyncio.run(checkpoints.sweep(world["settings"]))
    assert str(run_id) in closed["source_deleted"]
    row = run_row(pg, run_id)
    assert (row["status"], row["error_code"]) == ("failed", "source_deleted")
    assert [p["code"] for _, t, p in events(pg, run_id) if t == "error"] == ["source_deleted"]
    assert stream(run_id)[-1][1] == "error"
    _no_rows(pg, run_id)


def test_116_5_sweep_purges_threads_of_runs_ended_outside_the_runner(world, pg):
    doc_id = _document(world)
    run_id, _ = _waiting_approval(world, pg, doc_id)
    # The cancel API and the approval expiry end a waiting run without the runner.
    pg.execute(
        "UPDATE runs SET status = 'cancelled', error_code = 'cancelled', ended_at = now()"
        " WHERE id = %s",
        (run_id,),
    )
    assert _thread_rows(pg, run_id)["checkpoints"] > 0
    first = asyncio.run(checkpoints.sweep(world["settings"]))
    assert str(run_id) in first["purged"]
    _no_rows(pg, run_id)
    stamped = _deleted_at(pg, run_id)[0]
    second = asyncio.run(checkpoints.sweep(world["settings"]))
    assert str(run_id) not in second["purged"]  # idempotent: done once, stamped once
    assert _deleted_at(pg, run_id)[0] == stamped


def test_116_6_resume_with_live_source_completes(world, pg):
    doc_id = _document(world)
    run_id, ports = _waiting_approval(world, pg, doc_id)
    resumed = world["harness"].run(run_id, ports, {"decision": "approved", "comment": None})
    assert resumed == "completed"
    assert ports.tools.called and run_row(pg, run_id)["output"] == "Tamam [1]."
    # The resumed model call still had the passage: it came from the checkpointed messages.
    assert CHUNK_TEXT in json.dumps(ports.model.calls[-1], ensure_ascii=False)
    _no_rows(pg, run_id)


def test_116_7_failed_purge_leaves_run_finished_and_sweep_retries(world, pg, monkeypatch):
    run_id = seed_run(pg, world["project"], definition())

    async def broken(settings, run_id):
        raise OSError("checkpoint store unreachable")

    original = checkpoints.delete_thread
    monkeypatch.setattr(checkpoints, "delete_thread", broken)
    model = ScriptedModel(turn("30 gün [1]."))
    hits = [source(text=CHUNK_TEXT)]
    assert world["harness"].run(run_id, Ports(model, ScriptedRetriever(hits))) == "completed"
    assert _deleted_at(pg, run_id)[0] is None
    assert _thread_rows(pg, run_id)["checkpoints"] > 0

    monkeypatch.setattr(checkpoints, "delete_thread", original)
    later = datetime.now(UTC) + timedelta(minutes=1)
    assert str(run_id) in asyncio.run(checkpoints.sweep(world["settings"], now=later))["purged"]
    _no_rows(pg, run_id)
    assert run_row(pg, run_id)["status"] == "completed"


def test_116_10_knowledge_base_delete_marks_waiting_runs(world, pg):
    doc_id = _document(world)
    run_id, _ = _waiting_approval(world, pg, doc_id)
    other_id, _ = _waiting_approval(world, pg, str(uuid.uuid4()))  # another document
    response = world["admin"].delete(_kb_url(world, f"/{world['kb']}"))
    assert response.status_code == 204, response.text
    assert _deleted_at(pg, run_id)[1] is not None
    assert _deleted_at(pg, other_id)[1] is None


def test_116_11_running_run_stops_at_next_step_after_delete(world, pg):
    doc_id = _document(world)

    class DeletingRetriever(ScriptedRetriever):
        async def search(self, *args):
            found = await super().search(*args)
            # The document goes while the run is between retrieve and its next step.
            pg.execute("UPDATE runs SET source_deleted_at = now() WHERE id = %s", (run_id,))
            return found

    run_id = seed_run(pg, world["project"], definition())
    model = ScriptedModel(turn("never"))
    status = world["harness"].run(run_id, Ports(model, DeletingRetriever([_hit(doc_id)])))
    assert status == "failed" and run_row(pg, run_id)["error_code"] == "source_deleted"
    assert model.calls == []
    _no_rows(pg, run_id)


def test_116_12_sweep_isolates_a_failing_close(world, pg, monkeypatch):
    from ffcore.runtime import events as run_events

    doc_id = _document(world)
    first, _ = _waiting_approval(world, pg, doc_id)
    second, _ = _waiting_approval(world, pg, doc_id)
    _delete(world, doc_id)
    # The older mark is closed first (order_by source_deleted_at): make it the failing one.
    pg.execute(
        "UPDATE runs SET source_deleted_at = source_deleted_at - interval '1 minute' WHERE id = %s",
        (first,),
    )
    original = run_events.RunEventWriter.start

    async def broken_for_first(self):
        if str(self._run_id) == str(first):
            raise ConnectionError("redis unreachable")
        await original(self)

    monkeypatch.setattr(run_events.RunEventWriter, "start", broken_for_first)
    done = asyncio.run(checkpoints.sweep(world["settings"]))
    # The database is shared by the module's tests: other marked runs may be closed too.
    assert str(second) in done["source_deleted"] and str(first) not in done["source_deleted"]
    assert run_row(pg, second)["status"] == "failed"
    assert run_row(pg, first)["status"] == "waiting_approval"  # rolled back, left for next tick
    _no_rows(pg, second)

    monkeypatch.setattr(run_events.RunEventWriter, "start", original)
    assert str(first) in asyncio.run(checkpoints.sweep(world["settings"]))["source_deleted"]
    assert run_row(pg, first)["error_code"] == "source_deleted"
    _no_rows(pg, first)
