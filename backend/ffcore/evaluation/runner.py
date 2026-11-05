"""Exam start and the per-tick advance (09; design in evaluation/engine.py)."""

import asyncio
import csv
import io
import logging
import time
import uuid
from collections import Counter
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from ffcore.core.audit import AuditEntry, write_event
from ffcore.core.config import Settings
from ffcore.core.errors import ApiError
from ffcore.evaluation import scorers
from ffcore.evaluation.diagnosis import DIAGNOSIS_ORDER
from ffcore.evaluation.engine import (
    MAX_ATTEMPTS,
    TERMINAL,
    ItemFacts,
    ItemResult,
    _scorer_cfg,
    deterministic_scores,
    item_result,
    langfuse_scores,
    load_facts,
    now_utc,
    summarize,
)
from ffcore.evaluation.langfuse_api import LangfuseApi, LangfuseApiError
from ffcore.evaluation.scorers import Score
from ffcore.models.agents import Agent, AgentVersion
from ffcore.models.approvals import Approval
from ffcore.models.eval import EvalRun, EvalSuite
from ffcore.models.runs import Run
from ffcore.runtime.contracts import RunStatus
from ffcore.runtime.definition import parse_definition
from ffcore.runtime.queue import RunQueue
from ffcore.services.runs_start import start_run

log = logging.getLogger("ffcore.evaluation")

JudgeFn = Callable[[Run, dict, ItemFacts, dict], Awaitable[tuple[Score, str]]]
# The re-read of the agent's last executed run_sql: (rows, None) or (None, code).
SqlFn = Callable[[Run, str, str], Awaitable[tuple[list[list] | None, str | None]]]
EmbedFn = Callable[[list[str]], Awaitable[list[list[float]]]]
# Writes the end of a run the advancer cancelled (the `error` event, like POST …/cancel).
CloseFn = Callable[[AsyncSession, Run, str], Awaitable[None]]

ACTIVE = ("queued", "running")
# Who closes an approval whose run the exam cancelled (approve_tools=false).
EVAL_RESOLVER = "system:eval"


@dataclass(frozen=True)
class Starter:
    user_id: uuid.UUID
    actor_type: str
    actor_id: str
    request_id: str
    ip: str | None


def _always() -> bool:
    return True


@dataclass
class Budget:
    """What one tick may still spend on an exam (r1 MAJOR-2, r2 MAJOR-r2-2): judge calls
    (EVAL_JUDGE_CALLS_PER_TICK), time until `deadline` (monotonic; a model call is planned at
    `call_s` seconds), judge calls only while the background window `is_open`. `started`
    counts the items this tick began, `committed` the ones it saved: a tick that saved one made
    progress."""

    judge_calls: int
    deadline: float | None = None
    call_s: float = 0.0
    is_open: Callable[[], bool] = field(default=_always)
    started: int = 0
    committed: int = 0

    def judge_open(self) -> bool:
        return self.is_open()

    def may_judge(self, calls: int) -> bool:
        """Whether the next item (with `calls` judge calls, 0 without a judge) starts now.
        Judge calls only while the window is open. The tick's first item always starts (cut at
        `time_left`), so a slow judge still progresses one item per tick. A later item only
        when its calls fit in the judge calls left (a strict limit, r3 MINOR-r3-1) and, at
        `call_s` each, before the deadline. So a tick makes at most EVAL_JUDGE_CALLS_PER_TICK
        judge calls, or its first item's calls when that is more."""
        if calls and not self.is_open():
            return False
        if self.started == 0:
            return True
        if calls > self.judge_calls:
            return False
        return self.deadline is None or (
            time.monotonic() + self.call_s * max(calls, 1) <= self.deadline
        )

    def time_left(self) -> float | None:
        if self.deadline is None:
            return None
        return max(self.deadline - time.monotonic(), 0.0)


def run_name(suite: EvalSuite, version: AgentVersion) -> str:
    return f"{suite.key}-v{version.version}-{uuid.uuid4().hex[:8]}"


