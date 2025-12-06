"""Simple signed-cookie session middleware for Robyn."""

from __future__ import annotations

import hashlib
import hmac
import json
from base64 import urlsafe_b64decode, urlsafe_b64encode
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Mapping, MutableMapping, cast

from robyn import Request, Response, Robyn

from ....config import settings

SESSION_COOKIE_NAME = "robyn_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 14  # 14 days


@dataclass
class SessionState:
    data: dict[str, Any]
    serialized: str


_state: ContextVar[SessionState | None] = ContextVar(
    "session_state", default=None
)


def get_session() -> dict[str, Any]:
    state = _state.get()
    return state.data if state else {}


def _extract_cookie(raw_cookie_header: str | None) -> str | None:
    if not raw_cookie_header:
        return None

    for chunk in raw_cookie_header.split(";"):
        name, _, value = chunk.strip().partition("=")
        if name == SESSION_COOKIE_NAME:
            return value or None
    return None


def _encode_session(session: dict[str, Any], secret: bytes) -> str:
    payload = json.dumps(
        session, separators=(",", ":"), sort_keys=True
    ).encode()
    signature = hmac.new(secret, payload, hashlib.sha256).hexdigest()
    return f"{urlsafe_b64encode(payload).decode()}.{signature}"


def _decode_session(value: str, secret: bytes) -> tuple[dict[str, Any], str]:
    try:
        payload_b64, signature = value.split(".", 1)
        payload = urlsafe_b64decode(_pad_base64(payload_b64))
        expected = hmac.new(secret, payload, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return {}, ""
        data = json.loads(payload)
        if isinstance(data, dict):
            return data, value
    except Exception:
        pass
    return {}, ""


def _pad_base64(value: str) -> bytes:
    padding = (-len(value)) % 4
    return (value + ("=" * padding)).encode()


def _cookie_header(serialized: str | None) -> str:
    base = f"{SESSION_COOKIE_NAME}={serialized or ''}"
    parts = [base, "Path=/", "HttpOnly", "SameSite=Lax"]
    if serialized is None:
        parts.append("Max-Age=0")
    else:
        parts.append(f"Max-Age={SESSION_MAX_AGE}")
    return "; ".join(parts)


def register(app: Robyn) -> None:
    secret = settings.authentication.session_secret_key.encode()

    @app.before_request()
    def load_session(request: Request):
        raw_headers = getattr(request, "headers", {}) or {}
        if isinstance(raw_headers, dict):
            header_map = raw_headers
        else:  # Robyn exposes Headers objects; convert defensively
            try:
                header_map = dict(raw_headers)  # type: ignore[arg-type]
            except Exception:  # pragma: no cover - safety net
                header_map = {}

        raw_cookie = None
        for key, value in header_map.items():
            if isinstance(key, bytes):
                key = key.decode()
            if key.lower() == "cookie":
                raw_cookie = value if isinstance(value, str) else str(value)
                break

        cookie_value = _extract_cookie(raw_cookie)
        session_data: dict[str, Any]
        serialized: str
        if cookie_value:
            session_data, serialized = _decode_session(cookie_value, secret)
        else:
            session_data, serialized = {}, ""

        state = SessionState(data=session_data, serialized=serialized)
        _state.set(state)
        # Robyn Request objects don't allow setting arbitrary attributes, so
        # consumers should import `get_session()` from this module instead.
        return request

    @app.after_request()
    def persist_session(response: Response):
        state = _state.get()
        if state is None:
            return response

        headers_source = response.headers
        if isinstance(headers_source, MutableMapping):
            headers = dict(headers_source.items())
        elif headers_source is None:
            headers = {}
        else:
            headers = dict(cast(Mapping[str, Any], headers_source).items())
        session_data = state.data
        serialized = state.serialized

        if not session_data:
            if serialized:
                headers["set-cookie"] = _cookie_header(None)
        else:
            new_serialized = _encode_session(session_data, secret)
            if new_serialized != serialized:
                headers["set-cookie"] = _cookie_header(new_serialized)

        if headers:
            response.headers = headers

        _state.set(None)
        return response
