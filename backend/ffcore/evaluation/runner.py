"""Exam start and the per-tick advance (09; design in evaluation/engine.py)."""

import csv
import io
import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ffcore.core.audit import AuditEntry, write_event
from ffcore.core.config import Settings
from ffcore.core.errors import ApiError
from ffcore.evaluation import scorers
from ffcore.evaluation.engine import (
    MAX_ATTEMPTS,
    TERMINAL,
    ItemFacts,
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
from ffcore.models.eval import EvalRun, EvalSuite
from ffcore.models.runs import Run
from ffcore.runtime import events as run_events
from ffcore.runtime.contracts import RunStatus
from ffcore.runtime.queue import RunQueue
from ffcore.services.runs_start import start_run

log = logging.getLogger("ffcore.evaluation")

JudgeFn = Callable[[Run, dict, ItemFacts, dict], Awaitable[tuple[Score, str]]]
SqlFn = Callable[[Run, str, str], Awaitable[list[list] | None]]
EmbedFn = Callable[[list[str]], Awaitable[list[list[float]]]]


@dataclass(frozen=True)
class Starter:
    user_id: uuid.UUID
    actor_type: str
    actor_id: str
    request_id: str
    ip: str | None


def run_name(suite: EvalSuite, version: AgentVersion) -> str:
    return f"{suite.key}-v{version.version}-{uuid.uuid4().hex[:8]}"


async def start_eval(
    session: AsyncSession,
    settings: Settings,
    *,
    suite: EvalSuite,
    agent: Agent,
    version: AgentVersion,
    starter: Starter,
    api: LangfuseApi,
    queue: RunQueue,
    queued_event,
) -> EvalRun:
    items = [
        i
        for i in await api.items(suite.langfuse_dataset_name)
        if i.get("status") in (None, "ACTIVE")
    ]
    if not items:
        raise ApiError(
            409, "conflict_error", "dataset_empty", "The suite's dataset has no active items."
        )
    bad = [i["id"] for i in items if not isinstance((i.get("input") or {}).get("message"), str)]
    if bad:
        raise ApiError(
            422,
            "invalid_request_error",
            "item_input_invalid",
            f"Items without input.message: {bad[:5]}",
        )
    ev = EvalRun(
        project_id=suite.project_id,
        suite_id=suite.id,
        agent_version_id=version.id,
        user_id=starter.user_id,
        langfuse_run_name=run_name(suite, version),
        status="running",
        started_at=now_utc(),
        created_by=starter.actor_id,
        item_runs={},
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
    plan: dict[str, Any] = {}
    for item in items:
        runs: list[str] = []
        for _ in range(suite.repeat):

            async def audit(session, run, version, _item=item["id"]):
                await write_event(
                    session,
                    AuditEntry(
                        action="start_run",
                        resource_type="run",
                        outcome="success",
                        actor_type=starter.actor_type,
                        actor_id=starter.actor_id,
                        project_id=str(suite.project_id),
                        resource_id=str(run.id),
                        before=None,
                        after={
                            "agent_id": str(agent.id),
                            "version": version.version,
                            "channel": "test",
                            "eval_run_id": str(ev.id),
                            "item_id": _item,
                        },
                        request_id=starter.request_id,
                        ip=starter.ip,
                    ),
                )

            run = await start_run(
                session,
                settings,
                queue,
                project_id=suite.project_id,
                agent=agent,
                version=version,
                user_id=starter.user_id,
                created_by=starter.actor_id,
                input=item["input"]["message"],
                variables=dict(item["input"].get("variables") or {}),
                channel="test",
                conversation_id=None,
                audit=audit,
                queued_event=queued_event,
            )
            runs.append(str(run.id))
        plan[item["id"]] = {"item": item, "runs": runs, "scored": False, "attempts": 0}
        ev.item_runs = dict(plan)
        await session.commit()
    return ev


async def _cancel(session: AsyncSession, settings: Settings, run: Run, reason: str) -> None:
    """Same rule as POST /runs/{id}/cancel: a running run stops at its next step boundary, a
    queued or waiting one is cancelled at once."""
    now = now_utc()
    if run.status == RunStatus.running:
        run.cancel_requested_at = now
    else:
        run.status, run.error_code, run.ended_at = RunStatus.cancelled, reason, now
        run.cancel_requested_at = now


def parse_csv_rows(text: str) -> list[list] | None:
    """mcp-sql run_sql text (header, rows, `rows: N`); None when the result was cut."""
    if "[truncated:" in text:
        return None
    lines = [ln for ln in text.splitlines() if not ln.startswith("rows: ")]
    reader = list(csv.reader(io.StringIO("\n".join(lines))))
    return reader[1:] if reader else []


async def advance_eval(
    session: AsyncSession,
    settings: Settings,
    ev: EvalRun,
    *,
    api: LangfuseApi,
    redis,
    judge: JudgeFn | None,
    sql: SqlFn | None,
    embed: EmbedFn | None,
) -> None:
    suite = await session.get(EvalSuite, ev.suite_id)
    plan = {k: dict(v) for k, v in (ev.item_runs or {}).items()}
    run_ids = [uuid.UUID(r) for v in plan.values() for r in v["runs"]]
    runs = {
        str(r.id): r for r in (await session.scalars(select(Run).where(Run.id.in_(run_ids)))).all()
    }

    if ev.cancel_requested_at is not None:
        for r in runs.values():
            if r.status not in TERMINAL:
                await _cancel(session, settings, r, "cancelled")
        ev.status, ev.ended_at = "cancelled", now_utc()
        await session.commit()
        return

    for r in runs.values():
        if r.status in TERMINAL:
            continue
        # The engine follows its runs (06a abandons a run nobody listens to).
        await run_events.mark_listening(redis, r.id, settings.run_abandon_grace_s)
        if r.status == RunStatus.waiting_user:
            await _cancel(session, settings, r, "eval_waiting_user")
            _note(plan, str(r.id), "waiting_user")
        elif r.status == RunStatus.waiting_approval and not suite.approve_tools:
            await _cancel(session, settings, r, "eval_approval_required")
            _note(plan, str(r.id), "approval_required")
    await session.commit()

    cfg = _scorer_cfg(suite.scorers)
    for item_id, entry in plan.items():
        if entry["scored"] or any(runs[r].status not in TERMINAL for r in entry["runs"]):
            continue
        try:
            entry["result"] = await _score_item(
                session,
                settings,
                ev,
                suite,
                entry,
                runs,
                cfg,
                api=api,
                judge=judge,
                sql=sql,
                embed=embed,
            )
            entry["scored"] = True
        except LangfuseApiError as exc:
            entry["attempts"] = entry.get("attempts", 0) + 1
            entry["last_error"] = exc.code
            log.warning(
                "eval_item_langfuse_failed eval_run=%s item=%s code=%s", ev.id, item_id, exc.code
            )
            if entry["attempts"] >= MAX_ATTEMPTS:
                ev.item_runs = plan
                ev.status, ev.error_code, ev.ended_at = "failed", exc.code, now_utc()
                await session.commit()
                return
    ev.item_runs = plan
    if all(e["scored"] for e in plan.values()):
        ev.summary = _summary(plan, runs, suite)
        costs = [float(r.cost_usd) for r in runs.values() if r.cost_usd is not None]
        ev.cost_usd = sum(costs) if costs else None
        ev.status, ev.ended_at = "completed", now_utc()
    await session.commit()


def _note(plan: dict, run_id: str, note: str) -> None:
    for entry in plan.values():
        if run_id in entry["runs"]:
            entry["note"] = note


async def _score_item(
    session, settings, ev, suite, entry, runs, cfg, *, api, judge, sql, embed
) -> dict:
    item = entry["item"]
    per_run = []
    for i, rid in enumerate(entry["runs"]):
        run = runs[rid]
        if entry.get("note"):
            res = item_result(item, None, [], entry["note"])
            per_run.append({"run_id": rid, **_dump(res)})
            continue
        facts = await load_facts(session, run)
        sql_rows = None
        if "sql_result" in cfg and facts.status == "completed" and facts.sql and sql is not None:
            sql_rows = await sql(run, *facts.sql[-1])
        scores = (
            deterministic_scores(item, facts, cfg, sql_rows) if facts.status == "completed" else []
        )
        reason = ""
        answerable = (item.get("metadata") or {}).get("answerable", True)
        if facts.status == "completed" and answerable:
            expected = (item.get("expectedOutput") or {}).get("answer")
            if "semantic" in cfg:
                scores.append(await _semantic(facts.answer, expected, cfg["semantic"], embed))
            if "llm_judge" in cfg:
                if judge is None:
                    scores.append(Score("llm_judge", None, None, "judge_unavailable", "error"))
                else:
                    s, reason = await judge(run, item, facts, cfg["llm_judge"])
                    scores.append(s)
        res = item_result(item, facts, scores, "")
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


def _load(item: dict, d: dict):
    from ffcore.evaluation.engine import ItemResult

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


def combine(item: dict, per_run: list[dict]):
    """repeat > 1: scores are averaged per scorer; the item passes when most runs pass; the
    outcome is the most frequent one (ties: the earlier stage)."""
    from collections import Counter

    from ffcore.evaluation.diagnosis import OUTCOMES

    loaded = [_load(item, d) for d in per_run]
    if len(loaded) == 1:
        return loaded[0]
    first = loaded[0]
    names = [s.name for s in first.scores]
    scores = []
    for n in names:
        vals = [s.value for r in loaded for s in r.scores if s.name == n and s.value is not None]
        oks = [s.passed for r in loaded for s in r.scores if s.name == n and s.passed is not None]
        scores.append(
            Score(
                n,
                sum(vals) / len(vals) if vals else None,
                (sum(oks) * 2 > len(oks)) if oks else None,
                f"repeat={len(loaded)}",
            )
        )
    outs = Counter(r.outcome for r in loaded if r.outcome)
    outcome = None
    if outs:
        top = max(outs.values())
        outcome = next(o for o in OUTCOMES if outs.get(o) == top)
    decided = [r.passed for r in loaded if r.passed is not None]
    passed = (sum(decided) * 2 > len(decided)) if decided else None
    first.scores, first.outcome, first.passed = scores, outcome, passed
    return first


def _summary(plan: dict, runs: dict, suite: EvalSuite) -> dict:
    results, latencies, firsts = [], [], []
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
        results, pass_threshold=suite.pass_threshold, warmup_ms=warmup, latencies_ms=latencies
    )


async def active_runs(session: AsyncSession) -> list[EvalRun]:
    return list((await session.scalars(select(EvalRun).where(EvalRun.status == "running"))).all())


__all__ = ["Starter", "active_runs", "advance_eval", "parse_csv_rows", "start_eval"]
