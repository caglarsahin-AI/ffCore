"""`python -m ffcore.cli ingest-raw` (19): a raw-staging tree into one knowledge base.

Each accepted file goes through C6 `ingest_from_raw` with the `pii_regex` filter, always: there is
no option to leave it off (plan/19 şart 1). A file whose bytes are already indexed under the same
name is `unchanged` and not touched again (the second run reports `created 0`). Same bytes in any
other status but `skipped` (a gate decision on these bytes) is `retried`: the pipeline runs again
on the same record, no new version (FOLLOWUP-155: a fixed environment must not leave a failed
document behind a clean-looking run). A file that raises is `failed` in the database with the
exception's class name in `metadata.error_code`, never a message. This process
converts in its own bounded pool and asks the API for embeddings (C10), like the ingest worker.

The report is counts only: outcomes, refusal codes, gate reasons, masked findings per category.
No document text, no title, no person value; an error line names the path, never the content.

The corpus manifest (KARARLAR "M3 korpus kapsamı") fixes what was measured: per source documents
and chunks, current statuses from the database (a re-run counts earlier failures too), the ingest
time and `raw_manifest_sha256` over the sorted `<relpath> <sha256>` lines of the accepted files.
A `--limit` run is `stage0-pipeline-evidence`, never an acceptance corpus.

Personnel-data sources (PRSIM, only with `--accept-personnel-data`, KARARLAR "PRSIM M3 ölçümüne
girer") hold staff data, never customer or card holder data. A card number, IBAN or national id
found in one is taken as customer data: the ingest stops (`customer_data_suspected`, the path,
never the value) and the decision goes back to the user. The staged text is checked before the
document is registered; the masking counts after conversion cover its attachments.
"""

import hashlib
import json
import logging
import os
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select

from ffcore.core import db
from ffcore.core.config import Settings
from ffcore.knowledge import ingest, ingest_mask, raw_staging
from ffcore.knowledge.jobs import get_vector_store
from ffcore.models.identity import Project
from ffcore.models.knowledge import Chunk, Document, KnowledgeBase

TEXT_FILTER = "pii_regex"
CUSTOMER_DATA = ("CREDIT_CARD", "TR_IBAN", "TR_NATIONAL_ID")
# Same bytes in one of these statuses is not retried: indexed is done, skipped is the gates'
# decision on these bytes (it would be the same again).
DONE = ("indexed", "skipped")
log = logging.getLogger("ffcore.knowledge.raw_ingest")


class RawIngestError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code


@dataclass
class RawIngestReport:
    outcomes: Counter = field(default_factory=Counter)  # created, new_version, unchanged, retried
    statuses: Counter = field(default_factory=Counter)  # this run: indexed, skipped, failed, ...
    rejected: Counter = field(default_factory=Counter)  # raw_staging codes
    gates: Counter = field(default_factory=Counter)  # "gate1:boilerplate"
    masked: Counter = field(default_factory=Counter)  # PII category -> findings
    stage: str = "full"
    # Manifest inputs: (relpath, sha256, source) of every accepted file; each document's current
    # status and chunk count, filled after the walk.
    files: list[tuple[str, str, str]] = field(default_factory=list)
    current: dict[str, tuple[str, int]] = field(default_factory=dict)
    ingested_at: str = ""
    personnel_data_sources: set[str] = field(default_factory=set)

    def manifest(self) -> dict:
        sources: dict[str, dict[str, int]] = {}
        for relpath, _, source in self.files:
            entry = sources.setdefault(source, {"documents": 0, "chunks": 0})
            entry["documents"] += 1
            entry["chunks"] += self.current.get(relpath, ("", 0))[1]
        statuses = Counter(status for status, _ in self.current.values())
        listing = "".join(f"{relpath} {sha}\n" for relpath, sha, _ in sorted(self.files))
        return {
            "stage": self.stage,
            "ingested_at": self.ingested_at,
            "text_filter": ingest_mask.resolve(TEXT_FILTER).label,
            "documents": len(self.files),
            "chunks": sum(e["chunks"] for e in sources.values()),
            "sources": dict(sorted(sources.items())),
            "statuses": dict(sorted(statuses.items())),
            "failed": statuses["failed"],
            "timeout": statuses["timeout"],
            "rejected": dict(sorted(self.rejected.items())),
            "personnel_data_sources": sorted(self.personnel_data_sources),
            "raw_manifest_sha256": hashlib.sha256(listing.encode()).hexdigest(),
        }

    def lines(self) -> list[str]:
        def fmt(counter: Counter) -> str:
            return ", ".join(f"{k} {v}" for k, v in sorted(counter.items())) or "-"

        return [
            f"created {self.outcomes['created']}",
            f"new_version {self.outcomes['new_version']}",
            f"unchanged {self.outcomes['unchanged']}",
            f"retried {self.outcomes['retried']}",
            # Every document of the tree as the database has it (the manifest's statuses), not
            # only this run's: an unchanged failure stays visible (FOLLOWUP-155).
            f"status: {fmt(Counter(status for status, _ in self.current.values()))}",
            f"rejected: {fmt(self.rejected)}",
            f"gates: {fmt(self.gates)}",
            f"masked ({TEXT_FILTER}): {fmt(self.masked)}",
            "stage: "
            + (
                "full"
                if self.stage == "full"
                else "stage0-pipeline-evidence (--limit): pipeline evidence, not acceptance"
            ),
        ]


