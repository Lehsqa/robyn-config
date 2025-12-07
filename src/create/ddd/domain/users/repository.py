from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator

from .entities import UserFlat, UserUncommitted


class UsersRepository(ABC):
    """Contract that captures user persistence operations."""

    @abstractmethod
    async def all(self) -> AsyncGenerator[UserFlat, None]:
        """Return every user instance."""

    @abstractmethod
    async def get(self, id_: int) -> UserFlat:
        """Return a specific user by identifier."""

    @abstractmethod
    async def get_by_login(self, login: str) -> UserFlat:
        """Return a user matching a login credential."""

    @abstractmethod
    async def create(self, schema: UserUncommitted) -> UserFlat:
        """Persist a new user from the provided schema."""

    @abstractmethod
    async def update(
        self, attr: str, value: Any, payload: dict[str, Any]
    ) -> UserFlat:
        """Update an existing user."""
