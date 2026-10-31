"""The real ports: LiteLLM through the slot pool, the 04a search API, the 08 engine, tools.

- Model (C1, C10): `litellm_client` (01) streams; every call holds an LLM_SLOTS slot first.
  Its metadata puts LiteLLM's generation under the run's Langfuse trace (02 `trace_context`).
- Knowledge (S4): the worker never loads a model; it calls the backend's search API with the
  service account, the user's X-On-Behalf-Of token (ACL is the user's) and X-Run-Id (C12).
- Guardrail (S5): the 08 engine in-process (no model involved); events are stored with the same
  `record_events` as the API, and each check is a `guardrail_hook` run event (C4 form).
- Tools: `search_documents` (C7/C11) and `ask_user_question` are built in. MCP actions come
  from the project's 05a registry (`tools`, `tool_actions`) and are called with 05a's client
  (C7), the run's user as caller (forward_user signs for them) and X-Run-Id. The model sees
  `<tool_key>__<action>`; a tool or action that cannot be used stops the run at start with a
  code, never a silently missing tool.
"""

import contextlib
import json
import re
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ffcore.core import tracing
from ffcore.core.auth import OBO_HEADER, service_authorization, sign_on_behalf_of
from ffcore.core.config import Settings
from ffcore.core.egress import EgressTimeout, SafeOutboundClient
from ffcore.core.errors import ApiError
from ffcore.guardrails import engine
from ffcore.guardrails.masking import RedisTokenStore
from ffcore.guardrails.service import record_events, resolve_policy
from ffcore.guardrails.settings import get_guardrail_settings
from ffcore.knowledge.chunking import approx_tokens
from ffcore.models.knowledge import KnowledgeBase
from ffcore.models.runs import Message
from ffcore.models.tools import Tool, ToolAction
from ffcore.runtime.contracts import JobClass, RunEventType, RunStatus
from ffcore.runtime.definition import (
    MODEL_TOOL_NAME_PATTERN,
    AgentDefinition,
    model_tool_name,
)
from ffcore.runtime.events import RunEventWriter
from ffcore.runtime.prompting import Source, render_variables, system_parts
from ffcore.runtime.scheduler import LlmSlots
from ffcore.runtime.state import (
    GuardResult,
    ModelTurn,
    RunContext,
    StopRun,
    ToolCall,
    ToolOutcome,
)
from ffcore.services import mcp_client, mcp_tools
from ffcore.services.approvals import RunApprovalGate
from ffcore.services.litellm_client import LiteLLMClient, resolve_target
from ffcore.services.quota import QuotaGate, QuotaUnavailable, Subject, engine_for

OUTPUT_STAGES = {"output.pre", "output.stream.delta"}
# guardrail_events.source is 08's closed list (C4); the run's channel decides it.
GUARD_SOURCE = {"test": "agent-playground", "chat": "chat", "api": "api"}
SEARCH_TOOL, ASK_TOOL = "search_documents", "ask_user_question"
PLATFORM_RULES_PROMPT = "platform_rules"


