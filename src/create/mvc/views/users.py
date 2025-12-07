import uuid

from robyn import Request, Response, Robyn
from starlette import status

from ..authentication import AuthProvider, pwd_context
from ..cache import CacheRepository
from ..config import settings
from ..mailing import EmailMessage, mailing_service
from ..models import UsersRepository, transaction
from ..schemas import EmailChange, UserFlat, UserUncommitted
from ..utils import (
    DatabaseError,
    NotFoundError,
    UnprocessableError,
    json_response,
)
from .authentication import require_user_id
from .contracts import (
    ActivationBody,
    EmailChangeConfirmBody,
    EmailChangeRequestBody,
    PasswordChangeBody,
    PasswordResetConfirmBody,
    PasswordResetRequestBody,
    UserCreateBody,
    UserPublic,
)
from .helpers import parse_body


def _serialize(user: UserFlat) -> dict:
    return UserPublic.model_validate(user).model_dump(by_alias=True)


def _activation_link(key: uuid.UUID) -> str:
    base = str(settings.integrations.frontend.activation_base_url).rstrip("/")
    return f"{base}/{key}"


def _password_reset_link(key: uuid.UUID) -> str:
    base = str(settings.integrations.frontend.password_reset_base_url).rstrip(
        "/"
    )
    return f"{base}/{key}"


def _email_change_link(key: uuid.UUID) -> str:
    base = str(settings.integrations.frontend.email_change_base_url).rstrip(
        "/"
    )
    return f"{base}/{key}"


async def _cache_activation(user: UserFlat, key: uuid.UUID) -> None:
    async with CacheRepository[UserFlat]() as cache:
        await cache.set(
            namespace="activation",
            key=key,
            instance=user,
            ttl=settings.cache.ttl_activation_seconds or None,
        )


async def _send_activation_email(user: UserFlat, key: uuid.UUID) -> None:
    link = _activation_link(key)
    await mailing_service.send(
        EmailMessage(
            recipients=[user.email],
            subject="Account activation",
            body=f"Activate your account: {link}",
        )
    )


async def _cache_password_reset(user: UserFlat, key: uuid.UUID) -> None:
    async with CacheRepository[UserFlat]() as cache:
        await cache.set(
            namespace="password-reset",
            key=key,
            instance=user,
            ttl=settings.cache.ttl_password_reset_seconds or None,
        )


async def _send_password_reset_email(user: UserFlat, key: uuid.UUID) -> None:
    link = _password_reset_link(key)
    await mailing_service.send(
        EmailMessage(
            recipients=[user.email],
            subject="Password reset",
            body=f"Reset your password: {link}",
        )
    )


async def _cache_email_change(entry: EmailChange, key: uuid.UUID) -> None:
    async with CacheRepository[EmailChange]() as cache:
        await cache.set(
            namespace="email-change",
            key=key,
            instance=entry,
        )


async def _send_email_change_email(email: str, key: uuid.UUID) -> None:
    link = _email_change_link(key)
    await mailing_service.send(
        EmailMessage(
            recipients=[email],
            subject="Confirm email change",
            body=f"Confirm your email change: {link}",
        )
    )


async def _create_user(payload: UserCreateBody) -> UserFlat:
    async with transaction():
        repo = UsersRepository()
        schema = UserUncommitted(
            username=payload.username,
            email=payload.email,
            password=pwd_context.hash(payload.password, scheme="bcrypt"),
            role=1,
        )
        try:
            user = await repo.create(schema)
        except DatabaseError as exc:
            raise UnprocessableError(message="User already exists") from exc

    activation_key = uuid.uuid4()
    await _cache_activation(user, activation_key)
    await _send_activation_email(user, activation_key)
    return user


