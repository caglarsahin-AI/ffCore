"""The retention job (03c, R2.2): every class, count -> record -> remove (K-03c-0011, cond. 5).

One pass at a time (Postgres advisory lock). Per class: the installation row and each project
override (within min/max, checked by the API); counts are recorded in `retention_runs` whether
the pass is a dry run or not. Removal is batched (`RETENTION_BATCH`, one commit per batch); a
failing class is recorded `partial` (or `failed` in a dry run) and the other classes go on. A
second pass the same day finds nothing left (idempotent).

Classes and targets (K-03c-0011, S7-A): content -> clear_content (services/retention.py),
jobs -> every event of terminal runs (the runs row stays; waiting runs never), telemetry ->
guardrail_events and kb_queries, alerts -> alerts, usage -> usage_daily, audit -> whole monthly
partitions (below), traces -> Langfuse's own retention (reported "external"), metrics, results
and memory -> no table yet (reported "none").
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select, text, true
from sqlalchemy.ext.asyncio import AsyncSession

from ffcore.models.retention import RetentionPolicy, RetentionRun
from ffcore.models.runs import Run, RunEvent
from ffcore.runtime.contracts import FINISHED
from ffcore.services.retention import clear_runs_content

log = logging.getLogger("ffcore.retention")

LOCK_KEY = 0x03C00002  # one retention pass at a time across workers
AUDIT_FLOOR_DAYS = 365  # never below, whatever a policy row says (K-03c-0011; [D] to change)
NO_TARGET = {"metrics", "results", "memory"}  # their tables arrive with 09 and 14
EXTERNAL = {"traces": "external:langfuse"}


@dataclass
class ClassResult:
    data_class: str
    project_id: str | None
    cutoff: datetime | None
    counts: dict = field(default_factory=dict)
    status: str = "ok"
    error_code: str | None = None


class RetentionBusy(Exception):
    """Another retention pass holds the lock."""


def _scope(column, project_id, overridden: list):
    """One project (an override), or every project without an override."""
    if project_id is not None:
        return column == project_id
    return column.not_in(overridden) if overridden else true()


async def _batched(session: AsyncSession, ids_query, act, batch: int) -> int:
    """`act(ids)` on batches of `ids_query` until none is left; one commit per batch."""
    done = 0
    while True:
        ids = list(await session.scalars(ids_query.limit(batch)))
        if not ids:
            return done
        await act(ids)
        await session.commit()
        done += len(ids)
        if len(ids) < batch:
            return done


async def _count(session, query) -> int:
    return await session.scalar(select(func.count()).select_from(query.subquery()))


async def _delete_where(session, table, key, where, dry_run: bool, batch: int) -> int:
    query = select(key).where(where)
    if dry_run:
        return await _count(session, query)

    async def remove(ids):
        await session.execute(delete(table).where(key.in_(ids)))

    return await _batched(session, query, remove, batch)


async def _content(session, project_id, overridden, cutoff, dry_run, batch) -> dict:
    query = select(Run.id).where(
        Run.status.in_(FINISHED),
        Run.ended_at < cutoff,
        Run.content_cleared_at.is_(None),
        _scope(Run.project_id, project_id, overridden),
    )
    if dry_run:
        return {"runs": await _count(session, query)}
    counts: dict[str, int] = {}

    async def clear(ids):
        for place, n in (await clear_runs_content(session, ids, include_user_text=True)).items():
            counts[place] = counts.get(place, 0) + n

    await _batched(session, query, clear, batch)
    return counts


async def _jobs(session, project_id, overridden, cutoff, dry_run, batch) -> dict:
    terminal = select(Run.id).where(
        Run.status.in_(FINISHED),
        Run.ended_at < cutoff,
        _scope(Run.project_id, project_id, overridden),
    )
    n = await _delete_where(
        session, RunEvent.__table__, RunEvent.id, RunEvent.run_id.in_(terminal), dry_run, batch
    )
    return {"run_events": n}


async def _telemetry(session, project_id, overridden, cutoff, dry_run, batch) -> dict:
    from ffcore.models.guardrails import GuardrailEventRow
    from ffcore.models.knowledge import KbQuery, KnowledgeBase

    guard = await _delete_where(
        session,
        GuardrailEventRow.__table__,
        GuardrailEventRow.id,
        (GuardrailEventRow.ts < cutoff)
        & _scope(GuardrailEventRow.project_id, project_id, overridden),
        dry_run,
        batch,
    )
    kbs = select(KnowledgeBase.id).where(_scope(KnowledgeBase.project_id, project_id, overridden))
    queries = await _delete_where(
        session,
        KbQuery.__table__,
        KbQuery.id,
        (KbQuery.ts < cutoff) & KbQuery.kb_id.in_(kbs),
        dry_run,
        batch,
    )
    return {"guardrail_events": guard, "kb_queries": queries}


async def _usage(session, project_id, overridden, cutoff, dry_run, batch) -> dict:
    from ffcore.models.quota import UsageDaily

    n = await _delete_where(
        session,
        UsageDaily.__table__,
        UsageDaily.id,
        (UsageDaily.date < cutoff.date()) & _scope(UsageDaily.project_id, project_id, overridden),
        dry_run,
        batch,
    )
    return {"usage_daily": n}


EXECUTORS = {"content": _content, "jobs": _jobs, "telemetry": _telemetry, "usage": _usage}


def register(data_class: str, executor) -> None:
    """A package that owns a class's table adds its executor (03c-2 alerts; later 09, 14)."""
    EXECUTORS[data_class] = executor
    NO_TARGET.discard(data_class)


