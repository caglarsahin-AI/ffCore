"""The sync engine: raw, silver and gold for one data source (plan/16 D3, D4; C6, C10, C15).

Layers (each a `sync_runs` row; one active run per source, a partial unique index):
- **raw** (sync worker, queue `sync`): the only layer that talks to the source. The source's
  count is taken before and after the listing; every listed item's bytes are stored as given
  (`payload.<ext>`); attachments pass Kapı 0 from the listing before anything is downloaded
  (`source_attachments`); permissions are mapped (`acl.resolve`). An item whose bytes did not
  change is `unchanged` (an ACL change alone is applied to the document and the vector store).
  A full run then applies the safe delete rule (`prune.decide`); a delta run deletes only on a
  driver with tombstones. The cursor moves to the run's start only when no item failed.
  Changed items are handed to silver: a queued silver run on the ingest queue.
- **silver** (ingest worker): the driver renders the payload (no network), and 04's pipeline
  converts, gates and indexes it (`ingest_from_raw`, C6; gold follows inside). Delta: the items
  whose content hash silver has not ingested yet. Full: every item, from raw again.
- **gold** (ingest worker): 04's `reindex_gold` on the source's documents; unchanged chunk text
  reuses its vector (`reused`), nothing is read from raw or the source.

Every item error is recorded with its code (never content, never credentials) and the others go
on. Deletion order: vector store first (a failure deletes nothing: `prune_failed`), then rows,
runs and retention (`knowledge.removal`), then files; an attachment file another item borrows
(`shared_from`) moves to the first borrower instead of being removed.
"""

import asyncio
import hashlib
import logging
import shutil
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from ffcore.core import db
from ffcore.core.config import Settings
from ffcore.core.secrets import decrypt_json
from ffcore.knowledge import ingest, raw_staging, removal
from ffcore.knowledge.jobs import JobQueue
from ffcore.knowledge.vectorstore.base import VectorStore, VectorStoreError
from ffcore.models.identity import ProjectMember, User
from ffcore.models.knowledge import Document, KnowledgeBase
from ffcore.models.sources import (
    AclMapping,
    DataSource,
    SourceAttachment,
    SourceItem,
    SourceSyncState,
    SyncRun,
)
from ffcore.sources import acl, gate0, paths, prune, registry
from ffcore.sources.base import ItemRef, RawPayload, SourceError, SourceSpec

log = logging.getLogger("ffcore.sources")

CANCEL_CHECK_EVERY = 20
PAYLOAD = "payload"
DOC_DIR = "doc"
PAGE = "_page"
SOURCE_LAYER_JOB = "source_layer_job"
SYNC_RAW_JOB = "sync_raw_job"
DOWNLOAD_PART = ".part"
# Recorded per item but not a failure to retry: the cursor still moves (a source member without
# a platform user stays without access until one exists; listing again changes nothing).
INFORMATIONAL = frozenset({"acl_user_unmatched"})


class SyncRunning(SourceError):
    def __init__(self) -> None:
        super().__init__("sync_running", "another run of this source is queued or running")


@dataclass
class Stats:
    listed: int = 0
    added: int = 0
    updated: int = 0
    deleted: int = 0
    skipped: int = 0
    reused: int = 0
    unchanged: int = 0
    errors: list[dict] = field(default_factory=list)

    def error(self, external_id: str | None, code: str, detail: str = "") -> None:
        entry: dict[str, Any] = {"code": code}
        if external_id is not None:
            entry["external_id"] = external_id
        if detail:
            entry["detail"] = detail[:300]
        self.errors.append(entry)

    def columns(self) -> dict:
        return {
            "listed": self.listed,
            "added": self.added,
            "updated": self.updated,
            "deleted": self.deleted,
            "skipped": self.skipped,
            "reused": self.reused,
            "unchanged": self.unchanged,
            "errors": self.errors,
        }


def _item_errors(stats: Stats) -> bool:
    return any("external_id" in e and e["code"] not in INFORMATIONAL for e in stats.errors)


def _now() -> datetime:
    return datetime.now(UTC)


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _detail(exc: BaseException) -> str:
    """An error's code-level description: the SourceError detail, else the exception type (an
    arbitrary exception text may carry content or a URL with credentials)."""
    return exc.detail if isinstance(exc, SourceError) else type(exc).__name__


def make_driver(source: DataSource, settings: Settings, http=None):
    driver_cls = registry.driver_for(source.kind, source.deployment, settings)
    secret = decrypt_json(source.secret_encrypted, settings) if source.secret_encrypted else None
    spec = SourceSpec(
        id=str(source.id),
        kind=source.kind,
        deployment=source.deployment,
        config=dict(source.config),
    )
    return driver_cls(spec, secret, http, settings)


def document_filename(source_key: str, external_id: str, rendered_name: str) -> str:
    """The 04 document name: unique per source in the KB, stable when the title changes (a new
    title is a new version, not a new document); ends with the converter's extension."""
    base = f"{source_key}/{external_id.strip('/')}"
    ext = PurePosixPath(rendered_name).suffix.lower()
    return base if not ext or base.lower().endswith(ext) else base + ext


