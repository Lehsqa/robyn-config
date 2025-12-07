from typing import Any, AsyncGenerator, Generic, get_args, get_origin

from sqlalchemy import asc, delete, desc, func, select, update
from sqlalchemy.engine import Result

from ..schemas import UserFlat, UserUncommitted
from ..utils import DatabaseError, NotFoundError, UnprocessableError
from .database import Session
from .models import ConcreteTable, UsersTable


class BaseRepository(Session, Generic[ConcreteTable]):
    schema_class: type[ConcreteTable] | None = None

    def __init__(self) -> None:
        super().__init__()
        if not getattr(self, "schema_class", None):
            raise UnprocessableError(message="schema_class is required")

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        if cls is BaseRepository:
            return
        if cls.schema_class is None:
            for base in getattr(cls, "__orig_bases__", ()):
                if get_origin(base) is BaseRepository:
                    args = get_args(base)
                    if args:
                        cls.schema_class = args[0]
                        break
        if cls.schema_class is None:
            raise UnprocessableError(message="schema_class is required")

    async def _filter(self, **filters: Any) -> ConcreteTable:
        query = select(self.schema_class).filter_by(**filters)
        result: Result = await self.execute(query)
        schema = result.scalar_one_or_none()
        if not schema:
            raise NotFoundError
        return schema

    async def _update(
        self, key: str, value: Any, payload: dict[str, Any]
    ) -> ConcreteTable:
        query = (
            update(self.schema_class)
            .where(getattr(self.schema_class, key) == value)
            .values(payload)
            .returning(self.schema_class)
        )
        result: Result = await self.execute(query)
        await self._session.flush()

        schema = result.scalar_one_or_none()
        if not schema:
            raise DatabaseError
        return schema

    async def _get(self, key: str, value: Any) -> ConcreteTable:
        query = select(self.schema_class).where(
            getattr(self.schema_class, key) == value
        )
        result: Result = await self.execute(query)
        schema = result.scalars().one_or_none()
        if not schema:
            raise NotFoundError
        return schema

    async def count(self) -> int:
        result: Result = await self.execute(func.count(self.schema_class.id))
        value = result.scalar()
        if not isinstance(value, int):
            raise UnprocessableError(message=f"Count returned {value}")
        return value

    async def _first(self, by: str = "id") -> ConcreteTable:
        result: Result = await self.execute(
            select(self.schema_class).order_by(asc(by)).limit(1)
        )
        schema = result.scalar_one_or_none()
        if not schema:
            raise NotFoundError
        return schema

    async def _last(self, by: str = "id") -> ConcreteTable:
        result: Result = await self.execute(
            select(self.schema_class).order_by(desc(by)).limit(1)
        )
        schema = result.scalar_one_or_none()
        if not schema:
            raise NotFoundError
        return schema

    async def _save(self, payload: dict[str, Any]) -> ConcreteTable:
        schema = self.schema_class(**payload)
        self._session.add(schema)
        await self._session.flush()
        await self._session.refresh(schema)
        return schema

    async def _all(self) -> AsyncGenerator[ConcreteTable, None]:
        result: Result = await self.execute(select(self.schema_class))
        for schema in result.scalars().all():
            yield schema

    async def delete(self, id_: int) -> None:
        await self.execute(
            delete(self.schema_class).where(self.schema_class.id == id_)
        )
        await self._session.flush()


class UsersRepository(BaseRepository[UsersTable]):
    async def all(self) -> AsyncGenerator[UserFlat, None]:
        async for instance in self._all():
            yield UserFlat.model_validate(instance)

    async def get(self, id_: int) -> UserFlat:
        instance = await self._get(key="id", value=id_)
        return UserFlat.model_validate(instance)

    async def get_by_login(self, login: str) -> UserFlat:
        for field in ("username", "email"):
            try:
                instance = await self._get(key=field, value=login)
                return UserFlat.model_validate(instance)
            except NotFoundError:
                continue
        raise NotFoundError

    async def create(self, schema: UserUncommitted) -> UserFlat:
        instance = await self._save(schema.model_dump())
        return UserFlat.model_validate(instance)

    async def update(
        self, attr: str, value: Any, payload: dict[str, Any]
    ) -> UserFlat:
        schema = await self._update(attr, value, payload)
        return UserFlat.model_validate(schema)
