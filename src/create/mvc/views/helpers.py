from typing import Type, TypeVar

import msgspec
from pydantic import BaseModel, ValidationError
from robyn import Request

from ..utils import BadRequestError

T = TypeVar("T", bound=BaseModel)


def _clean_body(body: bytes | str | None) -> bytes:
    if body is None:
        return b"{}"
    raw = body.encode() if isinstance(body, str) else body
    return raw or b"{}"


async def parse_body(request: Request, model: Type[T]) -> T:
    try:
        payload = msgspec.json.decode(_clean_body(request.body))
    except msgspec.DecodeError as exc:
        raise BadRequestError(message=f"JSON is malformed: {exc}") from exc

    if not isinstance(payload, dict):
        raise BadRequestError(message="Request body must be an object")

    try:
        return model(**payload)
    except ValidationError as exc:
        raise BadRequestError(message=exc.errors()[0]["msg"]) from exc


def _normalized_headers(request: Request) -> dict[str, str]:
    raw_headers = getattr(request, "headers", None) or {}
    if isinstance(raw_headers, dict):
        items = raw_headers.items()
    else:
        try:
            items = dict(raw_headers).items()
        except Exception:
            try:
                items = raw_headers.items()
            except Exception:
                return {}

    headers: dict[str, str] = {}
    for key, value in items:
        if isinstance(key, bytes):
            key = key.decode()
        if isinstance(value, bytes):
            value = value.decode()
        headers[str(key).lower()] = str(value)
    return headers


def get_header(request: Request, name: str) -> str | None:
    return _normalized_headers(request).get(name.lower())
