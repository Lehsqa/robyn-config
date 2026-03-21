"""HTTP error response builder."""

import json

from robyn import Response

from ..entities.response import ErrorResponse, JSON_HEADERS
from .entities import BaseError

__all__ = ("error_response",)


def error_response(exc: Exception) -> Response:
    if isinstance(exc, BaseError):
        payload = ErrorResponse(message=exc.message).model_dump(by_alias=True)
        body = json.dumps({"error": payload})
        return Response(exc.status_code, JSON_HEADERS, body)

    payload = ErrorResponse(
        message=str(exc) or "Internal Server Error"
    ).model_dump(by_alias=True)
    body = json.dumps({"error": payload})
    return Response(500, JSON_HEADERS, body)