def register(app: Robyn) -> None:
    @app.post("/users")
    async def user_create(request: Request) -> Response:
        payload = await parse_body(request, UserCreateBody)
        user = await _create_user(payload)
        return json_response(
            payload=_serialize(user),
            status_code=status.HTTP_201_CREATED,
        )

    @app.post("/users/activate")
    async def user_activate(request: Request) -> Response:
        payload = await parse_body(request, ActivationBody)

        async with CacheRepository[UserFlat]() as cache:
            try:
                cache_entry = await cache.get(
                    namespace="activation", key=payload.key
                )
            except NotFoundError as exc:
                raise UnprocessableError(
                    message="Invalid or expired activation key"
                ) from exc

            async with transaction():
                repo = UsersRepository()
                user = await repo.update(
                    attr="id",
                    value=cache_entry.instance.id,
                    payload={"is_active": True},
                )

            await cache.delete(namespace="activation", key=payload.key)

        return json_response(
            payload=_serialize(user),
            status_code=status.HTTP_200_OK,
        )

    @app.post("/users/password/change", auth_required=True)
    async def user_password_change(request: Request) -> Response:
        payload = await parse_body(request, PasswordChangeBody)
        user_id = require_user_id(request)

        async with transaction():
            repo = UsersRepository()
            user = await repo.get(id_=user_id)

            if not pwd_context.verify(
                payload.old_password, user.password, scheme="bcrypt"
            ):
                raise UnprocessableError(message="Password invalid")

            updated = await repo.update(
                attr="id",
                value=user.id,
                payload={
                    "password": pwd_context.hash(
                        payload.new_password, scheme="bcrypt"
                    ),
                    "auth_provider": AuthProvider.INTERNAL,
                },
            )

        return json_response(
            payload=_serialize(updated),
            status_code=status.HTTP_200_OK,
        )

    @app.post("/users/password/reset/request")
    async def user_password_reset_request(request: Request) -> Response:
        payload = await parse_body(request, PasswordResetRequestBody)

        try:
            async with transaction():
                repo = UsersRepository()
                user = await repo.get_by_login(login=payload.email)
        except NotFoundError:
            return json_response({}, status_code=status.HTTP_202_ACCEPTED)

        reset_key = uuid.uuid4()
        await _cache_password_reset(user, reset_key)
        await _send_password_reset_email(user, reset_key)
        return json_response({}, status_code=status.HTTP_202_ACCEPTED)

    @app.post("/users/password/reset/confirm")
    async def user_password_reset_confirm(request: Request) -> Response:
        payload = await parse_body(request, PasswordResetConfirmBody)

        async with CacheRepository[UserFlat]() as cache:
            try:
                cache_entry = await cache.get(
                    namespace="password-reset", key=payload.key
                )
            except NotFoundError as exc:
                raise UnprocessableError(
                    message="Invalid or expired reset key"
                ) from exc

            async with transaction():
                repo = UsersRepository()
                user = await repo.update(
                    attr="id",
                    value=cache_entry.instance.id,
                    payload={
                        "password": pwd_context.hash(
                            payload.password, scheme="bcrypt"
                        ),
                        "auth_provider": AuthProvider.INTERNAL,
                    },
                )

            await cache.delete(namespace="password-reset", key=payload.key)

        return json_response(
            payload=_serialize(user),
            status_code=status.HTTP_200_OK,
        )

    @app.post("/users/email-change/request", auth_required=True)
    async def user_email_change_request(request: Request) -> Response:
        payload = await parse_body(request, EmailChangeRequestBody)
        user_id = require_user_id(request)

        async with transaction():
            repo = UsersRepository()
            user = await repo.get(id_=user_id)

        change_key = uuid.uuid4()
        entry = EmailChange(user_id=user.id, email=payload.email)
        await _cache_email_change(entry, change_key)
        await _send_email_change_email(payload.email, change_key)

        return json_response({}, status_code=status.HTTP_202_ACCEPTED)

    @app.post("/users/email-change/confirm")
    async def user_email_change_confirm(request: Request) -> Response:
        payload = await parse_body(request, EmailChangeConfirmBody)

        async with CacheRepository[EmailChange]() as cache:
            try:
                cache_entry = await cache.get(
                    namespace="email-change", key=payload.key
                )
            except NotFoundError as exc:
                raise UnprocessableError(
                    message="Invalid or expired email change key"
                ) from exc

            async with transaction():
                repo = UsersRepository()
                user = await repo.update(
                    attr="id",
                    value=cache_entry.instance.user_id,
                    payload={
                        "email": cache_entry.instance.email,
                        "auth_provider": AuthProvider.INTERNAL,
                    },
                )

            await cache.delete(namespace="email-change", key=payload.key)

        return json_response(
            payload=_serialize(user),
            status_code=status.HTTP_200_OK,
        )