def snapshot(suite: EvalSuite, starter: Starter) -> dict[str, Any]:
    """The suite as the exam starts (r1 MAJOR-4) and who started it (the advancer starts the
    item runs for this user and audits them with this request)."""
    return {
        "scorers": list(suite.scorers),
        "pass_threshold": suite.pass_threshold,
        "repeat": suite.repeat,
        "approve_tools": suite.approve_tools,
        "dataset": suite.langfuse_dataset_name,
        "starter": {
            "actor_type": starter.actor_type,
            "actor_id": starter.actor_id,
            "request_id": starter.request_id,
            "ip": starter.ip,
        },
    }


def _check_items(items: list[dict], version: AgentVersion) -> None:
    """Every item is checked before anything starts: a broken item halfway would leave runs
    already billed for an exam that cannot finish (r1 MINOR-2)."""
    known = {v.key for v in parse_definition(version.definition).variables}
    bad: list[str] = []
    for i in items:
        given = i.get("input") or {}
        variables = given.get("variables") or {}
        if (
            not isinstance(given.get("message"), str)
            or not isinstance(variables, dict)
            or not all(isinstance(v, str) for v in variables.values())
            or set(variables) - known
        ):
            bad.append(i["id"])
    if bad:
        raise ApiError(
            422,
            "invalid_request_error",
            "item_input_invalid",
            f"Items without a text input.message or with unknown/non-text variables: {bad[:5]}",
        )


async def start_eval(
    session: AsyncSession,
    settings: Settings,
    *,
    suite: EvalSuite,
    version: AgentVersion,
    starter: Starter,
    api: LangfuseApi,
) -> EvalRun:
    """Check the dataset and write the exam `queued` with its plan; the advancer starts the
    item runs (in the background, resumable: a start that dies halfway goes on next tick)."""
    items = [
        i
        for i in await api.items(suite.langfuse_dataset_name)
        if i.get("status") in (None, "ACTIVE")
    ]
    if not items:
        raise ApiError(
            409, "conflict_error", "dataset_empty", "The suite's dataset has no active items."
        )
    total = len(items) * suite.repeat
    if total > settings.eval_max_item_runs:
        raise ApiError(
            422,
            "invalid_request_error",
            "eval_too_many_runs",
            f"{len(items)} items x repeat {suite.repeat} = {total} runs; "
            f"EVAL_MAX_ITEM_RUNS is {settings.eval_max_item_runs}.",
        )
    _check_items(items, version)
    ev = EvalRun(
        project_id=suite.project_id,
        suite_id=suite.id,
        agent_version_id=version.id,
        user_id=starter.user_id,
        langfuse_run_name=run_name(suite, version),
        status="queued",
        started_at=now_utc(),
        created_by=starter.actor_id,
        config=snapshot(suite, starter),
        item_runs={i["id"]: {"item": i, "runs": [], "scored": False, "attempts": 0} for i in items},
    )
    session.add(ev)
    await session.flush()
    await write_event(
        session,
        AuditEntry(
            action="start_eval_run",
            resource_type="eval_run",
            outcome="success",
            actor_type=starter.actor_type,
            actor_id=starter.actor_id,
            project_id=str(suite.project_id),
            resource_id=str(ev.id),
            before=None,
            after={
                "suite_id": str(suite.id),
                "agent_version_id": str(version.id),
                "items": len(items),
                "repeat": suite.repeat,
            },
            request_id=starter.request_id,
            ip=starter.ip,
        ),
    )
    await session.commit()
    return ev


def _save(ev: EvalRun, plan: dict) -> None:
    ev.item_runs = {k: dict(v) for k, v in plan.items()}
    flag_modified(ev, "item_runs")


