"""Retention class `memory` (03c, brief 14: 365 days, 30-1095; K-14-0003).

An item goes when it was neither changed nor used for `keep_days` (the later of `updated_at` and
`last_used_at` before the cutoff), or when its own `expires_at` (the settings' `ttl_days`)
passed. Deleting is the class's behaviour (`delete`); a user's own delete is immediate and
does not wait for this pass. The dry run counts.
"""

from datetime import UTC, datetime

from sqlalchemy import func, or_

from ffcore.models.memory import Memory
from ffcore.services import retention_job


async def retention_executor(session, project_id, overridden, cutoff, dry_run, batch) -> dict:
    touched = func.greatest(
        Memory.updated_at, func.coalesce(Memory.last_used_at, Memory.updated_at)
    )
    where = retention_job._scope(Memory.project_id, project_id, overridden) & or_(
        touched < cutoff, Memory.expires_at < datetime.now(UTC)
    )
    n = await retention_job._delete_where(
        session, Memory.__table__, Memory.id, where, dry_run, batch
    )
    return {"memories": n}


def _register() -> None:
    retention_job.register("memory", retention_executor)


_register()
