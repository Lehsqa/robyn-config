from typing import Any, AsyncGenerator

from sqlalchemy import Result, select, update

from ...infrastructure.application import DatabaseError, NotFoundError
from ...infrastructure.database import BaseRepository, UsersTable
from .entities import UserFlat, UserUncommitted


class UsersRepository(BaseRepository[UsersTable]):
    schema_class = UsersTable

    async def all(self) -> AsyncGenerator[UserFlat, None]:
        async for instance in self._all():
            yield UserFlat.model_validate(instance)

    async def get(self, id_: int) -> UserFlat:
        instance = await self._get(key="id", value=id_)
        return UserFlat.model_validate(instance)

    async def get_by_login(self, login: str) -> UserFlat:
        query = select(self.schema_class).where(
            (getattr(self.schema_class, "username") == login)
            | (getattr(self.schema_class, "email") == login)
        )
        result: Result = await self.execute(query)
        schema = result.scalars().one_or_none()
        if not schema:
            raise NotFoundError
        return UserFlat.model_validate(schema)

    async def create(self, schema: UserUncommitted) -> UserFlat:
        instance = await self._save(schema.model_dump())
        return UserFlat.model_validate(instance)

    async def update(
        self, attr: str, value: Any, payload: dict[str, Any]
    ) -> UserFlat:
        query = (
            update(self.schema_class)
            .where(getattr(self.schema_class, attr) == value)
            .values(payload)
            .returning(self.schema_class)
        )
        result: Result = await self.execute(query)
        await self._session.flush()
        schema = result.scalar_one_or_none()
        if not schema:
            raise DatabaseError
        return UserFlat.model_validate(schema)
