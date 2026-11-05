"""Exam engine (09): start an exam, advance it, summarize it.

Start (`POST …/eval-suites/{id}/run`): every ACTIVE item of the suite's Langfuse dataset is
checked (input, variables, items x repeat <= EVAL_MAX_ITEM_RUNS) and the exam is written
`queued` with its plan and a snapshot of the suite (`eval_runs.config`: scorers, threshold,
repeat, approve_tools). The advancer then starts `repeat` ordinary `channel=test` runs per
item (services/runs_start) on `llm-background` (C10), for the user who started the exam, and
turns the exam `running`; a start that dies halfway goes on at the next tick.

Advance (`advance_eval_runs`, arq cron on the background worker, K-09-0007 S4, 09-1 r1): one
tick per active exam under a Redis lock, reading only the snapshot. Item runs are followed by
the worker's own listener task (worker_tick.listen_loop), so a long tick never abandons them.
Runs that wait for a user answer are cancelled; runs that wait for an approval either stay in
the 07 queue for a person (`approve_tools=true`) or are cancelled (`approval_required`), never
approved by the exam (K-09-0008); the item's not_run note comes from the run's end code. A
finished item is diagnosed and scored (at most EVAL_JUDGE_CALLS_PER_TICK judge calls a tick);
its run's own Langfuse trace is linked into the dataset run and the scores written there
(upsert by id), and the item is committed on its own. When every item is scored the summary is
written and the exam is `completed`.

Langfuse failures are counted per item; after MAX_ATTEMPTS the exam ends `failed` with the
error code. A tick that keeps failing (MAX_ATTEMPTS in a row, a timeout included) ends the exam
`failed(advance_failed:<type>)` (fail-loud; no local copy of what could not be written).
"""

import logging
import statistics
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ffcore.evaluation import scorers
from ffcore.evaluation.diagnosis import OUTCOMES, Candidate, RunFacts, diagnose
from ffcore.evaluation.langfuse_api import score_id
from ffcore.evaluation.scorers import Score
from ffcore.models.eval import EvalRun, EvalSuite
from ffcore.models.knowledge import Document, KbQuery
from ffcore.models.runs import Run, RunEvent

log = logging.getLogger("ffcore.evaluation")

TERMINAL = {"completed", "failed", "cancelled", "abandoned"}
# Run end codes that mean "the exam could not ask", not "the agent failed" (K-09-0008, 09-1 r1
# MAJOR-3): an approval nobody gave in time, a run the advancer cancelled because it waited for
# an approval (approve_tools=false) or for a user answer. The note comes from the run's own end
# code, so it survives a tick that died after the cancel. Counted apart (n/N), never part of the
# pass rate.
NOT_RUN_CODES = {
    "approval_expired": "approval_expired",
    "eval_approval_required": "approval_required",
    "eval_waiting_user": "waiting_user",
}
# Why an item's own check could not be made (09-1 r2): a person rejected its run_sql (MAJOR-r2-1,
# the agent never saw rows), the advancer could not read the SQL again (MINOR-r2-1), or the tool
# of an executed call was removed since (MINOR-r2-7). Item-level not_run, never a failure.
# r3 NOTE-6: the judge's egress NER was down (`ner_unavailable`): an outage, not a score.
ITEM_NOT_RUN = (*scorers.CHECK_NOT_MADE, "ner_unavailable")
MAX_ATTEMPTS = 5
WORST = 10


# --- item scoring (pure over loaded facts) -----------------------------------------------------


@dataclass
class ItemFacts:
    """What one finished item run left behind, loaded by `load_facts`."""

    run_id: str
    status: str
    error_code: str | None
    outcome_label: str | None
    answer: str
    trace_id: str | None
    duration_ms: int | None
    cost_usd: float | None
    selected: list[str] = field(default_factory=list)
    candidates: list[Candidate] = field(default_factory=list)
    # run_sql calls that ran: a successful tool_result and, when an approval was asked, an
    # approved one (09-1 r1 MAJOR-1); (tool_key, sql) in call order.
    sql: list[tuple[str, str]] = field(default_factory=list)
    # A run_sql call a person rejected: the exam could not see the agent's rows.
    sql_rejected: bool = False


