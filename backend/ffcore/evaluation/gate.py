"""The exam gate on publish (09-2; plan/09 Akış 3, KARARLAR "09 Evaluation plan kararları" S2,
"09-1 r1 kararları" NOTE-2, "09-2 plan kararları" S1).

Every live suite bound to the agent (`eval_suites.agent_id`) needs, for the version being
published, a latest completed exam that passed, is complete and has nothing not run. A suite
with `approve_tools=false` cannot gate a version that binds an action asking for approval: such
an exam never completes unattended. Rollback is not gated (S3).
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ffcore.models.eval import EvalRun, EvalSuite
from ffcore.models.tools import Tool, ToolAction
from ffcore.runtime.definition import AgentDefinition

REASONS = ("no_exam", "not_passed", "incomplete", "suite_not_gateable")


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


async def gate_failures(
    session: AsyncSession,
    project_id: uuid.UUID,
    agent_id: uuid.UUID,
    version_id: uuid.UUID,
    definition: AgentDefinition,
) -> list[GateFailure]:
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
    if not suites:
        return []
    asks = await version_asks_approval(session, project_id, definition)
    out = []
    for suite in suites:
        if asks and not suite.approve_tools:
            out.append(GateFailure(suite.id, suite.key, None, "suite_not_gateable"))
            continue
        ev = await session.scalar(
            select(EvalRun)
            .where(
                EvalRun.suite_id == suite.id,
                EvalRun.agent_version_id == version_id,
                EvalRun.status == "completed",
            )
            .order_by(EvalRun.ended_at.desc().nulls_last(), EvalRun.created_at.desc())
            .limit(1)
        )
        reason = _reason(ev)
        if reason is not None:
            out.append(GateFailure(suite.id, suite.key, ev.id if ev else None, reason))
    return out


def _reason(ev) -> str | None:
    if ev is None:
        return "no_exam"
    summary = ev.summary or {}
    if not summary.get("passed"):
        return "not_passed"
    if not summary.get("complete") or summary.get("not_run"):
        return "incomplete"
    return None
