from __future__ import annotations

import asyncio
import functools
from typing import Any

from tortoise import Tortoise

from ....config import settings

APP_LABEL = "models"
MODEL_MODULES = (
    "app.infrastructure.database.tables",
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
