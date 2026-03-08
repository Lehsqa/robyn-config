from typing import Any, Type
from .base import BaseORMAdapter
from tortoise.models import Model


class TortoiseAdapter(BaseORMAdapter):
    """Tortoise adapter for generic admin CRUD helpers."""

    async def list(self, model: Type[Model], **filters) -> list[Model]:
        if filters:
            return await model.filter(**filters)
        return await model.all()

    async def get(self, model: Type[Model], **filters) -> Model | None:
        if not filters:
            return None
        return await model.filter(**filters).first()

    async def create(self, model: Type[Model], **data) -> Model:
        return await model.create(**data)

    async def update(
        self, model: Type[Model], identity: Any, **data
    ) -> Model | None:
        instance = await model.filter(id=identity).first()
        if not instance:
            return None
        for key, value in data.items():
            setattr(instance, key, value)
        await instance.save()
        return instance

    async def delete(self, model: Type[Model], identity: Any) -> bool:
        instance = await model.filter(id=identity).first()
        if not instance:
            return False
        await instance.delete()
        return True