# --- runs ---------------------------------------------------------------------------------


async def create_run(
    session,
    source: DataSource,
    *,
    layer: str,
    mode: str,
    trigger: str,
    requested_by: str,
    force_prune: bool = False,
) -> SyncRun:
    """A queued run, or SyncRunning when the source already has one (partial unique index)."""
    run = SyncRun(
        id=uuid.uuid4(),
        data_source_id=source.id,
        layer=layer,
        mode=mode,
        trigger=trigger,
        requested_by=requested_by,
        force_prune=force_prune,
        status="queued",
    )
    try:
        async with session.begin_nested():
            session.add(run)
            await session.flush()
    except IntegrityError:
        # The savepoint is gone; the refused row must not be flushed again with the caller's
        # next statement (the scheduler goes on with other sources in the same session).
        if run in session:
            session.expunge(run)
        raise SyncRunning() from None
    return run


async def enqueue_run(run: SyncRun, *, sync_queue: JobQueue, ingest_queue: JobQueue) -> str:
    if run.layer == "raw":
        return await sync_queue.enqueue(SYNC_RAW_JOB, str(run.id))
    return await ingest_queue.enqueue(SOURCE_LAYER_JOB, str(run.id))


MAX_ROW_WAIT_TRIES = 5


async def wait_for_run(ctx, run_id: uuid.UUID) -> None:
    """A job may start before the request that queued it committed (04 upload pattern): retry a
    few times, then fail loudly."""
    from arq import Retry

    async with db.session_scope() as session:
        exists = await session.get(SyncRun, run_id)
    if exists is None:
        if ctx.get("job_try", 1) < MAX_ROW_WAIT_TRIES:
            raise Retry(defer=2)
        raise LookupError(f"sync run {run_id} not found after {MAX_ROW_WAIT_TRIES} tries")


async def fail_queued(run_id: uuid.UUID, code: str) -> None:
    async with db.session_scope() as session:
        run = await session.get(SyncRun, run_id)
        if run is not None and run.status in ("queued", "running"):
            run.status, run.error, run.ended_at = "failed", code, _now()
            await session.commit()


async def _begin(run_id: uuid.UUID, layer: str) -> tuple[SyncRun, DataSource]:
    async with db.session_scope() as session:
        run = await session.get(SyncRun, run_id)
        if run is None:
            raise LookupError(f"sync run {run_id} not found")
        if run.layer != layer or run.status != "queued":
            raise SourceError(
                "run_not_queued", f"run {run_id} is {run.status} ({run.layer}), not queued {layer}"
            )
        source = await session.get(DataSource, run.data_source_id)
        run.status, run.started_at = "running", _now()
        await session.commit()
        session.expunge_all()
    return run, source


async def _kb_alive(source: DataSource) -> bool:
    """16-1 r1 MINOR-1: a run never writes into a deleted knowledge base."""
    async with db.session_scope() as session:
        alive = await session.scalar(
            select(KnowledgeBase.id).where(
                KnowledgeBase.id == source.kb_id, KnowledgeBase.deleted_at.is_(None)
            )
        )
    return alive is not None


async def _cancel_requested(run_id: uuid.UUID) -> bool:
    async with db.session_scope() as session:
        return bool(
            await session.scalar(select(SyncRun.cancel_requested).where(SyncRun.id == run_id))
        )


async def _finish(
    run_id: uuid.UUID,
    stats: Stats,
    *,
    status: str,
    error: str | None = None,
    count_before: int | None = None,
    count_after: int | None = None,
    prune_decision: str | None = None,
    session=None,
) -> None:
    own = session is None
    session = session or db.session_scope()
    try:
        run = await session.get(SyncRun, run_id)
        for name, value in stats.columns().items():
            setattr(run, name, value)
        run.status, run.error, run.ended_at = status, error, _now()
        run.count_before, run.count_after, run.prune_decision = (
            count_before,
            count_after,
            prune_decision,
        )
        source = await session.get(DataSource, run.data_source_id)
        source.last_sync_at = run.ended_at
        source.last_error = error or (stats.errors[0]["code"] if stats.errors else None)
        if own:
            await session.commit()
    finally:
        if own:
            await session.close()


async def _cursor(session, source_id: uuid.UUID, layer: str) -> SourceSyncState | None:
    return await session.get(SourceSyncState, (source_id, layer))


async def _advance(session, source_id: uuid.UUID, layer: str, cursor: str | None) -> None:
    state = await _cursor(session, source_id, layer)
    if state is None:
        state = SourceSyncState(data_source_id=source_id, layer=layer)
        session.add(state)
    state.cursor, state.completed_at = cursor, _now()


# --- raw ----------------------------------------------------------------------------------


