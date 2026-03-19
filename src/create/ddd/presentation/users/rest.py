"""Robyn route registrations for the user flows."""

from robyn import Request, Response as RobynResponse, Robyn

from ...infrastructure.application import JSON_HEADERS, Response
from ...operational import authentication as auth_ops
from ...operational import users as users_ops
from .contracts import (
    ActivationBody,
    EmailChangeConfirmBody,
    EmailChangeRequestBody,
    PasswordChangeBody,
    PasswordResetConfirmBody,
    PasswordResetRequestBody,
    UserCreateBody,
    UserExternalBody,
    UserPublic,
)


def _wrap(user) -> Response[UserPublic]:
    return Response[UserPublic](result=UserPublic.model_validate(user))


def register(app: Robyn) -> None:
    @app.post("/users")
    async def user_create(body: UserCreateBody) -> RobynResponse:
        user = await users_ops.create(payload=body.model_dump())
        return RobynResponse(
            status_code=201,
            headers=JSON_HEADERS,
            description=_wrap(user).model_dump_json(),
        )

    @app.post("/users/external")
    async def user_create_external(body: UserExternalBody) -> RobynResponse:
        user = await users_ops.create_external(payload=body.model_dump())
        return RobynResponse(
            status_code=201,
            headers=JSON_HEADERS,
            description=_wrap(user).model_dump_json(),
        )

    @app.post("/users/activate")
    async def user_activate(body: ActivationBody) -> Response[UserPublic]:
        user = await users_ops.activate(key=body.key)
        return _wrap(user)

    @app.post("/users/password/change", auth_required=True)
    async def user_password_change(request: Request, body: PasswordChangeBody) -> Response[UserPublic]:
        user_id = auth_ops.require_user_id(request)
        user = await users_ops.get(user_id=user_id)
        updated = await users_ops.password_change(
            user=user,
            old_password=body.old_password,
            new_password=body.new_password,
        )
        return _wrap(updated)

    @app.post("/users/password/reset/request")
    async def user_password_reset_request(body: PasswordResetRequestBody) -> RobynResponse:
        await users_ops.password_reset(email=body.email)
        return RobynResponse(status_code=202, headers={}, description="")

    @app.post("/users/password/reset/confirm")
    async def user_password_reset_confirm(body: PasswordResetConfirmBody) -> Response[UserPublic]:
        user = await users_ops.password_reset_change(
            key=body.key,
            new_password=body.password,
        )
        return _wrap(user)

    @app.post("/users/email-change/request", auth_required=True)
    async def user_email_change_request(request: Request, body: EmailChangeRequestBody) -> RobynResponse:
        user_id = auth_ops.require_user_id(request)
        user = await users_ops.get(user_id=user_id)
        await users_ops.email_change_request(user=user, email=body.email)
        return RobynResponse(status_code=202, headers={}, description="")

    @app.post("/users/email-change/confirm")
    async def user_email_change_confirm(body: EmailChangeConfirmBody) -> Response[UserPublic]:
        user = await users_ops.email_change_confirmation(key=body.key)
        return _wrap(user)
