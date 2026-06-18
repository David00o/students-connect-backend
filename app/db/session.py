from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings


def _build_engine():
    url = settings.DATABASE_URL
    # SQLite (used in tests) does not support pool_size/max_overflow
    is_sqlite = url.startswith("sqlite")
    kwargs = {} if is_sqlite else {"pool_size": 10, "max_overflow": 20}
    return create_async_engine(
        url,
        echo=settings.DEBUG,
        pool_pre_ping=not is_sqlite,
        **kwargs,
    )


engine = _build_engine()

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
