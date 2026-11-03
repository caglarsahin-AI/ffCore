"""06b-2 external agent (`agents.kind = external`): an OpenAI-compatible agent elsewhere, behind
the facade (plan/06 "Connect Agent", minimum; K-06b-0002 S5, K-06b2-0002).

- Registration keeps `base_url`, the remote `model` and its `api_key` in `agents.external_config`
  (Fernet). The key is written, never read back (`***`), never exported in a manifest.
- The base URL passes the egress policy when it is registered, updated and published
  (check_base_url) and again at every connection (SafeOutboundClient's pinned backend: DNS
  rebinding is refused at the dial). Redirects are not followed: any 3xx is a failure.
- The call is not a run (K-06b2-0002 S1): the client's messages pass `input.pre` and `egress`,
  the request carries only the registered key (no user identity, no On-Behalf-Of), the answer
  is read as untrusted text: only `choices[0].message.content` is taken; tool calls and other
  fields are never executed or turned into text. The text then passes `output.pre`.
- Limits: the profile's model call timeout (`LLM_CALL_TIMEOUT_S`) for the whole call, at most
  MAX_EXTERNAL_RESPONSE_BYTES of answer; beyond either the call fails with a code, nothing
  partial reaches the client. Every call writes one audit event (host, status, time, bytes;
  never content). The call is outside token and USD quotas (S2, FOLLOWUP-144) and outside
  Langfuse (it does not go through LiteLLM).
"""

import asyncio
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import anyio
import httpx2
from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select

from ffcore.api.facade_schemas import AGENT_EVENTS_HEADER, KEEPALIVE, NUMERIC_PARAMS, STREAM_END
from ffcore.core import db
from ffcore.core.audit import AuditEntry, request_context, write_event_detached
from ffcore.core.auth import RoleRequirement, authorize
from ffcore.core.config import Settings
from ffcore.core.egress import (
    EgressError,
    EgressTimeout,
    EgressTimeoutError,
    Resolver,
    SafeOutboundClient,
)
from ffcore.core.errors import ApiError
from ffcore.models.agents import Agent
from ffcore.services.external_config import ExternalConfig
from ffcore.services.facade_guard import FacadeGuard, client_messages, message_text
from ffcore.services.facade_identity import FacadeCaller
from ffcore.services.facade_proxy import KEEPALIVE_S, _chunk, chunk_json, error_event
from ffcore.services.quota import redis_client

log = logging.getLogger("ffcore.facade")

MAX_EXTERNAL_RESPONSE_BYTES = 65_536
# The answer's finish reasons passed on as given; any other is reported as `stop`.
FINISH_REASONS = ("stop", "length")


def not_this_path() -> ApiError:
    """An external agent without a configuration or key (C11: the code stays frozen)."""
    return ApiError(
        501,
        "api_error",
        "external_agent_not_available",
        "The external agent has no endpoint key; an administrator must set it again.",
    )


class ExternalCallFailed(ApiError):
    """A failed external call; `audit` is what the audit event records (never content)."""

    def __init__(self, status_code: int, code: str, message: str, audit: dict[str, Any]) -> None:
        super().__init__(status_code, "api_error", code, message)
        self.audit = audit


@dataclass
class Upstream:
    content: str
    finish_reason: str
    host: str
    upstream_status: int
    response_bytes: int
    duration_ms: int
    ignored_fields: list[str] = field(default_factory=list)

    def audit(self) -> dict[str, Any]:
        return {
            "host": self.host,
            "upstream_status": self.upstream_status,
            "error_code": None,
            "duration_ms": self.duration_ms,
            "response_bytes": self.response_bytes,
        }


def _failed(code: str, error_code: str, audit: dict[str, Any]) -> ExternalCallFailed:
    audit["error_code"] = error_code
    if code == "external_agent_timeout":
        return ExternalCallFailed(504, code, "The external agent did not answer in time.", audit)
    if code == "external_agent_response_too_large":
        message = f"The external agent's answer exceeds {MAX_EXTERNAL_RESPONSE_BYTES} bytes."
        return ExternalCallFailed(502, code, message, audit)
    # The reason (egress code, upstream status) is in the audit event, never the upstream body.
    return ExternalCallFailed(502, code, "The external agent call failed.", audit)


