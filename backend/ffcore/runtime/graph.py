r"""The agent graph, built from the definition (brief 06 "Graf üretimi").

    prepare -> retrieve -> guard_in -> model --(tool calls)--> tool_guard -> approval -> tools
                                         ^                         |  \--> ask_user ---/   |
                                         |                         \--------> tools -------|
                                         \--------------------------------------------------/
                                       model --(answer)--> guard_out -> finalize

On resume LangGraph re-runs the node that called `interrupt()` from its start (measured, U2-a).
So the nodes that wait (`approval`, `ask_user`) only wait: every event, guardrail check and
counter happens in `tool_guard` before them, once, and the decision is written after the
interrupt returns. `boundary()` runs first in every node: cancel, abandon and run timeout stop
the run there (a model or tool call in progress is never cut).
"""

import json
import re
import time
from typing import Any

from jsonschema import Draft202012Validator
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import interrupt

from ffcore.runtime.contracts import RunEventType, RunStatus, SseEvent
from ffcore.runtime.prompting import (
    DECLINE_PATTERN,
    Source,
    fit_history,
    fit_sources,
    plan_budget,
    system_message,
    user_message,
)
from ffcore.runtime.state import RunContext, RunState, StopRun

SEARCH_TOOL = "search_documents"
ASK_TOOL = "ask_user_question"
BLOCKED_TOOL_TEXT = "The platform's guardrail blocked this tool call."
DECLINED = re.compile(DECLINE_PATTERN, re.IGNORECASE)


def _ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


def _add_time(state: RunState, kind: str, ms: int) -> dict[str, int]:
    timing = dict(state.get("timing") or {})
    timing[kind] = timing.get(kind, 0) + ms
    timing[f"{kind}_max"] = max(timing.get(f"{kind}_max", 0), ms)
    return timing


def _tool_result_text(name: str, text: str) -> str:
    # Qwen prompt rule (brief 06): every tool result in this envelope, marked as data.
    return f'<tool_result name="{name}">\n{text}\n</tool_result>'


def _source_payload(sources: list[Source]) -> list[dict[str, Any]]:
    return [s.public() | {"text": s.text} for s in sources]


def _sources(state: RunState) -> list[Source]:
    return [Source(**s) for s in state.get("sources") or []]


async def prepare(state: RunState, runtime: Runtime[RunContext]) -> dict:
    ctx = runtime.context
    await ctx.boundary("prepare")
    d = ctx.definition
    system = system_message(ctx.system)
    budget = plan_budget(d, system, ctx.tools.schemas())
    ctx.budget = budget
    history = fit_history(budget, ctx.history, d.context_policy.history_turns)
    await ctx.events.record(RunEventType.budget, budget.event() | {"phase": "planned"})
    if not ctx.stream_live:
        # V8 (K-06a-0003): the client is told up front that the answer comes in one piece.
        await ctx.events.record(
            RunEventType.progress,
            {"stage": "output_buffered", "reason": "guardrail_enforce"},
            sse=SseEvent.progress,
        )
    return {
        "messages": [{"role": "system", "content": system}, *history],
        "iteration": 0,
        "tool_calls_used": 0,
        "sources": [],
        "pending_tool": None,
        "timing": {},
        "usage": {"prompt_tokens": 0, "completion_tokens": 0},
    }


async def retrieve(state: RunState, runtime: Runtime[RunContext]) -> dict:
    ctx = runtime.context
    await ctx.boundary("retrieve")
    always = [k for k in ctx.definition.knowledge if k.mode == "always"]
    if not always:
        return {}
    started, found, details = time.monotonic(), [], {}
    for ref in always:
        scope = ref.filter.scope if ref.filter else []
        hits, info = await ctx.retriever.search(ref.kb_key, state["question"], ref.top_k, scope)
        details[ref.kb_key] = info
        found.extend(hits)
    for n, source in enumerate(found, start=1):
        source.n = n
    budget = ctx.budget or plan_budget(ctx.definition, state["messages"][0]["content"], [])
    kept = fit_sources(budget, found)
    payload = {
        "selected": [s.public() for s in kept],
        "dropped_by_budget": budget.dropped.get("rag", []),
        "search": details,
    }
    await ctx.events.record(
        RunEventType.sources,
        payload,
        sse=SseEvent.sources,
        sse_data={"sources": payload["selected"]},
    )
    ms = _ms(started)
    return {"sources": _source_payload(kept), "timing": _add_time(state, "retrieval", ms)}