@dataclass
class _RawContext:
    run: SyncRun
    source: DataSource
    settings: Settings
    driver: Any
    rules: list[acl.AclRule]
    users_by_email: dict[str, str]
    stats: Stats
    seen: set[str] = field(default_factory=set)
    tombstones: list[str] = field(default_factory=list)
    # Listed but refused (a symlink out of the root): present at the source, so never a deletion
    # candidate; not counted as seen either (the source's count leaves it out too).
    refused: set[str] = field(default_factory=set)
    to_delete: int = 0


async def _acl_inputs(source: DataSource) -> tuple[list[acl.AclRule], dict[str, str]]:
    async with db.session_scope() as session:
        rows = (
            await session.scalars(select(AclMapping).where(AclMapping.data_source_id == source.id))
        ).all()
        members = (
            await session.execute(
                select(User.id, func.lower(User.email))
                .join(ProjectMember, ProjectMember.user_id == User.id)
                .where(ProjectMember.project_id == source.project_id)
            )
        ).all()
    rules = [
        acl.AclRule(r.external_group, r.role, str(r.user_id) if r.user_id else None) for r in rows
    ]
    return rules, {email: str(user_id) for user_id, email in members}


async def run_raw(
    run_id: uuid.UUID, *, settings: Settings, store: VectorStore, ingest_queue, http=None
) -> dict:
    """One raw run (sync worker). Returns the run's counters."""
    run, source = await _begin(run_id, "raw")
    stats = Stats()
    if not await _kb_alive(source):
        stats.error(None, "kb_deleted", "the source's knowledge base was deleted")
        await _finish(run_id, stats, status="failed", error="kb_deleted")
        return {"status": "failed", "error": "kb_deleted"}
    try:
        driver = make_driver(source, settings, http)
    except SourceError as exc:
        await _finish(run_id, stats, status="failed", error=exc.code)
        return {"status": "failed", "error": exc.code}
    rules, users = await _acl_inputs(source)
    ctx = _RawContext(run, source, settings, driver, rules, users, stats)
    try:
        return await _raw(ctx, store=store, ingest_queue=ingest_queue)
    except Exception as exc:
        # Never leave a run `running` (it would block the source until abandoned): fail it.
        log.exception("source_raw_failed source=%s run=%s", source.id, run_id)
        stats.error(None, "raw_failed", _detail(exc))
        await fail_queued(run_id, "raw_failed")
        raise
    finally:
        await driver.aclose()


async def _raw(ctx: _RawContext, *, store: VectorStore, ingest_queue) -> dict:
    run, source, stats = ctx.run, ctx.source, ctx.stats
    try:
        count_before = await ctx.driver.count()
    except Exception as exc:  # the source cannot be counted: nothing is listed
        code = exc.code if isinstance(exc, SourceError) else "count_failed"
        stats.error(None, code, _detail(exc))
        await _finish(run.id, stats, status="failed", error=code)
        return {"status": "failed", "error": code}
    async with db.session_scope() as session:
        state = await _cursor(session, source.id, "raw")
    since = None
    if run.mode == "delta" and state is not None and state.cursor:
        since = datetime.fromisoformat(state.cursor)
    listing_ok, cancelled = True, False
    try:
        n = 0
        async for item in ctx.driver.list_changes(since):
            n += 1
            if n % CANCEL_CHECK_EVERY == 0 and await _cancel_requested(run.id):
                cancelled = True
                break
            await _raw_item(ctx, item)
    except Exception as exc:  # the listing broke: no deletion, no cursor move
        listing_ok = False
        code = exc.code if isinstance(exc, SourceError) else "listing_failed"
        stats.error(None, code, _detail(exc))
    if cancelled:
        await _finish(run.id, stats, status="cancelled", count_before=count_before)
        return {"status": "cancelled"}
    count_after = None
    if listing_ok:
        try:
            count_after = await ctx.driver.count()
        except Exception as exc:
            stats.error(None, "count_failed", _detail(exc))
    decision = await _prune(ctx, store, listing_ok, count_before, count_after)
    await _reresolve_acl(ctx, store)
    async with db.session_scope() as session:
        item_errors = _item_errors(stats)
        if listing_ok and not item_errors and decision.decision != "prune_failed":
            await _advance(session, source.id, "raw", run.started_at.isoformat())
        status = "completed" if listing_ok else "failed"
        await _finish(
            run.id,
            stats,
            status=status,
            error=None if listing_ok else stats.errors[-1]["code"],
            count_before=count_before,
            count_after=count_after,
            prune_decision=decision.decision,
            session=session,
        )
        await session.flush()  # the raw run leaves the active set before silver enters it
        pending = await _pending_silver(session, source.id)
        silver = None
        if pending:
            silver = await create_run(
                session,
                source,
                layer="silver",
                mode="delta",
                trigger=run.trigger,
                requested_by=run.requested_by,
            )
        await session.commit()
    if decision.decision == "prune_refused":
        await _alert_prune_refused(ctx, decision, count_after)
    if silver is not None:
        try:
            await ingest_queue.enqueue(SOURCE_LAYER_JOB, str(silver.id))
        except Exception:
            log.exception("source_silver_enqueue_failed source=%s run=%s", source.id, silver.id)
            await fail_queued(silver.id, "enqueue_failed")
    log.info(
        "source_raw source=%s run=%s status=%s listed=%d added=%d updated=%d unchanged=%d "
        "deleted=%d skipped=%d errors=%d prune=%s",
        source.id, run.id, status, stats.listed, stats.added, stats.updated, stats.unchanged,
        stats.deleted, stats.skipped, len(stats.errors), decision.decision,
    )  # fmt: skip
    return {
        "status": status,
        "prune_decision": decision.decision,
        "count_before": count_before,
        "count_after": count_after,
        **stats.columns(),
    }


