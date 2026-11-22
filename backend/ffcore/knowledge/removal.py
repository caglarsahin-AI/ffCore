"""Removing documents from a knowledge base: one order for every caller (K-16-0002 S3 c).

The DELETE endpoint (04a) and a data source's safe delete (16, D4) take the same steps:
1. the vector store first (`remove_vectors`): the pgvector driver writes chunks in its own
   session, which would wait on rows this transaction already deleted, and Qdrant must not keep
   points of a document that is gone; a failure here stops the caller before anything else;
2. the rows (`remove_rows`): `deleted_at`, chunks, live runs that showed the documents end
   `source_deleted` (FOLLOWUP-116), finished runs lose the text they kept (03c, FOLLOWUP-119);
3. silver and text_raw files last (`remove_silver`, FOLLOWUP-133); raw is the caller's choice
   (an upload keeps raw, D3; a source's deleted item loses its raw tree).
"""

import asyncio
import uuid
from collections.abc import Iterable

from sqlalchemy import func, select

from ffcore.knowledge import ingest
from ffcore.knowledge.vectorstore.base import VectorStore
from ffcore.models.knowledge import Attachment, Chunk, Document


async def remove_vectors(store: VectorStore, document_ids: Iterable[uuid.UUID]) -> None:
    """Raises VectorStoreError on the first document the store cannot remove."""
    for document_id in document_ids:
        await store.delete_by_document(document_id)


async def remove_rows(session, document_ids: list[uuid.UUID]) -> None:
    """Steps 2 and 3, in the caller's transaction, after `remove_vectors` succeeded."""
    from ffcore.runtime import checkpoints
    from ffcore.services import retention

    if not document_ids:
        return
    await session.execute(
        Document.__table__.update()
        .where(Document.id.in_(document_ids), Document.deleted_at.is_(None))
        .values(deleted_at=func.now())
    )
    await session.execute(Chunk.__table__.delete().where(Chunk.document_id.in_(document_ids)))
    await checkpoints.mark_document_runs(session, document_ids)
    await retention.clear_document_content(session, document_ids)
    await remove_silver(session, document_ids)


async def remove_silver(session, document_ids: list[uuid.UUID]) -> None:
    """FOLLOWUP-133: silver and text_raw of deleted documents (and their attachments) go.
    Called last, after every database change of the caller."""
    if not document_ids:
        return
    documents = list(
        (await session.scalars(select(Document).where(Document.id.in_(document_ids)))).all()
    )
    attachments = (
        await session.scalars(
            select(Attachment.silver_path).where(Attachment.document_id.in_(document_ids))
        )
    ).all()
    paths = [d.silver_path for d in documents] + list(attachments)
    for document in documents:
        document.silver_path = None
    await session.flush()
    await asyncio.to_thread(ingest.remove_silver, paths)