async def guard_in(state: RunState, runtime: Runtime[RunContext]) -> dict:
    ctx = runtime.context
    await ctx.boundary("guard_in")
    checked = await ctx.guard.check("input.pre", state["question"])
    if checked.action == "block":
        raise StopRun(
            RunStatus.failed, "guardrail_block", checked.message, reference_id=checked.reference_id
        )
    content = user_message(checked.text, _sources(state))
    outgoing = await ctx.guard.check("egress", content)
    if outgoing.action == "block":
        raise StopRun(
            RunStatus.failed,
            "guardrail_block",
            outgoing.message,
            reference_id=outgoing.reference_id,
        )
    return {"messages": [*state["messages"], {"role": "user", "content": outgoing.text}]}


def _always_found_nothing(ctx: RunContext, state: RunState) -> bool:
    d = ctx.definition
    only_always = d.knowledge and all(k.mode == "always" for k in d.knowledge) and not d.tools
    return bool(only_always and not d.ask_user and not state.get("sources"))


async def model(state: RunState, runtime: Runtime[RunContext]) -> dict:
    ctx = runtime.context
    await ctx.boundary("model")
    d = ctx.definition
    iteration = state["iteration"] + 1
    if iteration > d.limits.max_turns:
        raise StopRun(
            RunStatus.failed, "limit_reached", partial=state.get("answer"), limit="max_turns"
        )
    if iteration == 1 and _always_found_nothing(ctx, state):
        # Nothing retrieved for a documents-only agent: the definition's unknown_reply, without
        # a model call that could only make something up (brief 06 acceptance 2; PayCore).
        await ctx.events.record(
            RunEventType.progress, {"skipped_model": "no_sources"}, iteration=iteration
        )
        return {"iteration": iteration, "answer": d.answer_rules.unknown_reply}

    async def on_token(text: str) -> None:
        await ctx.events.live(SseEvent.token, {"text": text})

    turn = await ctx.model.call(
        state["messages"],
        tools=ctx.tools.schemas(),
        max_tokens=min(d.limits.output_tokens, d.answer_rules.max_answer_tokens)
        if not ctx.tools.schemas()
        else d.limits.output_tokens,
        on_token=on_token if ctx.stream_live else None,
    )
    usage = dict(state.get("usage") or {})
    for key in ("prompt_tokens", "completion_tokens"):
        usage[key] = usage.get(key, 0) + int((turn.usage or {}).get(key) or 0)
    await ctx.events.record(
        RunEventType.llm_call,
        {
            "model": turn.model,
            "finish_reason": turn.finish_reason,
            "usage": turn.usage,
            "ms": turn.ms,
            "queue_ms": turn.queue_ms,
            "tool_calls": [c.name for c in turn.tool_calls],
            # The final, masked messages sent to the model (02/08 content rule).
            "request_messages": state["messages"],
        },
        iteration=iteration,
    )
    if turn.fallback:
        await ctx.events.record(
            RunEventType.fallback, turn.fallback, sse=SseEvent.fallback, iteration=iteration
        )
    assistant: dict[str, Any] = {"role": "assistant", "content": turn.content}
    if turn.tool_calls:
        assistant["tool_calls"] = [
            {
                "id": c.id,
                "type": "function",
                "function": {"name": c.name, "arguments": json.dumps(c.arguments)},
            }
            for c in turn.tool_calls
        ]
    return {
        "iteration": iteration,
        "messages": [*state["messages"], assistant],
        "answer": turn.content,
        "usage": usage,
        "timing": _add_time(state, "model", turn.ms),
    }


def _unanswered(state: RunState) -> list[dict[str, Any]]:
    """Tool calls of the last assistant message without a tool message yet."""
    messages = state["messages"]
    for index in range(len(messages) - 1, -1, -1):
        if messages[index]["role"] == "assistant":
            answered = {m.get("tool_call_id") for m in messages[index + 1 :]}
            return [c for c in messages[index].get("tool_calls", []) if c["id"] not in answered]
    return []


def after_model(state: RunState) -> str:
    return "tool_guard" if _unanswered(state) else "guard_out"


