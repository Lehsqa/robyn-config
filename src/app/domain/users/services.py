import uuid

from pydantic import EmailStr

from ...config import settings
from ...infrastructure.application import DatabaseError, UnprocessableError
from ...infrastructure.authentication import AuthProvider
from ...infrastructure.database import transaction
from .constants import Role
from .entities import UserFlat, UserUncommitted
from .repository import UsersRepository


def generate_key(email: EmailStr) -> uuid.UUID:
    return uuid.uuid3(namespace=uuid.uuid4(), name=email)


def create_activation_link(activation_key: uuid.UUID) -> str:
    return f"{settings.integrations.frontend.activation_base_url}/{activation_key}"


def create_password_reset_link(activation_key: uuid.UUID) -> str:
    return f"{settings.integrations.frontend.password_reset_base_url}/{activation_key}"


def create_email_change_link(activation_key: uuid.UUID) -> str:
    return f"{settings.integrations.frontend.email_change_base_url}/{activation_key}"


async def create(payload: dict) -> UserFlat:
    payload.setdefault("role", Role.ADMIN)
    try:
        async with transaction():
            schema = UserUncommitted(**payload)
            user = await UsersRepository().create(schema)
    except DatabaseError as exc:
        raise UnprocessableError(message="User already exists") from exc
    return user


async def update_partial(id_: int, payload: dict) -> UserFlat:
    async with transaction():
        return await UsersRepository().update(
            attr="id", value=id_, payload=payload
        )


async def activate(id_: int) -> UserFlat:
    async with transaction():
        return await UsersRepository().update(
            attr="id", value=id_, payload={"is_active": True}
        )


async def password_update(id_: int, password_hash: str) -> UserFlat:
    payload = {
        "password": password_hash,
        "auth_provider": AuthProvider.INTERNAL,
    }
    async with transaction():
        return await UsersRepository().update(
            attr="id", value=id_, payload=payload
        )
