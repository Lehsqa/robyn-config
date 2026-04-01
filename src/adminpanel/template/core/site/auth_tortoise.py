from __future__ import annotations

from datetime import datetime
import uuid
from typing import Any, Optional

from robyn import Request

from ...auth_models import AdminUser, UserRole
from .auth_common import (
    generate_session_token,  # noqa: F401
    get_language,  # noqa: F401
    verify_session_token,
)
from .helpers import parse_cookie_header


async def authenticate_credentials(
    site: Any, username: str, password: str
) -> tuple[str, str] | None:
    user = await AdminUser.authenticate(username, password)
    if not user:
        return None

    user.last_login = datetime.utcnow()
    await user.save()
    return str(user.id), str(user.username)


def _coerce_user_id(raw_user_id: str) -> Any:
    id_field = AdminUser._meta.fields_map.get("id")
    field_name = type(id_field).__name__ if id_field is not None else ""

    if field_name == "IntField":
        return int(raw_user_id)
    if field_name == "UUIDField":
        return uuid.UUID(raw_user_id)
    return raw_user_id


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

    try:
        return await AdminUser.get(id=_coerce_user_id(user_id))
    except Exception:
        return None


async def check_permission(
    site: Any, request: Request, model_name: str, action: str
) -> bool:
    _ = action
    user = await get_current_user(site, request)
    if not user:
        return False

    if user.is_superuser:
        return True

    user_roles = await UserRole.filter(user=user).prefetch_related("role")
    roles = [user_role.role for user_role in user_roles]
    for role in roles:
        if role.accessible_models == ["*"]:
            return True
        if model_name in role.accessible_models:
            return True
    return False
