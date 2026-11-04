"""The exam advancer on the background worker (09, K-09-0007 S4; 09-1 r1 MAJOR-2).

Two parts:

- `listen_loop`: a task of the worker process (not an arq job, so busy job slots never delay
  it) that every EVAL_ADVANCE_INTERVAL_S marks every unfinished item run of every active exam
  as listened. The exam is the item runs' follower; while the worker lives they are never
  abandoned, however long a tick takes. A dead worker stops following, and 06a abandons them.
- `tick` (arq cron): per active exam, under a Redis lock (`SET NX` + TTL, kept alive while the
  tick works), start the missing item runs of a queued exam or advance a running one. At most
  EVAL_JUDGE_CALLS_PER_TICK judge calls per exam per tick. A failure, the job's timeout
  (`CancelledError`) included, counts towards MAX_ATTEMPTS; a successful tick resets the count.

Production bindings for runner.advance_eval: the judge (LiteLLM, background class, egress),
the SQL re-read (mcp-sql as the exam's starter), the embedding (API /internal/embed).
"""

import asyncio
import contextlib
import logging
import uuid

from sqlalchemy import select

from ffcore.core import db
from ffcore.core.audit import AuditEntry, write_event
from ffcore.core.config import Settings
from ffcore.evaluation import judge as judge_mod
from ffcore.evaluation.engine import MAX_ATTEMPTS, TERMINAL, now_utc
from ffcore.evaluation.langfuse_api import LangfuseApi
from ffcore.evaluation.runner import (
    ACTIVE,
    Budget,
    active_runs,
    advance_eval,
    parse_csv_rows,
    start_items,
)
from ffcore.evaluation.scorers import Score
from ffcore.guardrails.service import resolve_policy
from ffcore.guardrails.settings import get_guardrail_settings
from ffcore.models.agents import AgentVersion
from ffcore.models.eval import EvalRun
from ffcore.models.runs import Run
from ffcore.models.tools import Tool, ToolAction
from ffcore.runtime import events as run_events
from ffcore.runtime.contracts import JobClass
from ffcore.runtime.definition import parse_definition

log = logging.getLogger("ffcore.evaluation")

# Lock life; renewed every LOCK_TTL_S / 3 while the tick works, so only a dead tick lets it go.
LOCK_TTL_S = 60
# arq cron timeout of one tick; past it the job is cancelled and that counts as a failure.
TICK_TIMEOUT_S = 600
SQL_ERROR_PREFIXES = ("sql_rejected:", "sql_error:")


def lock_key(ev_id) -> str:
    return f"eval:{ev_id}:lock"


def failures_key(ev_id) -> str:
    return f"eval:{ev_id}:advance_failures"


@contextlib.asynccontextmanager
async def exam_lock(redis, ev_id, ttl_s: int = LOCK_TTL_S):
    """One worker advances an exam at a time (r1 MAJOR-2). Yields False when another holds
    it. The lock is renewed while held; it is released only by its holder."""
    token = uuid.uuid4().hex
    if not await redis.set(lock_key(ev_id), token, nx=True, ex=ttl_s):
        yield False
        return

    async def renew():
        while True:
            await asyncio.sleep(ttl_s / 3)
            await redis.expire(lock_key(ev_id), ttl_s)

    keeper = asyncio.create_task(renew())
    try:
        yield True
    finally:
        keeper.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await keeper
        held = await redis.get(lock_key(ev_id))
        if held in (token, token.encode()):
            await redis.delete(lock_key(ev_id))


async def keep_listening(settings: Settings, redis) -> int:
    """Mark every unfinished item run of every active exam listened; returns how many."""
    async with db.session_scope() as session:
        plans = (
            await session.scalars(select(EvalRun.item_runs).where(EvalRun.status.in_(ACTIVE)))
        ).all()
        ids = [uuid.UUID(r) for plan in plans for e in (plan or {}).values() for r in e["runs"]]
        if not ids:
            return 0
        live = (
            await session.scalars(
                select(Run.id).where(Run.id.in_(ids), Run.status.not_in(tuple(TERMINAL)))
            )
        ).all()
    for run_id in live:
        await run_events.mark_listening(redis, run_id, settings.run_abandon_grace_s)
    return len(live)