async def tool_guard(state: RunState, runtime: Runtime[RunContext]) -> dict:
    ctx = runtime.context
    await ctx.boundary("tool_guard")
    d = ctx.definition
    call = _unanswered(state)[0]
    name = call["function"]["name"]
    arguments = json.loads(call["function"]["arguments"] or "{}")
    iteration = state["iteration"]
    used = state["tool_calls_used"]
    if name == ASK_TOOL and d.ask_user:
        # Not counted in max_tool_calls (K-06a-0002 S7); counted in max_turns.
        question = str(arguments.get("question", ""))
        await ctx.events.record(
            RunEventType.question,
            {"question": question},
            sse=SseEvent.question,
            iteration=iteration,
        )
        return {"pending_tool": {"id": call["id"], "name": name, "kind": "ask_user"}}
    if used + 1 > d.limits.max_tool_calls:
        raise StopRun(
            RunStatus.failed, "limit_reached", partial=state.get("answer"), limit="max_tool_calls"
        )
    checked = await ctx.guard.check(
        "tool.pre", json.dumps(arguments, ensure_ascii=False), tool=name
    )
    blocked = checked.action == "block"
    masked = arguments if blocked else json.loads(checked.text)
    approval = ctx.tools.needs_approval(name) and not blocked
    await ctx.events.record(
        RunEventType.tool_call,
        {"tool_call_id": call["id"], "name": name, "arguments": masked, "needs_approval": approval},
        sse=SseEvent.tool_call,
        iteration=iteration,
    )
    pending = {"id": call["id"], "name": name, "arguments": masked, "kind": "tool"}
    if blocked:
        pending["kind"] = "blocked"
    elif approval:
        pending["kind"] = "approval"
        assign_to = d.approval.assign_to if d.approval else "admin"
        await ctx.events.record(
            RunEventType.approval_requested,
            {
                "tool_call_id": call["id"],
                "action": name,
                "arguments": masked,
                "assign_to": assign_to,
            },
            sse=SseEvent.approval_required,
            sse_data={"action": name, "arguments": masked, "assign_to": assign_to},
            iteration=iteration,
        )
    return {"pending_tool": pending, "tool_calls_used": used + 1}


def after_tool_guard(state: RunState) -> str:
    kind = state["pending_tool"]["kind"]
    return {"ask_user": "ask_user", "approval": "approval"}.get(kind, "tools")


async def approval(state: RunState, runtime: Runtime[RunContext]) -> dict:
    """Waits; nothing before `interrupt()` has side effects (re-run on resume)."""
    ctx = runtime.context
    pending = state["pending_tool"]
    decision = interrupt({"kind": "approval", "action": pending["name"]})
    await ctx.events.record(
        RunEventType.approval_resolved,
        {"tool_call_id": pending["id"], "action": pending["name"], **decision},
        iteration=state["iteration"],
    )
    if decision.get("decision") == "approved":
        return {"pending_tool": {**pending, "kind": "approved"}}
    note = decision.get("comment") or ""
    text = "The approver rejected this action." + (f" Comment: {note}" if note else "")
    return {
        "pending_tool": None,
        "messages": [
            *state["messages"],
            {
                "role": "tool",
                "tool_call_id": pending["id"],
                "content": _tool_result_text(pending["name"], text),
            },
        ],
    }


def after_approval(state: RunState) -> str:
    return "tools" if state.get("pending_tool") else "model"


async def ask_user(state: RunState, runtime: Runtime[RunContext]) -> dict:
    ctx = runtime.context
    pending = state["pending_tool"]
    answer = interrupt({"kind": "question"})
    await ctx.events.record(
        RunEventType.user_answer, {"tool_call_id": pending["id"]}, iteration=state["iteration"]
    )
    return {
        "pending_tool": None,
        "messages": [
            *state["messages"],
            {
                "role": "tool",
                "tool_call_id": pending["id"],
                "content": _tool_result_text(ASK_TOOL, answer["answer"]),
            },
        ],
    }


async def _search_tool(ctx: RunContext, state: RunState, arguments: dict) -> tuple[str, list[dict]]:
    kb_key = arguments.get("kb_key")
    allowed = {k.kb_key: k for k in ctx.definition.knowledge if k.mode == "tool"}
    if kb_key not in allowed:
        return f"Unknown knowledge base {kb_key!r}; use one of {sorted(allowed)}.", []
    ref = allowed[kb_key]
    top_k = arguments.get("top_k") or ref.top_k
    hits, _ = await ctx.retriever.search(
        kb_key, str(arguments.get("query", "")), top_k, ref.filter.scope if ref.filter else []
    )
    start = len(state.get("sources") or [])
    for offset, source in enumerate(hits, start=1):
        source.n = start + offset
    await ctx.events.record(
        RunEventType.sources,
        {"selected": [s.public() for s in hits], "dropped_by_budget": [], "tool": SEARCH_TOOL},
        sse=SseEvent.sources,
        sse_data={"sources": [s.public() for s in hits]},
        iteration=state["iteration"],
    )
    text = "\n\n".join(f"[{s.n}] {s.document_name} ({s.breadcrumb})\n{s.text}" for s in hits)
    return text or "No matching passages.", _source_payload(hits)