def _content(raw: bytes) -> tuple[str, str, list[str]] | None:
    """(text, finish_reason, ignored field names) or None when the answer cannot be read. The one
    place an answer is parsed (review r1 MAJOR-1): invalid JSON, nesting deeper than the parser
    goes (RecursionError, not a ValueError), a wrong shape or no text content are all None."""
    try:
        payload = json.loads(raw)
        choice = payload["choices"][0]
        message = choice["message"]
    except (ValueError, RecursionError, KeyError, IndexError, TypeError):
        return None
    if not isinstance(choice, dict) or not isinstance(message, dict):
        return None
    content = message.get("content")
    if not isinstance(content, str) or not content:
        return None
    ignored = sorted(k for k, v in message.items() if k not in ("role", "content") and v)
    finish = choice.get("finish_reason")
    return content, finish if finish in FINISH_REASONS else "stop", ignored


async def call_upstream(
    config: ExternalConfig,
    messages: list[dict],
    params: dict[str, Any],
    settings: Settings,
    *,
    resolver: Resolver | None = None,
    inner_backend=None,
) -> Upstream:
    """One non-streaming chat completion at the external agent."""
    url = config.base_url.rstrip("/") + "/chat/completions"
    host = httpx2.URL(url).host
    limit = settings.llm_call_timeout_s
    audit: dict[str, Any] = {
        "host": host,
        "upstream_status": None,
        "error_code": None,
        "duration_ms": 0,
        "response_bytes": 0,
    }
    started = time.monotonic()
    body = {"model": config.model, "messages": messages, "stream": False, **params}
    headers = {"Authorization": f"Bearer {config.api_key.get_secret_value()}"}
    client = SafeOutboundClient(
        timeout=EgressTimeout(connect=min(10, limit), read=limit, total=limit),
        settings=settings,
        resolver=resolver,
        inner_backend=inner_backend,
        max_redirects=0,  # K-06b2-0002: redirects are not followed
    )
    raw = bytearray()
    try:
        try:
            with anyio.fail_after(limit):
                async with client, client.stream("POST", url, headers=headers, json=body) as resp:
                    audit["upstream_status"] = resp.status_code
                    declared = resp.headers.get("content-length")
                    if (
                        declared
                        and declared.isdigit()
                        and int(declared) > MAX_EXTERNAL_RESPONSE_BYTES
                    ):
                        audit["response_bytes"] = int(declared)
                        raise _failed("external_agent_response_too_large", "too_large", audit)
                    async for chunk in resp.aiter_bytes():
                        raw += chunk
                        if len(raw) > MAX_EXTERNAL_RESPONSE_BYTES:
                            audit["response_bytes"] = len(raw)
                            raise _failed("external_agent_response_too_large", "too_large", audit)
        except (TimeoutError, EgressTimeoutError, httpx2.TimeoutException):
            raise _failed("external_agent_timeout", "egress_timeout", audit) from None
        except EgressError as exc:
            raise _failed("external_agent_failed", exc.code, audit) from None
        except httpx2.HTTPError:
            raise _failed("external_agent_failed", "egress_request_failed", audit) from None
    finally:
        audit["duration_ms"] = int((time.monotonic() - started) * 1000)
    audit["response_bytes"] = len(raw)
    if not 200 <= audit["upstream_status"] < 300:
        raise _failed("external_agent_failed", "upstream_status", audit)
    answer = _content(bytes(raw))
    if answer is None:
        raise _failed("external_agent_failed", "invalid_answer", audit)
    content, finish, ignored = answer
    return Upstream(
        content=content,
        finish_reason=finish,
        host=host,
        upstream_status=audit["upstream_status"],
        response_bytes=len(raw),
        duration_ms=audit["duration_ms"],
        ignored_fields=ignored,
    )


# --- the facade path (agent:<project>/<external agent>) ---

