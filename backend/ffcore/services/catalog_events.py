"""Catalog change events: the hook 01's reconciler listens to (providers, assignments, models).

Events are queued on the database session and delivered only after that session commits, so a
rolled-back change never reaches LiteLLM. Listeners are plain callables; one that needs async
work schedules it itself (e.g. an arq job). With no listener registered (before 01 is merged) the
event is logged as `catalog_change_unhandled`, not dropped silently.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

log = logging.getLogger("ffcore.catalog_events")

_KEY = "ffcore_catalog_events"


@dataclass(frozen=True)
class CatalogChanged:
    kind: str  # provider | provider_projects | model
    action: str  # created | updated | deleted
    resource_id: str
    project_id: str | None = None
    # False for models LiteLLM must not serve (embedding runs in process, C10 reversed).
    litellm: bool = True


Listener = Callable[[CatalogChanged], None]
_listeners: list[Listener] = []


def subscribe(listener: Listener) -> None:
    if listener not in _listeners:
        _listeners.append(listener)


def unsubscribe(listener: Listener) -> None:
    if listener in _listeners:
        _listeners.remove(listener)


def publish_on_commit(session: AsyncSession, change: CatalogChanged) -> None:
    sync = session.sync_session
    pending = sync.info.setdefault(_KEY, [])
    if not pending:
        event.listen(sync, "after_commit", _deliver, once=True)
        event.listen(sync, "after_rollback", _discard, once=True)
    pending.append(change)


def _deliver(sync: Session) -> None:
    changes = sync.info.pop(_KEY, [])
    if event.contains(sync, "after_rollback", _discard):
        event.remove(sync, "after_rollback", _discard)
    for change in changes:
        if not _listeners:
            log.warning("catalog_change_unhandled %s", change)
        for listener in list(_listeners):
            listener(change)


def _discard(sync: Session) -> None:
    sync.info.pop(_KEY, None)
    if event.contains(sync, "after_commit", _deliver):
        event.remove(sync, "after_commit", _deliver)