async def start_items(
    session: AsyncSession,
    settings: Settings,
    ev: EvalRun,
    *,
    queue: RunQueue,
    queued_event,
) -> None:
    """A queued exam: start the item runs still missing, one commit per run, then `running`.
    The exam stays queued until every item run exists, so the advancer never summarizes half a
    plan; a tick that fails here is counted like any tick failure (worker_tick)."""
    version = await session.get(AgentVersion, ev.agent_version_id)
    agent = await session.get(Agent, version.agent_id)
    who = ev.config["starter"]
    repeat = int(ev.config["repeat"])
    plan = {k: dict(v) for k, v in (ev.item_runs or {}).items()}
    for item_id, entry in plan.items():
        while len(entry["runs"]) < repeat:
            item = entry["item"]

            async def audit(session, run, version, _item=item_id):
                await write_event(
                    session,
                    AuditEntry(
                        action="start_run",
                        resource_type="run",
                        outcome="success",
                        actor_type=who["actor_type"],
                        actor_id=who["actor_id"],
                        project_id=str(ev.project_id),
                        resource_id=str(run.id),
                        before=None,
                        after={
                            "agent_id": str(agent.id),
                            "version": version.version,
                            "channel": "test",
                            "eval_run_id": str(ev.id),
                            "item_id": _item,
                        },
                        request_id=who["request_id"],
                        ip=who["ip"],
                    ),
                )

            # start_run commits the run and enqueues it; the plan row follows at once, so a
            # failure in between leaves at most one run outside the plan (it runs, unscored).
            run = await start_run(
                session,
                settings,
                queue,
                project_id=ev.project_id,
                agent=agent,
                version=version,
                user_id=ev.user_id,
                created_by=who["actor_id"],
                input=item["input"]["message"],
                variables=dict(item["input"].get("variables") or {}),
                channel="test",
                conversation_id=None,
                audit=audit,
                queued_event=queued_event,
            )
            entry["runs"] = [*entry["runs"], str(run.id)]
            _save(ev, plan)
            await session.commit()
    ev.status = "running"
    await session.commit()


async def cancel_waiting(session: AsyncSession, run: Run, code: str, *, close: CloseFn) -> bool:
    """Cancel an item run that waits for a user or an approval (r1 MINOR-5): only if it still
    waits (a person who decided first wins), its pending approval closed, `cancel_run` audited,
    the run's `error` event written. Committed together by the event write. False: the run
    moved on since it was read; nothing is changed."""
    now = datetime.now(UTC)
    # Lock order as approvals.decide (approval row, then run; r2 MINOR-r2-3): a person deciding
    # at the same moment waits for this cancel, or this cancel finds the run moved on.
    await session.execute(
        select(Approval.id)
        .where(Approval.run_id == run.id, Approval.status == "pending")
        .with_for_update()
    )
    changed = await session.scalar(
        update(Run)
        .where(Run.id == run.id, Run.status == run.status)
        .values(status=RunStatus.cancelled, error_code=code, ended_at=now, cancel_requested_at=now)
        .returning(Run.id)
    )
    if changed is None:
        return False
    await session.execute(
        update(Approval)
        .where(Approval.run_id == run.id, Approval.status == "pending")
        .values(status="expired", resolved_at=now, resolved_by=EVAL_RESOLVER, updated_at=now)
    )
    await write_event(
        session,
        AuditEntry(
            action="cancel_run",
            resource_type="run",
            outcome="success",
            actor_type="system",
            actor_id="eval",
            project_id=str(run.project_id),
            resource_id=str(run.id),
            before={"status": str(run.status)},
            after={"status": "cancelled", "error_code": code},
            request_id="eval",
            ip=None,
        ),
    )
    await close(session, run, code)
    await session.commit()
    return True


def parse_csv_rows(text: str) -> list[list] | None:
    """mcp-sql run_sql text (header, rows, `rows: N`); None when the result was cut."""
    if "[truncated:" in text:
        return None
    lines = [ln for ln in text.splitlines() if not ln.startswith("rows: ")]
    reader = list(csv.reader(io.StringIO("\n".join(lines))))
    return reader[1:] if reader else []


async def _cancel_all(session: AsyncSession, runs: dict[str, Run], close: CloseFn) -> None:
    for r in runs.values():
        if r.status in TERMINAL:
            continue
        if r.status == RunStatus.running:
            # Same rule as POST /runs/{id}/cancel: it stops at its next step boundary.
            r.cancel_requested_at = now_utc()
            await session.commit()
        else:
            await cancel_waiting(session, r, "cancelled", close=close)


