from __future__ import annotations

from typing import Any, Callable, Type

from sqlalchemy import delete, select
from sqlalchemy.inspection import inspect as sa_inspect

from .base import BaseORMAdapter


class SQLAlchemyAdapter(BaseORMAdapter):
    """SQLAlchemy adapter for generic admin CRUD helpers."""

    def __init__(self, transaction: Callable) -> None:
        self.transaction = transaction

    async def list(self, model: Type[Any], **filters) -> list[Any]:
        stmt = select(model)
        if filters:
            stmt = stmt.filter_by(**filters)
        async with self.transaction() as session:
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get(self, model: Type[Any], **filters) -> Any | None:
        rows = await self.list(model, **filters)
        return rows[0] if rows else None

    async def create(self, model: Type[Any], **data) -> Any:
        async with self.transaction() as session:
            instance = model(**data)
            session.add(instance)
            await session.flush()
            await session.refresh(instance)
            return instance

    async def update(
        self, model: Type[Any], identity: Any, **data
    ) -> Any | None:
        async with self.transaction() as session:
            pk = _primary_key_name(model)
            stmt = select(model).where(getattr(model, pk) == identity)
            result = await session.execute(stmt)
            instance = result.scalar_one_or_none()
            if not instance:
                return None
            for key, value in data.items():
                setattr(instance, key, value)
            await session.flush()
            await session.refresh(instance)
            return instance

    async def delete(self, model: Type[Any], identity: Any) -> bool:
        async with self.transaction() as session:
            pk = _primary_key_name(model)
            stmt = delete(model).where(getattr(model, pk) == identity)
            result = await session.execute(stmt)
            return bool(result.rowcount)


def _primary_key_name(model: Type[Any]) -> str:
    mapper = sa_inspect(model)
    pk = [column.name for column in mapper.primary_key]
    return pk[0] if pk else "id"
