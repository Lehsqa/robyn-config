import functools

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from ....config import settings


def build_engine() -> AsyncEngine:
    return create_async_engine(
        settings.database.url,
        future=True,
        pool_pre_ping=True,
        echo=settings.debug,
    )


@functools.lru_cache(maxsize=1)
def create_engine() -> AsyncEngine:
    return build_engine()