async def tools(state: RunState, runtime: Runtime[RunContext]) -> dict:
    ctx = runtime.context
    await ctx.boundary("tools")
    pending = state["pending_tool"]
    name, started = pending["name"], time.monotonic()
    new_sources: list[dict] = []
    truncated, is_error = False, False
    if pending["kind"] == "blocked":
        text, is_error = BLOCKED_TOOL_TEXT, True
    elif name == SEARCH_TOOL:
        text, new_sources = await _search_tool(ctx, state, pending["arguments"])
    else:
        outcome = await ctx.tools.call(name, pending["arguments"])
        text, truncated, is_error = outcome.text, outcome.truncated, outcome.is_error
    if pending["kind"] != "blocked":
        checked = await ctx.guard.check("tool.post", text, tool=name)
        if checked.action == "block":
            text, is_error = BLOCKED_TOOL_TEXT, True
        else:
            text = checked.text
    ms = _ms(started)
    await ctx.events.record(
        RunEventType.tool_result,
        {
            "tool_call_id": pending["id"],
            "name": name,
            "truncated": truncated,
            "is_error": is_error,
            "chars": len(text),
            "ms": ms,
        },
        sse=SseEvent.tool_result,
        iteration=state["iteration"],
    )
    return {
        "pending_tool": None,
        "sources": [*(state.get("sources") or []), *new_sources],
        "messages": [
            *state["messages"],
            {
                "role": "tool",
                "tool_call_id": pending["id"],
                "content": _tool_result_text(name, text),
            },
        ],
        "timing": _add_time(state, "tool", ms),
    }


def after_tools(state: RunState) -> str:
    return "tool_guard" if _unanswered(state) else "model"


async def guard_out(state: RunState, runtime: Runtime[RunContext]) -> dict:
    ctx = runtime.context
    await ctx.boundary("guard_out")
    checked = await ctx.guard.check("output.pre", state.get("answer") or "")
    if checked.action == "block":
        raise StopRun(
            RunStatus.failed, "guardrail_block", checked.message, reference_id=checked.reference_id
        )
    if not ctx.stream_live or state["iteration"] == 1 and _always_found_nothing(ctx, state):
        # Shown only now: either output is checked first, or no model wrote it.
        await ctx.events.live(SseEvent.token, {"text": checked.text})
    return {"answer": checked.text}


def _cited(answer: str, sources: list[dict]) -> list[dict]:
    numbers = {int(n) for n in re.findall(r"\[(\d+)\]", answer)}
    return [s for s in sources if s["n"] in numbers]


async def finalize(state: RunState, runtime: Runtime[RunContext]) -> dict:
    ctx = runtime.context
    await ctx.boundary("finalize")
    d = ctx.definition
    answer = state.get("answer") or ""
    if d.structured_output is not None:
        try:
            Draft202012Validator(d.structured_output).validate(json.loads(answer))
        except Exception as exc:  # noqa: BLE001 - bad JSON and schema mismatch alike
            raise StopRun(
                RunStatus.failed,
                "structured_output_invalid",
                partial=answer,
                detail=type(exc).__name__,
            ) from None
    sources = state.get("sources") or []
    declined = answer.strip() == d.answer_rules.unknown_reply.strip() or bool(
        DECLINED.search(answer)
    )
    cited = _cited(answer, sources)
    scores = [
        s["rerank_score"]
        for s in (cited if d.answer_rules.confidence_formula == "cited" else sources)
        if s.get("rerank_score") is not None
    ]
    if d.answer_rules.confidence_formula == "cited":
        confidence = sum(scores) / len(scores) if scores else None
    else:
        confidence = max(scores) if scores else None
    outcome = "declined" if declined else "answered"
    threshold = d.answer_rules.confidence_threshold
    if not declined and threshold is not None and confidence is not None and confidence < threshold:
        outcome = "below_threshold"
    await ctx.events.record(
        RunEventType.answer,
        {
            "text": answer,
            "outcome_label": outcome,
            "confidence": confidence,
            "confidence_formula": d.answer_rules.confidence_formula,
            "cited": [s["n"] for s in cited],
        },
    )
    return {"answer": answer, "outcome": outcome, "confidence": confidence}


def build_graph() -> StateGraph:
    graph = StateGraph(RunState, context_schema=RunContext)
    for name, node in (
        ("prepare", prepare),
        ("retrieve", retrieve),
        ("guard_in", guard_in),
        ("model", model),
        ("tool_guard", tool_guard),
        ("approval", approval),
        ("ask_user", ask_user),
        ("tools", tools),
        ("guard_out", guard_out),
        ("finalize", finalize),
    ):
        graph.add_node(name, node)
    graph.add_edge(START, "prepare")
    graph.add_edge("prepare", "retrieve")
    graph.add_edge("retrieve", "guard_in")
    graph.add_edge("guard_in", "model")
    graph.add_conditional_edges("model", after_model, ["tool_guard", "guard_out"])
    graph.add_conditional_edges("tool_guard", after_tool_guard, ["ask_user", "approval", "tools"])
    graph.add_conditional_edges("approval", after_approval, ["tools", "model"])
    graph.add_edge("ask_user", "model")
    graph.add_conditional_edges("tools", after_tools, ["tool_guard", "model"])
    graph.add_edge("guard_out", "finalize")
    graph.add_edge("finalize", END)
    return graph
