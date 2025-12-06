from contextlib import asynccontextmanager
from typing import AsyncGenerator

from loguru import logger
from sqlalchemy.exc import IntegrityError, InvalidRequestError
from sqlalchemy.ext.asyncio import AsyncSession

from ....infrastructure.application import DatabaseError
from .session import CTX_SESSION, create_session


@asynccontextmanager
async def transaction() -> AsyncGenerator[AsyncSession, None]:
    session = create_session()
    CTX_SESSION.set(session)
    try:
        yield session
        await session.commit()
    except DatabaseError as exc:
        logger.error(f"Rolling back changes: {exc}")
        await session.rollback()
        raise
    except (IntegrityError, InvalidRequestError) as exc:  # pragma: no cover
        logger.error(f"Rolling back changes: {exc}")
        await session.rollback()
        raise DatabaseError(message=str(exc)) from exc
    finally:
        await session.close()
