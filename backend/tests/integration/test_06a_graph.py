"""06a acceptance on the real graph, runner, checkpointer and event stream, scripted ports."""

import os
from datetime import timedelta

import pytest
from pydantic import SecretStr

from ffcore.runtime.state import ToolOutcome
from tests.integration.runtime_support import (
    Harness,
    Ports,
    ScriptedGuard,
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

SQL_TOOL = "mcp-sql__run_sql"
SQL_SCHEMA = [
    {"type": "function", "function": {"name": SQL_TOOL, "parameters": {"type": "object"}}}
]
SQL_DEFINITION = definition(
    knowledge=[],
    tools=[{"tool_key": "mcp-sql", "actions": ["run_sql"]}],
    approval={"actions": ["mcp-sql.run_sql"], "assign_to": "analyst"},
    limits={"max_tool_calls": 1},
    answer_rules={"cite_sources": False, "unknown_reply": "Veride yok."},
)


@pytest.fixture
def harness(database_url, app_settings):
    setup(database_url)
    settings = app_settings.model_copy(
        update={
            "database_url": SecretStr(database_url),
            "redis_url": SecretStr(os.environ["REDIS_URL"]),
        }
    )
    return Harness(database_url, settings)


@pytest.fixture
def project(make_project):
    return make_project()


def _types(pg, run_id):
    return [t for _, t, _ in events(pg, run_id)]


def test_06a_1_contract_assistant_answers_with_sources(harness, pg, project):
    run_id = seed_run(pg, project, definition())
    hits = [source(1, "hizmet-sozlesmesi.pdf", 3, 0.9), source(2, "eski.pdf", 1, 0.5, "2022-01-01")]
    model = ScriptedModel(turn("Fesih süresi 30 gündür [1]."))
    status = harness.run(run_id, Ports(model, ScriptedRetriever(hits)))
    assert status == "completed"
    row = run_row(pg, run_id)
    assert row["output"] == "Fesih süresi 30 gündür [1]."
    assert row["outcome_label"] == "answered"
    assert row["confidence"] == pytest.approx(0.9)  # cited: [1] only
    sources = [p for _, t, p in events(pg, run_id) if t == "sources"][0]["selected"]
    assert {(s["document_name"], s["page"]) for s in sources} == {
        ("hizmet-sozlesmesi.pdf", 3),
        ("eski.pdf", 1),
    }
    live = stream(run_id)
    names = [e for _, e, _ in live]
    assert names[0] == "sources" and names[-1] == "done" and "token" in names
    # The model saw the sources newest first, before the question (D5, D6).
    user = model.calls[0][-1]["content"]
    assert user.index("hizmet-sozlesmesi.pdf") < user.index("eski.pdf") < user.index("QUESTION")


def test_06a_2_unknown_reply_declined(harness, pg, project):
    run_id = seed_run(pg, project, definition(), question="Uzay istasyonu nerede?")
    model = ScriptedModel()  # never called
    assert harness.run(run_id, Ports(model, ScriptedRetriever([]))) == "completed"
    row = run_row(pg, run_id)
    assert row["output"] == "Bu bilgi belgelerde yok."
    assert row["outcome_label"] == "declined"
    assert model.calls == []
    assert [d["text"] for _, e, d in stream(run_id) if e == "token"] == ["Bu bilgi belgelerde yok."]


def test_06a_2_model_saying_not_found_is_declined(harness, pg, project):
    run_id = seed_run(pg, project, definition())
    model = ScriptedModel(turn("Bu bilgi kaynaklarda bulunamadı."))
    harness.run(run_id, Ports(model, ScriptedRetriever([source()])))
    assert run_row(pg, run_id)["outcome_label"] == "declined"


def _sql_ports(model):
    tools = ScriptedTools(
        schema=SQL_SCHEMA,
        approval={SQL_TOOL},
        results={SQL_TOOL: ToolOutcome("rows: 3", False, 7, False, 12)},
    )
    return Ports(model, tools=tools)


def test_06a_3_approval_interrupt_resume(harness, pg, project):
    run_id = seed_run(pg, project, SQL_DEFINITION, question="Kaç sözleşme var?")
    model = ScriptedModel(
        turn(tools=[(SQL_TOOL, {"sql": "select count(*) from s", "reason": "count"})]),
        turn("3 sözleşme var."),
    )
    ports = _sql_ports(model)
    assert harness.run(run_id, ports) == "waiting_approval"
    assert ports.tools.called == []  # nothing ran before the approval
    assert stream(run_id)[-1][1] == "approval_required"

    assert harness.run(run_id, ports, {"decision": "approved", "comment": None}) == "completed"
    assert ports.tools.called == [(SQL_TOOL, {"sql": "select count(*) from s", "reason": "count"})]
    types = _types(pg, run_id)
    # One tool_call and one approval_requested: the resumed node did not repeat them (U2-a).
    assert types.count("tool_call") == 1 and types.count("approval_requested") == 1
    assert types.index("approval_resolved") < types.index("tool_result")
    assert run_row(pg, run_id)["output"] == "3 sözleşme var."


def test_06a_3_approval_rejected(harness, pg, project):
    run_id = seed_run(pg, project, SQL_DEFINITION)
    model = ScriptedModel(
        turn(tools=[(SQL_TOOL, {"sql": "select 1", "reason": "r"})]), turn("İşlem reddedildi.")
    )
    ports = _sql_ports(model)
    harness.run(run_id, ports)
    resumed = harness.run(run_id, ports, {"decision": "rejected", "comment": "too broad"})
    assert resumed == "completed"
    assert ports.tools.called == []
    assert (
        "rejected" in model.calls[-1][-1]["content"]
        and "too broad" in model.calls[-1][-1]["content"]
    )


def test_06a_5a_events_ordered_and_streamed_in_order(harness, pg, project):
    run_id = seed_run(pg, project, definition())
    harness.run(run_id, Ports(ScriptedModel(turn("Cevap [1].")), ScriptedRetriever([source()])))
    seqs = [s for s, _, _ in events(pg, run_id)]
    assert seqs == list(range(1, len(seqs) + 1))
    assert _types(pg, run_id) == ["budget", "sources", "llm_call", "answer"]
    llm_call = [p for _, t, p in events(pg, run_id) if t == "llm_call"][0]
    # Present and null when the model port gave no call id: said, not left out (K-06a-0007).
    assert "litellm_call_id" in llm_call and llm_call["litellm_call_id"] is None
    ids = [tuple(map(int, i.split("-"))) for i, _, _ in stream(run_id)]
    assert ids == sorted(ids)


def test_06a_5c_fallback_event(harness, pg, project):
    run_id = seed_run(pg, project, definition())
    fallback = {"source_model": "p.chat-default", "target_model": "p.chat-fallback", "reason": "x"}
    harness.run(
        run_id,
        Ports(ScriptedModel(turn("A [1].", fallback=fallback)), ScriptedRetriever([source()])),
    )
    stored = [p for _, t, p in events(pg, run_id) if t == "fallback"]
    assert stored == [fallback]
    assert [d for _, e, d in stream(run_id) if e == "fallback"] == [fallback]


def test_06a_5d_tool_events_carry_truncated(harness, pg, project):
    doc = definition(
        knowledge=[],
        tools=[{"tool_key": "mcp-sql", "actions": ["run_sql"]}],
        answer_rules={"cite_sources": False, "unknown_reply": "Yok."},
    )
    run_id = seed_run(pg, project, doc)
    tools = ScriptedTools(
        schema=SQL_SCHEMA,
        results={SQL_TOOL: ToolOutcome("x" * 10 + "[truncated: 10/90 chars]", True, 90, False, 5)},
    )
    model = ScriptedModel(turn(tools=[(SQL_TOOL, {"sql": "s", "reason": "r"})]), turn("Tamam."))
    assert harness.run(run_id, Ports(model, tools=tools)) == "completed"
    result = [p for _, t, p in events(pg, run_id) if t == "tool_result"][0]
    assert result["truncated"] is True and result["is_error"] is False


def test_06a_6b_limit_reached_partial(harness, pg, project):
    doc = definition(
        knowledge=[],
        tools=[{"tool_key": "mcp-sql", "actions": ["run_sql"]}],
        limits={"max_turns": 2, "max_tool_calls": 6},
    )
    run_id = seed_run(pg, project, doc)
    tools = ScriptedTools(
        schema=SQL_SCHEMA, results={SQL_TOOL: ToolOutcome("r", False, 1, False, 1)}
    )
    model = ScriptedModel(
        turn("Önce bakıyorum", tools=[(SQL_TOOL, {"sql": "a"})]),
        turn("Biraz daha", tools=[(SQL_TOOL, {"sql": "b"})]),
    )
    assert harness.run(run_id, Ports(model, tools=tools)) == "failed"
    row = run_row(pg, run_id)
    assert row["error_code"] == "limit_reached"
    assert row["partial"] is True and row["output"] == "Biraz daha"
    error = [p for _, t, p in events(pg, run_id) if t == "error"][0]
    assert error["limit"] == "max_turns"
    assert stream(run_id)[-1][1] == "error"


def test_06a_6b_max_tool_calls(harness, pg, project):
    run_id = seed_run(pg, project, SQL_DEFINITION)
    tools = ScriptedTools(
        schema=SQL_SCHEMA, results={SQL_TOOL: ToolOutcome("r", False, 1, False, 1)}
    )
    model = ScriptedModel(
        turn(tools=[(SQL_TOOL, {"sql": "a"})]), turn(tools=[(SQL_TOOL, {"sql": "b"})])
    )
    harness.run(run_id, Ports(model, tools=tools))  # first call needs no approval here
    row = run_row(pg, run_id)
    assert (row["status"], row["error_code"]) == ("failed", "limit_reached")


def test_06a_7_time_breakdown_sums(harness, pg, project):
    run_id = seed_run(pg, project, definition())
    harness.run(run_id, Ports(ScriptedModel(turn("A [1].", ms=250)), ScriptedRetriever([source()])))
    row = run_row(pg, run_id)
    total = (row["ended_at"] - row["started_at"]) / timedelta(milliseconds=1)
    parts = row["model_ms"] + row["tool_ms"] + row["retrieval_ms"] + row["unaccounted_ms"]
    assert abs(total - parts) <= 1000
    assert row["model_ms"] == 250 and row["slowest_step"] == "model"


@pytest.mark.parametrize("stage", ["input.pre", "output.pre"])
def test_06a_9_guardrail_block(harness, pg, project, stage):
    run_id = seed_run(pg, project, definition(), question="şifrem 1234")
    guard = ScriptedGuard({"input.pre": "şifrem", "output.pre": "gizli"})
    model = ScriptedModel(turn("gizli cevap [1]."))
    question_guard = ScriptedGuard({stage: guard.block[stage]})
    ports = Ports(model, ScriptedRetriever([source()]), guard=question_guard)
    if stage == "output.pre":
        ports.stream_live = False  # enforce mode on output: nothing shown before the check
    assert harness.run(run_id, ports) == "failed"
    row = run_row(pg, run_id)
    assert row["error_code"] == "guardrail_block" and row["reference_id"] is not None
    error = stream(run_id)[-1]
    assert error[1] == "error" and error[2]["message"] == "Blocked by policy."
    assert error[2]["reference_id"] == str(row["reference_id"])
    assert "token" not in [e for _, e, _ in stream(run_id)]


def test_06a_13_tool_mode_and_ask_user(harness, pg, project):
    doc = definition(
        knowledge=[{"kb_key": "sozlesmeler", "mode": "tool", "top_k": 4}], ask_user=True
    )
    run_id = seed_run(pg, project, doc)
    model = ScriptedModel(
        turn(tools=[("ask_user_question", {"question": "Hangi sözleşme?"})]),
        turn(tools=[("search_documents", {"query": "fesih", "kb_key": "sozlesmeler"})]),
        turn("30 gün [1]."),
    )
    retriever = ScriptedRetriever([source()])
    ports = Ports(model, retriever)
    assert harness.run(run_id, ports) == "waiting_user"
    assert stream(run_id)[-1][1] == "question"
    assert harness.run(run_id, ports, {"answer": "Hizmet sözleşmesi"}) == "completed"
    assert retriever.queries == [("sozlesmeler", "fesih", 4, ())]
    row = run_row(pg, run_id)
    assert row["output"] == "30 gün [1]." and row["confidence"] == pytest.approx(0.8)
    # ask_user is not a tool call in the max_tool_calls sense (K-06a-0002 S7).
    assert _types(pg, run_id).count("tool_call") == 1


def test_06a_16_run_timeout(harness, pg, project):
    run_id = seed_run(pg, project, definition(limits={"run_timeout_s": 1}))
    model = ScriptedModel(turn("geç [1]."), delay=3)
    assert harness.run(run_id, Ports(model, ScriptedRetriever([source()]))) == "failed"
    row = run_row(pg, run_id)
    assert row["error_code"] == "limit_reached"
    assert [p for _, t, p in events(pg, run_id) if t == "error"][0]["limit"] == "run_timeout_s"


def test_06a_17b_unsubscribed_run_is_abandoned(harness, pg, project):
    run_id = seed_run(pg, project, definition())
    model = ScriptedModel(turn("A [1]."))
    status = harness.run(run_id, Ports(model, ScriptedRetriever([source()])), listen=False)
    assert status == "abandoned"
    assert model.calls == []  # stopped at the first boundary, no model call


def test_06a_17c_cancel_requested(harness, pg, project):
    run_id = seed_run(pg, project, definition())
    pg.execute("UPDATE runs SET cancel_requested_at = now() WHERE id = %s", (run_id,))
    assert harness.run(run_id, Ports(ScriptedModel(), ScriptedRetriever([source()]))) == "cancelled"


def test_06a_finished_run_is_left_alone(harness, pg, project):
    run_id = seed_run(pg, project, definition())
    harness.run(run_id, Ports(ScriptedModel(turn("A [1].")), ScriptedRetriever([source()])))
    before = events(pg, run_id)
    assert harness.run(run_id, Ports(ScriptedModel(), ScriptedRetriever())) == "completed"
    assert events(pg, run_id) == before


class WorkerDied(BaseException):
    """Stands for the worker process dying: not an Exception, so nothing in the run catches it."""


class DyingModel(ScriptedModel):
    async def call(self, messages, **kwargs):
        raise WorkerDied()


def test_06a_4_continues_from_checkpoint_after_worker_death(harness, pg, project):
    run_id = seed_run(pg, project, definition())
    retriever = ScriptedRetriever([source()])
    with pytest.raises(WorkerDied):
        harness.run(run_id, Ports(DyingModel(), retriever))
    assert run_row(pg, run_id)["status"] == "running"  # as a dead worker leaves it
    # The next attempt (arq retry, new process) continues at the model step: no new retrieval.
    model = ScriptedModel(turn("A [1]."))
    assert harness.run(run_id, Ports(model, retriever)) == "completed"
    assert len(retriever.queries) == 1
    assert _types(pg, run_id).count("sources") == 1
    resumed = [p for _, t, p in events(pg, run_id) if t == "progress"]
    assert resumed == [{"attempt": "resumed_after_worker_stop", "step": "model"}]


def test_06a_v8_buffered_answer_is_announced_and_shown_after_the_check(harness, pg, project):
    run_id = seed_run(pg, project, definition())
    ports = Ports(ScriptedModel(turn("Cevap burada [1].")), ScriptedRetriever([source()]))
    ports.stream_live = False
    assert harness.run(run_id, ports) == "completed"
    live = stream(run_id)
    assert (live[0][1], live[0][2]) == (
        "progress",
        {"stage": "output_buffered", "reason": "guardrail_enforce"},
    )
    tokens = [d["text"] for _, e, d in live if e == "token"]
    assert tokens == ["Cevap burada [1]."]  # one piece, after output.pre
    assert [e for _, e, _ in live].index("token") > [e for _, e, _ in live].index("sources")


class RedisDroppingRetriever(ScriptedRetriever):
    async def search(self, *args):
        from redis.exceptions import ConnectionError as RedisConnectionError

        raise RedisConnectionError("Connection closed by server.")


def test_06a_4_infrastructure_error_aborts_the_attempt_not_the_run(harness, pg, project):
    from ffcore.runtime.runner import AttemptAborted

    run_id = seed_run(pg, project, definition())
    with pytest.raises(AttemptAborted):
        harness.run(run_id, Ports(ScriptedModel(), RedisDroppingRetriever()))
    assert run_row(pg, run_id)["status"] == "running"
    assert "error" not in _types(pg, run_id)
    model = ScriptedModel(turn("A [1]."))
    assert harness.run(run_id, Ports(model, ScriptedRetriever([source()]))) == "completed"


def test_06a_4_last_aborted_attempt_ends_the_run_with_a_code(harness, pg, project):
    import asyncio

    import redis.asyncio as aioredis

    from ffcore.runtime.runner import Attempt, fail_after_retries

    run_id = seed_run(pg, project, definition(), status="running")

    async def go():
        client = aioredis.from_url(os.environ["REDIS_URL"])
        try:
            attempt = Attempt(harness.settings, client, harness.db.session_scope, None)
            await fail_after_retries(attempt, str(run_id), "ConnectionError")
        finally:
            await client.aclose()

    asyncio.run(go())
    row = run_row(pg, run_id)
    assert (row["status"], row["error_code"]) == ("failed", "worker_retries_exhausted")


class HalfStreamDyingModel(ScriptedModel):
    """Streams part of an answer, then the worker stops (live: SIGTERM during the stream)."""

    async def call(self, messages, *, tools, max_tokens, on_token):
        for word in ("t1 ", "t2 ", "t3 "):
            await on_token(word)
        raise WorkerDied()


def test_06a_4_tokens_after_a_restart_continue_the_stream(harness, pg, project):
    run_id = seed_run(pg, project, definition())
    retriever = ScriptedRetriever([source()])
    with pytest.raises(WorkerDied):
        harness.run(run_id, Ports(HalfStreamDyingModel(), retriever))
    assert harness.run(run_id, Ports(ScriptedModel(turn("A [1].")), retriever)) == "completed"
    live = stream(run_id)
    ids = [tuple(map(int, i.split("-"))) for i, _, _ in live]
    assert ids == sorted(ids) and len(set(ids)) == len(ids)
    names = [e for _, e, _ in live]
    restart = names.index("progress", names.index("sources"))
    assert names[restart + 1 :] == ["token", "token", "done"]


def test_06a_setup_failure_is_a_coded_end(harness, pg, project, monkeypatch):
    """prompt_unavailable (Langfuse down), tool_layer_unavailable, a missing guardrail policy:
    the run fails with that code and an error event (F12 relies on these codes)."""
    import asyncio

    import redis.asyncio as aioredis

    from ffcore.core.prompts import PromptUnavailable
    from ffcore.runtime.runner import Attempt, execute

    run_id = seed_run(pg, project, definition())

    async def broken(**kwargs):
        raise PromptUnavailable("platform_rules", "ConnectError")

    async def go():
        client = aioredis.from_url(os.environ["REDIS_URL"])
        try:
            attempt = Attempt(harness.settings, client, harness.db.session_scope, broken)
            return await execute(attempt, str(run_id))
        finally:
            await client.aclose()

    assert asyncio.run(go()) == "failed"
    row = run_row(pg, run_id)
    assert row["error_code"] == "prompt_unavailable"
    assert stream(run_id)[-1][1] == "error"
