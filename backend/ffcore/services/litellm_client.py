"""LiteLLM client: every model call of the backend goes through here (brief 01 madde 2, A4).

The backend calls the LiteLLM proxy with one internal key; project and user travel in `user` and
`metadata`. Fallback is explicit (K-01-0004 karar A): the request carries
`fallbacks=["<project>.chat-fallback"]` only when the project has an active `chat-fallback`
model; LiteLLM's global router settings are never written (`/config/update` stores the master key
in plain text). Which deployment answered is read from `x-litellm-model-id`, which the reconciler
sets to our `models.id`; a different id than the requested model's is a `FallbackObserved`.
"""

import json
import logging
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

import httpx2
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ffcore.core.config import Settings
from ffcore.core.egress import EgressError, EgressTimeout, SafeOutboundClient
from ffcore.core.errors import ApiError
from ffcore.models.catalog import Model, Provider, litellm_name
from ffcore.models.identity import Project

log = logging.getLogger("ffcore.litellm_client")

DEFAULT_KEY = "chat-default"
FALLBACK_KEY = "chat-fallback"
CHAT_PATH = "/v1/chat/completions"


class LiteLLMNotConfigured(RuntimeError):
    """LITELLM_URL or one of its keys is not set; model calls are impossible, not skipped."""


@dataclass(frozen=True)
class LiteLLMSettings:
    url: str
    master_key: str
    internal_key: str

    def __repr__(self) -> str:
        return f"LiteLLMSettings(url={self.url!r}, master_key='***', internal_key='***')"


def litellm_settings(settings: Settings) -> LiteLLMSettings:
    missing = [
        name
        for name, value in (
            ("LITELLM_URL", settings.litellm_url),
            ("LITELLM_MASTER_KEY", settings.litellm_master_key),
            ("LITELLM_INTERNAL_KEY", settings.litellm_internal_key),
        )
        if not value
    ]
    if missing:
        raise LiteLLMNotConfigured(f"not set: {', '.join(missing)}")
    assert settings.litellm_url and settings.litellm_master_key and settings.litellm_internal_key
    return LiteLLMSettings(
        url=settings.litellm_url.rstrip("/"),
        master_key=settings.litellm_master_key.get_secret_value(),
        internal_key=settings.litellm_internal_key.get_secret_value(),
    )


class LiteLLMError(RuntimeError):
    """LiteLLM answered an error to a management or model call. The message carries only
    `safe_error()` fields, never the upstream text (r1 MAJOR-2)."""

    def __init__(self, status: int, path: str, summary: str) -> None:
        super().__init__(f"LiteLLM {path} answered {summary}")
        self.status = status
        self.path = path


_TOKEN = re.compile(r"[^a-z0-9_.-]")
_CALL_ID = re.compile(r"^[0-9a-fA-F-]{8,64}$")


def _token(value: Any) -> str:
    """A short enum-like value from an untrusted body: lower case, [a-z0-9_.-] only."""
    return _TOKEN.sub("", str(value).lower())[:40] or "unknown"


def safe_error(response: httpx2.Response) -> str:
    """What may be logged about an error answer: status, the error's type and code as short
    tokens, and LiteLLM's call id (the full text is in LiteLLM's own, internal log). The message
    is never used: providers echo requests, keys and user text into it (r1 MAJOR-2)."""
    kind = code = "unknown"
    try:
        error = response.json().get("error")
    except (ValueError, AttributeError):
        error = None
    if isinstance(error, dict):
        kind, code = _token(error.get("type")), _token(error.get("code"))
    call_id = response.headers.get("x-litellm-call-id", "")
    call_id = call_id if _CALL_ID.match(call_id) else "unknown"
    return (
        f"upstream_status={response.status_code} error_type={kind} error_code={code}"
        f" call_id={call_id}"
    )


