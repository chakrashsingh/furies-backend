"""
app/core/database.py
────────────────────
Async SQLAlchemy engine + session factory.

Usage in routers:
    async def my_route(db: AsyncSession = Depends(get_db)):
        ...
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# ── Engine ────────────────────────────────────────────────────────────────────
# pool_pre_ping=True validates connections before use (guards against stale ones)
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,          # log SQL in development
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# ── Session factory ───────────────────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,       # keep objects usable after commit
    autoflush=False,
    autocommit=False,
)


# ── Base model class ──────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    """
    All ORM models inherit from this Base.
    Import this in every model file so Alembic can discover tables.
    """
    pass


# ── Dependency ────────────────────────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides a scoped DB session per request.
    Automatically rolls back on exception and always closes the session.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