class ToolSetupError(ApiError):
    """An agent's tool the run cannot use; the run ends at start with this code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(422, "invalid_request_error", code, message)


class LiteLLMModel:
    def __init__(
        self,
        settings: Settings,
        session: AsyncSession,
        slots: LlmSlots,
        *,
        run_id,
        project_id,
        user_id,
        model_key: str,
        job_class: JobClass,
        quota: QuotaGate | None = None,
    ) -> None:
        self._settings = settings
        self._session = session
        self._slots = slots
        self._run_id, self._project_id = str(run_id), project_id
        self._user_id = str(user_id) if user_id is not None else None
        self._model_key = model_key
        self._job_class = job_class
        # 03c: every call of a run passes the project's quotas (C20); None only in unit tests.
        self._quota = quota

    async def call(self, messages, *, tools, max_tokens, on_token) -> ModelTurn:
        target = await resolve_target(self._session, self._project_id, self._model_key)
        if self._quota is not None:
            decision = await _quota_step(
                self._quota.check(
                    target.id, input_tokens=approx_tokens(json.dumps(messages, ensure_ascii=False))
                )
            )
            _stop_if_blocked(decision)
            if decision.max_output_tokens is not None:
                max_tokens = min(max_tokens, decision.max_output_tokens)
        params: dict[str, Any] = {"max_tokens": max_tokens}
        if tools:
            params["tools"] = tools
        held = self._quota.hold() if self._quota is not None else contextlib.nullcontext(None)
        try:
            async with held as lease:
                if lease is not None:
                    _stop_if_blocked(lease)
                turn = await self._call(target, messages, params, on_token)
        except QuotaUnavailable as exc:  # the lease could not be taken (Redis)
            raise StopRun(RunStatus.failed, exc.code, exc.message) from None
        if self._quota is not None:
            # The fallback's own price and name when it answered (01 x-litellm-model-id).
            answered = (
                (target.fallback_id, turn.fallback["target_model"])
                if turn.fallback is not None and target.fallback_id
                else (target.id, turn.model)
            )
            await _quota_step(
                self._quota.commit(
                    call_id=turn.call_id,
                    model_id=answered[0],
                    model_name=answered[1],
                    usage=turn.usage or {},
                )
            )
        return turn

    async def _call(self, target, messages, params, on_token) -> ModelTurn:
        content: list[str] = []
        calls: dict[int, dict[str, str]] = {}
        metadata = tracing.trace_context(run_id=self._run_id, user_id=self._user_id) | {
            "project_id": str(self._project_id),
            "run_id": self._run_id,
        }
        async with self._slots.acquire(self._job_class) as waited:
            started = time.monotonic()
            async with LiteLLMClient(self._settings) as client:
                async with client.chat_stream(
                    target,
                    messages,
                    user=str(self._user_id or "service"),
                    metadata=metadata,
                    **params,
                ) as stream:
                    async for chunk in stream:
                        for choice in chunk.get("choices") or []:
                            delta = choice.get("delta") or {}
                            if delta.get("content"):
                                content.append(delta["content"])
                                if on_token is not None:
                                    await on_token(delta["content"])
                            for part in delta.get("tool_calls") or []:
                                slot = calls.setdefault(
                                    part.get("index", 0), {"id": "", "name": "", "args": ""}
                                )
                                slot["id"] = part.get("id") or slot["id"]
                                function = part.get("function") or {}
                                slot["name"] = function.get("name") or slot["name"]
                                slot["args"] += function.get("arguments") or ""
                    result = stream.result
            ms = int((time.monotonic() - started) * 1000)
        tool_calls = []
        for index in sorted(calls):
            slot = calls[index]
            try:
                arguments = json.loads(slot["args"] or "{}")
            except ValueError:
                # The model wrote broken JSON: the tool sees an error, never a guessed argument.
                arguments = {"_unparseable_arguments": slot["args"][:500]}
            tool_calls.append(
                ToolCall(slot["id"] or f"call-{uuid.uuid4().hex[:8]}", slot["name"], arguments)
            )
        fallback = None
        if result.fallback is not None:
            fallback = {
                "source_model": result.fallback.source_model,
                "target_model": result.fallback.target_model,
                "reason": result.fallback.reason,
            }
        return ModelTurn(
            content="".join(content),
            tool_calls=tool_calls,
            finish_reason=result.finish_reason,
            usage=result.usage,
            fallback=fallback,
            model=target.name,
            ms=ms,
            queue_ms=int(waited * 1000),
            call_id=result.call_id,
        )


async def _quota_step(step):
    """A quota check or count that cannot run stops the run (fail-loud; never unlimited)."""
    try:
        return await step
    except QuotaUnavailable as exc:
        raise StopRun(RunStatus.failed, exc.code, exc.message) from None


def _stop_if_blocked(decision) -> None:
    if decision.blocked:
        v = decision.violation
        raise StopRun(
            RunStatus.failed,
            decision.code,
            "A quota of this project does not allow this model call."
            if decision.code == "quota_exceeded"
            else "A USD budget applies but the model has no price.",
            limit=v.window if v else None,
            detail=f"{v.scope_type}:{v.quota_id}" if v else None,
        )


class HttpRetriever:
    def __init__(self, settings: Settings, session: AsyncSession, *, run_id, project_id, user_id):
        if user_id is None:
            raise ApiError(400, "invalid_request_error", "run_user_missing", "A run needs a user.")
        self._settings, self._session = settings, session
        self._run_id, self._project_id, self._user_id = str(run_id), str(project_id), str(user_id)
        self._kb_ids: dict[str, str] = {}

    async def _kb_id(self, kb_key: str) -> str:
        if kb_key not in self._kb_ids:
            kb_id = await self._session.scalar(
                select(KnowledgeBase.id).where(
                    KnowledgeBase.project_id == uuid.UUID(self._project_id),
                    KnowledgeBase.key == kb_key,
                    KnowledgeBase.deleted_at.is_(None),
                )
            )
            if kb_id is None:
                raise ApiError(
                    404,
                    "not_found_error",
                    "knowledge_base_not_found",
                    f"Knowledge base {kb_key} not found in the project.",
                )
            self._kb_ids[kb_key] = str(kb_id)
        return self._kb_ids[kb_key]

    async def search(self, kb_key, query, top_k, scope):
        kb_id = await self._kb_id(kb_key)
        s = self._settings
        headers = {
            **service_authorization(s),
            # Signed per call (C3): a long CPU run never sends an expired token.
            OBO_HEADER: sign_on_behalf_of(
                user_id=self._user_id,
                project_id=self._project_id,
                audience=s.obo_audience,
                settings=s,
            ),
            "X-Run-Id": self._run_id,
        }
        body = {"query": query[:2000], "top_k": top_k}
        project = f"{s.internal_api_url}/api/v1/projects/{self._project_id}"
        url = f"{project}/knowledge-bases/{kb_id}/search"
        timeout = EgressTimeout(connect=5, read=s.llm_call_timeout_s, total=s.llm_call_timeout_s)
        async with SafeOutboundClient(timeout=timeout, settings=s) as client:
            response = await client.request("POST", url, headers=headers, json=body)
        if response.status_code != 200:
            try:
                code = response.json()["error"]["code"]
            except (ValueError, KeyError, TypeError):
                code = f"search_http_{response.status_code}"
            raise ApiError(502, "api_error", code, "The knowledge search failed.")
        data = response.json()
        hits = [
            Source(
                n=0,
                kb_key=kb_key,
                chunk_id=str(h["chunk_id"]),
                document_id=str(h["document_id"]),
                document_name=h["document_name"],
                page=h.get("page"),
                breadcrumb=h.get("breadcrumb") or "",
                text=h["text"],
                updated_at_source=h.get("updated_at_source"),
                rerank_score=h.get("rerank_score"),
            )
            for h in data["hits"]
        ]
        info = {
            "query_id": str(data.get("query_id")),
            "threshold_mode": data.get("threshold_mode"),
            "filtered_by_rerank_floor": data.get("filtered_by_rerank_floor"),
            "filtered_by_min_score": data.get("filtered_by_min_score"),
            "latency_ms": data.get("latency_ms"),
        }
        return hits, info


class EngineGuard:
    def __init__(
        self,
        session: AsyncSession,
        redis,
        events: RunEventWriter,
        policy,
        *,
        run_id,
        project_id,
        egress_enabled: bool,
        token_ttl_s: int,
        channel: str = "chat",
    ) -> None:
        self._session, self._events, self._policy = session, events, policy
        self._source = GUARD_SOURCE.get(channel, "channel")
        self._run_id, self._project_id = str(run_id), project_id
        self._egress = egress_enabled
        self._tokens = RedisTokenStore(redis, token_ttl_s)

    @property
    def streams_live(self) -> bool:
        """V8: with an enforce-mode policy checking output, nothing is shown before the check."""
        spec = self._policy.spec
        checks_output = any(OUTPUT_STAGES & set(rule.stages) for rule in spec.rules)
        return not (spec.mode == "enforce" and checks_output)

    async def check(self, stage, text, *, tool=None) -> GuardResult:
        if stage == "egress" and not self._egress:
            # GUARDRAIL_EGRESS_ENABLED=false (airgap): the stage does not exist there (08 S3).
            return GuardResult("allow", text, None, None, 0)
        ctx = engine.EvalContext(
            run_id=self._run_id,
            project_id=str(self._project_id),
            source=self._source,
            tool=tool,
            token_store=self._tokens,
            egress_enabled=self._egress,
        )
        decision = await engine.evaluate(text, stage, self._policy, ctx=ctx)
        if decision.events:
            record_events(self._session, self._project_id, decision.events, decision.reference_id)
            await self._events.record(
                RunEventType.guardrail_hook,
                {
                    "stage": stage,
                    "policy_key": self._policy.key,
                    "action": decision.action,
                    "reference_id": decision.reference_id,
                    "events": len(decision.events),
                },
            )
        return GuardResult(
            decision.action,
            decision.text_out,
            decision.message,
            decision.reference_id,
            len(decision.events),
        )


@dataclass(frozen=True)
class McpBinding:
    target: mcp_client.ToolTarget
    action: str
    needs_approval: bool
    max_calls: int | None
    timeout_s: int | None


class AgentTools:
    """The run's tools: the built-in ones and the agent's MCP actions (05a)."""

    def __init__(
        self,
        definition: AgentDefinition,
        mcp: dict[str, McpBinding] | None = None,
        mcp_schemas: list[dict[str, Any]] | None = None,
        *,
        settings: Settings | None = None,
        caller: mcp_client.Caller | None = None,
        run_id: str | None = None,
    ) -> None:
        self._mcp = mcp or {}
        self._settings, self._caller, self._run_id = settings, caller, run_id
        self._schemas: list[dict[str, Any]] = []
        tool_kbs = [k.kb_key for k in definition.knowledge if k.mode == "tool"]
        if tool_kbs:
            self._schemas.append(
                _function(
                    SEARCH_TOOL,
                    "Search the knowledge base and return matching passages.",
                    {
                        "query": {"type": "string"},
                        "kb_key": {"type": "string", "enum": tool_kbs},
                        "top_k": {"type": "integer", "minimum": 1, "maximum": 50},
                    },
                    ["query", "kb_key"],
                )
            )
        if definition.ask_user:
            self._schemas.append(
                _function(
                    ASK_TOOL,
                    "Ask the user one short question when the request is ambiguous.",
                    {"question": {"type": "string"}},
                    ["question"],
                )
            )
        self._schemas += mcp_schemas or []

    @classmethod
    async def load(
        cls, session: AsyncSession, settings: Settings, definition: AgentDefinition, run
    ) -> "AgentTools":
        """Every `tools[]` entry from the project's registry: the tool discovered, each action
        listed, available and enabled; otherwise ToolSetupError with a code."""
        bindings: dict[str, McpBinding] = {}
        schemas: list[dict[str, Any]] = []
        for ref in definition.tools:
            tool = await session.scalar(
                select(Tool).where(
                    Tool.project_id == run.project_id,
                    Tool.key == ref.tool_key,
                    Tool.deleted_at.is_(None),
                )
            )
            if tool is None:
                raise ToolSetupError(
                    "tool_not_found", f"Tool {ref.tool_key!r} is not registered in the project."
                )
            if tool.status != "discovered":
                raise ToolSetupError(
                    "tool_not_discovered",
                    f"Tool {ref.tool_key!r} has no discovered actions (status {tool.status}).",
                )
            if tool.auth_type == "forward_user" and run.user_id is None:
                raise ToolSetupError(
                    "tool_needs_run_user",
                    f"Tool {ref.tool_key!r} forwards the user; this run has no user.",
                )
            rows = await session.scalars(
                select(ToolAction).where(
                    ToolAction.tool_id == tool.id, ToolAction.name.in_(ref.actions)
                )
            )
            actions = {a.name: a for a in rows.all()}
            target = mcp_tools.target_of(tool, settings)
            for name in ref.actions:
                action = actions.get(name)
                if action is None or action.status != "available" or not action.enabled:
                    raise ToolSetupError(
                        "tool_action_unavailable",
                        f"Action {ref.tool_key}.{name} is missing, gone or disabled.",
                    )
                model_name = model_tool_name(ref.tool_key, name)
                if not re.fullmatch(MODEL_TOOL_NAME_PATTERN, model_name):
                    raise ToolSetupError(
                        "tool_name_invalid",
                        f"Action {ref.tool_key}.{name} has no valid function name for the model.",
                    )
                bindings[model_name] = McpBinding(
                    target,
                    name,
                    action.needs_approval,
                    action.max_calls_per_run,
                    action.timeout_s,
                )
                schemas.append(
                    {
                        "type": "function",
                        "function": {
                            "name": model_name,
                            "description": action.description or "",
                            "parameters": action.input_schema or {"type": "object"},
                        },
                    }
                )
        caller = mcp_client.Caller(
            user_id=str(run.user_id) if run.user_id else "", project_id=str(run.project_id)
        )
        return cls(
            definition, bindings, schemas, settings=settings, caller=caller, run_id=str(run.id)
        )

    def schemas(self):
        return self._schemas

    def needs_approval(self, name):
        binding = self._mcp.get(name)
        return binding is not None and binding.needs_approval

    def max_calls(self, name):
        binding = self._mcp.get(name)
        return binding.max_calls if binding else None

    async def call(self, name, arguments) -> ToolOutcome:
        binding = self._mcp.get(name)
        if binding is None:
            # A name the model made up: said to the model, recorded with a code.
            return ToolOutcome(f"Unknown tool {name!r}.", False, 0, True, 0, "tool_unknown")
        started = time.monotonic()
        try:
            # tool.pre / tool.post run in the graph (one place for every tool), so no guard here.
            result = await mcp_client.call(
                binding.target,
                binding.action,
                arguments,
                self._settings,
                caller=self._caller,
                timeout_s=binding.timeout_s,
                run_id=self._run_id,
            )
        except mcp_client.ToolCallError as exc:
            ms = int((time.monotonic() - started) * 1000)
            text = f"The tool call failed ({exc.code})."
            return ToolOutcome(text, False, len(text), True, ms, exc.code)
        return ToolOutcome(
            result.text, result.truncated, result.total_chars, result.is_error, result.latency_ms
        )


def _function(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required},
        },
    }


async def _history(session: AsyncSession, conversation_id, run_id) -> list[dict[str, str]]:
    if conversation_id is None:
        return []
    rows = await session.scalars(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    # This run's own user message is the question, not history.
    return [{"role": m.role, "content": m.content} for m in rows.all() if m.run_id != run_id]


def _platform_rules(prompts, definition: AgentDefinition) -> str:
    """Langfuse prompt `platform_rules` (seed backend/prompts/platform_rules.md, S6); without
    Langfuse the run does not start (`prompt_unavailable`), never a local copy."""
    prompt = prompts.get(PLATFORM_RULES_PROMPT)
    return prompt.compile(unknown_reply=definition.answer_rules.unknown_reply)


def context_factory(
    settings: Settings, redis, slots: LlmSlots, prompts, *, job_class: JobClass
) -> Callable[..., Awaitable[RunContext]]:
    guardrail = get_guardrail_settings()

    async def build(*, session, run, definition: AgentDefinition, events, boundary) -> RunContext:
        policy = await resolve_policy(session, run.project_id, definition.guardrail_policy_key)
        guard = EngineGuard(
            session,
            redis,
            events,
            policy,
            run_id=run.id,
            project_id=run.project_id,
            egress_enabled=guardrail.guardrail_egress_enabled,
            token_ttl_s=guardrail.pii_token_ttl_s,
            channel=run.channel,
        )
        if definition.langfuse_prompt is not None:
            ref = definition.langfuse_prompt
            instructions = prompts.get(ref.name, ref.label).compile()
        else:
            instructions = definition.system_prompt or ""
        instructions = render_variables(instructions, definition, dict(run.variables or {}))
        return RunContext(
            run_id=str(run.id),
            project_id=str(run.project_id),
            user_id=str(run.user_id) if run.user_id else None,
            definition=definition,
            events=events,
            model=LiteLLMModel(
                settings,
                session,
                slots,
                run_id=run.id,
                project_id=run.project_id,
                user_id=run.user_id,
                model_key=definition.model,
                job_class=job_class,
                quota=QuotaGate(
                    engine_for(settings, redis),
                    redis,
                    session,
                    Subject(
                        project_id=str(run.project_id),
                        user_id=str(run.user_id) if run.user_id else None,
                        api_key_id=str(run.api_key_id) if run.api_key_id else None,
                    ),
                ),
            ),
            retriever=HttpRetriever(
                settings, session, run_id=run.id, project_id=run.project_id, user_id=run.user_id
            ),
            tools=await AgentTools.load(session, settings, definition, run),
            guard=guard,
            boundary=boundary,
            system=system_parts(_platform_rules(prompts, definition), instructions),
            history=await _history(session, run.conversation_id, run.id),
            stream_live=guard.streams_live,
            approvals=RunApprovalGate(session, settings, project_id=run.project_id, run_id=run.id),
        )

    return build