async def _item_row(session, source_id: uuid.UUID, external_id: str) -> SourceItem | None:
    return await session.scalar(
        select(SourceItem).where(
            SourceItem.data_source_id == source_id, SourceItem.external_id == external_id
        )
    )


async def _record_item_error(ctx: _RawContext, item: ItemRef, code: str, detail: str) -> None:
    ctx.stats.error(item.external_id, code, detail)
    async with db.session_scope() as session:
        row = await _item_row(session, ctx.source.id, item.external_id)
        if row is None:
            row = SourceItem(
                id=uuid.uuid4(),
                data_source_id=ctx.source.id,
                external_id=item.external_id,
                title=item.title,
                state="active",
            )
            session.add(row)
        row.last_error, row.last_run_id = code, ctx.run.id
        await session.commit()


async def _raw_item(ctx: _RawContext, item: ItemRef) -> None:
    ctx.stats.listed += 1
    if item.deleted:
        ctx.tombstones.append(item.external_id)
        return
    if item.refused is not None:
        ctx.refused.add(item.external_id)
        ctx.stats.skipped += 1
        await _record_item_error(ctx, item, item.refused, "refused while listing")
        return
    ctx.seen.add(item.external_id)
    try:
        await _raw_item_inner(ctx, item)
    except Exception as exc:  # one item never stops the run (brief: hata izole)
        code = exc.code if isinstance(exc, SourceError) else "item_failed"
        if not isinstance(exc, SourceError):
            log.exception("source_item_failed source=%s item=%s", ctx.source.id, item.external_id)
        await _record_item_error(ctx, item, code, _detail(exc))


async def _raw_item_inner(ctx: _RawContext, item: ItemRef) -> None:
    source, settings = ctx.source, ctx.settings
    label = f"{source.kind}:{item.space}"
    if raw_staging.personnel_data(label, item.external_id):
        raise SourceError(
            "prsim_requires_ner", "personnel data is ingested once names are masked (08 full)"
        )
    name = PurePosixPath(item.external_id).name
    if item.size is not None:
        status, reason = gate0.decide(name, item.size, None, min_date=None)
        if status == "skipped":
            await _gate0_skip(ctx, item, reason)
            return
    raw = await ctx.driver.fetch_raw(item)
    digest = _sha256(raw.content)
    item_dir = paths.raw_item_dir(
        settings.knowledge_storage_dir,
        str(source.project_id),
        str(source.kb_id),
        source.kind,
        item.space,
        item.external_id,
    )
    payload_path = item_dir / f"{PAYLOAD}.{raw.ext}"
    source_acl = await ctx.driver.acl(item, raw)
    by_email = acl.resolve((), source_acl.user_emails, (), ctx.users_by_email)
    if by_email.unmatched_emails:
        ctx.stats.error(item.external_id, "acl_user_unmatched", str(by_email.unmatched_emails))
    email_users = [] if by_email.default_admin else list(by_email.users)
    acl_source = {
        "groups": list(source_acl.groups),
        "email_users": email_users,
        **item_acl(source, source_acl.groups, email_users, ctx.rules),
    }
    async with db.session_scope() as session:
        row = await _item_row(session, source.id, item.external_id)
        unchanged = (
            row is not None
            and row.state == "active"
            and row.content_hash == digest
            and row.raw_path is not None
            and Path(row.raw_path).is_file()
        )
        is_new = row is None
        if is_new:
            row = SourceItem(
                id=uuid.uuid4(),
                data_source_id=source.id,
                external_id=item.external_id,
                acl_source={},
                state="active",
            )
            session.add(row)
            await session.flush()
        if not unchanged:
            await asyncio.to_thread(_write_atomic, payload_path, raw.content)
        previous = list((row.acl_source or {}).get("attachments", []))
        names = await _attachments(ctx, session, row, item, raw, item_dir)
        if is_new:
            ctx.stats.added += 1
        elif unchanged:
            ctx.stats.unchanged += 1  # a permission change alone: _reresolve_acl applies it
        else:
            ctx.stats.updated += 1
        if unchanged and names != previous:
            row.silver_hash = None  # an attachment changed under the same page bytes
        row.title, row.external_url = item.title, item.url
        row.external_updated_at = item.updated_at
        row.content_hash, row.raw_path = digest, str(payload_path)
        row.acl_source = {**acl_source, "attachments": names, "space": item.space}
        row.state, row.gate0_status, row.gate0_reason = "active", "ok", None
        row.last_error, row.last_run_id = None, ctx.run.id
        await session.commit()


