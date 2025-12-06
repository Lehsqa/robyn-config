from __future__ import annotations

from typing import Any, AsyncGenerator, Generic, get_args, get_origin

from tortoise.expressions import Q
from tortoise.queryset import QuerySet

from ....infrastructure.application import (
    DatabaseError,
    NotFoundError,
    UnprocessableError,
)
from ..services.session import Session
from ..tables import ConcreteTable


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

    def _query(self) -> QuerySet[ConcreteTable]:
        return self.schema_class.all().using_db(self._connection)

    def _filter(
        self, *expressions: Q, **filters: Any
    ) -> QuerySet[ConcreteTable]:
        return self.schema_class.filter(*expressions, **filters).using_db(
            self._connection
        )

    async def _update(
        self, key: str, value: Any, payload: dict[str, Any]
    ) -> ConcreteTable:
        filters = {key: value}
        updated = await self._filter(**filters).update(**payload)
        if not updated:
            raise DatabaseError
        schema = await self._filter(**filters).first()
        if not schema:
            raise DatabaseError
        return schema

    async def _get(self, key: str, value: Any) -> ConcreteTable:
        schema = await self._filter(**{key: value}).first()
        if not schema:
            raise NotFoundError
        return schema

    async def count(self) -> int:
        value = await self._query().count()
        if not isinstance(value, int):  # pragma: no cover - sanity
            raise UnprocessableError(message=f"Count returned {value}")
        return value

    async def _first(self, by: str = "id") -> ConcreteTable:
        schema = await self._query().order_by(by).first()
        if not schema:
            raise NotFoundError
        return schema

    async def _last(self, by: str = "id") -> ConcreteTable:
        schema = await self._query().order_by(f"-{by}").first()
        if not schema:
            raise NotFoundError
        return schema

    async def _save(self, payload: dict[str, Any]) -> ConcreteTable:
        schema = self.schema_class(**payload)
        await schema.save(using_db=self._connection)
        await schema.refresh_from_db(using_db=self._connection)
        return schema

    async def _all(self) -> AsyncGenerator[ConcreteTable, None]:
        async for schema in self._query():
            yield schema

    async def delete(self, id_: int) -> None:
        await self._filter(id=id_).delete()