# What an external agent request may carry besides messages: the numeric parameters and `stop`
# (text, through egress). Tool definitions and response formats mean nothing to a remote agent
# whose tool calls are never executed here; they are refused, not dropped.
EXTERNAL_PARAMS = (frozenset(NUMERIC_PARAMS) - {"n"}) | {"stop"}


def _invalid(code: str, message: str) -> ApiError:
    return ApiError(400, "invalid_request_error", code, message)


def events_on(request: Request) -> bool:
    value = (request.headers.get(AGENT_EVENTS_HEADER) or "all").strip().lower()
    if value not in ("all", "none"):
        raise _invalid("agent_events_invalid", f"{AGENT_EVENTS_HEADER} is 'all' or 'none'.")
    return value == "all"


async def find(caller: FacadeCaller, target) -> Agent | None:
    """The caller's external agent of this name, or None (the native path goes on)."""
    async with db.session_scope() as session:
        return await session.scalar(
            select(Agent).where(
                Agent.project_id == uuid.UUID(caller.project_id),
                Agent.key == target.key,
                Agent.kind == "external",
                Agent.deleted_at.is_(None),
            )
        )


def _outgoing(body, params: dict[str, Any]) -> list[dict]:
    """The client's messages; anything an external agent cannot take is refused."""
    refused = sorted(set(params) - EXTERNAL_PARAMS)
    if refused:
        raise _invalid("unsupported_field", f"Not supported for an external agent: {refused}")
    messages, dropped = client_messages(body)
    if dropped:
        log.info("facade_dropped_fields fields=%s", dropped)
    for m in messages:
        if m["role"] not in ("user", "assistant"):
            raise _invalid(
                "role_not_supported",
                f"An agent takes user and assistant messages only, not '{m['role']}'.",
            )
        if m.get("tool_calls") or m.get("name") or m.get("tool_call_id"):
            raise _invalid(
                "unsupported_field", "An external agent takes message role and content only."
            )
    if messages[-1]["role"] != "user":
        raise _invalid("last_message_not_user", "The last message must be the user's question.")
    return messages


async def _audit(request: Request, caller: FacadeCaller, agent: Agent, outcome: str, after):
    request_id, ip = request_context(request)
    await write_event_detached(
        AuditEntry(
            action="external_agent_call",
            resource_type="agent",
            outcome=outcome,
            actor_type=caller.actor.actor_type,
            actor_id=caller.actor.actor_id,
            project_id=caller.project_id,
            resource_id=str(agent.id),
            after=after,
            request_id=request_id,
            ip=ip,
            via_key_id=getattr(caller.actor, "via_key_id", None),
        )
    )


