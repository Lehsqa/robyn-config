"""Authentication workflows: verifying credentials and handling tokens."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import jwt
from robyn import Request
from robyn.authentication import AuthenticationHandler, BearerGetter, Identity

from ..config import settings
from ..domain.users import UserFlat
from ..infrastructure.application import (
    AuthenticationError,
    NotFoundError,
    json_response,
)
from ..infrastructure.application.entities.response import ErrorResponse
from ..infrastructure.authentication import pwd_context
from ..infrastructure.database import transaction
from ..infrastructure.database.repository import (
    UsersRepository as InfrastructureUsersRepository,
)


async def authenticate_user(login: str, password: str) -> UserFlat:
    """Validate credentials and return the matching active user."""
    try:
        async with transaction():
            repository = InfrastructureUsersRepository()
            user = await repository.get_by_login(login=login)
    except NotFoundError as exc:
        raise AuthenticationError(message="Invalid credentials") from exc

    if not pwd_context.verify(password, user.password, scheme="bcrypt"):
        raise AuthenticationError(message="Invalid credentials")

    if not user.is_active:
        raise AuthenticationError(message="Inactive account")

    return user


def create_access_token(user: UserFlat) -> str:
    """Generate a signed JWT for the provided user."""
    now = datetime.now(timezone.utc)
    ttl = settings.authentication.access_token.ttl
    exp = now + timedelta(seconds=ttl)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "username": user.username,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(
        payload,
        settings.authentication.access_token.secret_key,
        algorithm=settings.authentication.algorithm,
    )


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode a JWT and return its claims, raising AuthenticationError on failure."""
    try:
        payload = jwt.decode(
            token,
            settings.authentication.access_token.secret_key,
            algorithms=[settings.authentication.algorithm],
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError(message="Token has expired") from exc
    except jwt.PyJWTError as exc:
        raise AuthenticationError(message="Invalid token") from exc

    return payload


def require_user_id(request: Request) -> int:
    identity: Identity | None = getattr(request, "identity", None)
    if identity is None:
        raise AuthenticationError(message="Authentication required")

    sub: str | Any | None = identity.claims.get("sub")
    if sub is None:
        raise AuthenticationError(message="Subject claim missing")

    try:
        return int(sub)
    except (TypeError, ValueError) as exc:
        raise AuthenticationError(message="Subject claim invalid") from exc


class JWTAuthenticationHandler(AuthenticationHandler):
    """Robyn authentication handler that validates bearer tokens."""

    def __init__(self) -> None:
        super().__init__(BearerGetter())
        self._last_error = AuthenticationError()

    def authenticate(self, request) -> Identity | None:  # type: ignore[override]
        token = self.token_getter.get_token(request)
        if not token:
            self._last_error = AuthenticationError(
                message="Token not provided"
            )
            return None

        try:
            claims = decode_access_token(token)
        except AuthenticationError as exc:
            self._last_error = exc
            return None

        normalized = {str(key): str(value) for key, value in claims.items()}
        return Identity(claims=normalized)

    @property
    def unauthorized_response(self):
        payload = ErrorResponse(message=self._last_error.message).model_dump(
            by_alias=True
        )
        return json_response(payload, status_code=self._last_error.status_code)
