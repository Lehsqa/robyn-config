import functools
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import AsyncGenerator

from loguru import logger
from sqlalchemy.exc import IntegrityError, InvalidRequestError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from ..config import settings
from ..utils import BaseError


class DatabaseError(BaseError):
    def __init__(self, message: str = "Database error"):
        super().__init__(message)


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


def create_session() -> AsyncSession:
    Session = async_sessionmaker(
        create_engine(),
        expire_on_commit=False,
        class_=AsyncSession,
    )
    return Session()


@asynccontextmanager
async def transaction() -> AsyncGenerator[AsyncSession, None]:
    session = create_session()
    try:
        yield session
        await session.commit()
    except DatabaseError as exc:
        logger.error(f"Rolling back changes: {exc}")
        await session.rollback()
        raise
    except (IntegrityError, InvalidRequestError) as exc:
        logger.error(f"Rolling back changes: {exc}")
        await session.rollback()
        raise DatabaseError(message=str(exc)) from exc
    finally:
        await session.close()


CTX_SESSION: ContextVar[AsyncSession] = ContextVar(
    "session", default=create_session()
)


class Session:
    _ERRORS = (IntegrityError, InvalidRequestError)

    def __init__(self) -> None:
        self._session: AsyncSession = CTX_SESSION.get()

    async def execute(self, query):
        try:
            return await self._session.execute(query)
        except self._ERRORS as exc:
            raise DatabaseError(message=str(exc)) from exc