async def complete(
    request: Request, caller: FacadeCaller, target, agent: Agent, body, params, settings: Settings
):
    """One request to a published external agent. Not a run (K-06b2-0002 S1): guardrail events
    (source api) and one audit event per call are its record."""
    if agent.status != "published":
        raise ApiError(404, "not_found_error", "agent_not_published", "The agent is not published.")
    if agent.external_config is None:
        raise not_this_path()
    config = ExternalConfig.decrypt(agent.external_config, settings)
    if config.api_key is None:
        # Its key was reset when the base URL moved to another origin (review r1 MINOR-4).
        raise not_this_path()
    if caller.user_id is not None:
        # The user a key acts for must be a member (as on the native agent path).
        await authorize(
            request,
            caller.actor,
            caller.project_id,
            RoleRequirement("user", write=False, scope="project"),
        )
    stream_events = events_on(request)
    messages = _outgoing(body, params)
    redis = redis_client(settings)
    try:
        async with db.session_scope() as session:
            # No definition, so no policy key of its own: the project's default policy.
            guard = await FacadeGuard.load(session, redis, caller.project_id)
            outgoing = []
            for m in messages:
                text = message_text(m)
                if m["role"] == "user":
                    text = await guard.text("input.pre", text)
                outgoing.append({"role": m["role"], "content": await guard.text("egress", text)})
            if params.get("stop") is not None:
                params["stop"] = await guard.json_text("egress", params["stop"])
    finally:
        await redis.aclose()
    work = _Work(request, caller, agent, config, outgoing, params, settings, guard.scope)
    if body.stream:
        return StreamingResponse(
            _stream(work, target.name, stream_events),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    content, finish = await work.run()
    message = {"role": "assistant", "content": content}
    return JSONResponse(
        {
            "id": work.cid,
            "object": "chat.completion",
            "created": work.created,
            "model": target.name,
            "choices": [{"index": 0, "message": message, "finish_reason": finish}],
        }
    )


@dataclass
class _Work:
    request: Request
    caller: FacadeCaller
    agent: Agent
    config: ExternalConfig
    messages: list[dict]
    params: dict[str, Any]
    settings: Settings
    scope: str
    cid: str = field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex}")
    created: int = field(default_factory=lambda: int(time.time()))

    async def run(self) -> tuple[str, str]:
        """The call, its audit event, then `output.pre` on the answer's text."""
        started = time.monotonic()
        try:
            answer = await call_upstream(self.config, self.messages, self.params, self.settings)
        except asyncio.CancelledError:
            # The client went away mid-stream (review r1 MINOR-7): the call is cancelled and
            # still has its audit event; shielded, so the write itself is not cancelled.
            audit = {
                "host": httpx2.URL(self.config.base_url).host,
                "upstream_status": None,
                "error_code": "client_disconnected",
                "duration_ms": int((time.monotonic() - started) * 1000),
                "response_bytes": 0,
            }
            await asyncio.shield(_audit(self.request, self.caller, self.agent, "error", audit))
            raise
        except ExternalCallFailed as exc:
            await _audit(self.request, self.caller, self.agent, "error", exc.audit)
            log.warning(
                "facade_external_call agent=%s code=%s reason=%s",
                self.agent.id,
                exc.code,
                exc.audit.get("error_code"),
            )
            raise
        await _audit(self.request, self.caller, self.agent, "success", answer.audit())
        if answer.ignored_fields:
            # The count only (review r1 MINOR-5): the names are the upstream's text and never
            # passed output.pre, so they stay out of the log.
            log.info(
                "facade_external_ignored agent=%s fields=%d",
                self.agent.id,
                len(answer.ignored_fields),
            )
        redis = redis_client(self.settings)
        try:
            async with db.session_scope() as session:
                guard = await FacadeGuard.load(
                    session, redis, self.caller.project_id, scope=self.scope
                )
                checked = await guard.text("output.pre", answer.content)
                # C17: an upstream that echoes this request's placeholder gets the value back
                # to the same caller; one this scope never issued stays as it is.
                content = await guard.reveal(checked)
        finally:
            await redis.aclose()
        return content, answer.finish_reason


# Calls cancelled by a client disconnect, until their audit event is written.
_CANCELLED: set[asyncio.Task] = set()


async def _stream(work: _Work, public_name: str, stream_events: bool) -> AsyncIterator[str]:
    """The answer comes whole (upstream `stream: false`): keepalive while waiting, then the
    output-checked text as one chunk (S4, S6)."""
    try:
        if stream_events:
            yield chunk_json(
                _chunk(
                    work.cid,
                    work.created,
                    public_name,
                    {},
                    x_platform={"event": "progress", "kind": "output_buffered"},
                )
            )
        task = asyncio.ensure_future(work.run())
        try:
            while True:
                done, _ = await asyncio.wait({task}, timeout=KEEPALIVE_S)
                if done:
                    break
                yield KEEPALIVE
        finally:
            if not task.done():
                # Kept referenced until it has written its audit event (the loop holds tasks
                # weakly).
                _CANCELLED.add(task)
                task.add_done_callback(_CANCELLED.discard)
                task.cancel()
        content, finish = task.result()
        delta = {"role": "assistant", "content": content}
        yield chunk_json(_chunk(work.cid, work.created, public_name, delta))
        yield chunk_json(_chunk(work.cid, work.created, public_name, {}, finish))
        yield STREAM_END
    except ApiError as exc:
        log.warning("facade_stream_error code=%s model=%s", exc.code, public_name)
        yield error_event(exc)
        yield STREAM_END
