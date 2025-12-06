"""Application services orchestrating domain + infrastructure, Robyn edition."""

import uuid
from typing import Any

from pydantic import EmailStr

from ..config import settings
from ..domain.users import EmailChange, UserFlat
from ..domain.users import services as users_services
from ..infrastructure.application import NotFoundError, UnprocessableError
from ..infrastructure.authentication import AuthProvider, pwd_context
from ..infrastructure.cache import CacheRepository
from ..infrastructure.database import transaction
from ..infrastructure.database.repository import (
    UsersRepository as InfrastructureUsersRepository,
)
from ..infrastructure.mailing import EmailMessage, mailing_service

__all__ = (
    "create",
    "create_external",
    "activate",
    "password_change",
    "password_reset",
    "password_reset_change",
    "email_change_request",
    "email_change_confirmation",
    "get_by_login",
)


async def create(payload: dict[str, Any]) -> UserFlat:
    plain_password = payload.pop("password")
    payload["password"] = pwd_context.hash(plain_password, scheme="bcrypt")
    user = await users_services.create(
        payload=payload,
        repository_factory=InfrastructureUsersRepository,
    )

    activation_key = users_services.generate_key(user.email)
    activation_link = users_services.create_activation_link(activation_key)

    async with CacheRepository[UserFlat]() as cache:
        await cache.set(
            namespace="activation",
            key=activation_key,
            instance=user,
            ttl=settings.cache.ttl_activation_seconds or None,
        )

    await mailing_service.send(
        EmailMessage(
            recipients=[user.email],
            subject="Account activation",
            body=f"Activation link: {activation_link}",
        )
    )

    return user


async def create_external(payload: dict[str, Any]) -> UserFlat:
    return await users_services.create(
        payload=payload,
        repository_factory=InfrastructureUsersRepository,
    )


async def update_partial(user: UserFlat, payload: dict[str, Any]) -> UserFlat:
    return await users_services.update_partial(
        id_=user.id,
        payload=payload,
        repository_factory=InfrastructureUsersRepository,
    )


async def get_by_login(login: str) -> UserFlat:
    async with transaction():
        return await InfrastructureUsersRepository().get_by_login(login=login)


async def get(user_id: int) -> UserFlat:
    async with transaction():
        return await InfrastructureUsersRepository().get(id_=user_id)


async def activate(key: uuid.UUID) -> UserFlat:
    async with CacheRepository[UserFlat]() as cache:
        cache_entry = await cache.get(namespace="activation", key=key)
        user = await users_services.activate(
            cache_entry.instance.id,
            repository_factory=InfrastructureUsersRepository,
        )
        await cache.delete(namespace="activation", key=key)
        return user


async def password_change(
    user: UserFlat, old_password: str, new_password: str
) -> UserFlat:
    if not pwd_context.verify(old_password, user.password, scheme="bcrypt"):
        raise UnprocessableError(message="Password invalid")

    password_hash = pwd_context.hash(new_password, scheme="bcrypt")
    return await users_services.password_update(
        id_=user.id,
        password_hash=password_hash,
        repository_factory=InfrastructureUsersRepository,
    )


async def password_reset(email: EmailStr) -> None:
    try:
        async with transaction():
            repository = InfrastructureUsersRepository()
            user = await repository.get_by_login(login=email)
    except NotFoundError:
        return

    reset_key = users_services.generate_key(email)
    reset_link = users_services.create_password_reset_link(reset_key)

    async with CacheRepository[UserFlat]() as cache:
        await cache.set(
            namespace="password-reset",
            key=reset_key,
            instance=user,
            ttl=settings.cache.ttl_password_reset_seconds or None,
        )

    await mailing_service.send(
        EmailMessage(
            recipients=[email],
            subject="Password reset",
            body=f"Reset link: {reset_link}",
        )
    )


async def password_reset_change(key: uuid.UUID, new_password: str) -> UserFlat:
    async with CacheRepository[UserFlat]() as cache:
        try:
            cache_entry = await cache.get(namespace="password-reset", key=key)
        except NotFoundError as exc:
            raise UnprocessableError(message="Invalid key") from exc

        password_hash = pwd_context.hash(new_password, scheme="bcrypt")
        user = await users_services.password_update(
            id_=cache_entry.instance.id,
            password_hash=password_hash,
            repository_factory=InfrastructureUsersRepository,
        )
        await cache.delete(namespace="password-reset", key=key)
        return user


async def email_change_request(user: UserFlat, email: EmailStr) -> None:
    change_key = users_services.generate_key(email)
    change_link = users_services.create_email_change_link(change_key)

    async with CacheRepository[EmailChange]() as cache:
        await cache.set(
            namespace="email-change",
            key=change_key,
            instance=EmailChange(user_id=user.id, email=email),
        )

    await mailing_service.send(
        EmailMessage(
            recipients=[email],
            subject="Email migration",
            body=f"Confirmation link: {change_link}",
        )
    )


async def email_change_confirmation(key: uuid.UUID) -> UserFlat:
    async with CacheRepository[EmailChange]() as cache:
        try:
            cache_entry = await cache.get(namespace="email-change", key=key)
        except NotFoundError as exc:
            raise UnprocessableError(message="Invalid key") from exc

        async with transaction():
            repository = InfrastructureUsersRepository()
            user = await repository.update(
                attr="id",
                value=cache_entry.instance.user_id,
                payload={
                    "email": cache_entry.instance.email,
                    "auth_provider": AuthProvider.INTERNAL,
                },
            )
        await cache.delete(namespace="email-change", key=key)
        return user
