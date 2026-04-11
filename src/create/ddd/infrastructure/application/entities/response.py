from collections.abc import Mapping
from enum import StrEnum
from typing import Annotated, Any, Generic

from pydantic import Field, conlist, field_validator

from .base import PublicEntity, _PublicEntity

__all__ = (
    "JSON_HEADERS",
    "ResponseMulti",
    "Response",
    "_Response",
    "ErrorType",
    "ErrorDetail",
    "ErrorResponse",
    "ErrorResponseMulti",
)

JSON_HEADERS = {"content-type": "application/json; charset=utf-8"}


class ResponseMulti(PublicEntity, Generic[_PublicEntity]):
    """Generic response model that consist multiple results."""

    result: list[_PublicEntity]


class Response(PublicEntity, Generic[_PublicEntity]):
    """Generic response model that consist only one result."""

    result: _PublicEntity


_Response = Mapping[int | str, dict[str, Any]]


class ErrorType(StrEnum):
    """Error type enum."""

    INTERNAL = "internal"
    EXTERNAL = "external"
    VALIDATION = "validation"
    MISSING = "missing"


class ErrorDetail(PublicEntity):
    """Error detail model."""

    path: Annotated[
        list[str],
        Field(
            description="The path to the field that raised the error",
            default_factory=list,
        ),
    ]
    type: Annotated[
        ErrorType,
        Field(description="The error type", default=ErrorType.INTERNAL),
    ]

    @field_validator("type", mode="before")
    def type_validator(cls, value: str) -> str:
        """Check if the error type is valid."""

        if value not in ErrorType.__members__:
            return ErrorType.INTERNAL

        return value


class ErrorResponse(PublicEntity):
    """Error response model."""

    message: Annotated[
        str, Field(description="This field represent the message")
    ]
    detail: Annotated[
        ErrorDetail,
        Field(
            description="This field represents error details",
            default_factory=ErrorDetail,
        ),
    ]


class ErrorResponseMulti(PublicEntity):
    """The public error respnse model that includes multiple objects."""

    result: conlist(ErrorResponse, min_length=1)  # type: ignore
