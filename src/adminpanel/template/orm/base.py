from abc import ABC, abstractmethod
from typing import Any, List, Dict, Type

class BaseORMAdapter(ABC):
    """ORM适配器基类"""
    
    @abstractmethod
    async def get_all(self, model: Type[Any], **kwargs) -> List[Any]:
        """获取所有记录"""
        pass
        
    @abstractmethod
    async def get_by_id(self, model: Type[Any], id: Any) -> Any:
        """通过ID获取记录"""
        pass
        
    @abstractmethod
    async def create(self, model: Type[Any], **data) -> Any:
        """创建记录"""
        pass
        
    @abstractmethod
    async def update(self, instance: Any, **data) -> Any:
        """更新记录"""
        pass
        
    @abstractmethod
    async def delete(self, instance: Any) -> None:
        """删除记录"""
        pass