async def _gate0_skip(ctx: _RawContext, item: ItemRef, reason: str | None) -> None:
    ctx.stats.skipped += 1
    async with db.session_scope() as session:
        row = await _item_row(session, ctx.source.id, item.external_id)
        if row is None:
            row = SourceItem(
                id=uuid.uuid4(), data_source_id=ctx.source.id, external_id=item.external_id
            )
            session.add(row)
        row.title, row.external_url, row.external_updated_at = item.title, item.url, item.updated_at
        row.gate0_status, row.gate0_reason = "skipped", reason
        row.last_error, row.last_run_id, row.state = None, ctx.run.id, "active"
        await session.commit()


def _write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + DOWNLOAD_PART)
    part.write_bytes(content)
    part.replace(path)


async def _attachments(
    ctx: _RawContext, session, row: SourceItem, item: ItemRef, raw: RawPayload, item_dir
) -> list[str]:
    """Kapı 0 from the listing, then download; returns the names (under doc/) silver converts.
    An attachment another item already downloaded (same name and size in this source) is
    `shared_from` that one and not downloaded again."""
    min_date = ctx.settings.attachment_min_date
    doc_dir = item_dir / DOC_DIR
    names: list[str] = []
    listed: set[str] = set()
    existing = {
        a.name: a
        for a in (
            await session.scalars(
                select(SourceAttachment).where(SourceAttachment.source_item_id == row.id)
            )
        ).all()
    }
    async for att in ctx.driver.list_attachments(item, raw):
        listed.add(att.name)
        ledger = existing.get(att.name)
        if ledger is None:
            ledger = SourceAttachment(id=uuid.uuid4(), source_item_id=row.id, name=att.name)
            session.add(ledger)
            existing[att.name] = ledger
        ledger.size, ledger.mime, ledger.modified_at = att.size, att.mime, att.modified_at
        status, reason = gate0.decide(att.name, att.size, att.modified_at, min_date=min_date)
        if status == "skipped":
            await asyncio.to_thread(_drop_own_file, ledger)
            ledger.gate0_status, ledger.gate0_reason, ledger.raw_path = status, reason, None
            ledger.shared_from = None
            continue
        safe = paths.safe_name(att.name)
        if safe.startswith(PAGE):
            safe = "_" + safe
        target = doc_dir / safe
        if (
            ledger.shared_from is None
            and ledger.raw_path == str(target)
            and target.is_file()
            and (att.size is None or target.stat().st_size == att.size)
        ):
            ledger.gate0_status, ledger.gate0_reason = "ok", None
            names.append(safe)
            continue
        owner = await _shared_owner(session, ctx.source.id, row, att.name, att.size)
        if owner is not None:
            ledger.shared_from, ledger.raw_path = owner.id, owner.raw_path
            ledger.gate0_status, ledger.gate0_reason = "ok", "shared_from"
            continue
        try:
            await _download(ctx.driver, item, att, target)
        except SourceError as exc:
            if exc.code == "attachment_gone":
                ledger.gate0_status, ledger.gate0_reason, ledger.raw_path = "skipped", "gone", None
                continue
            if exc.code == "too_large":
                ledger.gate0_status, ledger.gate0_reason, ledger.raw_path = (
                    "skipped",
                    "too_large",
                    None,
                )
                continue
            ctx.stats.error(item.external_id, exc.code, f"attachment: {exc.detail}")
            continue
        ledger.shared_from, ledger.raw_path = None, str(target)
        ledger.gate0_status, ledger.gate0_reason = "ok", None
        names.append(safe)
    if ctx.run.mode == "full":
        # No longer listed with its record (full run only, like items): released, then removed.
        for ledger in [x for x in existing.values() if x.name not in listed]:
            await _release(session, ctx, [ledger])
            await session.delete(ledger)
    return sorted(names)


async def _shared_owner(session, source_id, row, name: str, size: int | None):
    if size is None:
        return None
    statement = (
        select(SourceAttachment)
        .join(SourceItem, SourceItem.id == SourceAttachment.source_item_id)
        .where(
            SourceItem.data_source_id == source_id,
            SourceItem.state == "active",
            SourceAttachment.name == name,
            SourceAttachment.size == size,
            SourceAttachment.shared_from.is_(None),
            SourceAttachment.raw_path.is_not(None),
            SourceAttachment.gate0_status == "ok",
        )
        .where(SourceAttachment.source_item_id != row.id)
        .order_by(SourceAttachment.id)
        .limit(1)
    )
    return await session.scalar(statement)


