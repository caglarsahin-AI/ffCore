"""06a test harness: the real graph, runner, Postgres checkpointer and Redis, with scripted ports.

The model, the knowledge search, the tools and the guardrail are ports (runtime/state.py); here
they follow a script so every acceptance test is deterministic (brief 06: recorded fake answers).
The adapters that reach LiteLLM, the 04a search API, MCP and the 08 engine have their own tests.
"""

import asyncio
import json
import os
import uuid
from dataclasses import dataclass, field
from typing import Any

import redis.asyncio as aioredis

from ffcore.runtime.events import mark_listening
from ffcore.runtime.prompting import Source
from ffcore.runtime.runner import Attempt, execute, setup_checkpointer
from ffcore.runtime.state import GuardResult, ModelTurn, RunContext, ToolCall, ToolOutcome

PROMPT = "You answer from the documents."


def turn(content="", *, tools=(), usage=(10, 5), fallback=None, ms=40) -> ModelTurn:
    return ModelTurn(
        content=content,
        tool_calls=[ToolCall(f"call-{uuid.uuid4().hex[:6]}", n, a) for n, a in tools],
        finish_reason="tool_calls" if tools else "stop",
        usage={"prompt_tokens": usage[0], "completion_tokens": usage[1]},
        fallback=fallback,
        model="p.chat-default",
        ms=ms,
    )


def source(n=1, name="hizmet-sozlesmesi.pdf", page=3, score=0.8, day="2024-05-01", text="Fesih"):
    return Source(
        n=n,
        kb_key="sozlesmeler",
        chunk_id=str(uuid.uuid4()),
        document_id=str(uuid.uuid4()),
        document_name=name,
        page=page,
        breadcrumb="Madde 9 > Fesih",
        text=text,
        updated_at_source=f"{day}T00:00:00+00:00",
        rerank_score=score,
    )


class ScriptedModel:
    def __init__(self, *turns: ModelTurn, delay: float = 0) -> None:
        self.turns = list(turns)
        self.calls: list[list[dict]] = []
        self.delay = delay

    async def call(self, messages, *, tools, max_tokens, on_token):
        self.calls.append(json.loads(json.dumps(messages)))
        await asyncio.sleep(self.delay)
        result = self.turns.pop(0)
        if on_token and result.content:
            for word in result.content.split(" "):
                await on_token(word + " ")
        return result


class ScriptedRetriever:
    def __init__(self, hits=None) -> None:
        self.hits = hits or []
        self.queries: list[tuple] = []

    async def search(self, kb_key, query, top_k, scope):
        self.queries.append((kb_key, query, top_k, tuple(scope)))
        return [Source(**s.__dict__) for s in self.hits], {"rerank_truncated": 0}


@dataclass
class ScriptedTools:
    schema: list[dict] = field(default_factory=list)
    approval: set[str] = field(default_factory=set)
    results: dict[str, ToolOutcome] = field(default_factory=dict)
    called: list[tuple[str, dict]] = field(default_factory=list)

    def schemas(self):
        return self.schema

    def needs_approval(self, name):
        return name in self.approval

    async def call(self, name, arguments):
        self.called.append((name, arguments))
        return self.results[name]


class ScriptedGuard:
    def __init__(self, block: dict[str, str] | None = None) -> None:
        # stage -> word that blocks at that stage
        self.block = block or {}
        self.seen: list[tuple[str, str]] = []

    async def check(self, stage, text, *, tool=None):
        self.seen.append((stage, text))
        word = self.block.get(stage)
        if word and word in text:
            return GuardResult("block", "", "Blocked by policy.", str(uuid.uuid4()), 1)
        return GuardResult("allow", text, None, None, 0)


@dataclass
class Ports:
    model: ScriptedModel
    retriever: ScriptedRetriever = field(default_factory=ScriptedRetriever)
    tools: ScriptedTools = field(default_factory=ScriptedTools)
    guard: ScriptedGuard = field(default_factory=ScriptedGuard)
    stream_live: bool = True


def definition(**overrides) -> dict[str, Any]:
    base = {
        "model": "chat-default",
        "system_prompt": PROMPT,
        "knowledge": [{"kb_key": "sozlesmeler", "mode": "always", "top_k": 8}],
        "answer_rules": {"unknown_reply": "Bu bilgi belgelerde yok."},
    }
    return {**base, **overrides}


def seed_run(pg, project_id, definition_doc, *, question="Fesih süresi nedir?", status="queued"):
    agent_id, version_id, run_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    pg.execute(
        "INSERT INTO agents (id, project_id, key, name, created_by) VALUES (%s, %s, %s, 'A', 't')",
        (agent_id, project_id, f"a-{agent_id.hex[:8]}"),
    )
    pg.execute(
        "INSERT INTO agent_versions (id, agent_id, version, definition, created_by)"
        " VALUES (%s, %s, 1, %s, 't')",
        (version_id, agent_id, json.dumps(definition_doc)),
    )
    pg.execute(
        "INSERT INTO runs (id, project_id, agent_id, agent_version_id, channel, trigger_type,"
        " input, status, created_by) VALUES (%s, %s, %s, %s, 'test', 'chat', %s, %s, 't')",
        (run_id, project_id, agent_id, version_id, question, status),
    )
    return run_id


class Harness:
    """Runs attempts of a run with given ports, as the worker would."""

    def __init__(self, database_url: str, settings) -> None:
        from ffcore.core import db

        self.database_url = database_url
        self.settings = settings
        db.configure(database_url, pooled=False)
        self.db = db

    async def attempt(self, run_id, ports: Ports, resume=None, *, listen=True) -> str:
        client = aioredis.from_url(os.environ["REDIS_URL"])
        try:
            if listen:
                await mark_listening(client, run_id, 600)

            async def context_factory(*, session, run, definition, events, boundary):
                return RunContext(
                    run_id=str(run.id),
                    project_id=str(run.project_id),
                    user_id=None,
                    definition=definition,
                    events=events,
                    model=ports.model,
                    retriever=ports.retriever,
                    tools=ports.tools,
                    guard=ports.guard,
                    boundary=boundary,
                    system={
                        "platform_rules": "RULES",
                        "runtime_profile": "",
                        "user_instructions": PROMPT,
                    },
                    stream_live=ports.stream_live,
                )

            attempt = Attempt(self.settings, client, self.db.session_scope, context_factory)
            return await execute(attempt, str(run_id), resume)
        finally:
            await client.aclose()

    def run(self, *args, **kwargs) -> str:
        return asyncio.run(self.attempt(*args, **kwargs))


def setup(database_url: str) -> None:
    asyncio.run(setup_checkpointer(database_url))


def events(pg, run_id) -> list[tuple[int, str, dict]]:
    return pg.execute(
        "SELECT seq, type, payload FROM run_events WHERE run_id = %s ORDER BY seq", (run_id,)
    ).fetchall()


def stream(run_id) -> list[tuple[str, str, dict]]:
    async def read():
        client = aioredis.from_url(os.environ["REDIS_URL"])
        try:
            entries = await client.xrange(f"run:{run_id}:events")
        finally:
            await client.aclose()
        return [
            (i.decode(), f[b"event"].decode(), json.loads(f[b"data"].decode())) for i, f in entries
        ]

    return asyncio.run(read())


def run_row(pg, run_id) -> dict:
    cur = pg.execute("SELECT * FROM runs WHERE id = %s", (run_id,))
    names = [c.name for c in cur.description]
    return dict(zip(names, cur.fetchone(), strict=True))