async def execute(
    settings, *, dry_run: bool, trigger: str, actor_id: str, now: datetime | None = None
) -> list[ClassResult]:
    """One pass over every class; raises RetentionBusy when another pass holds the lock."""
    from ffcore.core import db
    from ffcore.services import alerts  # noqa: F401 - registers the `alerts` class executor

    now = now or datetime.now(UTC)
    results: list[ClassResult] = []
    async with db.session_scope() as lock:
        if not await lock.scalar(text("SELECT pg_try_advisory_lock(:k)"), {"k": LOCK_KEY}):
            raise RetentionBusy()
        try:
            async with db.session_scope() as session:
                rows = await session.scalars(select(RetentionPolicy))
                grouped: dict[str, list[RetentionPolicy]] = {}
                for row in rows:
                    grouped.setdefault(row.data_class, []).append(row)
                # A real pass counts first and records the count, then removes and records
                # what it removed: two append-only rows, so a pass cut short still shows what
                # it was about to do (K-03c-0011 condition 5).
                steps = [(c, True) for c in sorted(grouped)]
                if not dry_run:
                    steps = [(c, s) for c in sorted(grouped) for s in (True, False)]
                for data_class, counting in steps:
                    for result in await _run_class(
                        session, settings, data_class, grouped[data_class], counting, now
                    ):
                        session.add(
                            RetentionRun(
                                data_class=result.data_class,
                                project_id=uuid.UUID(result.project_id)
                                if result.project_id
                                else None,
                                trigger=trigger,
                                dry_run=counting,
                                cutoff=result.cutoff,
                                counts=result.counts,
                                status=result.status,
                                error_code=result.error_code,
                                actor_id=actor_id,
                            )
                        )
                        await session.commit()
                        if counting == dry_run:
                            results.append(result)
        finally:
            await lock.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": LOCK_KEY})
    return results


