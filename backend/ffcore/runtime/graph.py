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

import hashlib
import json
import re
import time
from typing import Any

from jsonschema import Draft202012Validator
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import interrupt

from ffcore.core import tracing
from ffcore.guardrails.engine import TextTooLong
from ffcore.guardrails.masking import PlaceholderAligner
from ffcore.runtime.contracts import RunEventType, RunStatus, SseEvent
from ffcore.runtime.definition import DEFAULT_APPROVER, approval_name
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
REDACTED_BLOCK = {"redacted": True, "reason": "guardrail_block"}
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
    """The sources the run state keeps: no chunk text (FOLLOWUP-116). The text reaches the model
    only inside its messages; finalize needs `n` and `rerank_score`."""
    return [s.public() for s in sources]


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
    kept, blocked, all_blocked = await _egress_sources(ctx, fit_sources(budget, found))
    payload = {
        "selected": [s.public() for s in kept],
        "dropped_by_budget": budget.dropped.get("rag", []),
        "blocked": blocked,
        "search": details,
    }
    await ctx.events.record(
        RunEventType.sources,
        payload,
        sse=SseEvent.sources,
        sse_data={"sources": payload["selected"], "blocked": blocked},
    )
    _stop_if_all_blocked(all_blocked)
    ms = _ms(started)
    # The text rides along to guard_in, the next step, which writes it into the user message and
    # keeps the sources without it.
    with_text = [s.public() | {"text": s.text} for s in kept]
    return {"sources": with_text, "timing": _add_time(state, "retrieval", ms)}


async def guard_in(state: RunState, runtime: Runtime[RunContext]) -> dict:
    ctx = runtime.context
    await ctx.boundary("guard_in")
    checked = await ctx.guard.check("input.pre", state["question"])
    if checked.action == "block":
        raise StopRun(
            RunStatus.failed, "guardrail_block", checked.message, reference_id=checked.reference_id
        )
    content = user_message(checked.text, _sources(state))
    # Cached, so the model node does not check this message a second time.
    outgoing = await _egress_text(ctx, content)
    return {
        "messages": [*state["messages"], {"role": "user", "content": outgoing}],
        "sources": _source_payload(_sources(state)),
    }


def _always_found_nothing(ctx: RunContext, state: RunState) -> bool:
    d = ctx.definition
    only_always = d.knowledge and all(k.mode == "always" for k in d.knowledge) and not d.tools
    return bool(only_always and not d.ask_user and not state.get("sources"))


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


async def _egress_text(ctx: RunContext, text: str) -> str:
    """One text through `egress`, once per run execution: the result is cached under the hash of
    the input and of itself (a masked text asks again for nothing). A block fails the run
    (`guardrail_block`); a text over the engine's limit fails it with its own code."""
    key = _digest(text)
    masked = ctx.egress_cache.get(key)
    if masked is None:
        try:
            checked = await ctx.guard.check("egress", text)
        except TextTooLong as exc:
            raise StopRun(RunStatus.failed, "guardrail_text_too_long", str(exc)) from exc
        if checked.action == "block":
            raise StopRun(
                RunStatus.failed,
                "guardrail_block",
                checked.message,
                reference_id=checked.reference_id,
            )
        masked = checked.text
        ctx.egress_cache[key] = ctx.egress_cache[_digest(masked)] = masked
    return masked


async def _egress_sources(
    ctx: RunContext, sources: list[Source]
) -> tuple[list[Source], list[dict[str, Any]]]:
    """Each retrieved chunk through `egress` on its own (FOLLOWUP-107): a blocked chunk is left
    out and named in `blocked` (its public fields, the reason and the reference; never its
    text), the others go on tokenized. One chunk with an encoded blob no longer fails every
    answer that retrieves it; when no chunk is left the run fails `guardrail_block`."""
    kept: list[Source] = []
    blocked: list[dict[str, Any]] = []
    last_block = None
    for source in sources:
        key = _digest(source.text)
        masked = ctx.egress_cache.get(key)
        if masked is None:
            try:
                checked = await ctx.guard.check("egress", source.text)
            except TextTooLong as exc:
                raise StopRun(RunStatus.failed, "guardrail_text_too_long", str(exc)) from exc
            if checked.action == "block":
                last_block = checked
                blocked.append(
                    source.public()
                    | {"reason": "guardrail_block", "reference_id": checked.reference_id}
                )
                continue
            masked = checked.text
            ctx.egress_cache[key] = ctx.egress_cache[_digest(masked)] = masked
        source.text = masked
        kept.append(source)
    return kept, blocked, (last_block if not kept else None)


