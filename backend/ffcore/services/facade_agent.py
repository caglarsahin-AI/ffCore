"""The facade's agent path (06b): `agent:<project_key>/<agent_key>` runs the published version
through the 06a runtime and turns the run's events into OpenAI chunks.

- The run is a normal run (`channel=api`, `trigger_type=api`) of the caller: a user the key acts
  for, or the key itself (B7: `runs.user_id` empty, `runs.api_key_id` set; its searches use the
  key's acl_role, S2). Quota, guardrails, approvals and retention are the runtime's.
- Context (S3): without `X-Conversation-Id` each request is a new conversation; the client's
  earlier messages become its history rows after `input.pre` and `egress` (they leave with the
  run's prompt). With the header the history is the stored conversation's and the request holds
  only the new user message. The conversation id comes back in the `X-Conversation-Id` header.
- Events: tokens become `delta.content`; tool calls, results, sources, progress and fallback
  become one `x_platform` chunk each (the 06a payloads, arguments already masked by `tool.pre`,
  K-06a-0021); sources also become `annotations[]` (`url_citation`) on the last chunk.
  `X-Agent-Events: none` sends text only, except the approval chunk's ids (the client needs
  them to continue).
- A run waiting for approval ends the stream with `finish_reason: "approval_required"` and
  `x_platform.approval_id` / `run_id`; the client cannot approve (C4). After a person approves in
  the console, `X-Resume-Run-Id: <run id>` follows the run from where it stopped.
- Once the HTTP answer has started, a failure is an OpenAI error event in the stream; a
  non-streaming request gets the HTTP status (400 guardrail_blocked, 429 quota_exceeded, ...).
"""

import json
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select

from ffcore.api.facade_schemas import (
    AGENT_EVENTS_HEADER,
    CONVERSATION_HEADER,
    KEEPALIVE,
    RESUME_HEADER,
    STREAM_END,
)
from ffcore.api.runs import (
    _audit,
    _finished,
    _queued_event,
    _replay_rows,
    exit_hook,
    live_transform,
    policy_allows_reveal,
)
from ffcore.core import db
from ffcore.core.auth import RoleRequirement, authorize
from ffcore.core.config import Settings
from ffcore.core.errors import ApiError, error_body
from ffcore.models.agents import Agent, AgentVersion
from ffcore.models.runs import Conversation, Message, Run, RunEvent
from ffcore.runtime import events as run_events
from ffcore.runtime.contracts import Channel, RunEventType, RunStatus, TriggerType
from ffcore.runtime.definition import parse_definition
from ffcore.services import facade_external
from ffcore.services.facade_guard import FacadeGuard, client_messages, message_text
from ffcore.services.facade_identity import FacadeCaller
from ffcore.services.facade_proxy import call_params, chunk_json
from ffcore.services.quota import redis_client

RUN_ID_HEADER = "X-Run-Id"
WAITING = (RunStatus.waiting_approval, RunStatus.waiting_user)
# A run's failure code → the facade's HTTP answer (non-streaming) and its C11 code.
FAILURES = {
    "guardrail_block": (400, "invalid_request_error", "guardrail_blocked"),
    "quota_exceeded": (429, "rate_limit_error", "quota_exceeded"),
    "pricing_missing": (409, "conflict_error", "pricing_missing"),
    "quota_unavailable": (503, "api_error", "quota_unavailable"),
    "model_unavailable": (503, "api_error", "model_unavailable"),
}
_MARK = re.compile(r"\[(\d+)\]")


def _invalid(code: str, message: str) -> ApiError:
    return ApiError(400, "invalid_request_error", code, message)


def _not_found(code: str, message: str) -> ApiError:
    return ApiError(404, "not_found_error", code, message)


def events_mode(request: Request) -> bool:
    value = (request.headers.get(AGENT_EVENTS_HEADER) or "all").strip().lower()
    if value not in ("all", "none"):
        raise _invalid("agent_events_invalid", f"{AGENT_EVENTS_HEADER} is 'all' or 'none'.")
    return value == "all"


