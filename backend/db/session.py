"""
Async SQLAlchemy session factory.

Usage in FastAPI endpoints:
    async def my_endpoint(db: AsyncSession = Depends(get_db)):
        result = await db.execute(select(AnalysisJob))
        ...
"""

import os
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://pharma:pharma@localhost:5432/pharma_guard",
)

engine = create_async_engine(
    DATABASE_URL,
    echo=False,           # set True for SQL query logging in dev
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,   # reconnect on stale connections
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db():
    """FastAPI dependency that yields a database session and closes it after the request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
