from typing import Any, AsyncGenerator

from ....domain.users import UsersRepository as UsersRepositoryInterface
from ....domain.users.entities import UserFlat, UserUncommitted
from ..tables import UsersTable
from .base import BaseRepository


class UsersRepository(BaseRepository[UsersTable], UsersRepositoryInterface):
    async def all(self) -> AsyncGenerator[UserFlat, None]:
        async for instance in self._all():
            yield UserFlat.model_validate(instance)

    async def get(self, id_: int) -> UserFlat:
        instance = await self._get(key="id", value=id_)
        return UserFlat.model_validate(instance)

    async def get_by_login(self, login: str) -> UserFlat:
        instance = await self._get(key="username", value=login)
        return UserFlat.model_validate(instance)

    async def create(self, schema: UserUncommitted) -> UserFlat:
        instance = await self._save(schema.model_dump())
        return UserFlat.model_validate(instance)

    async def update(
        self, attr: str, value: Any, payload: dict[str, Any]
    ) -> UserFlat:
        schema = await self._update(attr, value, payload)
        return UserFlat.model_validate(schema)
