"""The effective memory settings of a run and the member's opt-out (K-14-0003 S2, S5).

The agent's row wins, else the project's, else the code default: memory **off** (S2, ARCH-10:
an administrator turns it on, the choice is shown). Turning memory on needs the installation's
NER model (S3): without it person names could not be checked, so the request is refused
(422 `memory_requires_ner`) instead of writing items with a weaker check.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ffcore.models.memory import (
    DEFAULT_EXTRACTION_MODEL,
    DEFAULT_MAX_ITEMS,
    DEFAULT_TOP_K,
    KINDS,
    MemoryOptOut,
    MemorySetting,
)


@dataclass(frozen=True)
class Effective:
    enabled: bool
    allowed_kinds: tuple[str, ...]
    max_items_per_user: int
    recall_top_k: int
    ttl_days: int | None
    extraction_model: str
    # Where the values came from: "agent", "project" or "default".
    source: str


DEFAULT = Effective(
    enabled=False,
    allowed_kinds=KINDS,
    max_items_per_user=DEFAULT_MAX_ITEMS,
    recall_top_k=DEFAULT_TOP_K,
    ttl_days=None,
    extraction_model=DEFAULT_EXTRACTION_MODEL,
    source="default",
)


def _of(row: MemorySetting, source: str) -> Effective:
    return Effective(
        enabled=row.enabled,
        allowed_kinds=tuple(row.allowed_kinds),
        max_items_per_user=row.max_items_per_user,
        recall_top_k=row.recall_top_k,
        ttl_days=row.ttl_days,
        extraction_model=row.extraction_model,
        source=source,
    )


async def setting_row(session: AsyncSession, project_id, agent_id=None) -> MemorySetting | None:
    query = select(MemorySetting).where(MemorySetting.project_id == uuid.UUID(str(project_id)))
    if agent_id is None:
        query = query.where(MemorySetting.agent_id.is_(None))
    else:
        query = query.where(MemorySetting.agent_id == uuid.UUID(str(agent_id)))
    return await session.scalar(query)


async def effective(session: AsyncSession, project_id, agent_id=None) -> Effective:
    if agent_id is not None:
        row = await setting_row(session, project_id, agent_id)
        if row is not None:
            return _of(row, "agent")
    row = await setting_row(session, project_id)
    if row is not None:
        return _of(row, "project")
    return DEFAULT


async def opted_out(session: AsyncSession, project_id, user_id) -> bool:
    row = await session.get(MemoryOptOut, (uuid.UUID(str(project_id)), uuid.UUID(str(user_id))))
    return row is not None


async def off_reason(session: AsyncSession, project_id, agent_id, user_id) -> str | None:
    """Why memory does nothing for this run (None: it works): `no_user`, `off`, `opt_out`."""
    if user_id is None:
        return "no_user"
    if not (await effective(session, project_id, agent_id)).enabled:
        return "off"
    if await opted_out(session, project_id, user_id):
        return "opt_out"
    return None
