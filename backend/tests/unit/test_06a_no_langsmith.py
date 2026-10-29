"""06a S1 / review r1 MINOR-1: LangGraph, langchain-core and langsmith make no outside call.

A fresh process traps name resolution and socket connections (every attempt is counted and
refused), imports the libraries, builds the real agent graph and runs it to the end with an
in-memory checkpointer and scripted ports. The run must complete (an error swallowed somewhere
does not pass) and the trap counters must stay at zero. A second check: LANGSMITH_TRACING or
LANGCHAIN_TRACING_V2 set to true stops the settings at start.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

BACKEND = Path(__file__).resolve().parents[2]

SCRIPT = r"""
import asyncio, json, socket

attempts = {"resolve": [], "connect": []}

def no_resolve(host, *args, **kwargs):
    attempts["resolve"].append(str(host))
    raise socket.gaierror("blocked by the 06a DNS trap")

class TrapSocket(socket.socket):
    def connect(self, address):
        attempts["connect"].append(str(address))
        raise ConnectionRefusedError("blocked by the 06a socket trap")

    def connect_ex(self, address):
        attempts["connect"].append(str(address))
        return 111

socket.getaddrinfo = no_resolve
socket.gethostbyname = no_resolve
def no_connection(address, *args, **kwargs):
    attempts["connect"].append(str(address))
    raise ConnectionRefusedError("blocked by the 06a socket trap")

socket.create_connection = no_connection
socket.socket = TrapSocket

import langchain_core, langgraph, langsmith  # noqa: F401 - imported under the trap
from langgraph.checkpoint.memory import InMemorySaver

from ffcore.runtime.definition import parse_definition
from ffcore.runtime.graph import build_graph
from ffcore.runtime.prompting import Source
from ffcore.runtime.state import GuardResult, ModelTurn, RunContext


class Events:
    def __init__(self):
        self.seen = []

    async def record(self, type_, payload, **kwargs):
        self.seen.append(str(type_))

    async def live(self, sse, data):
        self.seen.append(str(sse))


class Model:
    async def call(self, messages, *, tools, max_tokens, on_token):
        await on_token("30 gün [1].")
        return ModelTurn("30 gün [1].", [], "stop", {"prompt_tokens": 1}, None, "p.chat", 1)


class Retriever:
    async def search(self, kb_key, query, top_k, scope):
        return [Source(1, kb_key, "c", "d", "doc.txt", None, "B", "Fesih 30 gün", None, 0.9)], {}


class Tools:
    def schemas(self):
        return []

    def needs_approval(self, name):
        return False


class Guard:
    async def check(self, stage, text, *, tool=None):
        return GuardResult("allow", text, None, None, 0)


async def boundary(step):
    return None


async def main():
    definition = parse_definition({
        "model": "chat-default", "system_prompt": "S",
        "knowledge": [{"kb_key": "kb", "mode": "always"}],
    })
    events = Events()
    system = {"platform_rules": "R", "runtime_profile": "", "user_instructions": "S"}
    ctx = RunContext("r", "p", "u", definition, events, Model(), Retriever(), Tools(), Guard(),
                     boundary, system=system)
    graph = build_graph().compile(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "dns-trap"}}
    stream = graph.astream({"question": "fesih?"}, config, stream_mode="updates", context=ctx)
    async for _ in stream:
        pass
    final = (await graph.aget_state(config)).values
    return final.get("answer"), final.get("outcome"), events.seen

answer, outcome, seen = asyncio.run(main())
graph_attempts = {k: list(v) for k, v in attempts.items()}
# Control: the trap is live, a deliberate lookup is counted (the test would be empty otherwise).
try:
    socket.getaddrinfo("trap-check.invalid", 80)
except OSError:
    pass
print(json.dumps({
    "attempts": graph_attempts,
    "control": attempts["resolve"][len(graph_attempts["resolve"]):],
    "answer": answer, "outcome": outcome, "events": seen,
}))
"""


def test_06a_s1_no_outside_call_from_langgraph_or_langsmith():
    env = {k: v for k, v in os.environ.items() if not k.startswith(("LANGSMITH", "LANGCHAIN"))}
    done = subprocess.run(
        [sys.executable, "-c", SCRIPT],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    result = json.loads(done.stdout.strip().splitlines()[-1])
    assert result["answer"] == "30 gün [1]." and result["outcome"] == "answered"
    assert result["attempts"] == {"resolve": [], "connect": []}
    assert result["control"] == ["trap-check.invalid"]


@pytest.mark.parametrize("name", ["LANGSMITH_TRACING", "LANGCHAIN_TRACING_V2"])
def test_06a_s1_langsmith_tracing_stops_the_start(name, monkeypatch):
    from ffcore.core.config import Settings
    from tests.dummy import OBO_SECRET, SERVICE_TOKEN, SETTINGS_03A

    monkeypatch.setenv(name, "true")
    with pytest.raises(ValidationError, match="langsmith_tracing_forbidden"):
        Settings(
            deploy_profile="llmaas",
            offline=False,
            service_token=SERVICE_TOKEN,
            obo_jwt_secret=OBO_SECRET,
            **SETTINGS_03A,
        )
