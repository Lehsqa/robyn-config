from __future__ import annotations

from tortoise import fields

from ...authentication import AuthProvider, pwd_context
from .base import BaseTable

__all__ = ("UsersTable",)


class UsersTable(BaseTable):
    username = fields.CharField(max_length=255, unique=True, index=True)
    email = fields.CharField(max_length=255, unique=True, index=True)
    password = fields.CharField(max_length=512, null=True)
    is_active = fields.BooleanField(default=False)
    is_superuser = fields.BooleanField(default=False)
    last_login = fields.DatetimeField(null=True)
    role = fields.SmallIntField(default=1)
    auth_provider = fields.CharEnumField(
        enum_type=AuthProvider,
        default=AuthProvider.INTERNAL,
    )

    class Meta:
        table = "users"
        ordering = ("id",)

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
        cls, username: str, password: str
    ) -> "UsersTable | None":
        user = await cls.get_or_none(username=username)
        if (
            user
            and user.is_active
            and cls.verify_password(user.password, password)
        ):
            return user
        return None
