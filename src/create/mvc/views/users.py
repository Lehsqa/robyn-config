import uuid

from robyn import Request, Response as RobynResponse, Robyn
from ..authentication import AuthProvider, pwd_context
from ..cache import CacheRepository
from ..config import settings
from ..mailing import EmailMessage, mailing_service
from ..models import UsersRepository, transaction
from ..schemas import EmailChange, Response, UserFlat, UserUncommitted
from ..utils import (
    JSON_HEADERS,
    DatabaseError,
    NotFoundError,
    UnprocessableError,
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


def _wrap(user: UserFlat) -> Response[UserPublic]:
    return Response[UserPublic](result=UserPublic.model_validate(user))


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
    async def user_create(body: UserCreateBody) -> RobynResponse:
        user = await _create_user(body)
        return RobynResponse(
            status_code=201,
            headers=JSON_HEADERS,
            description=_wrap(user).model_dump_json(),
        )

    @app.post("/users/activate")
    async def user_activate(body: ActivationBody) -> Response[UserPublic]:
        async with CacheRepository[UserFlat]() as cache:
            try:
                cache_entry = await cache.get(
                    namespace="activation", key=body.key
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

            await cache.delete(namespace="activation", key=body.key)

        return _wrap(user)

    @app.post("/users/password/change", auth_required=True)
    async def user_password_change(request: Request, body: PasswordChangeBody) -> Response[UserPublic]:
        user_id = require_user_id(request)

        async with transaction():
            repo = UsersRepository()
            user = await repo.get(id_=user_id)

            if not pwd_context.verify(
                body.old_password, user.password, scheme="bcrypt"
            ):
                raise UnprocessableError(message="Password invalid")

            updated = await repo.update(
                attr="id",
                value=user.id,
                payload={
                    "password": pwd_context.hash(
                        body.new_password, scheme="bcrypt"
                    ),
                    "auth_provider": AuthProvider.INTERNAL,
                },
            )

        return _wrap(updated)

    @app.post("/users/password/reset/request")
    async def user_password_reset_request(body: PasswordResetRequestBody) -> RobynResponse:
        try:
            async with transaction():
                repo = UsersRepository()
                user = await repo.get_by_login(login=body.email)
        except NotFoundError:
            return RobynResponse(status_code=202, headers={}, description="")

        reset_key = uuid.uuid4()
        await _cache_password_reset(user, reset_key)
        await _send_password_reset_email(user, reset_key)
        return RobynResponse(status_code=202, headers={}, description="")

    @app.post("/users/password/reset/confirm")
    async def user_password_reset_confirm(body: PasswordResetConfirmBody) -> Response[UserPublic]:
        async with CacheRepository[UserFlat]() as cache:
            try:
                cache_entry = await cache.get(
                    namespace="password-reset", key=body.key
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
                            body.password, scheme="bcrypt"
                        ),
                        "auth_provider": AuthProvider.INTERNAL,
                    },
                )

            await cache.delete(namespace="password-reset", key=body.key)

        return _wrap(user)

    @app.post("/users/email-change/request", auth_required=True)
    async def user_email_change_request(request: Request, body: EmailChangeRequestBody) -> RobynResponse:
        user_id = require_user_id(request)

        async with transaction():
            repo = UsersRepository()
            user = await repo.get(id_=user_id)

        change_key = uuid.uuid4()
        entry = EmailChange(user_id=user.id, email=body.email)
        await _cache_email_change(entry, change_key)
        await _send_email_change_email(body.email, change_key)

        return RobynResponse(status_code=202, headers={}, description="")

    @app.post("/users/email-change/confirm")
    async def user_email_change_confirm(body: EmailChangeConfirmBody) -> Response[UserPublic]:
        async with CacheRepository[EmailChange]() as cache:
            try:
                cache_entry = await cache.get(
                    namespace="email-change", key=body.key
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

            await cache.delete(namespace="email-change", key=body.key)

        return _wrap(user)