async def _run_class(session, settings, data_class, rows, dry_run, now) -> list[ClassResult]:
    base = next(r for r in rows if r.project_id is None)
    overrides = [r for r in rows if r.project_id is not None]
    if data_class in EXTERNAL or (data_class in NO_TARGET and data_class not in EXECUTORS):
        return [ClassResult(data_class, None, None, {"target": EXTERNAL.get(data_class, "none")})]
    if data_class == "audit":
        return [await audit_partitions(settings, base.keep_days, dry_run=dry_run, now=now)]
    executor = EXECUTORS.get(data_class)
    if executor is None:
        return [ClassResult(data_class, None, None, {"target": "none"})]
    overridden = [r.project_id for r in overrides]
    passes = [(None, base.keep_days)] + [(r.project_id, r.keep_days) for r in overrides]
    results = []
    for project_id, keep_days in passes:
        cutoff = now - timedelta(days=keep_days)
        result = ClassResult(data_class, str(project_id) if project_id else None, cutoff)
        try:
            result.counts = await executor(
                session, project_id, overridden, cutoff, dry_run, settings.retention_batch
            )
        except Exception as exc:  # noqa: BLE001 - this class stops, the others go on
            await session.rollback()
            result.status = "failed" if dry_run else "partial"
            result.error_code = type(exc).__name__
            log.error("retention_class_failed class=%s error=%s", data_class, result.error_code)
        results.append(result)
    return results


async def audit_partitions(
    settings, keep_days: int, *, dry_run: bool, now: datetime
) -> ClassResult:
    """Whole monthly partitions older than max(keep_days, 365) days. Dropping needs a real pass
    and RETENTION_AUDIT_DROP_ENABLED: DETACH, then a retention_runs record (rows, min/max ts,
    SHA-256 over the rows) committed, then DROP as its own step, then an
    `audit_partition_dropped` audit event. A failed DROP leaves the detached table, reported."""
    from ffcore.core import db
    from ffcore.core.audit import AuditEntry, write_event_detached

    cutoff = now - timedelta(days=max(keep_days, AUDIT_FLOOR_DAYS))
    result = ClassResult("audit", None, cutoff)
    async with db.session_scope() as session:
        names = list(
            await session.scalars(
                text(
                    "SELECT c.relname FROM pg_inherits i JOIN pg_class c ON c.oid = i.inhrelid"
                    " JOIN pg_class p ON p.oid = i.inhparent WHERE p.relname = 'audit_events'"
                    " ORDER BY c.relname"
                )
            )
        )
    old = []
    for name in names:
        try:
            year, month = (int(x) for x in name.removeprefix("audit_events_").split("_"))
        except ValueError:
            continue
        month_end = (datetime(year, month, 1, tzinfo=UTC) + timedelta(days=32)).replace(day=1)
        if month_end <= cutoff:  # every row of that month is older than the cutoff
            old.append(name)
    result.counts = {"partitions": old, "dropped": []}
    if dry_run:
        return result
    if not settings.retention_audit_drop_enabled:
        result.counts["skipped"] = "RETENTION_AUDIT_DROP_ENABLED is false"
        return result
    for name in old:
        async with db.session_scope() as session:
            await session.execute(text(f'ALTER TABLE audit_events DETACH PARTITION "{name}"'))
            rows, first, last, digest = (
                await session.execute(
                    text(
                        "SELECT count(*), min(ts), max(ts), encode(sha256(convert_to("
                        "coalesce(string_agg(t::text, chr(10) ORDER BY t.ts, t.id), ''),"
                        f" 'UTF8')), 'hex') FROM \"{name}\" t"
                    )
                )
            ).one()
            session.add(
                RetentionRun(
                    data_class="audit",
                    trigger="schedule",
                    dry_run=False,
                    cutoff=cutoff,
                    counts={
                        "partition": name,
                        "detached": True,
                        "rows": rows,
                        "min_ts": first.isoformat() if first else None,
                        "max_ts": last.isoformat() if last else None,
                        "sha256": digest,
                    },
                    actor_id="retention",
                )
            )
            await session.commit()
        try:
            async with db.session_scope() as session:
                await session.execute(text(f'DROP TABLE "{name}"'))
                await session.commit()
        except Exception as exc:  # noqa: BLE001 - the detached table stays and is reported
            result.status, result.error_code = "partial", f"drop_failed:{type(exc).__name__}"
            log.error("audit_partition_drop_failed partition=%s", name)
            continue
        await write_event_detached(
            AuditEntry(
                action="audit_partition_dropped",
                resource_type="audit_partition",
                outcome="success",
                actor_type="system",
                actor_id="retention",
                resource_id=name,
                after={"rows": rows, "sha256": digest},
            )
        )
        result.counts["dropped"].append(name)
    return result
