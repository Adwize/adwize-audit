from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from storage.config import database_url
from storage.models import Base

_engine = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def _get_engine():
    global _engine, _sessionmaker
    if _engine is None:
        _engine = create_async_engine(database_url(), pool_pre_ping=True)
        _sessionmaker = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)
    return _engine


def _migrate_columns(conn) -> None:
    """Add columns introduced after initial release. SQLite ALTER TABLE ADD COLUMN is safe."""
    inspector = sa.inspect(conn)
    existing = {c["name"] for c in inspector.get_columns("audit_runs")}
    if "analysis_status" not in existing:
        conn.execute(sa.text("ALTER TABLE audit_runs ADD COLUMN analysis_status VARCHAR(32)"))
    if "analysis_detail" not in existing:
        conn.execute(sa.text("ALTER TABLE audit_runs ADD COLUMN analysis_detail TEXT"))


async def init_db() -> None:
    """Create tables if missing and migrate schema for existing DBs."""
    engine = _get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_migrate_columns)


@asynccontextmanager
async def session() -> AsyncGenerator[AsyncSession, None]:
    _get_engine()
    assert _sessionmaker is not None
    async with _sessionmaker() as s:
        yield s
