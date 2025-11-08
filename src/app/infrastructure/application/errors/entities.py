"""Internal error hierarchy, adapted from src 2."""

from starlette import status

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
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    ) -> None:
        self.message = message or self.__class__.__name__
        self.status_code = status_code
        super().__init__(self.message)


class BadRequestError(BaseError):
    def __init__(self, *, message: str = "Bad request") -> None:
        super().__init__(
            message=message, status_code=status.HTTP_400_BAD_REQUEST
        )


class UnprocessableError(BaseError):
    def __init__(self, *, message: str = "Validation error") -> None:
        super().__init__(
            message=message, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
        )


class NotFoundError(BaseError):
    def __init__(self, *, message: str = "Not found") -> None:
        super().__init__(
            message=message, status_code=status.HTTP_404_NOT_FOUND
        )


class AuthenticationError(BaseError):
    def __init__(self, *, message: str = "Not authenticated") -> None:
        super().__init__(
            message=message, status_code=status.HTTP_401_UNAUTHORIZED
        )


class AuthorizationError(BaseError):
    def __init__(self, *, message: str = "Forbidden") -> None:
        super().__init__(
            message=message, status_code=status.HTTP_403_FORBIDDEN
        )


class DatabaseError(BaseError):
    def __init__(self, *, message: str = "Database error") -> None:
        super().__init__(
            message=message, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
