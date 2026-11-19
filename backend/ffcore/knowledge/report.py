"""Ingest report (brief 04 "Rapor", FOLLOWUP-86): source x gate x reason counts and the
rejected documents and chunks with their reasons.

The counts have the shape of the `ingest_gate_stats` view (one row per document and gate, so
per gate they add up to the documents) but are computed here under the caller's document ACL:
the view has no ACL columns, and a report must not count what its reader may not see (C15).
"""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import case, func, literal, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from ffcore.models.knowledge import Chunk, Document

GATES = ("gate0", "gate1", "gate2")


@dataclass
class GateReport:
    documents: int
    by_status: dict[str, int]
    gates: list[dict]
    rejected_documents: list[dict]
    rejected_documents_total: int
    rejected_chunks: list[dict]
    rejected_chunks_total: int


def _source():
    return func.coalesce(Document.meta["source"].astext, literal("upload"))


def _first_skipped_gate():
    """gate0 before gate1 before gate2: the gate that took the document out."""
    return case(
        (Document.gate0_status == "skipped", literal("gate0")),
        (Document.gate1_status == "skipped", literal("gate1")),
        (Document.gate2_status == "skipped", literal("gate2")),
        else_=None,
    )


async def gate_report(session: AsyncSession, kb_id: UUID, visible, *, limit: int) -> GateReport:
    live = [Document.kb_id == kb_id, Document.deleted_at.is_(None), visible]
    documents = await session.scalar(select(func.count()).select_from(Document).where(*live))
    by_status = dict(
        (
            await session.execute(
                select(Document.status, func.count()).where(*live).group_by(Document.status)
            )
        ).all()
    )
    per_gate = union_all(
        *(
            select(
                _source().label("source"),
                literal(gate).label("gate"),
                getattr(Document, f"{gate}_status").label("status"),
                getattr(Document, f"{gate}_reason").label("reason"),
            ).where(*live)
            for gate in GATES
        )
    ).subquery()
    gate_rows = (
        await session.execute(
            select(
                per_gate.c.source,
                per_gate.c.gate,
                per_gate.c.status,
                per_gate.c.reason,
                func.count().label("documents"),
            )
            .group_by(per_gate.c.source, per_gate.c.gate, per_gate.c.status, per_gate.c.reason)
            .order_by(per_gate.c.gate, per_gate.c.source, per_gate.c.status, per_gate.c.reason)
        )
    ).all()
    first = _first_skipped_gate()
    rejected = [*live, first.is_not(None)]
    rejected_total = await session.scalar(
        select(func.count()).select_from(Document).where(*rejected)
    )
    doc_rows = (
        await session.execute(
            select(
                Document.id,
                Document.filename,
                _source(),
                Document.status,
                first,
                Document.gate0_reason,
                Document.gate1_reason,
                Document.gate2_reason,
            )
            .where(*rejected)
            .order_by(Document.filename, Document.id)
            .limit(limit)
        )
    ).all()
    chunk_where = [*live, Chunk.chunk_status == "skipped"]
    chunk_total = await session.scalar(
        select(func.count())
        .select_from(Chunk)
        .join(Document, Document.id == Chunk.document_id)
        .where(*chunk_where)
    )
    chunk_rows = (
        await session.execute(
            select(
                Chunk.id, Chunk.document_id, Document.filename, Chunk.ordinal, Chunk.chunk_reason
            )
            .join(Document, Document.id == Chunk.document_id)
            .where(*chunk_where)
            .order_by(Document.filename, Chunk.ordinal, Chunk.id)
            .limit(limit)
        )
    ).all()
    return GateReport(
        documents=documents,
        by_status=by_status,
        gates=[r._asdict() for r in gate_rows],
        rejected_documents=[
            {
                "document_id": r[0],
                "filename": r[1],
                "source": r[2],
                "status": r[3],
                "gate": r[4],
                "reason": {"gate0": r[5], "gate1": r[6], "gate2": r[7]}[r[4]],
            }
            for r in doc_rows
        ],
        rejected_documents_total=rejected_total,
        rejected_chunks=[
            {
                "chunk_id": r[0],
                "document_id": r[1],
                "filename": r[2],
                "ordinal": r[3],
                "reason": r[4],
            }
            for r in chunk_rows
        ],
        rejected_chunks_total=chunk_total,
    )
