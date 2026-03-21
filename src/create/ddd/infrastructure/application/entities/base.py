"""Base entities used across the Robyn app."""

from typing import TypeVar

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel, to_snake


class InternalEntity(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=True,
        validate_assignment=True,
        arbitrary_types_allowed=True,
        from_attributes=True,
    )


_InternalEntity = TypeVar("_InternalEntity", bound=InternalEntity)


class PublicEntity(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        use_enum_values=True,
        validate_assignment=True,
        populate_by_name=True,
        arbitrary_types_allowed=True,
        from_attributes=True,
        loc_by_alias=True,
        alias_generator=to_camel,
    )

    def model_dump_json(self, *, by_alias: bool = True, **kwargs) -> str:
        return super().model_dump_json(by_alias=by_alias, **kwargs)


_PublicEntity = TypeVar("_PublicEntity", bound=PublicEntity)


class PublicSnakeCaseEntity(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        use_enum_values=True,
        validate_assignment=True,
        populate_by_name=True,
        arbitrary_types_allowed=True,
        from_attributes=True,
        loc_by_alias=True,
        alias_generator=to_snake,
    )


_PublicSnakeCaseEntity = TypeVar(
    "_PublicSnakeCaseEntity", bound=PublicSnakeCaseEntity
)
