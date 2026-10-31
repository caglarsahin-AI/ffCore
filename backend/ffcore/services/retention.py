"""Retention (03c, R2.2): the `content` class's clear_content and FOLLOWUP-119.

`content` keeps prompt and answer text for `keep_days` (30) after a run ended, then clears it;
metrics (tokens, timing, outcome, sources' public fields) stay. Deleting a document clears the
text of every finished run that showed it as a source at once (the live ones end
`source_deleted` through FOLLOWUP-116 and are cleared by the sweep after that). The text places
are listed in `TEXT_FIELDS` (state/pr/03c.md "03c-2 plan", tip tablosu); `tool_result`,
`user_answer` and `error` carry no text. A cleared value is `"[cleared]"` (objects:
`{"_cleared": true}`) and the run is stamped `content_cleared_at`, so a second pass is a no-op.
"""

import logging
import uuid
from collections.abc import Iterable

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from ffcore.models.runs import Run
from ffcore.runtime.checkpoints import _shows_document
from ffcore.runtime.contracts import FINISHED

log = logging.getLogger("ffcore.retention")

CLEARED = "[cleared]"
# run_events type -> payload key holding text, and whether it is an object (arguments).
TEXT_FIELDS = {
    "llm_call": ("request_messages", False),
    "answer": ("text", False),
    "question": ("question", False),
    "tool_call": ("arguments", True),
    "approval_requested": ("arguments", True),
}
_EVENT_SQL = text(
    """
    UPDATE run_events SET payload = jsonb_set(payload, CAST(:path AS text[]),
        CAST(:value AS jsonb))
    WHERE run_id = ANY(:run_ids) AND type = :type AND payload ? :key
    """
)


async def clear_runs_content(
    session: AsyncSession, run_ids: Iterable, *, include_user_text: bool
) -> dict[str, int]:
    """Clear the text of these runs in every place; returns counts per place (no content).

    `include_user_text`: the time trigger also clears the user's own words (`runs.input`, the
    user message); a document delete clears only what could hold the document's text."""
    ids = [uuid.UUID(str(i)) for i in run_ids]
    counts: dict[str, int] = {}
    if not ids:
        return counts
    for kind, (key, is_object) in TEXT_FIELDS.items():
        value = '{"_cleared": true}' if is_object else f'"{CLEARED}"'
        result = await session.execute(
            _EVENT_SQL,
            {"path": [key], "value": value, "run_ids": ids, "type": kind, "key": key},
        )
        counts[f"run_events.{kind}"] = result.rowcount
    values = {"output": text(f"CASE WHEN output IS NULL THEN NULL ELSE '{CLEARED}' END")}
    if include_user_text:
        values["input"] = CLEARED
    result = await session.execute(
        update(Run)
        .where(Run.id.in_(ids))
        .values(**values, content_cleared_at=text("now()"))
        .execution_options(synchronize_session=False)
    )
    counts["runs"] = result.rowcount
    roles = "" if include_user_text else " AND role = 'assistant'"
    result = await session.execute(
        text(f"UPDATE messages SET content = :cleared WHERE run_id = ANY(:run_ids){roles}"),
        {"cleared": CLEARED, "run_ids": ids},
    )
    counts["messages"] = result.rowcount
    result = await session.execute(
        text(
            "UPDATE approvals SET arguments = '{\"_cleared\": true}'::jsonb"
            " WHERE run_id = ANY(:run_ids)"
        ),
        {"run_ids": ids},
    )
    counts["approvals"] = result.rowcount
    return counts


async def runs_showing_documents(session: AsyncSession, document_ids: Iterable) -> list:
    """Finished runs whose sources listed one of the documents (116's containment test)."""
    ids = [str(i) for i in document_ids]
    if not ids:
        return []
    rows = await session.scalars(
        select(Run.id).where(Run.status.in_(FINISHED), _shows_document(ids))
    )
    return list(rows)


async def clear_document_content(session: AsyncSession, document_ids: Iterable) -> dict:
    """FOLLOWUP-119 document trigger, in the document delete's transaction."""
    run_ids = await runs_showing_documents(session, document_ids)
    counts = await clear_runs_content(session, run_ids, include_user_text=False)
    if run_ids:
        log.info("content_cleared_for_deleted_document runs=%s", len(run_ids))
    return counts


async def sweep_source_deleted(session: AsyncSession) -> int:
    """Runs closed `source_deleted` after the document delete (116 sweep): clear them too."""
    rows = await session.scalars(
        select(Run.id).where(
            Run.source_deleted_at.is_not(None),
            Run.status.in_(FINISHED),
            Run.content_cleared_at.is_(None),
        )
    )
    run_ids = list(rows)
    await clear_runs_content(session, run_ids, include_user_text=False)
    return len(run_ids)