class ModelUnavailable(ApiError):
    """The model could not answer (provider down, timeout, LiteLLM unreachable). No silent
    degrade: with no `chat-fallback` record this is the caller's answer (brief 01 madde 1)."""

    def __init__(self, reason: str) -> None:
        super().__init__(
            503, "api_error", "model_unavailable", "The model is not available right now."
        )
        self.reason = reason


class ModelNotFound(ApiError):
    """No active model with this key in the project, or the project is deleted (permanent: 404,
    not a retry signal; r1 MINOR-1, K-01-0012)."""

    def __init__(self, model_key: str, reason: str) -> None:
        super().__init__(
            404, "not_found_error", "model_not_found", f"No active model {model_key} in project."
        )
        self.reason = reason


class ModelCallFailed(ApiError):
    """The provider answered, but not with a usable result: `upstream_error` (an error inside a
    200 answer or stream) or `stream_incomplete` (the stream ended before it completed). A
    partial answer is never a success (ARCH-06, r1 MAJOR-3)."""

    MESSAGES = {
        "upstream_error": "The model provider reported an error.",
        "stream_incomplete": "The model stream ended before the answer was complete.",
    }

    def __init__(self, code: str) -> None:
        super().__init__(502, "api_error", code, self.MESSAGES[code])


class EmptyCompletion(ApiError):
    """The model answered nothing (D6): an error, never an empty string handed on."""

    def __init__(self, model: str, finish_reason: str | None) -> None:
        super().__init__(502, "api_error", "empty_completion", "The model returned no answer.")
        self.model = model
        self.finish_reason = finish_reason


@dataclass(frozen=True)
class FallbackObserved:
    """The configured `chat-fallback` answered instead of the requested model. 06a writes it as
    a `run_events.fallback` event and a Langfuse tag."""

    source_model: str
    target_model: str
    reason: str


@dataclass(frozen=True)
class ModelTarget:
    """What to call: the virtual name and models.id, and the fallback if one is configured."""

    name: str
    id: str
    fallback_name: str | None = None
    fallback_id: str | None = None


@dataclass
class ChatResult:
    content: str
    message: dict[str, Any]
    finish_reason: str | None
    usage: dict[str, Any] | None
    fallback: FallbackObserved | None


@dataclass
class StreamResult:
    """Filled while the stream is read; complete once iteration ends."""

    fallback: FallbackObserved | None = None
    usage: dict[str, Any] | None = None
    finish_reason: str | None = None
    content: list[str] = field(default_factory=list)
    tool_calls: bool = False


async def resolve_target(session: AsyncSession, project_id: Any, model_key: str) -> ModelTarget:
    """Short name in a project -> LiteLLM target (C1). Only `chat-default` gets a fallback, and
    only when the project has an active `chat-fallback` record (karar A, K-01-0004)."""
    rows = await session.execute(
        select(Model.id, Model.key, Project.key, Project.deleted_at)
        .join(Project, Project.id == Model.project_id)
        .join(Provider, Provider.id == Model.provider_id)
        .where(
            Model.project_id == project_id,
            Model.key.in_([model_key, FALLBACK_KEY]),
            Model.deleted_at.is_(None),
            Model.is_active.is_(True),
            Model.category == "llm",
            Provider.is_active.is_(True),
        )
    )
    found = {}
    for model_id, key, project_key, project_deleted in rows:
        if project_deleted is not None:
            # Its models leave LiteLLM at the next reconcile; until then nothing calls them.
            raise ModelNotFound(model_key, "project_deleted")
        found[key] = (str(model_id), project_key)
    if model_key not in found:
        raise ModelNotFound(model_key, "no_active_model")
    model_id, project_key = found[model_key]
    if model_key == DEFAULT_KEY and FALLBACK_KEY in found:
        fallback_id, _ = found[FALLBACK_KEY]
        return ModelTarget(
            litellm_name(project_key, model_key),
            model_id,
            litellm_name(project_key, FALLBACK_KEY),
            fallback_id,
        )
    return ModelTarget(litellm_name(project_key, model_key), model_id)