@dataclass
class ItemResult:
    item_id: str
    style: str
    answerable: bool
    outcome: str | None
    passed: bool | None  # None: not_run
    scores: list[Score]
    note: str = ""
    # repeat > 1: the not-run code of repeats left out of a decided item (09-1 r2 MINOR-r2-4).
    repeats_not_run: str = ""

    def mean(self) -> float | None:
        values = [s.value for s in self.scores if s.status == "ok" and s.value is not None]
        return sum(values) / len(values) if values else None


def _scorer_cfg(suite_scorers: list[dict]) -> dict[str, dict]:
    return {c["name"]: c for c in suite_scorers}


def deterministic_scores(
    item: dict,
    facts: ItemFacts,
    cfg: dict[str, dict],
    sql_rows: list[list] | None,
    sql_missing: str | None = None,
) -> list[Score]:
    """Every configured scorer except llm_judge and semantic (they call services)."""
    expected = item.get("expectedOutput") or {}
    meta = item.get("metadata") or {}
    out: list[Score] = []
    if not meta.get("answerable", True):
        # An unanswerable item is judged by holding back only (13b `holds`); content scorers
        # have nothing to compare.
        held = facts.outcome_label != "answered"
        return [Score("holds", 1.0 if held else 0.0, held)]
    if "contains" in cfg:
        out.append(scorers.contains(facts.answer, expected.get("must_contain") or []))
    if "regex" in cfg:
        out.append(scorers.regex(facts.answer, expected.get("regex")))
    if "json_schema" in cfg:
        out.append(scorers.json_schema(facts.answer, expected.get("json")))
    if "cites_source" in cfg:
        wanted = expected.get("must_cite") or meta.get("expected_docs") or []
        out.append(scorers.cites_source(facts.selected, wanted))
    if "sql_result" in cfg:
        out.append(scorers.sql_result(expected.get("sql_result"), sql_rows, sql_missing))
    if "latency_cost" in cfg:
        c = cfg["latency_cost"]
        out.append(
            scorers.latency_cost(
                facts.duration_ms, facts.cost_usd, max_ms=c.get("max_ms"), max_usd=c.get("max_usd")
            )
        )
    return out


def item_result(item: dict, facts: ItemFacts | None, scores: list[Score], note: str) -> ItemResult:
    meta = item.get("metadata") or {}
    answerable = bool(meta.get("answerable", True))
    base = dict(item_id=item["id"], style=meta.get("style", "-"), answerable=answerable)
    if facts is None:
        return ItemResult(**base, outcome=None, passed=None, scores=[], note=note)
    outcome = diagnose(
        RunFacts(
            status=facts.status,
            outcome_label=facts.outcome_label,
            answerable=answerable,
            expected_docs=list(meta.get("expected_docs") or []),
            candidates=facts.candidates,
            selected=facts.selected,
        )
    )
    if facts.status != "completed" and facts.error_code in NOT_RUN_CODES:
        return ItemResult(
            **base, outcome=None, passed=None, scores=[], note=NOT_RUN_CODES[facts.error_code]
        )
    if facts.status != "completed":
        return ItemResult(
            **base, outcome=None, passed=False, scores=[], note=facts.error_code or facts.status
        )
    if facts.sql_rejected and not facts.sql:
        # A person rejected the agent's only run_sql: the exam could not see what the agent
        # would have got (K-09-0014, KARARLAR "09-1 r2 kararları").
        return ItemResult(
            **base, outcome=outcome, passed=None, scores=scores, note="approval_rejected"
        )
    blocked = next(
        (s.comment for s in scores if s.status == "not_run" and s.comment in ITEM_NOT_RUN), None
    )
    if blocked is not None:
        return ItemResult(**base, outcome=outcome, passed=None, scores=scores, note=blocked)
    checked = [s for s in scores if s.status != "not_run"]
    if not checked:
        # No scorer had anything to compare (suite and item do not fit): a visible failure,
        # not a not_run that would only mark the exam incomplete (09-1 r1 MINOR-3).
        return ItemResult(
            **base, outcome=outcome, passed=False, scores=scores, note=note or "nothing_scored"
        )
    if any(s.status == "error" for s in checked):
        passed = False
    else:
        passed = all(s.passed for s in checked)
    return ItemResult(**base, outcome=outcome, passed=passed, scores=scores, note=note)


