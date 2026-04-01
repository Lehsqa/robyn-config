from __future__ import annotations

from datetime import datetime
import uuid
from typing import Any, Optional

from robyn import Request
from sqlalchemy import select

from ...auth_models import Role, UserRole
from ...models import AdminUser
from .auth_common import (
    generate_session_token,  # noqa: F401
    get_language,  # noqa: F401
    verify_session_token,
)
from .helpers import parse_cookie_header


async def authenticate_credentials(
    site: Any, username: str, password: str
) -> tuple[str, str] | None:
    async with site.transaction() as session:
        user = await AdminUser.authenticate(session, username, password)
        if not user:
            return None

        user.last_login = datetime.utcnow()
    return str(user.id), str(user.username)


def _coerce_user_id(raw_user_id: str) -> Any:
    id_column = AdminUser.__table__.c.id
    try:
        python_type = id_column.type.python_type
    except (AttributeError, NotImplementedError):
        return raw_user_id

    if python_type is str:
        return raw_user_id
    if python_type is uuid.UUID:
        return uuid.UUID(raw_user_id)
    return python_type(raw_user_id)


async def get_current_user(site: Any, request: Request) -> Optional[AdminUser]:
    cookie_header = request.headers.get("Cookie")
    if not cookie_header:
        return None

    cookies = parse_cookie_header(cookie_header)
    token = cookies.get("session_token")
    if not token:
        return None

    valid, user_id = verify_session_token(site, token)
    if not valid or user_id is None:
        return None

    async with site.transaction() as session:
        return await session.get(AdminUser, _coerce_user_id(user_id))


async def check_permission(
    site: Any, request: Request, model_name: str, action: str
) -> bool:
    _ = action
    user = await get_current_user(site, request)
    if not user:
        return False

    if user.is_superuser:
        return True

    async with site.transaction() as session:
        stmt = (
            select(Role)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user.id)
        )
        result = await session.execute(stmt)
        roles = result.scalars().all()
        for role in roles:
            if role.accessible_models == ["*"]:
                return True
            if role.accessible_models and model_name in role.accessible_models:
                return True
    return False