# --- starting a run ---


def _split(body) -> tuple[list[dict], str, list[str]]:
    """(earlier messages, the new user question, echo fields left out). The agent's own
    instructions govern: system and developer messages are refused, not merged; the last
    message must be the user's."""
    messages, dropped = client_messages(body)
    for m in messages:
        if m["role"] not in ("user", "assistant"):
            raise _invalid(
                "role_not_supported",
                f"An agent takes user and assistant messages only, not '{m['role']}'.",
            )
    if messages[-1]["role"] != "user":
        raise _invalid("last_message_not_user", "The last message must be the user's question.")
    question = message_text(messages[-1]).strip()
    if not question:
        raise _invalid("empty_question", "The user's question is empty.")
    return messages[:-1], question, dropped


async def _agent_version(session, caller: FacadeCaller, target) -> tuple[Agent, AgentVersion]:
    agent = await session.scalar(
        select(Agent).where(
            Agent.project_id == uuid.UUID(caller.project_id),
            Agent.key == target.key,
            Agent.deleted_at.is_(None),
        )
    )
    if agent is None:
        raise _not_found("model_not_found", f"The model '{target.name}' does not exist.")
    if agent.status != "published" or agent.current_version_id is None:
        raise _not_found("agent_not_published", "The agent is not published.")
    return agent, await session.get(AgentVersion, agent.current_version_id)


async def _conversation(session, caller, agent, conversation_id: str) -> Conversation:
    try:
        cid = uuid.UUID(conversation_id)
    except ValueError:
        raise _not_found("conversation_not_found", "Conversation not found.") from None
    owner = (
        Conversation.user_id == uuid.UUID(caller.user_id)
        if caller.user_id
        else (Conversation.user_id.is_(None) & (Conversation.created_by == caller.key_id))
    )
    conversation = await session.scalar(
        select(Conversation).where(
            Conversation.id == cid,
            Conversation.project_id == uuid.UUID(caller.project_id),
            Conversation.agent_id == agent.id,
            Conversation.deleted_at.is_(None),
            owner,
        )
    )
    if conversation is None:
        raise _not_found("conversation_not_found", "Conversation not found.")
    return conversation


