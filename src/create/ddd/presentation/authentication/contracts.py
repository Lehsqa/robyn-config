from datetime import datetime, timedelta

from app.infrastructure.application import PublicEntity
from pydantic import EmailStr, Field


class LoginRequestBody(PublicEntity):
    login: EmailStr | str = Field(
        description="User login", examples=["john@email.com", "john"]
    )
    password: str = Field(description="User password", examples=["password"])


class TokenResponse(PublicEntity):
    access_token: str = Field(description="Access token", examples=["token"])
    token_type: str = Field(
        description="Token type", examples=["Bearer"], default="Bearer"
    )


class TokenInfo(PublicEntity):
    subject: str = Field(description="Subject", examples=["1"])
    email: EmailStr = Field(
        description="User email", examples=["john@email.com"]
    )
    username: str = Field(description="User username", examples=["john"])
    issued_at: datetime = Field(
        description="Issued at", examples=[datetime.now()]
    )
    expires_at: datetime = Field(
        description="Expires at",
        examples=[datetime.now() + timedelta(hours=1)],
    )
