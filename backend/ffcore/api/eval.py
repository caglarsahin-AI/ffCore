"""Exams (09): suites over Langfuse datasets, exam runs, progress.

A suite is a project's exam: one Langfuse dataset (`<project_key>.<suite_key>`, the one Langfuse
project is shared by every FFCore project, K-09-0007 S6), its scorers and threshold, and
optionally the agent whose publish it gates. Items are edited in Langfuse (its own CSV/JSON
import) or seeded with `make seed-eval`; there is no local item table (A5).
"""

import asyncio
import json
import re
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import func, select

from ffcore.api.common import ERROR_RESPONSES, SessionDep, conflict, invalid, not_found
from ffcore.api.eval_schemas import (
    EvalRunList,
    EvalRunOut,
    SuiteCreate,
    SuiteList,
    SuiteOut,
    SuiteUpdate,
)
from ffcore.core import db
from ffcore.core.audit import audited, request_context
from ffcore.core.auth import Actor, require_role
from ffcore.core.config import Settings, get_settings
from ffcore.core.errors import ApiError
from ffcore.evaluation.langfuse_api import LangfuseApi, LangfuseApiError
from ffcore.evaluation.runner import Starter, start_eval
from ffcore.models.agents import Agent, AgentVersion
from ffcore.models.eval import EvalRun, EvalSuite
from ffcore.models.identity import Project, ProjectMember

router = APIRouter(prefix="/projects/{project_id}", tags=["evaluation"], responses=ERROR_RESPONSES)

Reader = Annotated[Actor, Depends(require_role("analyst"))]
# Analysts build, test and publish agents (PLAN 1); exams are part of that.
Editor = Annotated[Actor, Depends(require_role("analyst", write=True))]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def suite_resource(suite_id: UUID) -> UUID:
    """The audited resource of a suite endpoint (also when it fails or deletes, r1 MINOR-7)."""
    return suite_id


def eval_run_resource(eval_run_id: UUID) -> UUID:
    return eval_run_id


SuiteResource = Annotated[UUID, Depends(suite_resource)]
EvalRunResource = Annotated[UUID, Depends(eval_run_resource)]

# After `<project_key>.`: lower-case letters, digits, `.`, `_`, `-`; no `..` (r1 MINOR-11; the
# name goes into Langfuse URL paths).
DATASET_TAIL = re.compile(r"[a-z0-9][a-z0-9._-]{0,127}")


def dataset_name_ok(name: str, project_key: str) -> bool:
    prefix = f"{project_key}."
    return (
        name.startswith(prefix)
        and DATASET_TAIL.fullmatch(name[len(prefix) :]) is not None
        and ".." not in name
    )


def langfuse_dependency(settings: SettingsDep) -> LangfuseApi:
    try:
        return LangfuseApi(settings)
    except LangfuseApiError as exc:
        raise ApiError(503, "api_error", exc.code, "Exams need Langfuse.") from None


LangfuseDep = Annotated[LangfuseApi, Depends(langfuse_dependency)]


def langfuse_failed(exc: LangfuseApiError) -> ApiError:
    return ApiError(502, "api_error", exc.code, "The Langfuse call failed.")


def suite_out(row: EvalSuite) -> SuiteOut:
    return SuiteOut.model_validate(row, from_attributes=True)


def run_out(row: EvalRun) -> EvalRunOut:
    plan = row.item_runs or {}
    return EvalRunOut(
        id=row.id,
        project_id=row.project_id,
        suite_id=row.suite_id,
        agent_version_id=row.agent_version_id,
        langfuse_run_name=row.langfuse_run_name,
        status=row.status,
        error_code=row.error_code,
        items=len(plan),
        scored=sum(1 for e in plan.values() if e.get("scored")),
        summary=row.summary,
        cost_usd=float(row.cost_usd) if row.cost_usd is not None else None,
        started_at=row.started_at,
        ended_at=row.ended_at,
        created_at=row.created_at,
    )


async def _suite(session, project_id: UUID, suite_id: UUID) -> EvalSuite:
    row = await session.scalar(
        select(EvalSuite).where(
            EvalSuite.id == suite_id,
            EvalSuite.project_id == project_id,
            EvalSuite.deleted_at.is_(None),
        )
    )
    if row is None:
        raise not_found("suite")
    return row


async def _eval_run(session, project_id: UUID, eval_run_id: UUID) -> EvalRun:
    row = await session.scalar(
        select(EvalRun).where(
            EvalRun.id == eval_run_id,
            EvalRun.project_id == project_id,
            EvalRun.deleted_at.is_(None),
        )
    )
    if row is None:
        raise not_found("eval_run")
    return row


async def _native_agent(session, project_id: UUID, agent_id: UUID) -> Agent:
    agent = await session.scalar(
        select(Agent).where(
            Agent.id == agent_id, Agent.project_id == project_id, Agent.deleted_at.is_(None)
        )
    )
    if agent is None:
        raise not_found("agent")
    if agent.kind == "external":
        raise invalid("external_agent_not_runnable", "An external agent has no versions to test.")
    return agent


