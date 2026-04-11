from datetime import datetime, timedelta
from typing import Annotated

from app.infrastructure.application import PublicEntity
from pydantic import EmailStr, Field


class LoginRequestBody(PublicEntity):
    login: Annotated[
        EmailStr | str,
        Field(description="User login", examples=["john@email.com", "john"]),
    ]
    password: Annotated[
        str, Field(description="User password", examples=["password"])
    ]


class TokenResponse(PublicEntity):
    access_token: Annotated[
        str, Field(description="Access token", examples=["token"])
    ]
    token_type: Annotated[
        str,
        Field(
            description="Token type",
            examples=["Bearer"],
            default="Bearer",
        ),
    ]


class TokenInfo(PublicEntity):
    subject: Annotated[str, Field(description="Subject", examples=["1"])]
    email: Annotated[
        EmailStr,
        Field(description="User email", examples=["john@email.com"]),
    ]
    username: Annotated[
        str, Field(description="User username", examples=["john"])
    ]
    issued_at: Annotated[
        datetime, Field(description="Issued at", examples=[datetime.now()])
    ]
    expires_at: Annotated[
        datetime,
        Field(
            description="Expires at",
            examples=[datetime.now() + timedelta(hours=1)],
        ),
    ]
