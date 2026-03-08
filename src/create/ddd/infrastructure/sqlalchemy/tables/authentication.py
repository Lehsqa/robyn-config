from __future__ import annotations

from datetime import datetime

from sqlalchemy import SmallInteger, select
from sqlalchemy.orm import Mapped, mapped_column

from ...authentication import AuthProvider, pwd_context
from .base import BaseTable

__all__ = ("UsersTable",)


class UsersTable(BaseTable):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(unique=True, index=True)
    email: Mapped[str] = mapped_column(unique=True, index=True)
    password: Mapped[str | None] = mapped_column()
    is_active: Mapped[bool] = mapped_column(default=False, server_default="0")
    is_superuser: Mapped[bool] = mapped_column(
        default=False,
        server_default="0",
    )
    last_login: Mapped[datetime | None] = mapped_column(nullable=True)
    role: Mapped[int] = mapped_column(
        SmallInteger,
        default=1,
        server_default="1",
    )
    auth_provider: Mapped[str] = mapped_column(
        default=AuthProvider.INTERNAL,
        server_default=AuthProvider.INTERNAL,
    )

    @staticmethod
    def hash_password(password: str) -> str:
        return pwd_context.hash(password, scheme="bcrypt")

    @staticmethod
    def verify_password(
        stored_password: str | None, provided_password: str
    ) -> bool:
        if not stored_password:
            return False
        try:
            return pwd_context.verify(
                provided_password, stored_password, scheme="bcrypt"
            )
        except Exception:
            return False

    @classmethod
    async def authenticate(
        cls,
        session,
        username: str,
        password: str,
    ) -> "UsersTable | None":
        result = await session.execute(
            select(cls).where(cls.username == username)
        )
        user = result.scalar_one_or_none()
        if (
            user
            and user.is_active
            and cls.verify_password(user.password, password)
        ):
            return user
        return None
