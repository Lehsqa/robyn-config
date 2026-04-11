import uuid
from typing import Annotated

from app.domain.authentication import validators as auth_validators
from app.infrastructure.application import (
    PrimaryKey,
    PublicEntity,
    UnprocessableError,
)
from pydantic import EmailStr, Field, field_validator, model_validator


class _BaseUser(PublicEntity):
    username: Annotated[
        str,
        Field(
            description="User username",
            examples=["john"],
            min_length=1,
            max_length=255,
        ),
    ]
    email: Annotated[
        EmailStr,
        Field(
            description="User email",
            examples=["john@email.com"],
        ),
    ]


class UserCreateBody(_BaseUser):
    password: Annotated[
        str,
        Field(
            description="User password",
            examples=["@Dm1n#LKJ"],
        ),
    ]

    @field_validator("password", mode="before")
    @classmethod
    def password_nist(cls, value: str) -> str:
        return auth_validators.password_nist(value)

    @model_validator(mode="before")
    @classmethod
    def username_email(cls, values: dict) -> dict:
        """Check if the username and email are not the same."""

        if values.get("username") == values.get("email"):
            raise UnprocessableError(
                message="The username and email must be different."
            )

        return values


class UserExternalBody(_BaseUser):
    role: Annotated[
        int,
        Field(
            description="User role",
            examples=[1],
            default=1,
        ),
    ]
    auth_provider: Annotated[
        str | None,
        Field(
            default=None,
            description="External auth provider identifier",
        ),
    ]


class ActivationBody(PublicEntity):
    key: Annotated[uuid.UUID, Field(description="Activation key from email")]


class PasswordChangeBody(PublicEntity):
    old_password: Annotated[str, Field(description="User's current password")]
    new_password: Annotated[str, Field(description="A new user's password")]

    @field_validator("new_password", mode="before")
    @classmethod
    def password_nist(cls, value: str) -> str:
        return auth_validators.password_nist(value)


class PasswordResetRequestBody(PublicEntity):
    email: Annotated[
        EmailStr,
        Field(description="User email", examples=["john@email.com"]),
    ]


class PasswordResetConfirmBody(PublicEntity):
    key: Annotated[
        uuid.UUID,
        Field(description="Password reset key that is taken from the email"),
    ]
    password: Annotated[str, Field(description="A new user's password")]

    @field_validator("password", mode="before")
    @classmethod
    def password_nist(cls, value: str) -> str:
        return auth_validators.password_nist(value)


class EmailChangeRequestBody(PublicEntity):
    email: Annotated[
        EmailStr, Field(description="A new email you want to change to")
    ]


class EmailChangeConfirmBody(PublicEntity):
    key: Annotated[
        uuid.UUID,
        Field(description="Email change key that is taken from the email"),
    ]


class UserPublic(_BaseUser):
    """The public user's data model."""

    id: Annotated[PrimaryKey, Field(description="User id")]
    is_active: Annotated[
        bool,
        Field(
            description="Whether the user activated the account",
            examples=[True],
        ),
    ]
    role: Annotated[
        int,
        Field(
            description="User role. Possible values: [1,2,3]",
            examples=[2],
        ),
    ]
