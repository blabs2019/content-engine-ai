from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

from app.config import get_settings

settings = get_settings()

# Sync engine (used by Alembic migrations)
sync_engine = create_engine(settings.DATABASE_URL, echo=settings.DEBUG)
SyncSessionLocal = sessionmaker(bind=sync_engine, class_=Session)

# Async engine (used by FastAPI)
async_engine = create_async_engine(settings.ASYNC_DATABASE_URL, echo=settings.DEBUG)
AsyncSessionLocal = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
