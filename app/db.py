from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .settings import settings


# API (async)
async_engine = create_async_engine(settings.ASYNC_DATABASE_URL, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False)


async def get_async_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session

# Worker (sync)
sync_engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SyncSessionLocal = sessionmaker(bind=sync_engine, autocommit=False, autoflush=False)