async def _download(driver, item: ItemRef, att, target: Path) -> None:
    limit = gate0.max_bytes(att.name)
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_name(target.name + DOWNLOAD_PART)
    written = 0
    try:
        async with driver.fetch_attachment(item, att) as chunks:
            with part.open("wb") as handle:
                async for chunk in chunks:
                    written += len(chunk)
                    if written > limit:
                        raise SourceError("too_large", f"over {limit} bytes while downloading")
                    handle.write(chunk)
        part.replace(target)
    finally:
        part.unlink(missing_ok=True)


def _drop_own_file(ledger: SourceAttachment) -> None:
    if ledger.shared_from is None and ledger.raw_path:
        Path(ledger.raw_path).unlink(missing_ok=True)


async def _release(
    session, ctx: _RawContext, ledgers: list[SourceAttachment], doomed: frozenset = frozenset()
) -> None:
    """An attachment file that others borrow moves to the first borrower (by id) instead of
    being removed; the borrowers point at the heir; the heir's item waits for silver again.
    A borrower whose own item is deleted in the same run is never the heir."""
    for ledger in ledgers:
        if ledger.shared_from is not None or not ledger.raw_path:
            continue
        borrowers = (
            await session.scalars(
                select(SourceAttachment)
                .where(SourceAttachment.shared_from == ledger.id)
                .order_by(SourceAttachment.id)
            )
        ).all()
        borrowers = [b for b in borrowers if b.source_item_id not in doomed]
        if not borrowers:
            await asyncio.to_thread(_drop_own_file, ledger)
            continue
        heir, *others = borrowers
        heir_item = await session.get(SourceItem, heir.source_item_id)
        heir_dir = Path(heir_item.raw_path).parent / DOC_DIR
        safe = paths.safe_name(heir.name)
        target = heir_dir / ("_" + safe if safe.startswith(PAGE) else safe)
        await asyncio.to_thread(_move, Path(ledger.raw_path), target)
        heir.shared_from, heir.raw_path, heir.gate0_reason = None, str(target), None
        for other in others:
            other.shared_from, other.raw_path = heir.id, str(target)
        names = list(heir_item.acl_source.get("attachments", []))
        heir_item.acl_source = {
            **heir_item.acl_source,
            "attachments": sorted({*names, target.name}),
        }
        heir_item.silver_hash = None
        ledger.raw_path = None


def _move(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(target))


# --- prune --------------------------------------------------------------------------------


async def _prune(ctx: _RawContext, store, listing_ok, count_before, count_after):
    source, run = ctx.source, ctx.run
    async with db.session_scope() as session:
        active = dict(
            (
                await session.execute(
                    select(SourceItem.external_id, SourceItem.id).where(
                        SourceItem.data_source_id == source.id, SourceItem.state == "active"
                    )
                )
            ).all()
        )
    if run.mode == "full":
        doomed = sorted(set(active) - ctx.seen - ctx.refused)
    elif ctx.driver.tombstones:
        doomed = sorted(set(ctx.tombstones) & set(active))
    else:
        doomed = []
    ctx.to_delete = len(doomed)
    decision = prune.decide(
        prune.PruneInput(
            mode=run.mode,
            tombstones=ctx.driver.tombstones,
            listing_ok=listing_ok,
            count_before=count_before,
            count_after=count_after,
            seen=len(ctx.seen),
            to_delete=len(doomed),
            max_ratio=source.prune_max_ratio or ctx.settings.prune_max_ratio,
            force=run.force_prune,
        )
    )
    if not decision.allowed:
        if decision.decision not in ("none",):
            log.warning(
                "prune_refused source=%s run=%s decision=%s to_delete=%d before=%s after=%s "
                "seen=%d ratio=%s",
                source.id, run.id, decision.decision, len(doomed), count_before, count_after,
                len(ctx.seen), decision.ratio,
            )  # fmt: skip
        return decision
    try:
        ctx.stats.deleted = await prune_items(ctx, store, [active[e] for e in doomed])
    except VectorStoreError as exc:
        ctx.stats.error(None, "prune_failed", f"vector store: {exc.code}")
        return prune.PruneDecision("prune_failed", decision.ratio)
    if decision.decision == "forced":
        log.warning(
            "prune_forced source=%s run=%s deleted=%d ratio=%s requested_by=%s",
            source.id, run.id, ctx.stats.deleted, decision.ratio, run.requested_by,
        )  # fmt: skip
    return decision


async def prune_items(ctx: _RawContext, store, item_ids: list[uuid.UUID]) -> int:
    """Vector store first (raises: nothing else changes), then rows, then files."""
    if not item_ids:
        return 0
    async with db.session_scope() as session:
        items = list(
            (await session.scalars(select(SourceItem).where(SourceItem.id.in_(item_ids)))).all()
        )
        document_ids = [i.document_id for i in items if i.document_id is not None]
        await removal.remove_vectors(store, document_ids)
        ledgers = list(
            (
                await session.scalars(
                    select(SourceAttachment).where(SourceAttachment.source_item_id.in_(item_ids))
                )
            ).all()
        )
        await _release(session, ctx, ledgers, frozenset(item_ids))
        await removal.remove_rows(session, document_ids)
        raw_dirs = [Path(i.raw_path).parent for i in items if i.raw_path]
        for item in items:
            item.state, item.raw_path, item.last_run_id = "deleted", None, ctx.run.id
            item.silver_hash = None
        await session.commit()
    for directory in raw_dirs:
        await asyncio.to_thread(shutil.rmtree, directory, True)
    return len(items)


