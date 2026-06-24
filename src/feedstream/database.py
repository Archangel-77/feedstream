from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from feedstream.settings import settings

engine = create_async_engine(settings.database_url, echo=False)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


def get_pool_stats() -> dict[str, int]:
    """Return SQLAlchemy pool stats for observability."""
    pool = engine.pool

    stats = {"checked_out": 0, "size": 0, "overflow": 0}
    for field_name, method_name in (
        ("checked_out", "checkedout"),
        ("size", "size"),
        ("overflow", "overflow"),
    ):
        method = getattr(pool, method_name, None)
        if callable(method):
            try:
                stats[field_name] = int(method())
            except Exception:
                stats[field_name] = 0
    return stats