async def advance_eval(
    session: AsyncSession,
    settings: Settings,
    ev: EvalRun,
    *,
    api: LangfuseApi,
    judge: JudgeFn | None,
    sql: SqlFn | None,
    embed: EmbedFn | None,
    close: CloseFn,
    budget: Budget,
) -> None:
    """One tick of a running exam, under its lock (worker_tick). Reads only `ev.config`.
    Every scored item is committed on its own (r1 MAJOR-3): a later error in the tick never
    takes back a score, and a not_run note comes from the run's own end code."""
    cfg = ev.config
    plan = {k: dict(v) for k, v in (ev.item_runs or {}).items()}
    run_ids = [uuid.UUID(r) for v in plan.values() for r in v["runs"]]
    runs = {
        str(r.id): r for r in (await session.scalars(select(Run).where(Run.id.in_(run_ids)))).all()
    }

    if ev.cancel_requested_at is not None:
        await _cancel_all(session, runs, close)
        ev.status, ev.ended_at = "cancelled", now_utc()
        await session.commit()
        return

    for r in list(runs.values()):
        if r.status == RunStatus.waiting_user:
            await cancel_waiting(session, r, "eval_waiting_user", close=close)
        elif r.status == RunStatus.waiting_approval and not cfg["approve_tools"]:
            await cancel_waiting(session, r, "eval_approval_required", close=close)
    runs = {
        str(r.id): r
        for r in (
            await session.scalars(
                select(Run).where(Run.id.in_(run_ids)).execution_options(populate_existing=True)
            )
        ).all()
    }

    scorer_cfg = _scorer_cfg(cfg["scorers"])
    judged = "llm_judge" in scorer_cfg
    for item_id, entry in plan.items():
        if entry["scored"] or any(runs[r].status not in TERMINAL for r in entry["runs"]):
            continue
        calls = len(entry["runs"]) if judged else 0
        if not budget.may_judge(calls):
            # Out of judge calls or time, or the background window is closed: the exam stays
            # running and waits for a later tick (r2 MAJOR-r2-2); not a failure.
            break
        budget.started += 1
        timer = asyncio.timeout(budget.time_left())
        try:
            async with timer:
                entry["result"] = await _score_item(
                    session,
                    ev,
                    entry,
                    runs,
                    scorer_cfg,
                    api=api,
                    judge=judge,
                    sql=sql,
                    embed=embed,
                )
            entry["scored"] = True
        except TimeoutError:
            if not timer.expired():
                raise
            # r3 MAJOR-r3-1 (A): consecutive cuts are counted per item; at MAX_ATTEMPTS the
            # item ends `error(judge_out_of_time)` and the exam goes on (never running forever).
            entry["timeouts"] = entry.get("timeouts", 0) + 1
            log.info(
                "eval_tick_out_of_time eval_run=%s item=%s cuts=%s",
                ev.id,
                item_id,
                entry["timeouts"],
            )
            if entry["timeouts"] >= MAX_ATTEMPTS:
                entry["result"] = _out_of_time(entry)
                entry["scored"] = True
                budget.committed += 1
            _save(ev, plan)
            await session.commit()
            break  # otherwise scored again next tick (score ids are stable)
        except LangfuseApiError as exc:
            entry["attempts"] = entry.get("attempts", 0) + 1
            entry["last_error"] = exc.code
            log.warning(
                "eval_item_langfuse_failed eval_run=%s item=%s code=%s", ev.id, item_id, exc.code
            )
            if entry["attempts"] >= MAX_ATTEMPTS:
                _save(ev, plan)
                ev.status, ev.error_code, ev.ended_at = "failed", exc.code, now_utc()
                await session.commit()
                return
        budget.judge_calls -= calls
        _save(ev, plan)
        await session.commit()
        if entry["scored"]:
            budget.committed += 1
    if all(e["scored"] for e in plan.values()):
        ev.summary = _summary(plan, runs, cfg)
        costs = [float(r.cost_usd) for r in runs.values() if r.cost_usd is not None]
        ev.cost_usd = sum(costs) if costs else None
        ev.status, ev.ended_at = "completed", now_utc()
        await session.commit()


