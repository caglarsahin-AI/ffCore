"""The exam gate on publish (09-2; plan/09 Akış 3, KARARLAR "09 Evaluation plan kararları" S2,
"09-1 r1 kararları" NOTE-2, "09-2 plan kararları" S1).

Every live suite bound to the agent (`eval_suites.agent_id`) needs, for the version being
published, a latest completed exam that passed, is complete and has nothing not run. A suite
with `approve_tools=false` cannot gate a version that binds an action asking for approval: such
an exam never completes unattended. Rollback is not gated (S3).

The gate publishes what was examined (09-2 r1 MAJOR-1, KARARLAR "09-2 r1 kararları" A): the
exam's `definition_sha256` must be the digest of the version's definition now (`stale_exam`,
also for an exam without one), and the suite's scorers, threshold and repeat now must be the
ones the exam ran with (`stale_suite`). `approve_tools` is not compared: true -> false is
`suite_not_gateable` or an incomplete exam already, false -> true asks nothing new of a passed,
complete exam.
"""

import hashlib
import json
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ffcore.models.agents import AgentVersion
from ffcore.models.eval import EvalRun, EvalSuite
from ffcore.models.tools import Tool, ToolAction
from ffcore.runtime.definition import AgentDefinition

REASONS = (
    "no_exam",
    "stale_exam",
    "stale_suite",
    "not_passed",
    "incomplete",
    "suite_not_gateable",
)
# The suite's settings an exam's config snapshot keeps and the gate compares (stale_suite).
SUITE_KEYS = ("scorers", "pass_threshold", "repeat")


def definition_sha256(definition: dict) -> str:
    """The digest of an agent definition: sha256 of its canonical JSON (sorted keys, no
    spaces, UTF-8). Key order does not change it; any value does."""
    text = json.dumps(definition, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode()).hexdigest()


@dataclass(frozen=True)
class GateFailure:
    suite_id: uuid.UUID
    key: str
    eval_run_id: uuid.UUID | None
    reason: str

    def public(self) -> dict:
        return {
            "suite_id": str(self.suite_id),
            "key": self.key,
            "eval_run_id": str(self.eval_run_id) if self.eval_run_id else None,
            "reason": self.reason,
        }


async def version_asks_approval(
    session: AsyncSession, project_id: uuid.UUID, definition: AgentDefinition
) -> bool:
    """Whether a run of this version may stop for an approval: the agent's own approval list,
    or an action that needs approval in the tool catalog (as the graph joins the two)."""
    if definition.approval is not None and definition.approval.actions:
        return True
    for ref in definition.tools:
        found = await session.scalar(
            select(ToolAction.id)
            .join(Tool, Tool.id == ToolAction.tool_id)
            .where(
                Tool.project_id == project_id,
                Tool.key == ref.tool_key,
                Tool.deleted_at.is_(None),
                ToolAction.name.in_(ref.actions),
                ToolAction.needs_approval.is_(True),
            )
            .limit(1)
        )
        if found is not None:
            return True
    return False


@dataclass
class GateResult:
    failures: list[GateFailure] = field(default_factory=list)
    # The exams that let their suite through, the latest first (r1 MINOR-2).
    passed: list[EvalRun] = field(default_factory=list)


async def check_gate(
    session: AsyncSession,
    project_id: uuid.UUID,
    agent_id: uuid.UUID,
    version: AgentVersion,
    definition: AgentDefinition,
) -> GateResult:
    suites = (
        await session.scalars(
            select(EvalSuite)
            .where(
                EvalSuite.project_id == project_id,
                EvalSuite.agent_id == agent_id,
                EvalSuite.deleted_at.is_(None),
            )
            .order_by(EvalSuite.key)
        )
    ).all()
    out = GateResult()
    if not suites:
        return out
    asks = await version_asks_approval(session, project_id, definition)
    digest = definition_sha256(version.definition)
    for suite in suites:
        if asks and not suite.approve_tools:
            out.failures.append(GateFailure(suite.id, suite.key, None, "suite_not_gateable"))
            continue
        ev = await session.scalar(
            select(EvalRun)
            .where(
                EvalRun.suite_id == suite.id,
                EvalRun.agent_version_id == version.id,
                EvalRun.status == "completed",
            )
            .order_by(EvalRun.ended_at.desc().nulls_last(), EvalRun.created_at.desc())
            .limit(1)
        )
        reason = _reason(ev, suite, digest)
        if reason is None:
            out.passed.append(ev)
        else:
            out.failures.append(GateFailure(suite.id, suite.key, ev.id if ev else None, reason))
    out.passed.sort(key=lambda e: (e.ended_at is not None, e.ended_at, e.created_at), reverse=True)
    return out


def _reason(ev, suite: EvalSuite, digest: str) -> str | None:
    if ev is None:
        return "no_exam"
    config = ev.config or {}
    if config.get("definition_sha256") != digest:
        return "stale_exam"  # the version was edited after the exam, or the exam has no digest
    if any(config.get(k) != getattr(suite, k) for k in SUITE_KEYS):
        return "stale_suite"
    summary = ev.summary or {}
    if not summary.get("passed"):
        return "not_passed"
    if not summary.get("complete") or summary.get("not_run"):
        return "incomplete"
    return None
