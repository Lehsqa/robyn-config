from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from loguru import logger
from tortoise.backends.base.client import BaseDBAsyncClient
from tortoise.exceptions import IntegrityError, OperationalError
from tortoise.transactions import in_transaction

from ....infrastructure.application import DatabaseError
from .engine import create_engine
from .session import CTX_CONNECTION


@asynccontextmanager
async def transaction() -> AsyncGenerator[BaseDBAsyncClient, None]:
    await create_engine()
    async with in_transaction(connection_name="default") as connection:
        token = CTX_CONNECTION.set(connection)
        try:
            yield connection
        except DatabaseError as exc:
            logger.error(f"Rolling back changes: {exc}")
            raise
        except (IntegrityError, OperationalError) as exc:  # pragma: no cover
            logger.error(f"Rolling back changes: {exc}")
            raise DatabaseError(message=str(exc)) from exc
        finally:
            CTX_CONNECTION.reset(token)
