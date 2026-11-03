"""The facade's direct model path (06b): an OpenAI request to a project model through LiteLLM.

LiteLLM already speaks OpenAI (ARCH-09): its chunks are passed on, with the public model name.
Around the call: the guardrail (`input.pre` and `egress` before, `output.pre` after, S4), the
03c quota (check, concurrent hold, commit per LiteLLM call id) and LiteLLM's own fallback.

The stream is opened before the HTTP answer starts, so failures up to the provider's first byte
are ordinary HTTP errors. Later failures arrive as an OpenAI error event in the stream. With an
enforce-mode policy that checks output, the answer is held until `output.pre` has seen it
(06a V8): the client gets `x_platform.progress: output_buffered`, then the checked answer in one
piece; a held answer larger than OUTPUT_BUFFER_BYTES is cut off with `output_buffer_exceeded`.
"""

import contextlib
import json
import logging
import math
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse

from ffcore.api.facade_schemas import (
    KEEPALIVE,
    NUMERIC_PARAMS,
    STREAM_END,
    ChatCompletionRequest,
)
from ffcore.core import db, tracing
from ffcore.core.config import Settings
from ffcore.core.errors import ApiError, error_body
from ffcore.guardrails.masking import (
    count_placeholders,
    log_skipped_policy,
    log_skipped_url,
    log_unresolved,
)
from ffcore.knowledge.chunking import approx_tokens
from ffcore.services.facade_guard import FacadeGuard, client_messages, guard_messages
from ffcore.services.facade_identity import FacadeCaller
from ffcore.services.litellm_client import LiteLLMClient, resolve_target
from ffcore.services.quota import (
    QuotaGate,
    Subject,
    engine_for,
    redis_client,
)

log = logging.getLogger("ffcore.facade")

# OpenAI parameters passed on to LiteLLM. Anything else is refused (400 `unsupported_field`),
# never dropped or passed silently: LiteLLM reads provider settings from the body too.
PASSED_PARAMS = frozenset(
    {
        "temperature",
        "top_p",
        "max_tokens",
        "max_completion_tokens",
        "stop",
        "presence_penalty",
        "frequency_penalty",
        "seed",
        "response_format",
        "tools",
        "tool_choice",
        "logit_bias",
    }
)
# The passed parameters that can carry text; each goes through `egress` (strings inside a JSON
# value included, the structure kept). The rest are numbers (logit_bias: token ids, checked).
TEXT_PARAMS = ("stop", "tools", "tool_choice", "response_format")
# Accepted and handled by the facade itself (not passed on as given).
OWN_FIELDS = frozenset({"model", "messages", "stream", "user", "n", "stream_options"})
# The most a held (buffered) answer may grow to before it is cut off (S4); max_tokens bounds it
# long before in practice.
OUTPUT_BUFFER_BYTES = 1_000_000
KEEPALIVE_S = 10.0


def _invalid(code: str, message: str) -> ApiError:
    return ApiError(400, "invalid_request_error", code, message)


def _bad_value(param: str, message: str) -> ApiError:
    # The value itself is never echoed: it may be what egress would have caught.
    return ApiError(400, "invalid_request_error", "invalid_parameter", message, param=param)


def _number(name: str, value: Any) -> None:
    kind, low, high = NUMERIC_PARAMS[name]
    allowed = int if kind == "integer" else int | float
    # NaN and the infinities are floats but no number in a range (FOLLOWUP-142).
    if isinstance(value, bool) or not isinstance(value, allowed) or not math.isfinite(value):
        raise _bad_value(name, f"'{name}' must be an {kind}.")
    if (low is not None and value < low) or (high is not None and value > high):
        bounds = f"at least {low}" if high is None else f"between {low} and {high}"
        raise _bad_value(name, f"'{name}' must be {bounds}.")


def call_params(body: ChatCompletionRequest) -> dict[str, Any]:
    """The parameters passed to LiteLLM. Numbers are strictly typed and in OpenAI's ranges; text
    parameters go through egress (guard_params); anything else is refused (reviews r1, r2)."""
    given = body.model_dump(exclude_none=True)
    unknown = sorted(set(given) - PASSED_PARAMS - OWN_FIELDS)
    if unknown:
        raise _invalid("unsupported_field", f"Unsupported parameters: {unknown}")
    for name in NUMERIC_PARAMS:
        if name in given:
            _number(name, given[name])
    bias = given.get("logit_bias")
    if bias is not None and not (
        isinstance(bias, dict)
        and all(isinstance(k, str) and k.isdigit() for k in bias)
        and all(isinstance(v, int | float) and not isinstance(v, bool) for v in bias.values())
    ):
        # Token ids and numbers only: nothing in it is text for egress to check.
        raise _bad_value("logit_bias", "'logit_bias' maps token ids to numbers.")
    return {k: v for k, v in given.items() if k in PASSED_PARAMS}