async def _score_item(session, ev, entry, runs, cfg, *, api, judge, sql, embed) -> dict:
    item = entry["item"]
    per_run = []
    for i, rid in enumerate(entry["runs"]):
        run = runs[rid]
        facts = await load_facts(session, run)
        sql_rows, sql_missing = None, None
        if "sql_result" in cfg and facts.status == "completed":
            if facts.sql and sql is not None:
                sql_rows, sql_missing = await sql(run, *facts.sql[-1])
            elif facts.sql_rejected:
                sql_missing = "approval_rejected"
            elif sql is None:
                sql_missing = "sql_unavailable"
            else:
                sql_missing = "no_executed_sql"
        scores = (
            deterministic_scores(item, facts, cfg, sql_rows, sql_missing)
            if facts.status == "completed"
            else []
        )
        reason = ""
        answerable = (item.get("metadata") or {}).get("answerable", True)
        if facts.status == "completed" and answerable:
            expected = (item.get("expectedOutput") or {}).get("answer")
            if "semantic" in cfg:
                scores.append(await _semantic(facts.answer, expected, cfg["semantic"], embed))
            if "llm_judge" in cfg:
                if not _judge_expectation(item):
                    scores.append(Score("llm_judge", None, None, "no_expectation", "not_run"))
                elif judge is None:
                    scores.append(Score("llm_judge", None, None, "judge_unavailable", "error"))
                else:
                    s, reason = await judge(run, item, facts, cfg["llm_judge"])
                    scores.append(s)
        res = item_result(item, facts, scores, "")
        if res.passed is None:  # not run: nothing to write to Langfuse
            per_run.append({"run_id": rid, **_dump(res)})
            continue
        if facts.trace_id is None:
            raise LangfuseApiError("trace_missing", f"run {rid} has no Langfuse trace")
        if i == 0:
            await api.link_run_item(
                ev.langfuse_run_name,
                item["id"],
                facts.trace_id,
                description=f"agent_version {ev.agent_version_id}",
                metadata={
                    "eval_run_id": str(ev.id),
                    "agent_version_id": str(ev.agent_version_id),
                    "run_id": rid,
                },
            )
        for row in langfuse_scores(res, rid, facts.trace_id, reason):
            await api.upsert_score(
                row["score_id"],
                name=row["name"],
                value=row["value"],
                data_type=row["data_type"],
                trace_id=facts.trace_id,
                comment=row["comment"],
                metadata=row["metadata"],
            )
        per_run.append({"run_id": rid, "duration_ms": facts.duration_ms, **_dump(res)})
    return {"runs": per_run}


def _out_of_time(entry: dict) -> dict:
    """The result of an item whose scoring never fitted in a tick: an error per run."""
    score = {
        "name": "llm_judge",
        "value": None,
        "passed": None,
        "status": "error",
        "comment": "judge_out_of_time",
    }
    return {
        "runs": [
            {
                "run_id": rid,
                "outcome": None,
                "passed": False,
                "note": "judge_out_of_time",
                "scores": [dict(score)],
            }  # fmt: skip
            for rid in entry["runs"]
        ]
    }


def _judge_expectation(item: dict) -> bool:
    """The judge compares with an expected answer (or the texts it must contain); an item with
    neither has nothing to judge against (r1 MINOR-3)."""
    expected = item.get("expectedOutput") or {}
    return bool(expected.get("answer") or expected.get("must_contain"))


async def _semantic(answer: str, expected: str | None, c: dict, embed: EmbedFn | None) -> Score:
    if not expected:
        return Score("semantic", None, None, "no_expectation", "not_run")
    if embed is None:
        return Score("semantic", None, None, "embed_unavailable", "error")
    a, b = await embed([answer, expected])
    return scorers.semantic(a, b, threshold=float(c.get("threshold", 0.8)))


def _dump(res) -> dict:
    return {
        "outcome": res.outcome,
        "passed": res.passed,
        "note": res.note,
        "scores": [
            {
                "name": s.name,
                "value": s.value,
                "passed": s.passed,
                "status": s.status,
                "comment": s.comment,
            }
            for s in res.scores
        ],
    }


def _load(item: dict, d: dict) -> ItemResult:
    meta = item.get("metadata") or {}
    return ItemResult(
        item_id=item["id"],
        style=meta.get("style", "-"),
        answerable=bool(meta.get("answerable", True)),
        outcome=d["outcome"],
        passed=d["passed"],
        note=d.get("note", ""),
        scores=[
            Score(s["name"], s["value"], s["passed"], s.get("comment", ""), s["status"])
            for s in d["scores"]
        ],
    )


