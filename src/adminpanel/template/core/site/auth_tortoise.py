from __future__ import annotations

import base64
import json
import secrets
from datetime import datetime
from typing import Any, Optional

from robyn import Request

from ...auth_models import AdminUser, UserRole
from .helpers import parse_cookie_header, sign_token


async def authenticate_credentials(
    site: Any, username: str, password: str
) -> tuple[int, str] | None:
    user = await AdminUser.authenticate(username, password)
    if not user:
        return None

    user.last_login = datetime.utcnow()
    await user.save()
    return int(user.id), str(user.username)


def generate_session_token(site: Any, user_id: int) -> str:
    timestamp = int(datetime.utcnow().timestamp())
    raw_token = f"{user_id}:{timestamp}:{secrets.token_hex(16)}"
    signature = sign_token(raw_token, site.session_secret)
    return base64.urlsafe_b64encode(f"{raw_token}:{signature}".encode()).decode()


def verify_session_token(site: Any, token: str) -> tuple[bool, Optional[int]]:
    try:
        decoded = base64.urlsafe_b64decode(token.encode()).decode()
        raw_token, signature = decoded.rsplit(":", 1)
        expected_signature = sign_token(raw_token, site.session_secret)
        if not secrets.compare_digest(signature, expected_signature):
            return False, None

        user_id, timestamp, _ = raw_token.split(":", 2)
        if datetime.utcnow().timestamp() - int(timestamp) > site.session_expire:
            return False, None
        return True, int(user_id)
    except Exception:
        return False, None


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
        return await AdminUser.get(id=user_id)
    except Exception:
        return None


async def get_language(site: Any, request: Request) -> str:
    session_data = request.headers.get("Cookie")
    if not session_data:
        return site.default_language

    session_dict = parse_cookie_header(session_data)
    payload = session_dict.get("session")
    if not payload:
        return site.default_language

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return site.default_language
    return data.get("language", site.default_language)


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