def summarize(
    results: list[ItemResult],
    *,
    pass_threshold: float,
    warmup_ms: int | None,
    latencies_ms: list[int],
) -> dict[str, Any]:
    scored = [r for r in results if r.passed is not None]
    not_run = Counter(r.note or "not_run" for r in results if r.passed is None)
    # Decided items with some repeats not run count apart: the exam did not run them all either.
    not_run.update(f"partial:{r.repeats_not_run}" for r in scored if r.repeats_not_run)
    passed_items = sum(1 for r in scored if r.passed)
    pass_rate = passed_items / len(scored) if scored else 0.0
    by_scorer: dict[str, list[float]] = {}
    errors: Counter = Counter()
    for r in results:
        for s in r.scores:
            if s.status == "ok" and s.value is not None:
                by_scorer.setdefault(s.name, []).append(s.value)
            elif s.status == "error":
                errors[s.comment or "error"] += 1
        if r.passed is False and r.note and not any(s.status == "error" for s in r.scores):
            errors[r.note] += 1
    outcomes = Counter(r.outcome for r in results if r.outcome)
    styles: dict[str, dict] = {}
    for r in results:
        s = styles.setdefault(r.style, {"n": 0, "passed": 0, "outcomes": {}})
        s["n"] += 1
        s["passed"] += 1 if r.passed else 0
        if r.outcome:
            s["outcomes"][r.outcome] = s["outcomes"].get(r.outcome, 0) + 1
    worst = sorted(
        (r for r in scored),
        key=lambda r: (r.passed is True, r.mean() if r.mean() is not None else -1.0, r.item_id),
    )[:WORST]
    return {
        "n": len(results),
        "scored": len(scored),
        "not_run": dict(not_run),
        "passed_items": passed_items,
        "pass_rate": round(pass_rate, 4),
        "pass_threshold": pass_threshold,
        "passed": bool(scored) and pass_rate >= pass_threshold,
        # False when any item was not run (waiting for a user, approval required or expired):
        # the exam did not complete unattended and its pass rate covers `scored` items only.
        "complete": not not_run,
        "scores": {k: round(sum(v) / len(v), 4) for k, v in sorted(by_scorer.items())},
        "outcomes": {o: outcomes.get(o, 0) for o in OUTCOMES},
        "styles": styles,
        "worst": [
            {
                "item_id": r.item_id,
                "style": r.style,
                "outcome": r.outcome,
                "passed": r.passed,
                "mean": None if r.mean() is None else round(r.mean(), 4),
                "note": r.note,
            }
            for r in worst
        ],
        "errors": dict(errors),
        # No model-server reset before an exam (EVAL_RESET_MODEL rejected, N22): the first
        # run's time is reported apart as warm-up and left out of the latency figures.
        "warm_cache": True,
        "warmup_ms": warmup_ms,
        "latency_ms": (
            {"p50": int(statistics.median(latencies_ms)), "max": max(latencies_ms)}
            if latencies_ms
            else None
        ),
    }


# --- loading facts from the database ---------------------------------------------------------


def _stem_names(payload: dict) -> list[str]:
    return [s.get("document_name", "") for s in payload.get("selected") or []]