def litellm_user(caller: FacadeCaller) -> str:
    """LiteLLM's `user` (it may reach the provider): the acting user's id or the key's id, never
    the client's `user` label (review r1 MAJOR-1: the label is often an e-mail)."""
    return caller.user_id or f"api_key:{caller.key_id}"


async def guard_params(guard: FacadeGuard, params: dict[str, Any]) -> dict[str, Any]:
    """Every parameter that carries text leaves through `egress` (review r1 MAJOR-1). S9: the
    client's tool definitions are its input too."""
    if params.get("tools"):
        params["tools"] = await guard.json_text("input.pre", params["tools"])
    for name in TEXT_PARAMS:
        if params.get(name) is not None:
            params[name] = await guard.json_text("egress", params[name])
    return params


def quota_error(decision) -> ApiError:
    if decision.code == "quota_exceeded":
        return ApiError(
            429, "rate_limit_error", "quota_exceeded", "A quota of this project is exhausted."
        )
    return ApiError(
        409,
        "conflict_error",
        decision.code or "quota_blocked",
        "A USD budget applies but the model has no price.",
    )


def chunk_json(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False, separators=(',', ':'))}\n\n"


def error_event(exc: ApiError) -> str:
    return chunk_json(error_body(exc.error_type, exc.code, exc.message, exc.param))


def _chunk(cid: str, created: int, model: str, delta: dict, finish=None, **extra) -> dict:
    return {
        "id": cid,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
        **extra,
    }


def _fallback_platform(result) -> dict | None:
    if result.fallback is None:
        return None
    return {
        "event": "fallback",
        "source_model": result.fallback.source_model,
        "target_model": result.fallback.target_model,
        "reason": result.fallback.reason,
    }