class LiteLLMClient:
    """Model calls with the internal key, through SafeOutboundClient (C5; LiteLLM is internal,
    its host must be in ALLOWED_INTERNAL_HOSTS)."""

    def __init__(self, settings: Settings, **client_options) -> None:
        self._conf = litellm_settings(settings)
        # LiteLLM may try the primary 1 + NUM_RETRIES times and the fallback as often, each up
        # to the per-call timeout; our wait covers that, plus a margin.
        budget = settings.llm_call_timeout_s * 6 + 30
        timeout = EgressTimeout(connect=5, read=budget, total=budget)
        self._client = SafeOutboundClient(timeout=timeout, settings=settings, **client_options)

    async def __aenter__(self) -> "LiteLLMClient":
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self._client.aclose()

    def _body(self, target, messages, user, metadata, stream, params) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": target.name,
            "messages": messages,
            "user": user,
            "metadata": metadata,
            **params,
        }
        if target.fallback_name:
            body["fallbacks"] = [target.fallback_name]
        if body.get("tools"):
            # Qwen over Ollama: one call at a time (brief 01 teknik notlar).
            body["parallel_tool_calls"] = False
        if stream:
            body["stream"] = True
            body["stream_options"] = {"include_usage": True}
        return body

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._conf.internal_key}"}

    async def chat(
        self,
        target: ModelTarget,
        messages: list[dict[str, Any]],
        *,
        user: str,
        metadata: dict[str, Any],
        **params: Any,
    ) -> ChatResult:
        body = self._body(target, messages, user, metadata, False, params)
        try:
            response = await self._client.request(
                "POST", f"{self._conf.url}{CHAT_PATH}", headers=self._headers(), json=body
            )
        except EgressError as exc:
            raise _unavailable(target, exc.code) from None
        _raise_for_status(target, response)
        fallback = _fallback(target, response)
        try:
            data = response.json()
            choice = data["choices"][0]
        except (ValueError, KeyError, IndexError, TypeError):
            # A 200 that is not a completion (e.g. {"error": ...}): its text is not trusted.
            raise _failed(target, "upstream_error", safe_error(response)) from None
        message = choice.get("message") or {}
        content = message.get("content") or ""
        if not content.strip() and not message.get("tool_calls"):
            raise _empty(target, choice.get("finish_reason"))
        return ChatResult(
            content, message, choice.get("finish_reason"), data.get("usage"), fallback
        )

    @asynccontextmanager
    async def chat_stream(
        self,
        target: ModelTarget,
        messages: list[dict[str, Any]],
        *,
        user: str,
        metadata: dict[str, Any],
        **params: Any,
    ) -> AsyncIterator["ChatStream"]:
        """`async with client.chat_stream(...) as stream: async for chunk in stream: ...`.
        Chunks are OpenAI chunk dicts; `stream.result` holds the fallback (known before the
        first chunk), usage and finish reason (complete after the last)."""
        body = self._body(target, messages, user, metadata, True, params)
        try:
            async with self._client.stream(
                "POST", f"{self._conf.url}{CHAT_PATH}", headers=self._headers(), json=body
            ) as response:
                if response.status_code >= 400:
                    await response.aread()
                _raise_for_status(target, response)
                result = StreamResult(fallback=_fallback(target, response))
                yield ChatStream(target, response, result)
        except EgressError as exc:
            raise _unavailable(target, exc.code) from None


