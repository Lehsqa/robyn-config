"""HTTP helpers for Robyn routes."""

from typing import Any

import msgspec
from robyn import Response
from starlette import status

from .entities.response import ErrorResponse
from .errors import BaseError

JSON_HEADERS = {"content-type": "application/json; charset=utf-8"}


def _encode(payload: Any) -> bytes:
    return msgspec.json.encode(payload)


def json_response(
    payload: Any, status_code: int = status.HTTP_200_OK
) -> Response:
    return Response(
        status_code,
        JSON_HEADERS,
        _encode({"result": payload}),
    )


def error_response(exc: Exception) -> Response:
    if isinstance(exc, BaseError):
        payload = ErrorResponse(message=exc.message).model_dump(by_alias=True)
        body = _encode({"error": payload})
        return Response(exc.status_code, JSON_HEADERS, body)

    payload = ErrorResponse(
        message=str(exc) or "Internal Server Error"
    ).model_dump(by_alias=True)
    body = _encode({"error": payload})
    return Response(status.HTTP_500_INTERNAL_SERVER_ERROR, JSON_HEADERS, body)
