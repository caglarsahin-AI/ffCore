"""Prompt assembly and the context budget (brief 06 P8, PayCore D5/D6).

Order for the model's KV cache (D6): the fixed part first (system prompt, then the SOURCES
block), the question last; a second call with the same sources does not re-read them.
Sources are given newest first with their update day (D5); the prompt tells the model to build
the answer from the newest source and to name an older one that differs, with its date.

The system prompt has three parts kept apart in the trace (02): `platform_rules` (Langfuse prompt
`platform_rules`), `runtime_profile` (reserved, empty) and `user_instructions` (the agent's own).

Budget: `context_tokens − (system + tool schemas + output reserve)` is shared between history,
RAG and memory by `context_policy`; over a share, parts are dropped in `trim_order`: history
loses its oldest turns, RAG its lowest-ranked chunks (chunks are never cut), memory (14) its
items. Everything dropped is listed in the `budget` and `sources` events (C13, no silent trim).
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ffcore.knowledge.chunking import approx_tokens
from ffcore.runtime.definition import PLACEHOLDER, AgentDefinition


@dataclass
class Source:
    """One retrieved chunk as the runtime keeps it (from the 04a search response)."""

    n: int
    kb_key: str
    chunk_id: str
    document_id: str
    document_name: str
    page: int | None
    breadcrumb: str
    text: str
    updated_at_source: str | None
    rerank_score: float | None

    def public(self) -> dict[str, Any]:
        """What the `sources` event and the message carry: no chunk text (it stays in the KB)."""
        return {
            "n": self.n,
            "kb_key": self.kb_key,
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "document_name": self.document_name,
            "page": self.page,
            "breadcrumb": self.breadcrumb,
            "updated_at_source": self.updated_at_source,
            "rerank_score": self.rerank_score,
        }


@dataclass
class Budget:
    context_tokens: int
    fixed_tokens: int
    shares: dict[str, int]
    used: dict[str, int] = field(default_factory=dict)
    dropped: dict[str, list[Any]] = field(default_factory=dict)

    def event(self) -> dict[str, Any]:
        return {
            "planned": {"context_tokens": self.context_tokens, "fixed": self.fixed_tokens}
            | {f"{k}_share": v for k, v in self.shares.items()},
            "used": self.used,
            "dropped": self.dropped,
        }


class VariableError(ValueError):
    """A run's variables do not fit its instructions; the run ends at start with this code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def render_variables(text: str, definition: AgentDefinition, given: dict[str, str]) -> str:
    """`{{key}}` placeholders from the definition's variables (default, then the run's value).
    An unknown given key is `variable_unknown`; a placeholder without a variable, or any `{{`
    left over, is `variable_unresolved`: nothing reaches the model as written."""
    known = {v.key: v.default for v in definition.variables}
    unknown = sorted(set(given) - set(known))
    if unknown:
        raise VariableError("variable_unknown", f"unknown variables: {unknown}")
    values = {**known, **given}
    missing = sorted({key for key in PLACEHOLDER.findall(text) if key not in values})
    if missing or "{{" in PLACEHOLDER.sub("", text):
        raise VariableError(
            "variable_unresolved", f"placeholders without a variable: {missing or ['{{']}"
        )
    return PLACEHOLDER.sub(lambda m: values[m.group(1)], text)


def system_parts(platform_rules: str, user_instructions: str) -> dict[str, str]:
    return {
        "platform_rules": platform_rules,
        "runtime_profile": "",
        "user_instructions": user_instructions,
    }


def system_message(parts: dict[str, str]) -> str:
    return "\n\n".join(p for p in parts.values() if p)


def by_recency(sources: list[Source]) -> list[Source]:
    """Newest first (D5); undated sources last, in their rank order."""

    def key(s: Source):
        stamp = s.updated_at_source
        return (stamp is None, -(datetime.fromisoformat(stamp).timestamp()) if stamp else 0)

    return sorted(sources, key=key)


def sources_block(sources: list[Source]) -> str:
    lines = ["SOURCES (newest first; cite as [n]):"]
    for s in by_recency(sources):
        day = s.updated_at_source[:10] if s.updated_at_source else "unknown date"
        page = f", page {s.page}" if s.page is not None else ""
        lines.append(f"[{s.n}] {s.document_name}{page} (updated {day}) {s.breadcrumb}\n{s.text}")
    return "\n\n".join(lines)


def plan_budget(definition: AgentDefinition, system: str, tools_schema: list[dict]) -> Budget:
    policy = definition.context_policy
    tools_tokens = approx_tokens(str(tools_schema)) if tools_schema else 0
    fixed = approx_tokens(system) + tools_tokens + policy.output_reserve_tokens
    left = definition.limits.context_tokens - fixed
    if left <= 0:
        raise ValueError(
            f"context_configuration_invalid: the fixed part ({fixed} tokens) leaves nothing of "
            f"context_tokens {definition.limits.context_tokens}"
        )
    shares = {
        "history": min(policy.history_max_tokens, left),
        "rag": min(policy.rag_max_tokens, left),
        "memory": min(policy.memory_max_tokens, left),
    }
    return Budget(definition.limits.context_tokens, fixed, shares)


def fit_sources(budget: Budget, sources: list[Source]) -> list[Source]:
    """Keep the best-ranked chunks within the RAG share; whole chunks only."""
    kept, used = [], 0
    for s in sources:
        cost = approx_tokens(s.text) + 30  # header line
        if used + cost > budget.shares["rag"]:
            budget.dropped.setdefault("rag", []).append(s.chunk_id)
            continue
        kept.append(s)
        used += cost
    budget.used["rag"] = used
    return kept


def fit_history(budget: Budget, turns: list[dict[str, str]], max_turns: int) -> list[dict]:
    """The last `max_turns` turns (a turn = user + assistant message) within the history share;
    older ones drop and are counted (the summary call is FOLLOWUP-88)."""
    pairs = [turns[i : i + 2] for i in range(0, len(turns), 2)]
    keep_pairs = pairs[-max_turns:] if max_turns else []
    dropped = len(pairs) - len(keep_pairs)
    while (
        keep_pairs
        and sum(approx_tokens(m["content"]) for p in keep_pairs for m in p)
        > (budget.shares["history"])
    ):
        keep_pairs.pop(0)
        dropped += 1
    kept = [m for p in keep_pairs for m in p]
    budget.used["history"] = sum(approx_tokens(m["content"]) for m in kept)
    if dropped:
        budget.dropped["history_turns"] = dropped
    return kept


def user_message(question: str, sources: list[Source] | None) -> str:
    """Sources before the question, so the varying part comes last (D6)."""
    if not sources:
        return question
    return f"{sources_block(sources)}\n\nQUESTION:\n{question}"


# The model's own "not found" (brief 06): negative forms only; "bulunmaktadır" does not match.
DECLINE_PATTERN = (
    r"\b(bulamadım|bulunamadı|bulunamamıştır|bulunmamaktadır"
    r"|could not find|not found in the (?:documents|sources))\b"
)
