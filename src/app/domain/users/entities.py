from pydantic import EmailStr, field_validator

from ...infrastructure.application import InternalEntity, TimeStampMixin
from ...infrastructure.authentication import AuthProvider
from .constants import Role


class UserUncommitted(InternalEntity):
    username: str
    email: EmailStr
    password: str
    role: int
    is_active: bool = False
    auth_provider: AuthProvider = AuthProvider.INTERNAL

    @field_validator("role", mode="before")
    @classmethod
    def role_validator(cls, value: int) -> int:
        if value not in Role.values():
            raise ValueError(f"Unsupported role: {value}")
        return value


class UserFlat(UserUncommitted, TimeStampMixin):
    id: int


class PasswordForgot(InternalEntity):
    email: EmailStr


class EmailChange(InternalEntity):
    user_id: int
    email: EmailStr
