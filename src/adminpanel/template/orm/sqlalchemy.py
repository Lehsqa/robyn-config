from __future__ import annotations

from typing import Any, Callable, Type

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.inspection import inspect as sa_inspect

from .base import BaseORMAdapter


class SQLAlchemyAdapter(BaseORMAdapter):
    """SQLAlchemy adapter for generic admin CRUD helpers."""

    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self.session_factory = session_factory

    async def list(self, model: Type[Any], **filters) -> list[Any]:
        stmt = select(model)
        if filters:
            stmt = stmt.filter_by(**filters)
        session = self.session_factory()
        try:
            result = await session.execute(stmt)
            return list(result.scalars().all())
        finally:
            await session.close()

    async def get(self, model: Type[Any], **filters) -> Any | None:
        rows = await self.list(model, **filters)
        return rows[0] if rows else None

    async def create(self, model: Type[Any], **data) -> Any:
        session = self.session_factory()
        try:
            instance = model(**data)
            session.add(instance)
            await session.commit()
            await session.refresh(instance)
            return instance
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    async def update(
        self, model: Type[Any], identity: Any, **data
    ) -> Any | None:
        session = self.session_factory()
        try:
            pk = _primary_key_name(model)
            stmt = select(model).where(getattr(model, pk) == identity)
            result = await session.execute(stmt)
            instance = result.scalar_one_or_none()
            if not instance:
                return None
            for key, value in data.items():
                setattr(instance, key, value)
            await session.commit()
            await session.refresh(instance)
            return instance
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    async def delete(self, model: Type[Any], identity: Any) -> bool:
        session = self.session_factory()
        try:
            pk = _primary_key_name(model)
            stmt = delete(model).where(getattr(model, pk) == identity)
            result = await session.execute(stmt)
            await session.commit()
            return bool(result.rowcount)
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def _primary_key_name(model: Type[Any]) -> str:
    mapper = sa_inspect(model)
    pk = [column.name for column in mapper.primary_key]
    return pk[0] if pk else "id"
