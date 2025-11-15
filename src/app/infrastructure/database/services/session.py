from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Sequence

from tortoise import connections
from tortoise.backends.base.client import BaseDBAsyncClient
from tortoise.exceptions import OperationalError

from ....infrastructure.application import DatabaseError
from .engine import create_engine

CTX_CONNECTION: ContextVar[BaseDBAsyncClient | None] = ContextVar(
    "tortoise_connection", default=None
)


async def create_session(
    connection: BaseDBAsyncClient | None = None,
) -> BaseDBAsyncClient:
    await create_engine()
    conn = connection
    if conn is None:
        try:
            conn = connections.get("default")
        except KeyError as exc:  # pragma: no cover - defensive
            raise DatabaseError(
                message="Unable to acquire Tortoise connection"
            ) from exc
    CTX_CONNECTION.set(conn)
    return conn


class Session:
    _ERRORS = (OperationalError,)

    def __init__(self) -> None:
        connection = CTX_CONNECTION.get()
        if connection is None:
            raise DatabaseError(
                message="Session requested outside transaction context"
            )
        self._connection: BaseDBAsyncClient = connection
        # Maintain SQLAlchemy parity for downstream consumers.
        self._session: BaseDBAsyncClient = connection

    async def execute(
        self, query: str, values: Sequence[Any] | None = None
    ) -> list[dict[str, Any]]:
        try:
            return await self._connection.execute_query_dict(query, values)
        except self._ERRORS as exc:  # pragma: no cover - defensive
            raise DatabaseError(message=str(exc)) from exc

    @property
    def connection(self) -> BaseDBAsyncClient:
        return self._connection
