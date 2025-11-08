"""Authentication routes: login and token introspection."""

from datetime import datetime, timezone

from robyn import Request, Response, Robyn
from robyn.authentication import Identity
from starlette import status

from ...infrastructure.application import AuthenticationError, json_response
from ...operational import authentication as auth_ops
from .._helpers import parse_body
from .contracts import LoginRequestBody, TokenInfo, TokenResponse


def register(app: Robyn) -> None:
    @app.post("/auth/login")
    async def login(request: Request) -> Response:
        payload = await parse_body(request, LoginRequestBody)
        user = await auth_ops.authenticate_user(
            payload.login, payload.password
        )
        token = auth_ops.create_access_token(user)
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