def _stop_if_all_blocked(all_blocked) -> None:
    """After the `sources` event (r1 MAJOR-6: it names what was blocked even when nothing is
    left), the run fails `guardrail_block` when every chunk was blocked."""
    if all_blocked is not None:
        raise StopRun(
            RunStatus.failed,
            "guardrail_block",
            all_blocked.message,
            reference_id=all_blocked.reference_id,
        )


async def _egress_json(ctx: RunContext, node: Any) -> Any:
    if isinstance(node, str):
        return await _egress_text(ctx, node) if node else node
    if isinstance(node, list):
        return [await _egress_json(ctx, item) for item in node]
    if isinstance(node, dict):
        return {key: await _egress_json(ctx, value) for key, value in node.items()}
    return node


async def _egress_call(ctx: RunContext, call: dict[str, Any]) -> dict[str, Any]:
    """A tool call of an assistant message: its arguments (a JSON string) are checked value by
    value, so the structure stays valid."""
    raw = call.get("function", {}).get("arguments")
    if not isinstance(raw, str) or not raw:
        return call
    try:
        arguments = json.loads(raw)
    except ValueError as exc:
        raise StopRun(
            RunStatus.failed, "unsupported_message_content", "Tool call arguments are not JSON."
        ) from exc
    masked = await _egress_json(ctx, arguments)
    if masked == arguments:
        return call
    return {**call, "function": {**call["function"], "arguments": json.dumps(masked)}}


