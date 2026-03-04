from __future__ import annotations

import hashlib
import os
from datetime import datetime

from sqlalchemy import SmallInteger, select
from sqlalchemy.orm import Mapped, mapped_column

from ...authentication import AuthProvider
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
        salt = os.urandom(32)
        key = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            100000,
        )
        return f"{salt.hex()}{key.hex()}"

    @staticmethod
    def verify_password(
        stored_password: str | None, provided_password: str
    ) -> bool:
        if not stored_password:
            return False
        try:
            salt = bytes.fromhex(stored_password[:64])
            stored_key = bytes.fromhex(stored_password[64:])
            key = hashlib.pbkdf2_hmac(
                "sha256",
                provided_password.encode("utf-8"),
                salt,
                100000,
            )
            return stored_key == key
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