async def listen_loop(settings: Settings, redis) -> None:
    """The background worker's follower task (started on worker startup, cancelled on
    shutdown). An error is logged and the loop goes on: a missed beat is caught by the next."""
    while True:
        try:
            await keep_listening(settings, redis)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("eval_listen_failed")
        await asyncio.sleep(settings.eval_advance_interval_s)


async def tick(settings: Settings, redis, slots, prompts, *, queue=None) -> None:
    async with db.session_scope() as session:
        ids = [ev.id for ev in await active_runs(session)]
    if not ids:
        return
    await keep_listening(settings, redis)
    api = LangfuseApi(settings)
    for ev_id in ids:
        async with exam_lock(redis, ev_id) as held:
            if not held:
                continue
            await _advance_one(settings, redis, slots, prompts, api, ev_id, queue)


async def _advance_one(settings, redis, slots, prompts, api, ev_id, queue) -> None:
    async with db.session_scope() as session:
        ev = await session.get(EvalRun, ev_id)
        if ev is None or ev.status not in ACTIVE:
            return
        try:
            if ev.status == "queued" and ev.cancel_requested_at is None:
                await start_items(
                    session, settings, ev, queue=queue or _queue(settings), queued_event=_queued()
                )
            else:
                await advance_eval(
                    session,
                    settings,
                    ev,
                    api=api,
                    judge=_judge(settings, session, redis, slots, prompts),
                    sql=_sql(settings, session),
                    embed=_embed(settings),
                    close=_closer(settings),
                    budget=Budget(settings.eval_judge_calls_per_tick),
                )
        except asyncio.CancelledError:
            # The job's timeout (or a shutdown): a failure like any other, never silent.
            log.error("eval_advance_cancelled eval_run=%s", ev_id)
            await asyncio.shield(_count_failure(redis, ev_id, TimeoutError("tick cancelled")))
            raise
        except Exception as exc:  # one exam's error never stops the others
            log.exception("eval_advance_failed eval_run=%s", ev_id)
            await session.rollback()
            await _count_failure(redis, ev_id, exc)
            return
    await redis.delete(failures_key(ev_id))  # r1 MINOR-8: only consecutive failures count


async def _count_failure(redis, ev_id, exc: BaseException) -> None:
    """A tick that keeps failing ends the exam `failed` after MAX_ATTEMPTS ticks in a row with
    the error type as its code: a stuck exam is visible, never active forever (ARCH-06)."""
    key = failures_key(ev_id)
    count = await redis.incr(key)
    await redis.expire(key, 3600)
    if count < MAX_ATTEMPTS:
        return
    async with db.session_scope() as session:
        ev = await session.get(EvalRun, ev_id)
        if ev is not None and ev.status in ACTIVE:
            ev.status = "failed"
            ev.error_code = f"advance_failed:{type(exc).__name__}"
            ev.ended_at = now_utc()
            await session.commit()
    await redis.delete(key)


def _queue(settings):
    from ffcore.runtime.queue import get_background_queue

    return get_background_queue(settings)


def _queued():
    from ffcore.api.runs import _queued_event

    return _queued_event


def _closer(settings):
    """The end of a run the advancer cancelled: its `error` event, like POST …/cancel."""
    from ffcore.runtime.contracts import RunEventType, RunStatus, SseEvent

    async def close(session, run, code):
        client = run_events.redis_client(settings)
        try:
            writer = run_events.RunEventWriter(
                session, client, run.id, ttl_s=settings.run_event_stream_ttl_s
            )
            await writer.start()
            await writer.record(
                RunEventType.error,
                {"code": code, "status": RunStatus.cancelled, "message": None},
                sse=SseEvent.error,
            )
        finally:
            await client.aclose()

    return close


