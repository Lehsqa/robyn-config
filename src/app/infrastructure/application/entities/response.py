from enum import StrEnum
from typing import Any, Mapping

from pydantic import Field, conlist

from .base import PublicEntity

__all__ = (
    "ErrorType",
    "ErrorDetail",
    "ErrorResponse",
    "ErrorResponseMulti",
)


class ErrorType(StrEnum):
    INTERNAL = "internal"
    EXTERNAL = "external"
    VALIDATION = "validation"
    MISSING = "missing"


class ErrorDetail(PublicEntity):
    path: list[str] = Field(default_factory=list)
    type: ErrorType = Field(default=ErrorType.INTERNAL)


class ErrorResponse(PublicEntity):
    message: str
    detail: ErrorDetail = Field(default_factory=ErrorDetail)


class ErrorResponseMulti(PublicEntity):
    result: conlist(ErrorResponse, min_length=1)  # type: ignore[valid-type]


_Response = Mapping[int | str, dict[str, Any]]