async def _egress_messages(ctx: RunContext, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The single checkpoint before the provider (BLOCKERS 134): every text field of the list that
    goes to the model (system prompt, history, user, assistant, tool results, tool call
    arguments) passes `egress` on every call. The run's token store makes it idempotent: an
    already tokenized text comes back unchanged and issued placeholders are not matched again.
    Nothing is skipped or cut: a block, a too long text or a content that is not text fails the
    run."""
    out: list[dict[str, Any]] = []
    for message in messages:
        content = message.get("content")
        if content is not None and not isinstance(content, str):
            raise StopRun(
                RunStatus.failed,
                "unsupported_message_content",
                f"A {message.get('role')} message has non-text content.",
            )
        changed: dict[str, Any] = {}
        if content:
            masked = await _egress_text(ctx, content)
            if masked != content:
                changed["content"] = masked
        calls = message.get("tool_calls")
        if calls:
            checked_calls = [await _egress_call(ctx, c) for c in calls]
            if checked_calls != calls:
                changed["tool_calls"] = checked_calls
        out.append({**message, **changed} if changed else message)
    return out


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

    # C17: a delta may end inside a placeholder; the aligner holds that tail so every live
    # token entry carries whole placeholders and a reader reverses it entry by entry.
    aligner = PlaceholderAligner()

    async def on_token(text: str) -> None:
        ready = aligner.feed(text)
        if ready:
            await ctx.events.live(SseEvent.token, {"text": ready})

    outgoing = await _egress_messages(ctx, state["messages"])
    try:
        turn = await ctx.model.call(
            outgoing,
            tools=ctx.tools.schemas(),
            max_tokens=min(d.limits.output_tokens, d.answer_rules.max_answer_tokens)
            if not ctx.tools.schemas()
            else d.limits.output_tokens,
            on_token=on_token if ctx.stream_live else None,
        )
    finally:
        # Also when the call fails or the run is cancelled: what the aligner held (at most 15
        # characters) was the model's and reaches the reader (r1 MINOR-1).
        if ctx.stream_live and (tail := aligner.flush()):
            await ctx.events.live(SseEvent.token, {"text": tail})
    usage = dict(state.get("usage") or {})
    for key in ("prompt_tokens", "completion_tokens"):
        usage[key] = usage.get(key, 0) + int((turn.usage or {}).get(key) or 0)
    await ctx.events.record(
        RunEventType.llm_call,
        {
            "model": turn.model,
            "litellm_call_id": turn.call_id,
            "finish_reason": turn.finish_reason,
            "usage": turn.usage,
            "ms": turn.ms,
            "queue_ms": turn.queue_ms,
            "tool_calls": [c.name for c in turn.tool_calls],
            # The final, masked messages sent to the model (02/08 content rule).
            "request_messages": outgoing,
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


def _with_arguments(messages: list[dict], call_id: str, arguments: dict) -> list[dict]:
    """The conversation with one tool call's arguments replaced (masked or redacted)."""
    out = list(messages)
    for index in range(len(out) - 1, -1, -1):
        calls = out[index].get("tool_calls") or []
        if any(c["id"] == call_id for c in calls):
            replaced = [
                {**c, "function": {**c["function"], "arguments": json.dumps(arguments)}}
                if c["id"] == call_id
                else c
                for c in calls
            ]
            out[index] = {**out[index], "tool_calls": replaced}
            break
    return out


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
    counts = dict(state.get("tool_counts") or {})
    action_limit = ctx.tools.max_calls(name)
    if action_limit is not None and counts.get(name, 0) + 1 > action_limit:
        raise StopRun(
            RunStatus.failed,
            "limit_reached",
            partial=state.get("answer"),
            limit="max_calls_per_run",
            detail=name,
        )
    counts[name] = counts.get(name, 0) + 1
    checked = await ctx.guard.check(
        "tool.pre", json.dumps(arguments, ensure_ascii=False), tool=name
    )
    blocked = checked.action == "block"
    # Events, the approval record and the model's later requests see the guardrail's output,
    # never the raw arguments; a block has no output to show (review r2 MAJOR-2).
    masked = REDACTED_BLOCK if blocked else json.loads(checked.text)
    # The action's own needs_approval (05a tool_actions) joined with the agent's approval list.
    listed = d.approval is not None and approval_name(name) in d.approval.actions
    approval = (ctx.tools.needs_approval(name) or listed) and not blocked
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
        assign_to = d.approval.assign_to if d.approval else DEFAULT_APPROVER
        if ctx.approvals is None:
            raise StopRun(RunStatus.failed, "approval_gate_missing", detail=name)
        # 07: the approval record (idempotent per tool call); an approved twin answers.
        ticket = await ctx.approvals.open(
            tool_call_id=call["id"], action=name, arguments=masked, assign_to=assign_to
        )
        if ticket.reused:
            pending["kind"] = "approved"
            await ctx.events.record(
                RunEventType.approval_reused,
                {"tool_call_id": call["id"], "action": name, "approval_id": ticket.approval_id},
                iteration=iteration,
            )
        else:
            pending["kind"] = "approval"
            ids = {"approval_id": ticket.approval_id, "expires_at": ticket.expires_at}
            await ctx.events.record(
                RunEventType.approval_requested,
                {
                    "tool_call_id": call["id"],
                    "action": name,
                    "arguments": masked,
                    "assign_to": assign_to,
                    **ids,
                },
                sse=SseEvent.approval_required,
                sse_data={"action": name, "arguments": masked, "assign_to": assign_to, **ids},
                iteration=iteration,
            )
    return {
        "pending_tool": pending,
        "tool_calls_used": used + 1,
        "tool_counts": counts,
        "messages": _with_arguments(state["messages"], call["id"], masked),
    }


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
    hits, blocked, all_blocked = await _egress_sources(ctx, hits)
    await ctx.events.record(
        RunEventType.sources,
        {
            "selected": [s.public() for s in hits],
            "dropped_by_budget": [],
            "blocked": blocked,
            "tool": SEARCH_TOOL,
        },
        sse=SseEvent.sources,
        sse_data={"sources": [s.public() for s in hits], "blocked": blocked},
        iteration=state["iteration"],
    )
    _stop_if_all_blocked(all_blocked)
    text = "\n\n".join(f"[{s.n}] {s.document_name} ({s.breadcrumb})\n{s.text}" for s in hits)
    return text or "No matching passages.", _source_payload(hits)


async def tools(state: RunState, runtime: Runtime[RunContext]) -> dict:
    ctx = runtime.context
    await ctx.boundary("tools")
    pending = state["pending_tool"]
    name, started = pending["name"], time.monotonic()
    new_sources: list[dict] = []
    truncated, is_error, error_code = False, False, None
    if pending["kind"] == "blocked":
        text, is_error = BLOCKED_TOOL_TEXT, True
    elif name == SEARCH_TOOL:
        text, new_sources = await _search_tool(ctx, state, pending["arguments"])
    else:
        outcome = await ctx.tools.call(name, pending["arguments"])
        text, truncated, is_error = outcome.text, outcome.truncated, outcome.is_error
        error_code = outcome.error_code
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
            "error_code": error_code,
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


def _traced(name: str, node):
    """Each node is one Langfuse span under the run's trace (02 `span`); LiteLLM's generation
    lands under it through `trace_context`. No LangChain callback: it needs the full `langchain`
    package (V10)."""

    async def run(state: RunState, runtime: Runtime[RunContext]) -> dict:
        with tracing.span(f"agent.{name}"):
            return await node(state, runtime)

    run.__name__ = name
    return run


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
        graph.add_node(name, _traced(name, node))
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