async def load_facts(session: AsyncSession, run: Run) -> ItemFacts:
    events = (
        await session.scalars(
            select(RunEvent).where(RunEvent.run_id == run.id).order_by(RunEvent.seq)
        )
    ).all()
    selected: list[str] = []
    for e in events:
        if e.type == "sources":
            selected.extend(_stem_names(e.payload or {}))
    sql, sql_rejected = executed_sql(events)
    queries = (await session.scalars(select(KbQuery).where(KbQuery.run_id == run.id))).all()
    raw = [c for q in queries for c in (q.candidates or [])]
    ids = {uuid.UUID(c["document_id"]) for c in raw if c.get("document_id")}
    names = {}
    if ids:
        rows = await session.execute(
            select(Document.id, Document.filename).where(Document.id.in_(ids))
        )
        names = {str(i): f for i, f in rows.all()}
    candidates = [
        Candidate(
            names.get(c["document_id"], c["document_id"]),
            bool(c.get("below_rerank_floor") or c.get("below_min_score")),
        )
        for c in raw
        if c.get("document_id")
    ]
    duration = None
    if run.started_at and run.ended_at:
        duration = int((run.ended_at - run.started_at).total_seconds() * 1000)
    return ItemFacts(
        run_id=str(run.id),
        status=run.status,
        error_code=run.error_code,
        outcome_label=run.outcome_label,
        answer=run.output or "",
        trace_id=run.langfuse_trace_id,
        duration_ms=duration,
        cost_usd=float(run.cost_usd) if run.cost_usd is not None else None,
        selected=selected,
        candidates=candidates,
        sql=sql,
        sql_rejected=sql_rejected,
    )


SQL_SUFFIX = "__run_sql"


def executed_sql(events) -> tuple[list[tuple[str, str]], bool]:
    """The run_sql calls the run really made (09-1 r1 MAJOR-1): a `tool_result` without an
    error and, when the call asked for an approval, `approval_resolved` approved (or an approved
    twin reused). A call a person rejected, one that failed, and one the runtime refused (a tool
    the agent was not given ends `tool_unknown`) are never read again. Returns the calls in
    order and whether a person rejected one."""
    calls: dict[str, dict] = {}
    order: list[str] = []
    for e in events:
        p = e.payload or {}
        cid = p.get("tool_call_id")
        if e.type == "tool_call" and str(p.get("name", "")).endswith(SQL_SUFFIX):
            args = p.get("arguments") or {}
            if isinstance(args.get("sql"), str) and cid:
                calls[cid] = {
                    "tool_key": p["name"].removesuffix(SQL_SUFFIX),
                    "sql": args["sql"],
                    "needs_approval": bool(p.get("needs_approval")),
                    "decision": None,
                    "ok": False,
                }
                order.append(cid)
        elif cid in calls and e.type == "approval_resolved":
            calls[cid]["decision"] = p.get("decision")
        elif cid in calls and e.type == "approval_reused":
            calls[cid]["decision"] = "approved"
        elif cid in calls and e.type == "tool_result":
            calls[cid]["ok"] = not p.get("is_error") and not p.get("error_code")
    done = [
        (c["tool_key"], c["sql"])
        for c in (calls[i] for i in order)
        if c["ok"] and (not c["needs_approval"] or c["decision"] == "approved")
    ]
    rejected = any(c["needs_approval"] and c["decision"] == "rejected" for c in calls.values())
    return done, rejected


def now_utc() -> datetime:
    return datetime.now(UTC)


def langfuse_scores(
    result: ItemResult, run_id: str, trace_id: str, judge_reason: str
) -> list[dict]:
    """The Langfuse score rows of one item run (ids deterministic, L10). No answer text (S8)."""
    meta = {"run_id": run_id, "outcome": result.outcome, "passed": result.passed}
    rows = [
        {
            "score_id": score_id(trace_id, s.name),
            "name": s.name,
            "value": s.value,
            "data_type": "NUMERIC",
            "comment": judge_reason if s.name == "llm_judge" else s.comment,
            "metadata": meta | {"passed": s.passed, "status": s.status},
        }
        for s in result.scores
        if s.value is not None
    ]
    if result.outcome:
        rows.append(
            {
                "score_id": score_id(trace_id, "outcome"),
                "name": "outcome",
                "value": result.outcome,
                "data_type": "CATEGORICAL",
                "comment": "",
                "metadata": meta,
            }
        )
    if result.passed is not None:
        rows.append(
            {
                "score_id": score_id(trace_id, "passed"),
                "name": "passed",
                "value": 1 if result.passed else 0,
                "data_type": "BOOLEAN",
                "comment": "",
                "metadata": meta,
            }
        )
    return rows


def suite_of(session: AsyncSession, ev: EvalRun):
    return session.get(EvalSuite, ev.suite_id)
