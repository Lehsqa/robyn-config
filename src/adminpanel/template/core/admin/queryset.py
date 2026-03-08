from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .helpers import _build_filter_expression, _get_model_column


@dataclass
class _QueryState:
    filters: list[Any]
    order: list[Any]
    offset: int
    limit: int | None


class SQLAlchemyQuerySet:
    def __init__(
        self,
        model: type[Any],
        session_factory: Callable[[], AsyncSession],
        state: _QueryState | None = None,
    ) -> None:
        self.model = model
        self.session_factory = session_factory
        self._state = state or _QueryState(
            filters=[], order=[], offset=0, limit=None
        )

    def _clone(self) -> "SQLAlchemyQuerySet":
        return SQLAlchemyQuerySet(
            self.model,
            self.session_factory,
            _QueryState(
                filters=list(self._state.filters),
                order=list(self._state.order),
                offset=self._state.offset,
                limit=self._state.limit,
            ),
        )

    def filter(self, *conditions: Any, **kwargs: Any) -> "SQLAlchemyQuerySet":
        clone = self._clone()
        for condition in conditions:
            if condition is None:
                continue
            clone._state.filters.append(condition)
        for key, value in kwargs.items():
            condition = _build_filter_expression(self.model, key, value)
            if condition is not None:
                clone._state.filters.append(condition)
        return clone

    def order_by(self, *order_fields: str) -> "SQLAlchemyQuerySet":
        clone = self._clone()
        for item in order_fields:
            if not item:
                continue
            if item.startswith("-"):
                column = _get_model_column(self.model, item[1:])
                if column is not None:
                    clone._state.order.append(column.desc())
            else:
                column = _get_model_column(self.model, item)
                if column is not None:
                    clone._state.order.append(column.asc())
        return clone

    def offset(self, value: int) -> "SQLAlchemyQuerySet":
        clone = self._clone()
        clone._state.offset = max(0, int(value))
        return clone

    def limit(self, value: int) -> "SQLAlchemyQuerySet":
        clone = self._clone()
        clone._state.limit = max(0, int(value))
        return clone

    async def count(self) -> int:
        stmt = select(func.count()).select_from(self.model)
        if self._state.filters:
            stmt = stmt.where(and_(*self._state.filters))
        session = self.session_factory()
        try:
            result = await session.execute(stmt)
            count = result.scalar_one_or_none()
            return int(count or 0)
        finally:
            await session.close()

    async def delete(self) -> int:
        stmt = delete(self.model)
        if self._state.filters:
            stmt = stmt.where(and_(*self._state.filters))
        session = self.session_factory()
        try:
            result = await session.execute(stmt)
            await session.commit()
            return int(result.rowcount or 0)
        finally:
            await session.close()

    async def all(self) -> list[Any]:
        stmt = select(self.model)
        if self._state.filters:
            stmt = stmt.where(and_(*self._state.filters))
        if self._state.order:
            stmt = stmt.order_by(*self._state.order)
        if self._state.offset:
            stmt = stmt.offset(self._state.offset)
        if self._state.limit is not None:
            stmt = stmt.limit(self._state.limit)

        session = self.session_factory()
        try:
            result = await session.execute(stmt)
            return list(result.scalars().all())
        finally:
            await session.close()

    async def first(self) -> Any | None:
        rows = await self.limit(1).all()
        return rows[0] if rows else None

    def __await__(self):
        return self.all().__await__()

    def __aiter__(self):
        async def _generator():
            for row in await self.all():
                yield row

        return _generator()