async def start(request: Request, caller: FacadeCaller, target, body, settings, queue) -> Run:
    earlier, question, dropped = _split(body)
    if caller.user_id is not None:
        # The user a key acts for must be a member (03a _grant; X-On-Behalf-Of reaches here
        # without a membership check, the `user` field was checked in facade_identity).
        await authorize(
            request,
            caller.actor,
            caller.project_id,
            RoleRequirement("user", write=False, scope="project"),
        )
    conversation_id = request.headers.get(CONVERSATION_HEADER)
    if conversation_id and earlier:
        raise _invalid(
            "conversation_history_conflict",
            f"With {CONVERSATION_HEADER} the history is the stored one; "
            "send only the new question.",
        )
    redis = redis_client(settings)
    try:
        async with db.session_scope() as session:
            agent, version = await _agent_version(session, caller, target)
            if agent.kind != "native":
                # complete() sends an external agent its own way first; it is never a run.
                raise facade_external.not_this_path()
            definition = parse_definition(version.definition)
            run_id = uuid.uuid4()
            history = []
            if earlier:
                # S3: the client's history leaves with the run's prompt. Its checks share the
                # run's token scope; the events are written without a run (it does not exist yet).
                # The rows keep the text as egress left it, in the run's scope (r2 MAJOR-r2-3: no
                # raw value is stored or carried); `_history` reads rows without a run in the
                # scope of the run whose question follows them. The scope's counter first passes
                # every number the request carries in (r2 MAJOR-r2-2).
                guard = await FacadeGuard.load(
                    session,
                    redis,
                    caller.project_id,
                    policy_key=definition.guardrail_policy_key,
                    scope=str(run_id),
                )
                await guard.reserve_carried([message_text(m) for m in earlier] + [question])
                for m in earlier:
                    text = message_text(m)
                    if m["role"] == "user":
                        text = await guard.text("input.pre", text)
                    text = await guard.text("egress", text)  # a block stops the request here
                    history.append((m["role"], text))
            if conversation_id:
                conversation = await _conversation(session, caller, agent, conversation_id)
            else:
                conversation = Conversation(
                    project_id=agent.project_id,
                    agent_id=agent.id,
                    user_id=uuid.UUID(caller.user_id) if caller.user_id else None,
                    title=question[:80],
                    created_by=caller.actor.actor_id if caller.user_id else caller.key_id,
                )
                session.add(conversation)
                await session.flush()
            # Explicit times: rows written in one transaction would share now(), and the
            # runtime reads history in created_at order.
            at = datetime.now(UTC)
            for i, (role, text) in enumerate(history):
                session.add(
                    Message(
                        conversation_id=conversation.id,
                        role=role,
                        content=text,
                        created_at=at + timedelta(microseconds=i),
                    )
                )
            await session.flush()
            run = Run(
                id=run_id,
                project_id=agent.project_id,
                agent_id=agent.id,
                agent_version_id=version.id,
                conversation_id=conversation.id,
                user_id=uuid.UUID(caller.user_id) if caller.user_id else None,
                api_key_id=uuid.UUID(caller.key_id),
                channel=Channel.api,
                trigger_type=TriggerType.api,
                status=RunStatus.queued,
                input=question,
                variables={},
                created_by=caller.actor.actor_id,
            )
            session.add(run)
            await session.flush()
            session.add(
                Message(
                    conversation_id=conversation.id,
                    run_id=run.id,
                    role="user",
                    content=question,
                    created_at=at + timedelta(microseconds=len(history)),
                )
            )
            await _audit(
                session,
                request,
                caller.actor,
                agent.project_id,
                "start_run",
                run.id,
                after={
                    "agent_id": str(agent.id),
                    "version": version.version,
                    "channel": "api",
                    # r2 MINOR-A: SDK echo fields of earlier answers, left out (names only).
                    **({"dropped_fields": dropped} if dropped else {}),
                },
            )
            await session.commit()
            await _queued_event(session, settings, run)
    finally:
        await redis.aclose()
    await queue.enqueue(str(run.id))
    return run


async def resumable(caller: FacadeCaller, run_id: str) -> tuple[Run, str]:
    """(run, Last-Event-ID): the caller's own run, followed from its last approval or question.
    Still waiting → 409: the person has not decided yet (C4: the client cannot)."""
    try:
        rid = uuid.UUID(run_id)
    except ValueError:
        raise _not_found("run_not_found", "Run not found.") from None
    async with db.session_scope() as session:
        run = await session.scalar(
            select(Run).where(Run.id == rid, Run.project_id == uuid.UUID(caller.project_id))
        )
        mine = run is not None and (
            run.user_id == uuid.UUID(caller.user_id)
            if caller.user_id
            else (run.user_id is None and str(run.api_key_id) == caller.key_id)
        )
        if not mine:
            raise _not_found("run_not_found", "Run not found.")
        if run.status in WAITING:
            raise ApiError(
                409, "conflict_error", "run_still_waiting", "The run still waits for a person."
            )
        seq = await session.scalar(
            select(RunEvent.seq)
            .where(
                RunEvent.run_id == rid,
                RunEvent.type.in_([RunEventType.approval_requested, RunEventType.question]),
            )
            .order_by(RunEvent.seq.desc())
            .limit(1)
        )
    return run, f"{seq or 0}-0"


# --- events → OpenAI ---


