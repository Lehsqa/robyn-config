import json
from typing import Any

from robyn import Response

JSON_HEADERS = {"content-type": "application/json; charset=utf-8"}


class BaseError(Exception):
    def __init__(self, message: str = "", status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class BadRequestError(BaseError):
    def __init__(self, message: str = "Bad request"):
        super().__init__(message, status_code=400)


class AuthenticationError(BaseError):
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, status_code=401)


class NotFoundError(BaseError):
    def __init__(self, message: str = "Not found"):
        super().__init__(message, status_code=404)


class UnprocessableError(BaseError):
    def __init__(self, message: str = "Unprocessable entity"):
        super().__init__(message, status_code=422)


class DatabaseError(BaseError):
    def __init__(self, message: str = "Database error"):
        super().__init__(message, status_code=500)


def json_response(payload: Any, status_code: int = 200) -> Response:
    return Response(
        status_code,
        JSON_HEADERS,
        json.dumps({"result": payload}),
    )


def error_response(exc: Exception) -> Response:
    if isinstance(exc, BaseError):
        body = json.dumps({"error": {"message": exc.message}})
        return Response(exc.status_code, JSON_HEADERS, body)

    body = json.dumps({"error": {"message": str(exc) or "Internal Server Error"}})
    return Response(500, JSON_HEADERS, body)
