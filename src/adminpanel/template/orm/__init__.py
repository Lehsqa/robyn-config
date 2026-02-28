from __future__ import annotations

from typing import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from .base import BaseORMAdapter
from .sqlalchemy import SQLAlchemyAdapter
from .tortoise import TortoiseAdapter


def resolve_adapter(
    orm: str,
    *,
    session_factory: Callable[[], AsyncSession] | None = None,
) -> BaseORMAdapter:
    if orm == "tortoise":
        return TortoiseAdapter()
    if orm == "sqlalchemy":
        if session_factory is None:
            raise ValueError("session_factory is required for sqlalchemy adapter")
        return SQLAlchemyAdapter(session_factory=session_factory)
    raise ValueError(f"Unsupported ORM adapter: {orm}")


__all__ = ["BaseORMAdapter", "TortoiseAdapter", "SQLAlchemyAdapter", "resolve_adapter"]
