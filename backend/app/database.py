"""
backend/app/database.py
────────────────────────
SQLAlchemy async engine and session factory.

Usage in endpoints:
    from app.database import get_db
    from sqlalchemy.ext.asyncio import AsyncSession

    @router.get("/jobs")
    async def get_jobs(db: AsyncSession = Depends(get_db)):
        ...

Usage in workers/scripts (sync):
    from app.database import get_sync_engine
    with get_sync_engine().connect() as conn:
        ...
"""
from functools import lru_cache
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import settings
from app.logger import get_logger

logger = get_logger("database")


# ── Async engine (used by FastAPI endpoints) ───────────────────────
def _make_async_url(url: str) -> str:
    """Convert sync postgres:// URL to async postgresql+asyncpg://"""
    return url.replace("postgresql://", "postgresql+asyncpg://", 1)


engine = create_async_engine(
    _make_async_url(settings.postgres_url),
    echo=settings.is_development,   # log SQL in dev, not in prod
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,             # check connection before use
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── Sync engine (used by Celery tasks / Prefect flows / scripts) ───
# One process-wide engine with a small pool, reused across every task —
# NOT a fresh create_engine() per call. Each Engine owns its own connection
# pool that's never torn down until the process exits, so creating one per
# task invocation leaks connections and can exhaust Postgres max_connections
# under load (100 by default) once enough tasks have run.
@lru_cache(maxsize=1)
def get_sync_engine() -> Engine:
    return create_engine(
        settings.postgres_url,
        pool_size=5,
        max_overflow=5,
        pool_pre_ping=True,
        pool_recycle=1800,
    )


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models. Import this in every model file."""
    pass


async def get_db():
    """
    FastAPI dependency — yields an async database session.
    Automatically commits on success, rolls back on error.

    Usage:
        async def my_endpoint(db: AsyncSession = Depends(get_db)):
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as exc:
            await session.rollback()
            logger.error(
                "Database session error — rolled back",
                extra={"extra": {"error": str(exc)}}
            )
            raise
