from __future__ import annotations

import hashlib
import os

from tortoise import fields

from ...authentication import AuthProvider
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
        salt = os.urandom(32)
        key = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            100000,
        )
        return f"{salt.hex()}{key.hex()}"

    @staticmethod
    def verify_password(stored_password: str | None, provided_password: str) -> bool:
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
    async def authenticate(cls, username: str, password: str) -> "UsersTable | None":
        user = await cls.get_or_none(username=username)
        if user and user.is_active and cls.verify_password(user.password, password):
            return user
        return None