@dataclass
class Translation:
    """What the client has been sent so far; the answer and its sources for annotations."""

    cid: str
    created: int
    model: str
    run_id: str
    events_on: bool
    text: list[str] = field(default_factory=list)
    sources: dict[int, dict] = field(default_factory=dict)
    platform: list[dict] = field(default_factory=list)
    finish: str | None = None
    error: ApiError | None = None
    approval: dict | None = None
    closed: bool = False  # the finishing chunk has been sent (approval, question)

    def chunk(self, delta: dict, finish=None, **extra) -> dict:
        return {
            "id": self.cid,
            "object": "chat.completion.chunk",
            "created": self.created,
            "model": self.model,
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
            **extra,
        }

    def _platform(self, data: dict) -> list[dict]:
        self.platform.append(data)
        return [self.chunk({}, x_platform=data)] if self.events_on else []

    def on(self, event: str, data: dict) -> list[dict]:
        """Chunks for one run event; terminal events set `finish` or `error`."""
        if event == "token":
            text = data.get("text") or ""
            self.text.append(text)
            return [self.chunk({"content": text})] if text else []
        if event == "sources":
            for s in data.get("sources") or []:
                if isinstance(s.get("n"), int):
                    self.sources[s["n"]] = s
            return self._platform({"event": "sources", "sources": data.get("sources") or []})
        if event in ("tool_call", "tool_result", "fallback"):
            return self._platform({"event": event, **data})
        if event == "progress":
            kind = data.get("stage") or data.get("status") or "step"
            return self._platform({"event": "progress", "kind": kind, **data})
        if event == "approval_required":
            self.finish = "approval_required"
            ids = {
                "run_id": self.run_id,
                "approval_id": data.get("approval_id"),
                "expires_at": data.get("expires_at"),
            }
            full = {"event": "approval_required", **data, **ids}
            self.platform.append(full)
            # The one x_platform chunk sent with X-Agent-Events: none: the ids the client needs,
            # never the action's arguments.
            shown = full if self.events_on else {"event": "approval_required", **ids}
            self.approval = shown
            self.closed = True
            return [self.chunk({}, "approval_required", x_platform=shown)]
        if event == "question":
            self.finish = "stop"
            question = str(data.get("question") or "")
            self.text.append(question)
            payload = {"event": "question", "run_id": self.run_id, "question": question}
            self.platform.append(payload)
            extra = {"x_platform": payload} if self.events_on else {}
            self.closed = True
            return [self.chunk({"content": question}, "stop", **extra)]
        if event == "done":
            self.finish = "stop"
            return []
        if event == "error":
            status, kind, code = FAILURES.get(
                data.get("code") or "", (502, "api_error", data.get("code") or "run_failed")
            )
            message = data.get("message") or "The agent run failed."
            if data.get("reference_id"):
                message = f"{message} (reference {data['reference_id']})"
            self.error = ApiError(status, kind, code, message)
            return []
        return []  # an event this facade does not know: ignored (C9 consumer rule)

    def annotations(self) -> list[dict]:
        """OpenAI `url_citation` per `[n]` marker the answer carries for a known source."""
        answer = "".join(self.text)
        out = []
        for match in _MARK.finditer(answer):
            source = self.sources.get(int(match.group(1)))
            if source is None:
                continue
            url = f"ffcore://knowledge-bases/{source.get('kb_key')}/documents/{source.get('document_id')}"
            if source.get("page"):
                url += f"#page={source['page']}"
            out.append(
                {
                    "type": "url_citation",
                    "url_citation": {
                        "url": url,
                        "title": source.get("document_name") or "",
                        "start_index": match.start(),
                        "end_index": match.end(),
                    },
                }
            )
        return out


def _parse(text: str) -> tuple[str, dict] | None:
    event, data = None, None
    for line in text.splitlines():
        if line.startswith("event: "):
            event = line[7:]
        elif line.startswith("data: "):
            data = json.loads(line[6:])
    return (event, data) if event is not None and data is not None else None