def write_manifest(report: RawIngestReport, path: Path, *, raw_dir: Path) -> None:
    """The manifest as JSON, never under the raw tree (read-only, and the measured source)."""
    base = os.path.realpath(raw_dir)
    target = os.path.realpath(path)
    if target == base or target.startswith(base + os.sep):
        raise RawIngestError("manifest_inside_raw_dir", f"{path} is under --raw-dir")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.manifest(), indent=2, sort_keys=True) + "\n", "utf-8")


async def _kb(project_key: str, kb_key: str) -> KnowledgeBase:
    async with db.session_scope() as session:
        kb = await session.scalar(
            select(KnowledgeBase)
            .join(Project, Project.id == KnowledgeBase.project_id)
            .where(
                Project.key == project_key,
                KnowledgeBase.key == kb_key,
                KnowledgeBase.deleted_at.is_(None),
            )
        )
    if kb is None:
        raise RawIngestError("kb_not_found", f"knowledge base {project_key}/{kb_key} not found")
    return kb


async def _current(kb_id, filename: str):
    async with db.session_scope() as session:
        return (
            await session.execute(
                select(Document.id, Document.sha256, Document.status).where(
                    Document.kb_id == kb_id,
                    Document.filename == filename,
                    Document.deleted_at.is_(None),
                )
            )
        ).first()


async def _clear_error(document_id) -> None:
    """A retry starts clean: the code of the earlier failure would outlive a success."""
    async with db.session_scope() as session:
        document = await session.get(Document, document_id, with_for_update=True)
        if document.meta and "error_code" in document.meta:
            document.meta = {k: v for k, v in document.meta.items() if k != "error_code"}
            await session.commit()


async def _mark_failed(kb_id, filename: str, code: str) -> None:
    """An exception between steps leaves the row where the last commit put it (`gated`,
    `embedding`): it becomes `failed` with the class name, so the database says what the console
    says. No row (the error came before registration): nothing to mark, the count stays."""
    async with db.session_scope() as session:
        document = await session.scalar(
            select(Document).where(
                Document.kb_id == kb_id,
                Document.filename == filename,
                Document.deleted_at.is_(None),
            )
        )
        if document is None:
            return
        document.status = "failed"
        document.error = code
        document.meta = {**(document.meta or {}), "error_code": code}
        await session.commit()


async def _fill_current(report: RawIngestReport, kb_id) -> None:
    names = [relpath for relpath, _, _ in report.files]
    async with db.session_scope() as session:
        rows = await session.execute(
            select(Document.filename, Document.status, func.count(Chunk.id))
            .outerjoin(
                Chunk, (Chunk.document_id == Document.id) & (Chunk.chunk_status != "skipped")
            )
            .where(
                Document.kb_id == kb_id,
                Document.filename.in_(names),
                Document.deleted_at.is_(None),
            )
            .group_by(Document.filename, Document.status)
        )
        report.current = {name: (status, count) for name, status, count in rows}


class InvalidEncoding(ValueError):
    pass


def _text_findings(path: Path, metadata: dict) -> dict[str, int]:
    """Regex PII counts of a staged text file (Markdown/plain) and of its metadata strings
    (r1 MAJOR-2); other formats are checked on their converted text after ingest. Text that is
    not UTF-8 is a coded refusal of that file (r1 MINOR-5), never a traceback for the run."""
    f = ingest_mask.resolve(TEXT_FILTER)
    counts = ingest_mask.mask_metadata(f, metadata)[1]
    if path.suffix.lower() in (".md", ".txt"):
        try:
            text = path.read_text(encoding="utf-8", errors="strict")
        except UnicodeDecodeError:
            raise InvalidEncoding(str(path)) from None
        counts.update(f.apply(text)[1])
    return dict(counts)


