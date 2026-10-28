"""Async database access (SQLAlchemy 2 asyncio over psycopg 3)."""

from collections.abc import AsyncIterator

from sqlalchemy import Select, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from ffcore.core.config import get_settings

__all__ = [
    "configure",
    "get_engine",
    "get_session",
    "reset",
    "scoped_to_project",
    "session_scope",
    "text",
]

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def configure(url: str, *, pooled: bool = True) -> None:
    """Bind the process to one database. `pooled=False` for tests that run several event loops."""
    global _engine, _sessionmaker
    kwargs = {} if pooled else {"poolclass": NullPool}
    _engine = create_async_engine(url, pool_pre_ping=pooled, **kwargs)
    _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)


def reset() -> None:
    global _engine, _sessionmaker
    _engine = None
    _sessionmaker = None


def _ensure_configured() -> async_sessionmaker[AsyncSession]:
    if _sessionmaker is None:
        url = get_settings().database_url
        if url is None:
            raise RuntimeError("DATABASE_URL is not set; the backend needs a database")
        configure(url.get_secret_value())
    assert _sessionmaker is not None
    return _sessionmaker


def get_engine() -> AsyncEngine:
    _ensure_configured()
    assert _engine is not None
    return _engine


def session_scope() -> AsyncSession:
    """A new session outside a request (detached audit writes, startup jobs)."""
    return _ensure_configured()()


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency. Rolls back whatever was not committed; @audited commits mutations."""
    async with _ensure_configured()() as session:
        yield session


def scoped_to_project(statement: Select, model, project_id) -> Select:
    """Mandatory project filter for project-owned tables (C3); a missing project is an error."""
    if project_id is None:
        raise ValueError(f"project_id is required to query {model.__tablename__}")
    return statement.where(model.project_id == project_id)
