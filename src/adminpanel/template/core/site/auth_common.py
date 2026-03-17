"""Shared authentication utilities (ORM-agnostic)."""

from __future__ import annotations

import base64
import json
import secrets
from datetime import datetime
from typing import Any

from robyn import Request

from .helpers import parse_cookie_header, sign_token

ADVISORY_LOCK_ID = 193384911


def generate_session_token(site: Any, user_id: int) -> str:
    timestamp = int(datetime.utcnow().timestamp())
    raw_token = f"{user_id}:{timestamp}:{secrets.token_hex(16)}"
    signature = sign_token(raw_token, site.session_secret)
    return base64.urlsafe_b64encode(
        f"{raw_token}:{signature}".encode()
    ).decode()


def verify_session_token(site: Any, token: str) -> tuple[bool, int | None]:
    try:
        decoded = base64.urlsafe_b64decode(token.encode()).decode()
        raw_token, signature = decoded.rsplit(":", 1)
        expected_signature = sign_token(raw_token, site.session_secret)
        if not secrets.compare_digest(signature, expected_signature):
            return False, None

        user_id, timestamp, _ = raw_token.split(":", 2)
        if (
            datetime.utcnow().timestamp() - int(timestamp)
            > site.session_expire
        ):
            return False, None
        return True, int(user_id)
    except Exception:
        return False, None


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