def combine(item: dict, per_run: list[dict]) -> ItemResult:
    """repeat > 1: scores are averaged per scorer over the runs that ran; a scorer error in any
    run stays an error; the item passes when most decided runs pass; not-run runs are left
    out (all not run: the item is not run; some: counted apart in the summary, r2 MINOR-r2-4);
    the outcome is the most frequent one (ties: the earlier stage, diagnosis order)."""
    loaded = [_load(item, d) for d in per_run]
    if len(loaded) == 1:
        return loaded[0]
    ran = [r for r in loaded if r.passed is not None]
    if not ran:
        return loaded[0]
    names = list(dict.fromkeys(s.name for r in ran for s in r.scores))
    scores = []
    for n in names:
        mine = [s for r in ran for s in r.scores if s.name == n]
        if any(s.status == "error" for s in mine):
            errs = sorted({s.comment for s in mine if s.status == "error"})
            scores.append(Score(n, None, None, ";".join(errs) or "error", "error"))
            continue
        vals = [s.value for s in mine if s.value is not None]
        oks = [s.passed for s in mine if s.passed is not None]
        if not oks:
            scores.append(Score(n, None, None, mine[0].comment if mine else "", "not_run"))
            continue
        scores.append(
            Score(
                n,
                sum(vals) / len(vals) if vals else None,
                sum(oks) * 2 > len(oks),
                f"repeat={len(loaded)}",
            )
        )
    outs = Counter(r.outcome for r in ran if r.outcome)
    outcome = None
    if outs:
        top = max(outs.values())
        outcome = next(o for o in DIAGNOSIS_ORDER if outs.get(o) == top)
    passed = sum(1 for r in ran if r.passed) * 2 > len(ran)
    if any(s.status == "error" for s in scores):
        passed = False
    first = ran[0]
    note = first.note
    left_out = [r for r in loaded if r.passed is None]
    if left_out:
        note = note or f"not_run={len(left_out)}/{len(loaded)}"
    return ItemResult(
        item_id=first.item_id,
        style=first.style,
        answerable=first.answerable,
        outcome=outcome,
        passed=passed,
        scores=scores,
        note=note,
        repeats_not_run=(left_out[0].note or "not_run") if left_out else "",
    )


def _summary(plan: dict, runs: dict, cfg: dict) -> dict:
    results, firsts = [], []
    for entry in plan.values():
        per_run = entry["result"]["runs"]
        results.append(combine(entry["item"], per_run))
        for d in per_run:
            if d.get("duration_ms") is not None:
                firsts.append((runs[d["run_id"]].started_at, d["duration_ms"]))
    firsts.sort(key=lambda t: t[0])
    warmup = firsts[0][1] if firsts else None
    latencies = [ms for _, ms in firsts[1:]]
    return summarize(
        results,
        pass_threshold=float(cfg["pass_threshold"]),
        warmup_ms=warmup,
        latencies_ms=latencies,
    )


async def is_exam_run(session: AsyncSession, run_id: uuid.UUID) -> bool:
    """Whether the run is an item run of an active exam (its resume stays in the background
    queue, r1 MINOR-6). Active exams are few; their plans are searched in Postgres."""
    hit = await session.scalar(
        select(EvalRun.id)
        .where(
            EvalRun.status.in_(ACTIVE),
            text(
                "jsonb_path_exists(eval_runs.item_runs, '$.*.runs[*] ? (@ == $id)', "
                "jsonb_build_object('id', CAST(:rid AS text)))"
            ).bindparams(rid=str(run_id)),
        )
        .limit(1)
    )
    return hit is not None


async def active_runs(session: AsyncSession) -> list[EvalRun]:
    """Queued and running exams, the oldest progress first (r3 MINOR-r3-2): a tick's shared
    deadline goes to the exam that waited longest."""
    stmt = (
        select(EvalRun).where(EvalRun.status.in_(ACTIVE)).order_by(EvalRun.updated_at, EvalRun.id)
    )
    return list((await session.scalars(stmt)).all())


__all__ = [
    "ACTIVE",
    "Budget",
    "Starter",
    "active_runs",
    "advance_eval",
    "cancel_waiting",
    "is_exam_run",
    "parse_csv_rows",
    "start_eval",
    "start_items",
]
