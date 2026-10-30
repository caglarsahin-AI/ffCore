"""06a model adapter: streamed tool-call fragments become whole calls; broken JSON is shown, not
guessed. LiteLLM is replaced here; the real path is in test_06a_adapters."""

import asyncio
import contextlib
from types import SimpleNamespace

from ffcore.runtime import adapters
from ffcore.runtime.contracts import JobClass
from ffcore.services.litellm_client import ModelTarget, StreamResult


class FakeSlots:
    @contextlib.asynccontextmanager
    async def acquire(self, job_class):
        yield 0.25


def _chunks():
    calls = [
        {
            "index": 0,
            "id": "c1",
            "function": {"name": "mcp-sql__run_sql", "arguments": '{"sql": "sel'},
        },
        {"index": 0, "function": {"arguments": 'ect 1"}'}},
        {"index": 1, "id": "c2", "function": {"name": "search_documents", "arguments": "{bad"}},
    ]
    for part in calls:
        yield {"choices": [{"delta": {"tool_calls": [part]}}]}
    yield {"choices": [{"delta": {}, "finish_reason": "tool_calls"}]}


class FakeClient:
    def __init__(self, settings):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    @contextlib.asynccontextmanager
    async def chat_stream(self, target, messages, *, user, metadata, **params):
        assert params["tools"] and params["max_tokens"] == 100
        result = StreamResult(finish_reason="tool_calls", usage={"prompt_tokens": 3})

        class Stream:
            def __init__(self):
                self.result = result

            async def __aiter__(self):
                for chunk in _chunks():
                    yield chunk

        yield Stream()


def test_06a_tool_call_fragments_are_assembled(monkeypatch):
    async def target(session, project_id, key):
        return ModelTarget("p.chat-default", "id-1")

    monkeypatch.setattr(adapters, "LiteLLMClient", FakeClient)
    monkeypatch.setattr(adapters, "resolve_target", target)
    model = adapters.LiteLLMModel(
        SimpleNamespace(),
        None,
        FakeSlots(),
        run_id="r",
        project_id="p",
        user_id="u",
        model_key="chat-default",
        job_class=JobClass.interactive,
    )
    turn = asyncio.run(model.call([], tools=[{"type": "function"}], max_tokens=100, on_token=None))
    assert [(c.id, c.name) for c in turn.tool_calls] == [
        ("c1", "mcp-sql__run_sql"),
        ("c2", "search_documents"),
    ]
    assert turn.tool_calls[0].arguments == {"sql": "select 1"}
    assert turn.tool_calls[1].arguments == {"_unparseable_arguments": "{bad"}
    assert turn.queue_ms == 250 and turn.fallback is None