def _judge(settings, session, redis, slots, prompts):
    from ffcore.runtime.adapters import LiteLLMModel
    from ffcore.services.quota import QuotaGate, Subject, engine_for

    guardrail = get_guardrail_settings()

    async def run_judge(run, item, facts, cfg):
        if not settings.eval_judge_model:
            return Score("llm_judge", None, None, "judge_model_not_configured", "error"), ""
        version = await session.get(AgentVersion, run.agent_version_id)
        definition = parse_definition(version.definition)
        policy = await resolve_policy(session, run.project_id, definition.guardrail_policy_key)
        guard = judge_mod.EgressGuard(
            session,
            redis,
            policy,
            run_id=run.id,
            project_id=run.project_id,
            egress_enabled=guardrail.guardrail_egress_enabled,
            ttl_s=guardrail.pii_token_ttl_s,
        )
        model = judge_mod.LiteLLMJudgeModel(
            LiteLLMModel(
                settings,
                session,
                slots,
                run_id=run.id,
                project_id=run.project_id,
                user_id=run.user_id,
                model_key=settings.eval_judge_model,
                job_class=JobClass.background,
                quota=QuotaGate(
                    engine_for(settings, redis),
                    redis,
                    session,
                    Subject(
                        project_id=str(run.project_id), user_id=str(run.user_id), api_key_id=None
                    ),
                    settings=settings,
                ),
            )
        )
        expected = item.get("expectedOutput") or {}
        try:
            result = await judge_mod.judge(
                question=item["input"]["message"],
                expected=str(
                    expected.get("answer") or ", ".join(expected.get("must_contain") or [])
                ),
                answer=facts.answer,
                rubric=judge_mod.PromptRubric(prompts),
                guard=guard,
                model=model,
                pass_min=int(cfg.get("pass_min", 4)),
            )
        except Exception as exc:  # model, quota or prompt failure: a coded item error
            code = getattr(exc, "code", None) or type(exc).__name__
            return Score("llm_judge", None, None, f"judge_failed:{code}", "error"), ""
        return result.score, result.reason

    return run_judge


async def bound_sql_action(session, run, tool_key: str):
    """The run_sql action of `tool_key` only if the run's agent version was given it and it is
    usable now (discovered tool, action available and enabled), as the runtime binds tools
    (r1 MAJOR-1). None otherwise."""
    version = await session.get(AgentVersion, run.agent_version_id)
    refs = parse_definition(version.definition).tools
    if not any(r.tool_key == tool_key and "run_sql" in r.actions for r in refs):
        return None
    found = (
        await session.execute(
            select(Tool, ToolAction)
            .join(ToolAction, ToolAction.tool_id == Tool.id)
            .where(
                Tool.project_id == run.project_id,
                Tool.key == tool_key,
                Tool.deleted_at.is_(None),
                Tool.status == "discovered",
                ToolAction.name == "run_sql",
                ToolAction.status == "available",
                ToolAction.enabled.is_(True),
            )
        )
    ).first()
    return found


def _sql(settings, session):
    from ffcore.services import mcp_client, mcp_tools

    async def reread(run, tool_key, sql_text):
        """The last run_sql the agent really ran (executed; approved when asked, engine
        `executed_sql`), read again with the same bound tool and the exam starter's identity:
        the read-only database and the validator apply. A refused or failed read is a coded
        failure, never an empty result (r1 MINOR-4); the audit is committed on its own."""
        found = await bound_sql_action(session, run, tool_key)
        if found is None:
            return None, "no_executed_sql"
        tool, action = found
        caller = mcp_client.Caller(user_id=str(run.user_id), project_id=str(run.project_id))
        result = await mcp_client.call(
            mcp_tools.target_of(tool, settings),
            action.name,
            {"sql": sql_text, "reason": "exam check"},
            settings,
            caller=caller,
            timeout_s=action.timeout_s,
        )
        text = result.text or ""
        refused = next((p for p in SQL_ERROR_PREFIXES if text.startswith(p)), None)
        failed = result.is_error or refused is not None
        async with db.session_scope() as audit_session:
            await write_event(
                audit_session,
                AuditEntry(
                    action="eval_sql_check",
                    resource_type="run",
                    outcome="failure" if failed else "success",
                    actor_type="system",
                    actor_id="eval",
                    project_id=str(run.project_id),
                    resource_id=str(run.id),
                    before=None,
                    after={"tool_key": tool_key, "is_error": failed},
                    request_id="eval",
                    ip=None,
                ),
            )
            await audit_session.commit()
        if result.is_error:
            return None, "no_sql_result:tool_error"
        if refused is not None:
            return None, f"no_sql_result:{refused.rstrip(':')}"
        rows = parse_csv_rows(text)
        if rows is None:
            return None, "sql_result_truncated"
        return rows, None

    return reread


def _embed(settings):
    from ffcore.knowledge.ingest import HttpEmbedClient

    client = HttpEmbedClient(settings)

    async def embed(texts):
        return (await client.embed(texts)).dense

    return embed
