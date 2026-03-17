from __future__ import annotations

from typing import Any, Callable, Type

from tortoise.models import Model

from .base import BaseORMAdapter


class TortoiseAdapter(BaseORMAdapter):
    """Tortoise adapter for generic admin CRUD helpers."""

    def __init__(self, transaction: Callable | None = None) -> None:
        self.transaction = transaction

    async def list(self, model: Type[Model], **filters) -> list[Model]:
        if filters:
            return await model.filter(**filters)
        return await model.all()

    async def get(self, model: Type[Model], **filters) -> Model | None:
        if not filters:
            return None
        return await model.filter(**filters).first()

    async def create(self, model: Type[Model], **data) -> Model:
        async with self.transaction() as connection:
            return await model.create(**data, using_db=connection)

    async def update(
        self, model: Type[Model], identity: Any, **data
    ) -> Model | None:
        async with self.transaction() as connection:
            instance = (
                await model.filter(id=identity).using_db(connection).first()
            )
            if not instance:
                return None
            for key, value in data.items():
                setattr(instance, key, value)
            await instance.save(using_db=connection)
            return instance

    async def delete(self, model: Type[Model], identity: Any) -> bool:
        async with self.transaction() as connection:
            instance = (
                await model.filter(id=identity).using_db(connection).first()
            )
            if not instance:
                return False
            await instance.delete(using_db=connection)
            return True
