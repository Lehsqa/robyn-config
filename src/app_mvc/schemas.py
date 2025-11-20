from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from .authentication import AuthProvider
from .constants import Role


class InternalEntity(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class PublicEntity(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class TimeStampMixin(BaseModel):
    created_at: datetime
    updated_at: datetime


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
