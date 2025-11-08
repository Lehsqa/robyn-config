from contextvars import ContextVar

from sqlalchemy.exc import IntegrityError, InvalidRequestError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from ....infrastructure.application import DatabaseError
from .engine import create_engine


def create_session(engine: AsyncEngine | None = None) -> AsyncSession:
    return AsyncSession(
        engine or create_engine(), expire_on_commit=False, autoflush=False
    )


CTX_SESSION: ContextVar[AsyncSession] = ContextVar(
    "session", default=create_session()
)


class Session:
    _ERRORS = (IntegrityError, InvalidRequestError)

    def __init__(self) -> None:
        self._session: AsyncSession = CTX_SESSION.get()

    async def execute(self, query):
        try:
            return await self._session.execute(query)
        except self._ERRORS as exc:  # pragma: no cover - defensive
            raise DatabaseError(message=str(exc)) from exc
