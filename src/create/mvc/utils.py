from typing import Any

import msgspec
from robyn import Response
from starlette import status

JSON_HEADERS = {"content-type": "application/json; charset=utf-8"}


class BaseError(Exception):
    def __init__(
        self, message: str = "", status_code: int = status.HTTP_400_BAD_REQUEST
    ):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class BadRequestError(BaseError):
    def __init__(self, message: str = "Bad request"):
        super().__init__(message, status_code=status.HTTP_400_BAD_REQUEST)


class AuthenticationError(BaseError):
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, status_code=status.HTTP_401_UNAUTHORIZED)


class NotFoundError(BaseError):
    def __init__(self, message: str = "Not found"):
        super().__init__(message, status_code=status.HTTP_404_NOT_FOUND)


class UnprocessableError(BaseError):
    def __init__(self, message: str = "Unprocessable entity"):
        super().__init__(
            message, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
        )


class DatabaseError(BaseError):
    def __init__(self, message: str = "Database error"):
        super().__init__(
            message, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


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
        payload = {"message": exc.message}
        body = _encode({"error": payload})
        return Response(exc.status_code, JSON_HEADERS, body)

    payload = {"message": str(exc) or "Internal Server Error"}
    body = _encode({"error": payload})
    return Response(status.HTTP_500_INTERNAL_SERVER_ERROR, JSON_HEADERS, body)
