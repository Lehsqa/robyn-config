from datetime import datetime, timedelta, timezone

import jwt
from robyn import Request, Response, Robyn
from robyn.authentication import AuthenticationHandler, BearerGetter, Identity
from starlette import status

from ..authentication import pwd_context
from ..config import settings
from ..models import UsersRepository, transaction
from ..utils import AuthenticationError, NotFoundError, json_response
from .contracts import LoginRequestBody, TokenInfo, TokenResponse
from .helpers import parse_body


def create_access_token(user_id: int, email: str, username: str) -> str:
    now = datetime.now(timezone.utc)
    ttl = settings.authentication.access_token.ttl
    exp = now + timedelta(seconds=ttl)
    payload = {
        "sub": str(user_id),
        "email": email,
        "username": username,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(
        payload,
        settings.authentication.access_token.secret_key,
        algorithm=settings.authentication.algorithm,
    )


def decode_access_token(token: str) -> dict:
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

    sub = identity.claims.get("sub")
    if sub is None:
        raise AuthenticationError(message="Subject claim missing")

    try:
        return int(sub)
    except (TypeError, ValueError) as exc:
        raise AuthenticationError(message="Subject claim invalid") from exc


class JWTAuthenticationHandler(AuthenticationHandler):
    def __init__(self) -> None:
        super().__init__(BearerGetter())
        self._last_error = AuthenticationError()

    def authenticate(self, request) -> Identity | None:
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
        # Simplified error response
        return json_response(
            {"message": self._last_error.message},
            status_code=self._last_error.status_code,
        )


def register(app: Robyn) -> None:
    @app.post("/auth/login")
    async def login(request: Request) -> Response:
        payload = await parse_body(request, LoginRequestBody)

        async with transaction():
            repo = UsersRepository()
            try:
                user = await repo.get_by_login(login=payload.login)
            except NotFoundError:
                raise AuthenticationError(message="Invalid credentials")

        if not user.is_active:
            raise AuthenticationError(message="Account not activated")

        if not user.password:
            raise AuthenticationError(message="Password not set")
        if not pwd_context.verify(
            payload.password, user.password, scheme="bcrypt"
        ):
            raise AuthenticationError(message="Invalid credentials")

        token = create_access_token(user.id, user.email, user.username)
        response = TokenResponse(access_token=token)
        return json_response(
            payload=response.model_dump(by_alias=True),
            status_code=status.HTTP_200_OK,
        )

    @app.get("/auth/me", auth_required=True)
    async def me(request: Request) -> Response:
        identity: Identity | None = getattr(request, "identity", None)
        if identity is None:
            raise AuthenticationError(message="Authentication required")

        claims = identity.claims
        issued_at = datetime.fromtimestamp(
            float(claims.get("iat", "0")), tz=timezone.utc
        )
        expires_at = datetime.fromtimestamp(
            float(claims.get("exp", "0")), tz=timezone.utc
        )
        info = TokenInfo(
            subject=claims.get("sub", ""),
            email=claims.get("email", ""),
            username=claims.get("username", ""),
            issued_at=issued_at,
            expires_at=expires_at,
        )
        return json_response(
            payload=info.model_dump(by_alias=True),
            status_code=status.HTTP_200_OK,
        )
