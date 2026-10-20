"""
Async SQLAlchemy session factory and dependency injection helper.

Uses asyncpg as the PostgreSQL driver. Sessions are created per-request
via the FastAPI dependency `get_db_session`.
"""

from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_settings = get_settings()

engine_kwargs = {
    "echo": _settings.app_debug and _settings.is_development,
    "pool_pre_ping": True,
}
if "sqlite" not in _settings.database_url:
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20

engine = create_async_engine(
    _settings.database_url,
    **engine_kwargs,
)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an async database session.

    The session is committed on success and rolled back on exception.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_db_connection() -> bool:
    """
    Test database connectivity by executing a trivial query.
    Returns True if the database is reachable, False otherwise.
    """
    try:
        async with engine.connect() as conn:
            await conn.execute(
                __import__("sqlalchemy").text("SELECT 1")
            )
        return True
    except Exception as exc:
        logger.error("database_connection_failed", error=str(exc))
        return False