async def complete(request: Request, caller: FacadeCaller, target, body, settings: Settings):
    params = call_params(body)
    raw_messages, dropped = client_messages(body)
    if dropped:
        # No run on this path: the log line is the record (field names only, no values).
        log.info("facade_dropped_fields fields=%s project=%s", dropped, caller.project_id)
    stack = contextlib.AsyncExitStack()
    try:
        redis = redis_client(settings)
        stack.push_async_callback(redis.aclose)
        session = await stack.enter_async_context(db.session_scope())
        model = await resolve_target(session, caller.project_id, target.key)
        guard = await FacadeGuard.load(session, redis, caller.project_id)
        messages = await guard_messages(guard, raw_messages)
        params = await guard_params(guard, params)
        gate = QuotaGate(
            engine_for(settings, redis),
            redis,
            session,
            Subject(project_id=caller.project_id, user_id=caller.user_id, api_key_id=caller.key_id),
            settings=settings,
        )
        decision = await gate.check(
            model.id, input_tokens=approx_tokens(json.dumps(messages, ensure_ascii=False))
        )
        if decision.blocked:
            raise quota_error(decision)
        if decision.max_output_tokens is not None:
            for name in ("max_tokens", "max_completion_tokens"):
                if name in params:
                    params[name] = min(params[name], decision.max_output_tokens)
            if "max_tokens" not in params and "max_completion_tokens" not in params:
                params["max_tokens"] = decision.max_output_tokens
        lease = await stack.enter_async_context(gate.hold())
        if lease is not None and lease.blocked:
            raise quota_error(lease)
        client = await stack.enter_async_context(LiteLLMClient(settings))
        user = litellm_user(caller)
        metadata = tracing.trace_context(user_id=caller.user_id) | {
            "project_id": caller.project_id,
            "api_key_id": caller.key_id,
            "channel": "api",
        }
        if not body.stream:
            try:
                result = await client.chat(model, messages, user=user, metadata=metadata, **params)
            finally:
                await stack.aclose()
            return await _answer(caller, target, model, result, settings, guard.scope)
        stream = await stack.enter_async_context(
            client.chat_stream(model, messages, user=user, metadata=metadata, **params)
        )
    except BaseException:
        await stack.aclose()
        raise
    return StreamingResponse(
        _relay(stream, stack, gate, guard, model, target.name),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _commit(settings: Settings, caller, model, call_id, usage, model_name) -> None:
    # Own session and Redis: the call is over; its cost is counted even if the output is then
    # refused by a guardrail (the provider was paid).
    redis = redis_client(settings)
    try:
        async with db.session_scope() as session:
            gate = QuotaGate(
                engine_for(settings, redis),
                redis,
                session,
                Subject(
                    project_id=caller.project_id, user_id=caller.user_id, api_key_id=caller.key_id
                ),
                settings=settings,
            )
            await gate.commit(call_id=call_id, model_id=model, model_name=model_name, usage=usage)
    finally:
        await redis.aclose()


def _answered(model, result) -> tuple[str, str]:
    # The fallback's own price and name when it answered (as 06a's adapter).
    if result.fallback is not None and model.fallback_id:
        return model.fallback_id, result.fallback.target_model
    return model.id, model.name


async def _answer(caller, target, model, result, settings, scope) -> JSONResponse:
    model_id, model_name = _answered(model, result)
    await _commit(settings, caller, model_id, result.call_id, result.usage or {}, model_name)
    redis = redis_client(settings)
    try:
        async with db.session_scope() as session:
            guard = await FacadeGuard.load(session, redis, caller.project_id, scope=scope)
            message = {"role": "assistant", "content": result.message.get("content")}
            if message["content"]:
                checked = await guard.text("output.pre", message["content"])
                message["content"] = await guard.reveal(checked)
            if result.message.get("tool_calls"):
                message["tool_calls"] = await _checked_calls(guard, result.message["tool_calls"])
    finally:
        await redis.aclose()
    data = {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": target.name,
        "choices": [{"index": 0, "message": message, "finish_reason": result.finish_reason}],
        "usage": result.usage,
    }
    platform = _fallback_platform(result)
    if platform is not None:
        data["x_platform"] = platform
    return JSONResponse(data)


async def _checked_calls(guard: FacadeGuard, calls: list[dict]) -> list[dict]:
    """S9: a tool call's arguments reach the client only after `output.pre`, then with the
    request's placeholders reversed (C17)."""
    checked = []
    for call in calls:
        call = json.loads(json.dumps(call))
        function = call.get("function") or {}
        if function.get("arguments"):
            arguments = await guard.text("output.pre", function["arguments"])
            function["arguments"] = await guard.reveal(arguments, json_escape=True)
        checked.append(call)
    return checked


class _Held:
    """The answer held back until `output.pre` (buffered mode): text and tool call parts."""

    def __init__(self) -> None:
        self.content: list[str] = []
        self.calls: dict[int, dict] = {}
        self.size = 0
        self.finish: str | None = None

    def add(self, delta: dict) -> None:
        text = delta.get("content") or ""
        self.content.append(text)
        self.size += len(text.encode())
        for part in delta.get("tool_calls") or []:
            slot = self.calls.setdefault(
                part.get("index", 0),
                {"id": "", "type": "function", "function": {"name": "", "arguments": ""}},
            )
            slot["id"] = part.get("id") or slot["id"]
            function = part.get("function") or {}
            slot["function"]["name"] = function.get("name") or slot["function"]["name"]
            arguments = function.get("arguments") or ""
            slot["function"]["arguments"] += arguments
            self.size += len(arguments.encode())
        if self.size > OUTPUT_BUFFER_BYTES:
            raise ApiError(
                502,
                "api_error",
                "output_buffer_exceeded",
                "The answer held for the output guardrail exceeded its size limit.",
            )


class _LiveReveal:
    """C17 on the live direct stream: each choice's content and each tool call's argument
    deltas pass their own StreamDetokenizer, so a placeholder split over two chunks reaches the
    client as its value. A choice that finishes gets what is still held in its own delta; what
    is held when the stream ends without a finish comes in one last delta (`rest`)."""

    def __init__(self, guard: FacadeGuard) -> None:
        self._guard = guard
        # ("content", choice index) or ("arguments", choice index, tool call index)
        self._open: dict[tuple, Any] = {}
        self.unresolved = 0
        self.skipped = 0
        self.skipped_url = 0

    def _reveal(self, key: tuple):
        if key not in self._open:
            # Arguments are JSON text: a value goes in escaped (r1 MINOR-3).
            self._open[key] = self._guard.stream_reveal(json_escape=key[0] == "arguments")
        return self._open[key]

    async def choice(self, choice: dict) -> dict:
        if not self._guard.reveals:
            self.skipped += count_placeholders(choice.get("delta") or {})
            return choice
        index = choice.get("index", 0)
        delta = dict(choice.get("delta") or {})
        if delta.get("content"):
            delta["content"] = await self._reveal(("content", index)).feed(delta["content"])
        if delta.get("tool_calls"):
            parts = []
            for part in delta["tool_calls"]:
                part = json.loads(json.dumps(part))
                function = part.get("function") or {}
                if function.get("arguments"):
                    key = ("arguments", index, part.get("index", 0))
                    function["arguments"] = await self._reveal(key).feed(function["arguments"])
                parts.append(part)
            delta["tool_calls"] = parts
        if choice.get("finish_reason"):
            await self._close(index, delta)
        return dict(choice, delta=delta)

    async def _close(self, index: int, delta: dict) -> None:
        for key in [k for k in self._open if k[1] == index]:
            reveal = self._open.pop(key)
            tail = await reveal.flush()
            self.unresolved += reveal.unresolved
            self.skipped_url += reveal.skipped_url
            if not tail:
                continue
            if key[0] == "content":
                delta["content"] = (delta.get("content") or "") + tail
            else:
                delta.setdefault("tool_calls", []).append(
                    {"index": key[2], "function": {"arguments": tail}}
                )

    async def rest(self) -> dict:
        delta: dict[str, Any] = {}
        for index in sorted({k[1] for k in self._open}):
            await self._close(index, delta)
        return delta


async def _relay(stream, stack, gate, guard, model, public_name) -> AsyncIterator[str]:
    cid = f"chatcmpl-{uuid.uuid4().hex}"
    created = int(time.time())
    live = guard.streams_live
    held = _Held()
    revealer = _LiveReveal(guard)
    usage = None
    try:
        if stream.result.fallback is not None:
            yield chunk_json(
                _chunk(cid, created, public_name, {}, x_platform=_fallback_platform(stream.result))
            )
        if not live:
            yield chunk_json(
                _chunk(
                    cid,
                    created,
                    public_name,
                    {},
                    x_platform={"event": "progress", "kind": "output_buffered"},
                )
            )
        last = time.monotonic()
        try:
            async for chunk in stream:
                if chunk.get("usage"):
                    usage = chunk["usage"]
                for choice in chunk.get("choices") or []:
                    held.add(choice.get("delta") or {})
                    if choice.get("finish_reason"):
                        held.finish = choice["finish_reason"]
                if live:
                    chunk = dict(chunk, model=public_name, id=cid)
                    if chunk.get("choices"):
                        chunk["choices"] = [await revealer.choice(c) for c in chunk["choices"]]
                    yield chunk_json(chunk)
                elif time.monotonic() - last > KEEPALIVE_S:
                    yield KEEPALIVE
                last = time.monotonic()
        finally:
            model_id, model_name = _answered(model, stream.result)
            await gate.commit(
                call_id=stream.result.call_id,
                model_id=model_id,
                model_name=model_name,
                usage=stream.result.usage or {},
            )
        if live and (rest := await revealer.rest()):
            yield chunk_json(_chunk(cid, created, public_name, rest))
        log_unresolved(guard.scope, revealer.unresolved)
        log_skipped_policy(guard.scope, revealer.skipped)
        log_skipped_url(guard.scope, revealer.skipped_url)
        text = "".join(held.content)
        checked_text = await guard.text("output.pre", text) if text else text
        calls = [held.calls[i] for i in sorted(held.calls)]
        checked_calls = await _checked_calls(guard, calls) if calls else []
        if not live:
            delta: dict[str, Any] = {
                "role": "assistant",
                "content": await guard.reveal(checked_text),
            }
            if checked_calls:
                delta["tool_calls"] = [dict(c, index=i) for i, c in enumerate(checked_calls)]
            yield chunk_json(_chunk(cid, created, public_name, delta, held.finish))
            if usage is not None:
                yield chunk_json(
                    dict(_chunk(cid, created, public_name, {}), choices=[], usage=usage)
                )
        yield STREAM_END
    except ApiError as exc:
        # Headers are sent: the OpenAI form of an error inside a stream, then the end marker.
        log.warning("facade_stream_error code=%s model=%s", exc.code, public_name)
        yield error_event(exc)
        yield STREAM_END
    finally:
        await stack.aclose()
