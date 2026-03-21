"""Internal error hierarchy, adapted from src 2."""

__all__ = (
    "BaseError",
    "BadRequestError",
    "UnprocessableError",
    "NotFoundError",
    "AuthenticationError",
    "AuthorizationError",
    "DatabaseError",
)


class BaseError(Exception):
    def __init__(
        self,
        *,
        message: str = "",
        status_code: int = 500,
    ) -> None:
        self.message = message or self.__class__.__name__
        self.status_code = status_code
        super().__init__(self.message)


class BadRequestError(BaseError):
    def __init__(self, *, message: str = "Bad request") -> None:
        super().__init__(message=message, status_code=400)


class UnprocessableError(BaseError):
    def __init__(self, *, message: str = "Validation error") -> None:
        super().__init__(message=message, status_code=422)


class NotFoundError(BaseError):
    def __init__(self, *, message: str = "Not found") -> None:
        super().__init__(message=message, status_code=404)


class AuthenticationError(BaseError):
    def __init__(self, *, message: str = "Not authenticated") -> None:
        super().__init__(message=message, status_code=401)


class AuthorizationError(BaseError):
    def __init__(self, *, message: str = "Forbidden") -> None:
        super().__init__(message=message, status_code=403)


class DatabaseError(BaseError):
    def __init__(self, *, message: str = "Database error") -> None:
        super().__init__(message=message, status_code=500)
