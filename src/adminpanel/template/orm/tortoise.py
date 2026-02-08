from typing import Any, List, Type
from .base import BaseORMAdapter
from tortoise.models import Model

class TortoiseAdapter(BaseORMAdapter):
    """Tortoise-ORM适配器"""
    
    async def get_all(self, model: Type[Model], **kwargs) -> List[Model]:
        return await model.all()
        
    async def get_by_id(self, model: Type[Model], id: Any) -> Model:
        return await model.get(id=id)
        
    async def create(self, model: Type[Model], **data) -> Model:
        return await model.create(**data)
        
    async def update(self, instance: Model, **data) -> Model:
        for key, value in data.items():
            setattr(instance, key, value)
        await instance.save()
        return instance
        
    async def delete(self, instance: Model) -> None:
        await instance.delete()