async def _events(settings: Settings, run: Run, after: str | None):
    client = run_events.redis_client(settings)
    async with db.session_scope() as session:
        allowed = await policy_allows_reveal(session, run)
    reveal = exit_hook(client, run.id, "reveal" if allowed else "policy")
    try:
        async for text in run_events.follow(
            client,
            run.id,
            after=after,
            keepalive_s=settings.sse_keepalive_s,
            grace_s=settings.run_abandon_grace_s,
            # C17 S8: the caller is the run's owner (start, or `resumable` checked it), so
            # placeholders go back to their values here, before the translation (annotation
            # offsets are computed on the text the client gets).
            replay_rows=_replay_rows(run.project_id, run.id, reveal),
            finished=_finished(run.id),
            transform=live_transform(reveal),
        ):
            if text.startswith(":"):
                yield None  # keepalive
                continue
            parsed = _parse(text)
            if parsed is not None:
                yield parsed
    finally:
        await client.aclose()


async def _usage(run_id) -> dict | None:
    async with db.session_scope() as session:
        run = await session.get(Run, run_id)
    if run is None or run.tokens_in is None:
        return None
    return {
        "prompt_tokens": run.tokens_in,
        "completion_tokens": run.tokens_out or 0,
        "total_tokens": run.tokens_in + (run.tokens_out or 0),
    }


def _headers(run: Run) -> dict[str, str]:
    headers = {RUN_ID_HEADER: str(run.id)}
    if run.conversation_id:
        headers[CONVERSATION_HEADER] = str(run.conversation_id)
    return headers


async def complete(request: Request, caller: FacadeCaller, target, body, settings, queue):
    # The same parameter table as the direct path (K-06b-0018): a wrong value or an unknown
    # field is 400 here too. The agent's definition sets the model and its settings.
    params = call_params(body)
    events_on = events_mode(request)
    resume = request.headers.get(RESUME_HEADER)
    if not resume:
        # 06b-2: an external agent is not a run; it has its own path (facade_external).
        external = await facade_external.find(caller, target)
        if external is not None:
            return await facade_external.complete(
                request, caller, target, external, body, params, settings
            )
    if resume:
        run, after = await resumable(caller, resume)
    else:
        run, after = await start(request, caller, target, body, settings, queue), None
    t = Translation(
        cid=f"chatcmpl-{run.id.hex}",
        created=int(time.time()),
        model=target.name,
        run_id=str(run.id),
        events_on=events_on,
    )
    if body.stream:
        return StreamingResponse(
            _stream(t, settings, run, after),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", **_headers(run)},
        )
    async for item in _events(settings, run, after):
        if item is not None:
            t.on(*item)
    if t.error is not None:
        raise t.error
    message: dict[str, Any] = {"role": "assistant", "content": "".join(t.text)}
    annotations = t.annotations()
    if annotations:
        message["annotations"] = annotations
    data = {
        "id": t.cid,
        "object": "chat.completion",
        "created": t.created,
        "model": t.model,
        "choices": [{"index": 0, "message": message, "finish_reason": t.finish or "stop"}],
        "usage": await _usage(run.id),
        "x_platform": {"run_id": t.run_id, "events": t.platform}
        if events_on
        else ({"run_id": t.run_id} | ({"approval": t.approval} if t.approval else {})),
    }
    return JSONResponse(data, headers=_headers(run))


async def _stream(t: Translation, settings: Settings, run: Run, after: str | None):
    async for item in _events(settings, run, after):
        if item is None:
            yield KEEPALIVE
            continue
        for chunk in t.on(*item):
            yield chunk_json(chunk)
        if t.error is not None:
            yield chunk_json(error_body(t.error.error_type, t.error.code, t.error.message))
            yield STREAM_END
            return
    if t.finish == "stop" and not t.closed:
        delta: dict[str, Any] = {}
        annotations = t.annotations()
        if annotations:
            delta["annotations"] = annotations
        yield chunk_json(t.chunk(delta, "stop"))
    usage = await _usage(run.id)
    if usage is not None:
        yield chunk_json(dict(t.chunk({}), choices=[], usage=usage))
    yield STREAM_END
