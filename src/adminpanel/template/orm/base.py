from abc import ABC, abstractmethod
from typing import Any, Type

class BaseORMAdapter(ABC):
    """ORM adapter base for admin data operations."""

    @abstractmethod
    async def list(self, model: Type[Any], **filters) -> list[Any]:
        """Return model rows matching filters."""
        raise NotImplementedError

    @abstractmethod
    async def get(self, model: Type[Any], **filters) -> Any | None:
        """Return one model row matching filters."""
        raise NotImplementedError

    @abstractmethod
    async def create(self, model: Type[Any], **data) -> Any:
        """Create a model row."""
        raise NotImplementedError

    @abstractmethod
    async def update(self, model: Type[Any], identity: Any, **data) -> Any | None:
        """Update a model row by identity."""
        raise NotImplementedError

    @abstractmethod
    async def delete(self, model: Type[Any], identity: Any) -> bool:
        """Delete a model row by identity."""
        raise NotImplementedError
