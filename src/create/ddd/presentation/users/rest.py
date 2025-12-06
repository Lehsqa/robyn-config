"""Robyn route registrations for the user flows."""

from robyn import Request, Response, Robyn
from starlette import status

from ...domain.users import UserFlat
from ...infrastructure.application import json_response
from ...operational import authentication as auth_ops
from ...operational import users as users_ops
from .._helpers import parse_body
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


def _serialize(user: UserFlat) -> dict:
    return UserPublic.model_validate(user).model_dump(by_alias=True)


def register(app: Robyn) -> None:
    @app.post("/users")
    async def user_create(request: Request) -> Response:
        payload = await parse_body(request, UserCreateBody)
        user = await users_ops.create(payload=payload.model_dump())
        return json_response(
            payload=_serialize(user),
            status_code=status.HTTP_201_CREATED,
        )

    @app.post("/users/external")
    async def user_create_external(request: Request) -> Response:
        payload = await parse_body(request, UserExternalBody)
        user = await users_ops.create_external(payload=payload.model_dump())
        return json_response(
            payload=_serialize(user),
            status_code=status.HTTP_201_CREATED,
        )

    @app.post("/users/activate")
    async def user_activate(request: Request) -> Response:
        payload = await parse_body(request, ActivationBody)
        user = await users_ops.activate(key=payload.key)
        return json_response(
            payload=_serialize(user),
            status_code=status.HTTP_200_OK,
        )

    @app.post("/users/password/change", auth_required=True)
    async def user_password_change(request: Request) -> Response:
        payload = await parse_body(request, PasswordChangeBody)
        user_id = auth_ops.require_user_id(request)
        user = await users_ops.get(user_id=user_id)
        updated = await users_ops.password_change(
            user=user,
            old_password=payload.old_password,
            new_password=payload.new_password,
        )
        return json_response(
            payload=_serialize(updated),
            status_code=status.HTTP_200_OK,
        )

    @app.post("/users/password/reset/request")
    async def user_password_reset_request(request: Request) -> Response:
        payload = await parse_body(request, PasswordResetRequestBody)
        await users_ops.password_reset(email=payload.email)
        return json_response(
            payload={},
            status_code=status.HTTP_202_ACCEPTED,
        )

    @app.post("/users/password/reset/confirm")
    async def user_password_reset_confirm(request: Request) -> Response:
        payload = await parse_body(request, PasswordResetConfirmBody)
        user = await users_ops.password_reset_change(
            key=payload.key,
            new_password=payload.password,
        )
        return json_response(
            payload=_serialize(user),
            status_code=status.HTTP_200_OK,
        )

    @app.post("/users/email-change/request", auth_required=True)
    async def user_email_change_request(request: Request) -> Response:
        payload = await parse_body(request, EmailChangeRequestBody)
        user_id = auth_ops.require_user_id(request)
        user = await users_ops.get(user_id=user_id)
        await users_ops.email_change_request(user=user, email=payload.email)
        return json_response(
            payload={},
            status_code=status.HTTP_202_ACCEPTED,
        )

    @app.post("/users/email-change/confirm")
    async def user_email_change_confirm(request: Request) -> Response:
        payload = await parse_body(request, EmailChangeConfirmBody)
        user = await users_ops.email_change_confirmation(key=payload.key)
        return json_response(
            payload=_serialize(user),
            status_code=status.HTTP_200_OK,
        )