def _check_scorers(scorers, settings: Settings) -> None:
    if any(s.name == "llm_judge" for s in scorers) and not settings.eval_judge_model:
        raise invalid(
            "judge_model_not_configured", "llm_judge needs EVAL_JUDGE_MODEL (a model key)."
        )


@router.get("/eval-suites", response_model=SuiteList)
async def list_suites(project_id: UUID, actor: Reader, session: SessionDep):
    rows = await session.scalars(
        select(EvalSuite)
        .where(EvalSuite.project_id == project_id, EvalSuite.deleted_at.is_(None))
        .order_by(EvalSuite.key)
    )
    return SuiteList(items=[suite_out(r) for r in rows])


@router.post("/eval-suites", response_model=SuiteOut, status_code=status.HTTP_201_CREATED)
@audited("create_eval_suite", "eval_suite")
async def create_suite(
    project_id: UUID,
    body: SuiteCreate,
    request: Request,
    actor: Editor,
    session: SessionDep,
    settings: SettingsDep,
    langfuse: LangfuseDep,
):
    """Create a suite and its Langfuse dataset (created if missing; an existing one is kept)."""
    project = await session.get(Project, project_id)
    if project is None:
        raise not_found("project")
    dataset = body.langfuse_dataset_name or f"{project.key}.{body.key}"
    if not dataset_name_ok(dataset, project.key):
        raise invalid(
            "dataset_name_not_in_project",
            f"The dataset name must be '{project.key}.' and then lower-case letters, digits, "
            "'.', '_' or '-' without '..' (one Langfuse project is shared).",
        )
    threshold = body.pass_threshold or settings.eval_pass_threshold
    if threshold is None:
        raise invalid(
            "eval_threshold_not_configured",
            "Give pass_threshold or set EVAL_PASS_THRESHOLD (no hidden default).",
        )
    _check_scorers(body.scorers, settings)
    if body.agent_id is not None:
        await _native_agent(session, project_id, body.agent_id)
    taken = await session.scalar(
        select(EvalSuite.id).where(
            EvalSuite.project_id == project_id,
            EvalSuite.key == body.key,
            EvalSuite.deleted_at.is_(None),
        )
    )
    if taken is not None:
        raise conflict("suite_key_taken", "A suite with this key exists in the project.")
    try:
        await langfuse.upsert_dataset(
            dataset, description=body.name, metadata={"project_key": project.key, "suite": body.key}
        )
    except LangfuseApiError as exc:
        raise langfuse_failed(exc) from None
    row = EvalSuite(
        project_id=project_id,
        key=body.key,
        name=body.name,
        agent_id=body.agent_id,
        langfuse_dataset_name=dataset,
        scorers=[s.model_dump(exclude_none=True) for s in body.scorers],
        pass_threshold=threshold,
        repeat=body.repeat,
        approve_tools=body.approve_tools,
        created_by=actor.actor_id,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return suite_out(row)


@router.get("/eval-suites/{suite_id}", response_model=SuiteOut)
async def get_suite(project_id: UUID, suite_id: UUID, actor: Reader, session: SessionDep):
    return suite_out(await _suite(session, project_id, suite_id))


async def _suite_before(project_id, suite_id, session, **_):
    return suite_out(await _suite(session, project_id, suite_id))


@router.patch("/eval-suites/{suite_id}", response_model=SuiteOut)
@audited("update_eval_suite", "eval_suite", load_before=_suite_before)
async def update_suite(
    project_id: UUID,
    suite_id: UUID,
    body: SuiteUpdate,
    request: Request,
    actor: Editor,
    session: SessionDep,
    settings: SettingsDep,
    resource_id: SuiteResource,
):
    """A running exam keeps the suite as it started (its own `config`); a change applies to
    the next exam."""
    row = await _suite(session, project_id, suite_id)
    fields = body.model_dump(exclude_unset=True)
    if "scorers" in fields:
        _check_scorers(body.scorers, settings)
        fields["scorers"] = [s.model_dump(exclude_none=True) for s in body.scorers]
    if fields.get("agent_id") is not None:
        await _native_agent(session, project_id, fields["agent_id"])
    for name, value in fields.items():
        setattr(row, name, value)
    await session.flush()
    await session.refresh(row)
    return suite_out(row)


@router.delete("/eval-suites/{suite_id}", status_code=status.HTTP_204_NO_CONTENT)
@audited("delete_eval_suite", "eval_suite", load_before=_suite_before)
async def delete_suite(
    project_id: UUID,
    suite_id: UUID,
    request: Request,
    actor: Editor,
    session: SessionDep,
    resource_id: SuiteResource,
):
    """Soft delete; the Langfuse dataset and its runs stay (they are the exam history)."""
    row = await _suite(session, project_id, suite_id)
    row.deleted_at = func.now()
    await session.flush()


@router.post(
    "/eval-suites/{suite_id}/run", response_model=EvalRunOut, status_code=status.HTTP_202_ACCEPTED
)
async def start_eval_run(
    project_id: UUID,
    suite_id: UUID,
    request: Request,
    actor: Editor,
    session: SessionDep,
    settings: SettingsDep,
    langfuse: LangfuseDep,
    agent_version_id: Annotated[UUID, Query(description="The agent version to examine.")],
):
    """Start an exam: every active item becomes `repeat` background `channel=test` runs of the
    version, for the caller. The items are checked and the exam is written `queued`; the
    advancer starts the runs and the exam turns `running`. Progress: GET …/eval-runs/{id} or
    …/stream. Audited once for the exam (start_eval_run) and per run (start_run)."""
    if actor.actor_type != "user":
        raise invalid("run_user_missing", "An exam is started by a user.")
    member = await session.scalar(
        select(ProjectMember.user_id).where(
            ProjectMember.project_id == project_id, ProjectMember.user_id == UUID(actor.actor_id)
        )
    )
    if member is None:
        raise ApiError(
            403,
            "permission_error",
            "run_needs_membership",
            "Exam runs act on behalf of a project member; add yourself to the project first.",
        )
    suite = await _suite(session, project_id, suite_id)
    version = await session.get(AgentVersion, agent_version_id)
    if version is None:
        raise not_found("version")
    # Another project's version is the same 404 as a missing one (r1 NOTE-6).
    agent = await session.scalar(
        select(Agent).where(
            Agent.id == version.agent_id,
            Agent.project_id == project_id,
            Agent.deleted_at.is_(None),
        )
    )
    if agent is None:
        raise not_found("version")
    if agent.kind == "external":
        raise invalid("external_agent_not_runnable", "An external agent has no versions to test.")
    if suite.agent_id is not None and suite.agent_id != agent.id:
        raise invalid("version_not_of_suite_agent", "The version belongs to another agent.")
    request_id, ip = request_context(request)
    try:
        ev = await start_eval(
            session,
            settings,
            suite=suite,
            version=version,
            starter=Starter(UUID(actor.actor_id), actor.actor_type, actor.actor_id, request_id, ip),
            api=langfuse,
        )
    except LangfuseApiError as exc:
        await session.rollback()
        raise langfuse_failed(exc) from None
    await session.refresh(ev)
    return run_out(ev)


@router.get("/eval-suites/{suite_id}/runs", response_model=EvalRunList)
async def list_eval_runs(project_id: UUID, suite_id: UUID, actor: Reader, session: SessionDep):
    await _suite(session, project_id, suite_id)
    rows = await session.scalars(
        select(EvalRun)
        .where(EvalRun.suite_id == suite_id, EvalRun.deleted_at.is_(None))
        .order_by(EvalRun.created_at.desc())
    )
    return EvalRunList(items=[run_out(r) for r in rows])


@router.get("/eval-runs/{eval_run_id}", response_model=EvalRunOut)
async def get_eval_run(project_id: UUID, eval_run_id: UUID, actor: Reader, session: SessionDep):
    return run_out(await _eval_run(session, project_id, eval_run_id))


@router.post("/eval-runs/{eval_run_id}/cancel", response_model=EvalRunOut)
@audited("cancel_eval_run", "eval_run")
async def cancel_eval_run(
    project_id: UUID,
    eval_run_id: UUID,
    request: Request,
    actor: Editor,
    session: SessionDep,
    resource_id: EvalRunResource,
):
    """The advancer cancels the item runs on its next tick and ends the exam `cancelled`."""
    row = await _eval_run(session, project_id, eval_run_id)
    if row.status not in ("queued", "running"):
        raise conflict("eval_run_finished", f"The exam is {row.status} already.")
    row.cancel_requested_at = func.now()
    await session.flush()
    await session.refresh(row)
    return run_out(row)


PROGRESS_INTERVAL_S = 2.0


@router.get(
    "/eval-runs/{eval_run_id}/stream",
    responses={200: {"content": {"text/event-stream": {"schema": {"type": "string"}}}}},
)
async def stream_eval_run(project_id: UUID, eval_run_id: UUID, actor: Reader, session: SessionDep):
    """Server-sent `progress` events (`status`, `items`, `scored`) until the exam ends, then
    one `done` with the status and `passed`. The stream only reads; closing it changes nothing."""
    from ffcore.api.runs import EventStreamResponse

    await _eval_run(session, project_id, eval_run_id)

    async def body():
        while True:
            async with db.session_scope() as reader:
                row = await _eval_run(reader, project_id, eval_run_id)
                out = run_out(row)
            data = {"status": out.status, "items": out.items, "scored": out.scored}
            if out.status in ("completed", "failed", "cancelled"):
                done = data | {
                    "error_code": out.error_code,
                    "passed": (out.summary or {}).get("passed"),
                }
                yield f"event: done\ndata: {json.dumps(done)}\n\n"
                return
            yield f"event: progress\ndata: {json.dumps(data)}\n\n"
            await asyncio.sleep(PROGRESS_INTERVAL_S)

    return EventStreamResponse(body(), headers={"Cache-Control": "no-cache"})