def _stop_on_customer_data(relpath: str, counts: dict) -> None:
    found = {k: counts[k] for k in CUSTOMER_DATA if counts.get(k)}
    if found:
        log.error("ingest-raw stopped path=%s customer_data=%s", relpath, sorted(found))
        raise RawIngestError(
            "customer_data_suspected",
            f"{relpath}: {', '.join(f'{k} {v}' for k, v in sorted(found.items()))} in a "
            "personnel-data source; ingest stopped, the decision goes back to the user",
        )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


async def ingest_tree(
    *,
    project_key: str,
    kb_key: str,
    raw_dir: Path,
    acl_roles: list[str],
    sources: list[str],
    limit: int | None,
    settings: Settings,
    embed_client: ingest.EmbedClient | None = None,
    convert: ingest.Converter = ingest.convert_bounded,
    accept_personnel_data: bool = False,
) -> RawIngestReport:
    # before any database or model work
    raw_staging.check_sources(sources, accept_personnel_data=accept_personnel_data)
    if not acl_roles:
        raise RawIngestError("acl_required", "name the roles that may read these documents")
    kb = await _kb(project_key, kb_key)
    store = get_vector_store(settings)
    client = embed_client or ingest.HttpEmbedClient(settings)
    report = RawIngestReport(
        stage="full" if limit is None else "stage0-pipeline-evidence",
        ingested_at=datetime.now(UTC).isoformat(timespec="seconds"),
    )
    entries = raw_staging.iter_staged(
        raw_dir, sources, limit=limit, accept_personnel_data=accept_personnel_data
    )
    for entry in entries:
        if isinstance(entry, raw_staging.Rejected):
            report.rejected[entry.code] += 1
            log.warning("ingest-raw rejected path=%s code=%s", entry.relpath, entry.code)
            continue
        if entry.personnel_data:
            report.personnel_data_sources.add(raw_staging.source_of(entry))
            try:
                findings = _text_findings(
                    entry.path, raw_staging.metadata_for(entry, kb_id=str(kb.id))
                )
            except InvalidEncoding:
                report.rejected["invalid_encoding"] += 1
                log.warning("ingest-raw rejected path=%s code=invalid_encoding", entry.relpath)
                continue
            _stop_on_customer_data(entry.relpath, findings)
        sha256 = _sha256(entry.path)
        report.files.append((entry.relpath, sha256, raw_staging.source_of(entry)))
        existed = await _current(kb.id, entry.relpath)
        same_bytes = existed is not None and existed.sha256 == sha256
        if same_bytes and existed.status in DONE:
            report.outcomes["unchanged"] += 1
            continue
        metadata = raw_staging.metadata_for(entry, kb_id=str(kb.id))
        try:
            if same_bytes:
                # Not through ingest_from_raw: its registration bumps the version even for the
                # same bytes. The record keeps its filter (`metadata.text_filter`).
                await _clear_error(existed.id)
                await ingest.ingest_document(
                    existed.id,
                    settings=settings,
                    store=store,
                    embed_client=client,
                    convert=convert,
                    attachments=list(metadata.get("attachments", [])),
                )
                document_id = existed.id
            else:
                document_id = await ingest.ingest_from_raw(
                    str(entry.path),
                    metadata,
                    {"roles": acl_roles},
                    settings=settings,
                    store=store,
                    embed_client=client,
                    convert=convert,
                    text_filter=TEXT_FILTER,
                )
        except Exception as exc:  # one file must not stop the tree; counted and logged by code
            report.statuses["failed"] += 1
            log.error("ingest-raw failed path=%s error=%s", entry.relpath, type(exc).__name__)
            await _mark_failed(kb.id, entry.relpath, type(exc).__name__)
            continue
        report.outcomes["retried" if same_bytes else "new_version" if existed else "created"] += 1
        async with db.session_scope() as session:
            document = await session.get(Document, document_id)
            report.statuses[document.status] += 1
            for gate in ("gate0", "gate1", "gate2"):
                if getattr(document, f"{gate}_status") == "skipped":
                    # The reason's code only: `duplicate_of:<id>` keeps no document id here.
                    reason = str(getattr(document, f"{gate}_reason")).split(":", 1)[0]
                    report.gates[f"{gate}:{reason}"] += 1
            meta = document.meta or {}
            counts = Counter(meta.get("text_filter_counts") or {})
            counts.update(meta.get("text_filter_meta_counts") or {})
            report.masked.update(counts)
        if entry.personnel_data:
            _stop_on_customer_data(entry.relpath, counts)
    await _fill_current(report, kb.id)
    return report