def item_acl(source: DataSource, groups, email_users, rules) -> dict:
    """An item's ACL from its source groups (mapped now) and its matched member e-mails."""
    resolved = acl.resolve(groups, (), rules, {}, most_specific=source.kind == "fs")
    if resolved.default_admin and email_users:
        roles, users, default_admin = [], list(email_users), False
    else:
        roles = list(resolved.roles)
        users = list(dict.fromkeys([*resolved.users, *email_users]))
        default_admin = resolved.default_admin
    return {
        "roles": roles,
        "users": users,
        "unmapped": list(resolved.unmapped_groups),
        "default_admin": default_admin,
    }


async def _reresolve_acl(ctx: _RawContext, store) -> None:
    """Every raw run maps the stored groups of all the source's items again (no request to the
    source): a mapping change, or a changed permission under unchanged bytes, reaches the
    document and the vector store on the next sync (C15), also for items a delta did not list."""
    async with db.session_scope() as session:
        rows = (
            await session.execute(
                select(SourceItem, Document)
                .join(Document, Document.id == SourceItem.document_id)
                .where(
                    SourceItem.data_source_id == ctx.source.id,
                    SourceItem.state == "active",
                    Document.deleted_at.is_(None),
                )
            )
        ).all()
        changed = 0
        for item, document in rows:
            stored = item.acl_source or {}
            fresh = item_acl(
                ctx.source, stored.get("groups", []), stored.get("email_users", []), ctx.rules
            )
            item.acl_source = {**stored, **fresh}
            roles = sorted(fresh["roles"])
            users = sorted(fresh["users"])
            if (sorted(document.acl_roles), sorted(map(str, document.acl_users))) == (roles, users):
                continue
            try:
                await store.update_acl(
                    document.kb_id, document.id, fresh["roles"], [uuid.UUID(u) for u in users]
                )
            except VectorStoreError as exc:
                ctx.stats.error(item.external_id, "acl_update_failed", exc.code)
                continue
            document.acl_roles = list(fresh["roles"])
            document.acl_users = [uuid.UUID(u) for u in users]
            changed += 1
        await session.commit()
    if changed:
        log.info("source_acl_updated source=%s documents=%d", ctx.source.id, changed)


async def _alert_prune_refused(ctx: _RawContext, decision, count_after) -> None:
    from ffcore.services import alerts

    await alerts.emit(
        ctx.settings,
        "prune_refused",
        {
            "data_source_id": str(ctx.source.id),
            "data_source": ctx.source.key,
            "run_id": str(ctx.run.id),
            "to_delete": ctx.to_delete,
            "ratio": None if decision.ratio in (None, float("inf")) else round(decision.ratio, 4),
            "count_after": count_after,
            "max_ratio": ctx.source.prune_max_ratio or ctx.settings.prune_max_ratio,
        },
        project_id=ctx.source.project_id,
        dedupe_key=f"prune_refused:{ctx.source.id}:{ctx.run.id}",
    )


async def _pending_silver(session, source_id: uuid.UUID) -> bool:
    return bool(
        await session.scalar(
            select(func.count())
            .select_from(SourceItem)
            .where(
                SourceItem.data_source_id == source_id,
                SourceItem.state == "active",
                SourceItem.gate0_status == "ok",
                SourceItem.raw_path.is_not(None),
                SourceItem.silver_hash.is_distinct_from(SourceItem.content_hash),
            )
        )
    )


# --- silver and gold (ingest worker) -------------------------------------------------------


async def run_layer(
    run_id: uuid.UUID,
    *,
    settings: Settings,
    store: VectorStore,
    embed_client,
    convert: Callable = ingest.convert_bounded,
) -> dict:
    async with db.session_scope() as session:
        layer = await session.scalar(select(SyncRun.layer).where(SyncRun.id == run_id))
    if layer not in ("silver", "gold"):
        raise SourceError("run_not_queued", f"run {run_id} is not a silver or gold run")
    run, source = await _begin(run_id, layer)
    stats = Stats()
    if not await _kb_alive(source):
        stats.error(None, "kb_deleted", "the source's knowledge base was deleted")
        await _finish(run.id, stats, status="failed", error="kb_deleted")
        return {"status": "failed", "error": "kb_deleted"}
    try:
        if layer == "gold":
            await _gold(run, source, stats, settings, store, embed_client)
        else:
            await _silver(run, source, stats, settings, store, embed_client, convert)
    except Exception as exc:
        code = exc.code if isinstance(exc, SourceError | VectorStoreError) else "layer_failed"
        log.exception("source_layer_failed source=%s run=%s", source.id, run.id)
        stats.error(None, code, _detail(exc))
        await _finish(run.id, stats, status="failed", error=code)
        return {"status": "failed", "error": code}
    async with db.session_scope() as session:
        if not _item_errors(stats):
            await _advance(session, source.id, layer, run.started_at.isoformat())
        await _finish(run.id, stats, status="completed", session=session)
        await session.commit()
    return {"status": "completed", **stats.columns()}


