"""`llm_judge` (09): the rubric judge runs in FFCore, not in Langfuse (K-09-0006, S-J A).

The judge sees the question, the expected answer and the agent's answer, rendered into the
Langfuse prompt `eval_judge_rubric` (seed backend/prompts/eval_judge_rubric.md). Before the
model call the whole text goes through the item run's guardrail policy at the `egress` stage
(08; a no-op where GUARDRAIL_EGRESS_ENABLED=false): the judge never sees what the agent's own
model call would not have been allowed to send. The call is a background-class model call
(LLM_SLOTS, BACKGROUND_WINDOW) on EVAL_JUDGE_MODEL, under the project's quotas, traced on the
item run's trace. Unreadable output is an error, never a guessed score (scorers.parse_judge).
The judge's reason is the model's answer to masked input; it is kept short with an explicit
truncation mark (S8).
"""

from dataclasses import dataclass
from typing import Any, Protocol

from ffcore.evaluation.scorers import JudgeParseError, Score, judge_score, parse_judge

RUBRIC_PROMPT = "eval_judge_rubric"
REASON_MAX = 500
JUDGE_MAX_TOKENS = 300


class Guard(Protocol):
    async def egress(self, text: str) -> tuple[str, str]:
        """(action, text after the stage): action is allow, mask or block."""


class Model(Protocol):
    async def complete(self, text: str) -> str: ...


class Rubric(Protocol):
    def render(self, *, question: str, expected: str, answer: str) -> str: ...


@dataclass(frozen=True)
class JudgeResult:
    score: Score
    reason: str


def clip(text: str, limit: int = REASON_MAX) -> str:
    """Short comment field: an explicit mark, never a silent cut (PLAN 5, K-05a-0002)."""
    if len(text) <= limit:
        return text
    return text[:limit] + f" [truncated: {limit}/{len(text)} chars]"


async def judge(
    *,
    question: str,
    expected: str,
    answer: str,
    rubric: Rubric,
    guard: Guard,
    model: Model,
    pass_min: int,
) -> JudgeResult:
    text = rubric.render(question=question, expected=expected, answer=answer)
    action, outgoing = await guard.egress(text)
    if action == "block":
        return JudgeResult(Score("llm_judge", None, None, "judge_blocked_at_egress", "error"), "")
    raw = await model.complete(outgoing)
    try:
        verdict = parse_judge(raw)
    except JudgeParseError as exc:
        return JudgeResult(Score("llm_judge", None, None, str(exc), "error"), "")
    return JudgeResult(judge_score(verdict, pass_min=pass_min), clip(verdict.reason))


# --- production bindings ---------------------------------------------------------------------


class PromptRubric:
    def __init__(self, prompts: Any) -> None:
        self._prompts = prompts

    def render(self, *, question: str, expected: str, answer: str) -> str:
        prompt = self._prompts.get(RUBRIC_PROMPT)
        return prompt.compile(question=question, expected=expected, answer=answer)


class EgressGuard:
    """The item run's policy at the egress stage, events recorded like the run's own."""

    def __init__(self, session, redis, policy, *, run_id, project_id, egress_enabled, ttl_s):
        from ffcore.guardrails.masking import RedisTokenStore

        self._session, self._policy = session, policy
        self._run_id, self._project_id = str(run_id), project_id
        self._egress = egress_enabled
        self._tokens = RedisTokenStore(redis, ttl_s)

    async def egress(self, text: str) -> tuple[str, str]:
        from ffcore.guardrails import engine
        from ffcore.guardrails.service import record_events

        if not self._egress:
            return "allow", text
        ctx = engine.EvalContext(
            run_id=self._run_id,
            project_id=str(self._project_id),
            source="eval",
            token_store=self._tokens,
            egress_enabled=True,
        )
        decision = await engine.evaluate(text, "egress", self._policy, ctx=ctx)
        if decision.events:
            record_events(self._session, self._project_id, decision.events, decision.reference_id)
        return decision.action, decision.text_out


class LiteLLMJudgeModel:
    def __init__(self, inner) -> None:
        self._inner = inner  # runtime.adapters.LiteLLMModel, job class background

    async def complete(self, text: str) -> str:
        turn = await self._inner.call(
            [{"role": "user", "content": text}],
            tools=None,
            max_tokens=JUDGE_MAX_TOKENS,
            on_token=None,
        )
        return turn.content
