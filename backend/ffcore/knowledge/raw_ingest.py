"""`python -m ffcore.cli ingest-raw` (19): a raw-staging tree into one knowledge base.

Each accepted file goes through C6 `ingest_from_raw` with the `pii_regex` filter, always: there is
no option to leave it off (plan/19 şart 1). A file whose bytes are already indexed under the same
name is `unchanged` and not touched again (the second run reports `created 0`). This process
converts in its own bounded pool and asks the API for embeddings (C10), like the ingest worker.

The report is counts only: outcomes, refusal codes, gate reasons, masked findings per category.
No document text, no title, no person value; an error line names the path, never the content.
"""

import hashlib
import logging
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select

from ffcore.core import db
from ffcore.core.config import Settings
from ffcore.knowledge import ingest, raw_staging
from ffcore.knowledge.jobs import get_vector_store
from ffcore.models.identity import Project
from ffcore.models.knowledge import Document, KnowledgeBase

TEXT_FILTER = "pii_regex"
log = logging.getLogger("ffcore.knowledge.raw_ingest")


class RawIngestError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code


@dataclass
class RawIngestReport:
    outcomes: Counter = field(default_factory=Counter)  # created, new_version, unchanged
    statuses: Counter = field(default_factory=Counter)  # indexed, skipped, failed, timeout
    rejected: Counter = field(default_factory=Counter)  # raw_staging codes
    gates: Counter = field(default_factory=Counter)  # "gate1:boilerplate"
    masked: Counter = field(default_factory=Counter)  # PII category -> findings

    def lines(self) -> list[str]:
        def fmt(counter: Counter) -> str:
            return ", ".join(f"{k} {v}" for k, v in sorted(counter.items())) or "-"

        return [
            f"created {self.outcomes['created']}",
            f"new_version {self.outcomes['new_version']}",
            f"unchanged {self.outcomes['unchanged']}",
            f"status: {fmt(self.statuses)}",
            f"rejected: {fmt(self.rejected)}",
            f"gates: {fmt(self.gates)}",
            f"masked ({TEXT_FILTER}): {fmt(self.masked)}",
        ]


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


async def _indexed_unchanged(kb_id, filename: str, sha256: str) -> bool:
    async with db.session_scope() as session:
        current = await session.scalar(
            select(Document.sha256).where(
                Document.kb_id == kb_id,
                Document.filename == filename,
                Document.deleted_at.is_(None),
            )
        )
    return current == sha256


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
) -> RawIngestReport:
    raw_staging.check_sources(sources)  # before any database or model work
    if not acl_roles:
        raise RawIngestError("acl_required", "name the roles that may read these documents")
    kb = await _kb(project_key, kb_key)
    store = get_vector_store(settings)
    client = embed_client or ingest.HttpEmbedClient(settings)
    report = RawIngestReport()
    for entry in raw_staging.iter_staged(raw_dir, sources, limit=limit):
        if isinstance(entry, raw_staging.Rejected):
            report.rejected[entry.code] += 1
            log.warning("ingest-raw rejected path=%s code=%s", entry.relpath, entry.code)
            continue
        if await _indexed_unchanged(kb.id, entry.relpath, _sha256(entry.path)):
            report.outcomes["unchanged"] += 1
            continue
        async with db.session_scope() as session:
            existed = await session.scalar(
                select(Document.id).where(
                    Document.kb_id == kb.id,
                    Document.filename == entry.relpath,
                    Document.deleted_at.is_(None),
                )
            )
        try:
            document_id = await ingest.ingest_from_raw(
                str(entry.path),
                raw_staging.metadata_for(entry, kb_id=str(kb.id)),
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
            continue
        report.outcomes["new_version" if existed else "created"] += 1
        async with db.session_scope() as session:
            document = await session.get(Document, document_id)
            report.statuses[document.status] += 1
            for gate in ("gate0", "gate1", "gate2"):
                if getattr(document, f"{gate}_status") == "skipped":
                    # The reason's code only: `duplicate_of:<id>` keeps no document id here.
                    reason = str(getattr(document, f"{gate}_reason")).split(":", 1)[0]
                    report.gates[f"{gate}:{reason}"] += 1
            report.masked.update((document.meta or {}).get("text_filter_counts") or {})
    return report