async def _silver_items(source_id: uuid.UUID, full: bool) -> list[SourceItem]:
    async with db.session_scope() as session:
        statement = select(SourceItem).where(
            SourceItem.data_source_id == source_id,
            SourceItem.state == "active",
            SourceItem.gate0_status == "ok",
            SourceItem.raw_path.is_not(None),
        )
        if not full:
            statement = statement.where(
                SourceItem.silver_hash.is_distinct_from(SourceItem.content_hash)
            )
        items = list((await session.scalars(statement.order_by(SourceItem.external_id))).all())
        session.expunge_all()
    return items


async def _silver(run, source, stats, settings, store, embed_client, convert) -> None:
    driver = make_driver(source, settings)
    try:
        for item in await _silver_items(source.id, run.mode == "full"):
            stats.listed += 1
            try:
                created = await _silver_item(
                    item, source, driver, settings, store, embed_client, convert
                )
            except Exception as exc:
                known = isinstance(exc, SourceError | VectorStoreError)
                code = exc.code if known else "ingest_failed"
                if not isinstance(exc, SourceError):
                    log.exception("source_silver_failed source=%s item=%s", source.id, item.id)
                stats.error(item.external_id, code, _detail(exc))
                continue
            if created:
                stats.added += 1
            else:
                stats.updated += 1
    finally:
        await driver.aclose()


async def _silver_item(item, source, driver, settings, store, embed_client, convert):
    payload_path = Path(item.raw_path)
    raw = RawPayload(
        content=await asyncio.to_thread(payload_path.read_bytes),
        ext=payload_path.suffix.lstrip("."),
    )
    ref = ItemRef(
        external_id=item.external_id,
        title=item.title or item.external_id,
        url=item.external_url,
        updated_at=item.external_updated_at,
        space=(item.acl_source or {}).get("space", "default"),
    )
    rendered = driver.render(ref, raw)
    ext = PurePosixPath(rendered.filename).suffix.lower()
    page = payload_path.parent / DOC_DIR / f"{PAGE}{ext}"
    await asyncio.to_thread(_write_atomic, page, rendered.content)
    acl_source = item.acl_source or {}
    names = list(acl_source.get("attachments", []))
    if item.document_id is not None:
        async with db.session_scope() as session:
            document = await session.get(Document, item.document_id)
        if (
            document is not None
            and document.deleted_at is None
            and document.sha256 == _sha256(rendered.content)
        ):
            # Same page bytes (a full silver run, an attachment change): reconvert this
            # document from raw; ingest_from_raw would register a new version (raw_ingest).
            await ingest.ingest_document(
                document.id,
                settings=settings,
                store=store,
                embed_client=embed_client,
                convert=convert,
                attachments=names,
            )
            await _mark_silver(item, document.id)
            return False
    metadata = {
        "kb_id": str(source.kb_id),
        "filename": document_filename(source.key, item.external_id, rendered.filename),
        "source": f"{source.kind}:{ref.space}",
        "source_item_id": str(item.id),
        "data_source_id": str(source.id),
        "source_url": item.external_url,
        "title": item.title,
        "breadcrumb": " › ".join(rendered.breadcrumb) if rendered.breadcrumb else None,
        "updated_at_source": item.external_updated_at.isoformat()
        if item.external_updated_at
        else None,
        "attachments": names,
    }
    metadata = {k: v for k, v in metadata.items() if v is not None}
    document_id = await ingest.ingest_from_raw(
        str(page),
        metadata,
        {"roles": acl_source.get("roles", ["admin"]), "users": acl_source.get("users", [])},
        settings=settings,
        store=store,
        embed_client=embed_client,
        convert=convert,
    )
    return await _mark_silver(item, document_id)


async def _mark_silver(item: SourceItem, document_id: uuid.UUID) -> bool:
    async with db.session_scope() as session:
        row = await session.get(SourceItem, item.id)
        created = row.document_id is None
        row.document_id, row.silver_hash = document_id, item.content_hash
        await session.commit()
    return created


async def _gold(run, source, stats, settings, store, embed_client) -> None:
    async with db.session_scope() as session:
        document_ids = list(
            (
                await session.scalars(
                    select(SourceItem.document_id).where(
                        SourceItem.data_source_id == source.id,
                        SourceItem.state == "active",
                        SourceItem.document_id.is_not(None),
                    )
                )
            ).all()
        )
    report = await ingest.reindex_gold(
        source.kb_id,
        full=run.mode == "full",
        settings=settings,
        store=store,
        embed_client=embed_client,
        document_ids=document_ids,
    )
    stats.listed = report.documents
    stats.updated = report.documents
    stats.reused = report.reused
