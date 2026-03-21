from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator
from pydantic.alias_generators import to_camel

from .authentication import AuthProvider
from .constants import Role


class InternalEntity(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=True,
        validate_assignment=True,
        arbitrary_types_allowed=True,
        from_attributes=True,
    )


class PublicEntity(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        use_enum_values=True,
        validate_assignment=True,
        populate_by_name=True,
        arbitrary_types_allowed=True,
        from_attributes=True,
        loc_by_alias=True,
        alias_generator=to_camel,
    )

    def model_dump_json(self, *, by_alias: bool = True, **kwargs) -> str:
        return super().model_dump_json(by_alias=by_alias, **kwargs)


_PublicEntity = TypeVar("_PublicEntity", bound=PublicEntity)


class ResponseMulti(PublicEntity, Generic[_PublicEntity]):
    """Generic response model that consists of multiple results."""

    result: list[_PublicEntity]


class Response(PublicEntity, Generic[_PublicEntity]):
    """Generic response model that consists of a single result."""

    result: _PublicEntity


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