class ChatStream:
    def __init__(self, target: ModelTarget, response: httpx2.Response, result: StreamResult):
        self._target = target
        self._response = response
        self.result = result

    async def __aiter__(self) -> AsyncIterator[dict[str, Any]]:
        """Completion contract of the pinned proxy (v1.80.0, include_usage on): a finish_reason,
        then a usage chunk, then `[DONE]`. A stream is complete when a finish_reason was seen and
        then `[DONE]` or the usage chunk; anything else that ends is `stream_incomplete`. An
        error object in the stream is `upstream_error` and is not handed to the caller."""
        done = False
        try:
            async for line in self._response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                payload = line[len("data:") :].strip()
                if payload == "[DONE]":
                    done = True
                    break
                try:
                    chunk = json.loads(payload)
                except ValueError:
                    raise _failed(self._target, "upstream_error", "unparseable chunk") from None
                if not isinstance(chunk, dict) or "error" in chunk:
                    raise _failed(self._target, "upstream_error", "error in stream")
                self._record(chunk)
                yield chunk
        except httpx2.HTTPError as exc:
            raise _failed(self._target, "stream_incomplete", type(exc).__name__) from None
        if not self.result.finish_reason or not (done or self.result.usage):
            raise _failed(self._target, "stream_incomplete", "ended before completion")
        if not "".join(self.result.content).strip() and not self.result.tool_calls:
            raise _empty(self._target, self.result.finish_reason)

    def _record(self, chunk: dict[str, Any]) -> None:
        if chunk.get("usage"):
            self.result.usage = chunk["usage"]
        for choice in chunk.get("choices") or []:
            delta = choice.get("delta") or {}
            if delta.get("content"):
                self.result.content.append(delta["content"])
            if delta.get("tool_calls"):
                self.result.tool_calls = True
            if choice.get("finish_reason"):
                self.result.finish_reason = choice["finish_reason"]


def _unavailable(target: ModelTarget, reason: str) -> ModelUnavailable:
    log.warning("model_unavailable model=%s reason=%s", target.name, reason)
    return ModelUnavailable(reason)


def _failed(target: ModelTarget, code: str, detail: str) -> ModelCallFailed:
    # `detail` is ours or safe_error(); never provider text.
    log.warning("model_call_failed model=%s code=%s detail=%s", target.name, code, detail)
    return ModelCallFailed(code)


def _empty(target: ModelTarget, finish_reason: str | None) -> EmptyCompletion:
    log.error("empty_completion model=%s finish_reason=%s", target.name, finish_reason)
    return EmptyCompletion(target.name, finish_reason)


def _raise_for_status(target: ModelTarget, response: httpx2.Response) -> None:
    status = response.status_code
    if status < 400:
        return
    summary = safe_error(response)
    try:
        message = str((response.json().get("error") or {}).get("message", ""))
    except (ValueError, AttributeError):
        message = ""
    # The message is only compared with a fixed phrase, never logged or raised.
    if status == 400 and "Invalid model name" in message:
        # resolve_target found the row, so LiteLLM is behind the tables: a reconcile is pending
        # or failed (litellm_reconcile_failed in the log). Not the caller's mistake.
        log.error("litellm_model_not_registered model=%s %s", target.name, summary)
        raise ModelUnavailable("not_registered")
    if status >= 500 or status in (404, 408, 429):
        # LiteLLM answers 500 when the upstream (and any fallback) failed (U3).
        log.warning("litellm_upstream_error model=%s %s", target.name, summary)
        raise ModelUnavailable(f"http_{status}")
    log.warning("litellm_request_refused model=%s %s", target.name, summary)
    raise LiteLLMError(status, CHAT_PATH, summary)


def _fallback(target: ModelTarget, response: httpx2.Response) -> FallbackObserved | None:
    answered = response.headers.get("x-litellm-model-id")
    if answered == target.id:
        return None
    if target.fallback_id and answered == target.fallback_id:
        assert target.fallback_name
        return FallbackObserved(target.name, target.fallback_name, "primary_failed")
    # No header, or a deployment we did not ask for: the answer cannot be attributed.
    shown = answered if answered and _CALL_ID.match(answered) else "missing-or-invalid"
    raise _unavailable(target, f"unexpected deployment {shown}")
