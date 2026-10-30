"""fake-llm `tool-*` mode (K-SEN-0025): with tools in the request the fake calls the first tool
once (sample values for its required arguments); after the tool result it answers in text.
Without tools it answers in text; the existing models are unchanged."""

import json
import threading
from http.server import ThreadingHTTPServer

import httpx
import pytest

from tests.fakes import fake_openai

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "send_reply",
            "description": "Send a reply.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticket_id": {"type": "string"},
                    "body": {"type": "string"},
                    "note": {"type": "string"},
                },
                "required": ["ticket_id", "body"],
            },
        },
    },
    {
        "type": "function",
        "function": {"name": "get_ticket", "parameters": {"type": "object", "properties": {}}},
    },
]
USER = [{"role": "user", "content": "Reply to the ticket."}]


@pytest.fixture(scope="module")
def base():
    server = ThreadingHTTPServer(("127.0.0.1", 0), fake_openai.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}/v1"
    server.shutdown()


def _post(base: str, **body) -> dict:
    r = httpx.post(f"{base}/chat/completions", json=body, timeout=10)
    assert r.status_code == 200, r.text
    return r.json()


def _stream(base: str, **body) -> list[dict]:
    chunks = []
    with httpx.stream(
        "POST", f"{base}/chat/completions", json={**body, "stream": True}, timeout=10
    ) as r:
        assert r.status_code == 200
        for line in r.iter_lines():
            if line.startswith("data: ") and line != "data: [DONE]":
                chunks.append(json.loads(line[6:]))
    return chunks


def test_fake_tool_mode_calls_first_tool_once(base):
    message = _post(base, model="tool-default", messages=USER, tools=TOOLS)["choices"][0]
    assert message["finish_reason"] == "tool_calls"
    calls = message["message"]["tool_calls"]
    assert len(calls) == 1 and calls[0]["type"] == "function" and calls[0]["id"]
    assert calls[0]["function"]["name"] == "send_reply"
    arguments = json.loads(calls[0]["function"]["arguments"])
    assert set(arguments) == {"ticket_id", "body"}  # required only
    assert arguments["ticket_id"] == "tkt-001" and arguments["body"]


def test_fake_tool_mode_streams_the_tool_call(base):
    chunks = _stream(base, model="tool-default", messages=USER, tools=TOOLS)
    deltas = [c["choices"][0]["delta"] for c in chunks if c.get("choices")]
    calls = [d["tool_calls"][0] for d in deltas if d.get("tool_calls")]
    assert calls and calls[0]["function"]["name"] == "send_reply" and calls[0]["id"]
    arguments = json.loads("".join(c["function"].get("arguments", "") for c in calls))
    assert arguments["ticket_id"] == "tkt-001"
    finishes = [c["choices"][0]["finish_reason"] for c in chunks if c.get("choices")]
    assert "tool_calls" in finishes
    assert any(c.get("usage") for c in chunks)


def test_fake_tool_mode_answers_after_the_tool_result(base):
    result = "Reply reply-0123 sent for tkt-001. " + "x" * 100
    messages = [
        *USER,
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "send_reply", "arguments": "{}"},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": result},
    ]
    message = _post(base, model="tool-default", messages=messages, tools=TOOLS)["choices"][0]
    assert message["finish_reason"] == "stop"
    assert message["message"]["content"] == "hello " + result[:50]
    streamed = _stream(base, model="tool-default", messages=messages, tools=TOOLS)
    text = "".join(
        c["choices"][0]["delta"].get("content") or "" for c in streamed if c.get("choices")
    )
    assert text == "hello " + result[:50]


def test_fake_tool_mode_without_tools_is_text(base):
    message = _post(base, model="tool-default", messages=USER)["choices"][0]
    assert message["message"]["content"] == "hello" and message["finish_reason"] == "stop"


def test_fake_chat_models_unchanged_with_tools(base):
    message = _post(base, model="ok-model", messages=USER, tools=TOOLS)["choices"][0]
    assert message["message"] == {"role": "assistant", "content": "hello"}
    assert message["finish_reason"] == "stop"
