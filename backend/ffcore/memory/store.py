"""Write and recall (brief 14 "Yazma" 3-6, "Okuma"). API process only: it embeds.

Write, per candidate, in this order; every refusal is counted by reason, nothing is skipped
silently:
1. `kind` outside the effective `allowed_kinds` -> `kind`;
2. `confidence` below the threshold (MEMORY_MIN_CONFIDENCE; "remember this" is 1.0)
   -> `low_confidence`;
3. the PII check (memory.pii) -> `pii`;
4. embedding, then dedupe: a valid `supersedes_id` of the same user, or the most similar active
   item of the same scope with cosine similarity > 0.9, is archived and the new item points to
   it (`supersedes_id`); the old one is never deleted (brief: contradictions);
5. over `max_items_per_user` active items, the least used are archived.

Scope: `profile` and `preference` are valid in every agent of the project (`agent_id` NULL),
`fact` and `decision` only in the agent of the run that taught them.
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ffcore.core.config import Settings
from ffcore.knowledge.embed import embed
from ffcore.memory.pii import check_memory_text
from ffcore.memory.settings import Effective
from ffcore.models.memory import Memory

DEDUPE_SIMILARITY = 0.9
AGENT_SCOPED_KINDS = ("fact", "decision")
REJECT_REASONS = ("kind", "low_confidence", "pii", "invalid")


@dataclass(frozen=True)
class Candidate:
    kind: str
    text: str
    confidence: float
    supersedes_id: str | None = None


@dataclass
class WriteResult:
    written: list[uuid.UUID] = field(default_factory=list)
    archived: list[uuid.UUID] = field(default_factory=list)
    rejected: dict[str, int] = field(default_factory=lambda: dict.fromkeys(REJECT_REASONS, 0))
    # The reference of the last PII refusal (the guardrail event), for the API's 400.
    pii_reference_id: str | None = None

    def summary(self) -> dict:
        """What a run event may carry: ids and counts, never text."""
        return {
            "written": [str(i) for i in self.written],
            "archived": [str(i) for i in self.archived],
            "rejected": dict(self.rejected),
        }


def _now() -> datetime:
    return datetime.now(UTC)


def _scope(kind: str, agent_id) -> uuid.UUID | None:
    if kind in AGENT_SCOPED_KINDS and agent_id is not None:
        return uuid.UUID(str(agent_id))
    return None


def _visible_in(agent_id):
    """Items of every agent (NULL) and of this agent."""
    if agent_id is None:
        return Memory.agent_id.is_(None)
    return or_(Memory.agent_id.is_(None), Memory.agent_id == uuid.UUID(str(agent_id)))


def _live(now: datetime):
    return or_(Memory.expires_at.is_(None), Memory.expires_at > now)


async def _supersede_target(
    session, project_id, user_id, scope, candidate: Candidate, vector
) -> Memory | None:
    owner = (
        Memory.project_id == project_id,
        Memory.user_id == user_id,
        Memory.status == "active",
    )
    if candidate.supersedes_id:
        try:
            wanted = uuid.UUID(candidate.supersedes_id)
        except ValueError:
            wanted = None
        if wanted is not None:
            row = await session.scalar(select(Memory).where(Memory.id == wanted, *owner))
            if row is not None:
                return row
    same_scope = Memory.agent_id.is_(None) if scope is None else Memory.agent_id == scope
    distance = Memory.embedding.cosine_distance(vector)
    row = (
        await session.execute(
            select(Memory, distance.label("d"))
            .where(*owner, same_scope)
            .order_by(distance)
            .limit(1)
        )
    ).first()
    if row is not None and 1 - float(row.d) > DEDUPE_SIMILARITY:
        return row[0]
    return None


async def _enforce_limit(session, project_id, user_id, limit: int) -> list[uuid.UUID]:
    active = await session.scalar(
        select(func.count()).where(
            Memory.project_id == project_id, Memory.user_id == user_id, Memory.status == "active"
        )
    )
    excess = int(active or 0) - limit
    if excess <= 0:
        return []
    ids = list(
        await session.scalars(
            select(Memory.id)
            .where(
                Memory.project_id == project_id,
                Memory.user_id == user_id,
                Memory.status == "active",
            )
            .order_by(Memory.use_count, Memory.last_used_at.asc().nullsfirst(), Memory.created_at)
            .limit(excess)
        )
    )
    await session.execute(
        update(Memory).where(Memory.id.in_(ids)).values(status="archived", updated_at=func.now())
    )
    return ids


async def write(
    session: AsyncSession,
    settings: Settings,
    effective: Effective,
    *,
    project_id,
    user_id,
    agent_id,
    candidates: list[Candidate],
    source_run_id=None,
    min_confidence: float,
) -> WriteResult:
    project_id, user_id = uuid.UUID(str(project_id)), uuid.UUID(str(user_id))
    result = WriteResult()
    kept: list[Candidate] = []
    for candidate in candidates:
        if candidate.kind not in effective.allowed_kinds:
            result.rejected["kind"] += 1
            continue
        if candidate.confidence < min_confidence:
            result.rejected["low_confidence"] += 1
            continue
        checked = await check_memory_text(session, project_id, candidate.text, run_id=source_run_id)
        if checked.blocked:
            result.rejected["pii"] += 1
            result.pii_reference_id = checked.reference_id or result.pii_reference_id
            continue
        kept.append(candidate)
    if not kept:
        return result
    vectors = (await embed(settings, [c.text for c in kept])).dense
    now = _now()
    expires = now + timedelta(days=effective.ttl_days) if effective.ttl_days else None
    for candidate, vector in zip(kept, vectors, strict=True):
        scope = _scope(candidate.kind, agent_id)
        old = await _supersede_target(session, project_id, user_id, scope, candidate, vector)
        item = Memory(
            id=uuid.uuid4(),
            project_id=project_id,
            user_id=user_id,
            agent_id=scope,
            kind=candidate.kind,
            text=candidate.text,
            embedding=vector,
            source_run_id=uuid.UUID(str(source_run_id)) if source_run_id else None,
            confidence=candidate.confidence,
            supersedes_id=old.id if old is not None else None,
            expires_at=expires,
            status="active",
        )
        if old is not None:
            old.status = "archived"
            old.updated_at = now
            result.archived.append(old.id)
        session.add(item)
        await session.flush()
        result.written.append(item.id)
    result.archived.extend(
        await _enforce_limit(session, project_id, user_id, effective.max_items_per_user)
    )
    return result


@dataclass(frozen=True)
class Recalled:
    id: uuid.UUID
    kind: str
    text: str


async def recall(
    session: AsyncSession,
    settings: Settings,
    *,
    project_id,
    user_id,
    agent_id,
    question: str,
    top_k: int,
) -> list[Recalled]:
    """Every active `profile` item, then the `top_k` other items closest to the question; the
    returned items are marked used (`last_used_at`, `use_count`)."""
    project_id, user_id = uuid.UUID(str(project_id)), uuid.UUID(str(user_id))
    now = _now()
    base = (
        Memory.project_id == project_id,
        Memory.user_id == user_id,
        Memory.status == "active",
        _live(now),
        _visible_in(agent_id),
    )
    profiles = list(
        await session.scalars(
            select(Memory).where(*base, Memory.kind == "profile").order_by(Memory.created_at)
        )
    )
    others: list[Memory] = []
    if top_k > 0:
        vector = (await embed(settings, [question])).dense[0]
        others = list(
            await session.scalars(
                select(Memory)
                .where(*base, Memory.kind != "profile")
                .order_by(Memory.embedding.cosine_distance(vector))
                .limit(top_k)
            )
        )
    items = [*profiles, *others]
    if items:
        await session.execute(
            update(Memory)
            .where(Memory.id.in_([m.id for m in items]))
            .values(last_used_at=now, use_count=Memory.use_count + 1)
            .execution_options(synchronize_session=False)
        )
    return [Recalled(m.id, m.kind, m.text) for m in items]


async def related(
    session: AsyncSession, settings: Settings, *, project_id, user_id, agent_id, text: str, n: int
) -> list[Recalled]:
    """The extraction's context (brief: the 5 related items); not marked used."""
    vector = (await embed(settings, [text])).dense[0]
    rows = await session.scalars(
        select(Memory)
        .where(
            Memory.project_id == uuid.UUID(str(project_id)),
            Memory.user_id == uuid.UUID(str(user_id)),
            Memory.status == "active",
            _live(_now()),
            _visible_in(agent_id),
        )
        .order_by(Memory.embedding.cosine_distance(vector))
        .limit(n)
    )
    return [Recalled(m.id, m.kind, m.text) for m in rows]
