import asyncio
import functools
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from loguru import logger
from tortoise import Tortoise
from tortoise.backends.base.client import BaseDBAsyncClient
from tortoise.exceptions import IntegrityError, OperationalError
from tortoise.transactions import in_transaction

from ..config import settings
from ..utils import BaseError


class DatabaseError(BaseError):
    def __init__(self, message: str = "Database error"):
        super().__init__(message)


APP_LABEL = "models"
MODEL_MODULES = (
    "app.models.models",
    "aerich.models",
)
DRIVER_ALIASES = {
    "sqlite+aiosqlite": "sqlite",
    "postgresql+asyncpg": "postgres",
    "mysql+aiomysql": "mysql",
}

_ENGINE_LOCK = asyncio.Lock()
_INITIALIZED = False


def _normalize_database_url(url: str) -> str:
    for candidate, alias in DRIVER_ALIASES.items():
        if url.startswith(candidate):
            return url.replace(candidate, alias, 1)
    return url


def _build_config() -> dict[str, Any]:
    return {
        "connections": {
            "default": _normalize_database_url(settings.database.url)
        },
        "apps": {
            APP_LABEL: {
                "models": list(MODEL_MODULES),
                "default_connection": "default",
            }
        },
        "use_tz": False,
        "timezone": "UTC",
    }


@functools.lru_cache(maxsize=1)
def build_engine() -> dict[str, Any]:
    return _build_config()


TORTOISE_ORM = build_engine()


async def create_engine() -> dict[str, Any]:
    global _INITIALIZED
    if _INITIALIZED:
        return TORTOISE_ORM

    async with _ENGINE_LOCK:
        if not _INITIALIZED:
            await Tortoise.init(config=TORTOISE_ORM)
            _INITIALIZED = True
    return TORTOISE_ORM


async def close_engine() -> None:
    global _INITIALIZED
    if not _INITIALIZED:
        return
    await Tortoise.close_connections()
    _INITIALIZED = False


@asynccontextmanager
async def transaction() -> AsyncGenerator[BaseDBAsyncClient, None]:
    await create_engine()
    async with in_transaction(connection_name="default") as connection:
        try:
            yield connection
        except DatabaseError as exc:
            logger.error(f"Rolling back changes: {exc}")
            raise
        except (IntegrityError, OperationalError) as exc:
            logger.error(f"Rolling back changes: {exc}")
            raise DatabaseError(message=str(exc)) from exc
