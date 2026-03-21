"""Authentication routes: login and token introspection."""

from datetime import datetime, timezone

from robyn import Request, Robyn
from robyn.authentication import Identity

from ...infrastructure.application import AuthenticationError, Response
from ...operational import authentication as auth_ops
from .contracts import LoginRequestBody, TokenInfo, TokenResponse


def register(app: Robyn) -> None:
    @app.post(
        "/auth/login", openapi_name="Login", openapi_tags=["Authentication"]
    )
    async def login(body: LoginRequestBody) -> Response[TokenResponse]:
        user = await auth_ops.authenticate_user(body.login, body.password)
        token = auth_ops.create_access_token(user)
        return Response[TokenResponse](
            result=TokenResponse(access_token=token)
        )

    @app.get(
        "/auth/me",
        auth_required=True,
        openapi_name="Current User",
        openapi_tags=["Authentication"],
    )
    async def me(request: Request) -> Response[TokenInfo]:
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
        return Response[TokenInfo](
            result=TokenInfo(
                subject=claims.get("sub", ""),
                email=claims.get("email", ""),
                username=claims.get("username", ""),
                issued_at=issued_at,
                expires_at=expires_at,
            )
        )
