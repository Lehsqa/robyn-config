from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

ALLOWED_UPLOAD_EXTENSIONS: tuple[str, ...] = (
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".sql",
    ".xlsx",
    ".csv",
    ".xls",
)


def parse_cookie_header(header: str) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for item in header.split(";"):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        cookies[key.strip()] = value.strip()
    return cookies


def sign_token(raw_token: str, secret: str) -> str:
    return hashlib.sha256(f"{raw_token}:{secret}".encode()).hexdigest()


def encode_cookie_payload(payload: str) -> str:
    return base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")


def decode_cookie_payload(encoded: str) -> str:
    padding = "=" * (-len(encoded) % 4)
    return base64.urlsafe_b64decode(f"{encoded}{padding}".encode()).decode()


def body_to_text(body: Any) -> str:
    if isinstance(body, bytes):
        return body.decode("utf-8")
    return str(body or "")


def first_value(value: Any, default: Any = None) -> Any:
    if isinstance(value, list):
        return value[0] if value else default
    if value is None:
        return default
    return value


def parse_form_payload(params: dict[str, list[str]]) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for key, value in params.items():
        raw = first_value(value, "")
        try:
            data[key] = json.loads(raw)
        except Exception:
            data[key] = raw
    return data


def to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
