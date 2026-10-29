"""The real ports: LiteLLM through the slot pool, the 04a search API, the 08 engine, tools.

- Model (C1, C10): `litellm_client` (01) streams; every call holds an LLM_SLOTS slot first.
  Its metadata puts LiteLLM's generation under the run's Langfuse trace (02 `trace_context`).
- Knowledge (S4): the worker never loads a model; it calls the backend's search API with the
  service account, the user's X-On-Behalf-Of token (ACL is the user's) and X-Run-Id (C12).
- Guardrail (S5): the 08 engine in-process (no model involved); events are stored with the same
  `record_events` as the API, and each check is a `guardrail_hook` run event (C4 form).
- Tools: `search_documents` (C7/C11) and `ask_user_question` are built in; MCP actions come with
  05a's client. Until 05a is merged an agent with MCP tools fails at start with a coded error.
"""

import json
import time
import uuid
from collections.abc import Awaitable, Callable
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
from ffcore.models.knowledge import KnowledgeBase
from ffcore.models.runs import Message
from ffcore.runtime.contracts import JobClass, RunEventType
from ffcore.runtime.definition import AgentDefinition
from ffcore.runtime.events import RunEventWriter
from ffcore.runtime.prompting import Source, render_variables, system_parts
from ffcore.runtime.scheduler import LlmSlots
from ffcore.runtime.state import GuardResult, ModelTurn, RunContext, ToolCall, ToolOutcome
from ffcore.services.litellm_client import LiteLLMClient, resolve_target

OUTPUT_STAGES = {"output.pre", "output.stream.delta"}
# guardrail_events.source is 08's closed list (C4); the run's channel decides it.
GUARD_SOURCE = {"test": "agent-playground", "chat": "chat", "api": "api"}
SEARCH_TOOL, ASK_TOOL = "search_documents", "ask_user_question"
PLATFORM_RULES_PROMPT = "platform_rules"


class ToolLayerUnavailable(ApiError):
    def __init__(self) -> None:
        super().__init__(
            503,
            "api_error",
            "tool_layer_unavailable",
            "This agent uses MCP tools; the tool layer is not installed yet.",
        )


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
    ) -> None:
        self._settings = settings
        self._session = session
        self._slots = slots
        self._run_id, self._project_id = str(run_id), project_id
        self._user_id = str(user_id) if user_id is not None else None
        self._model_key = model_key
        self._job_class = job_class

    async def call(self, messages, *, tools, max_tokens, on_token) -> ModelTurn:
        target = await resolve_target(self._session, self._project_id, self._model_key)
        params: dict[str, Any] = {"max_tokens": max_tokens}
        if tools:
            params["tools"] = tools
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


class BuiltinTools:
    """search_documents and ask_user_question; MCP actions after 05a (dilim 6)."""

    def __init__(self, definition: AgentDefinition) -> None:
        if definition.tools:
            raise ToolLayerUnavailable()
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

    def schemas(self):
        return self._schemas

    def needs_approval(self, name):
        return False

    async def call(self, name, arguments) -> ToolOutcome:
        raise ToolLayerUnavailable()


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
            ),
            retriever=HttpRetriever(
                settings, session, run_id=run.id, project_id=run.project_id, user_id=run.user_id
            ),
            tools=BuiltinTools(definition),
            guard=guard,
            boundary=boundary,
            system=system_parts(_platform_rules(prompts, definition), instructions),
            history=await _history(session, run.conversation_id, run.id),
            stream_live=guard.streams_live,
        )

    return build
