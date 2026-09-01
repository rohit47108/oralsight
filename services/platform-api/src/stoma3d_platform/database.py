"""Async SQLAlchemy engine, sessions, and Alembic-shared metadata."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from .config import Settings


class Base(DeclarativeBase):
    pass


class Database:
    """Owns one async engine and its session factory for an app instance."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.engine: AsyncEngine = create_async_engine(
            settings.database_url,
            pool_pre_ping=True,
        )
        if settings.database_url.startswith("sqlite+"):
            event.listen(
                self.engine.sync_engine, "connect", _enable_sqlite_foreign_keys
            )
        self.sessions = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

    async def create_schema(self) -> None:
        from . import models  # noqa: F401 - imports every mapped table

        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def drop_schema(self) -> None:
        from . import models  # noqa: F401 - imports every mapped table

        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)

    async def ping(self) -> None:
        async with self.sessions() as session:
            await asyncio.wait_for(
                session.execute(text("SELECT 1")),
                timeout=self.settings.database_ready_timeout_seconds,
            )

    async def dispose(self) -> None:
        await self.engine.dispose()

    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.sessions() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise


def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
