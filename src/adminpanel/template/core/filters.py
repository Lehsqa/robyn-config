from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from ._utils import (
    _extract_related_ids,
    _query_related_objects,
    _resolve_related_field_name,
)


class FilterType(Enum):
    """Filter types for admin table query controls."""

    INPUT = "input"
    SELECT = "select"
    DATE_RANGE = "date_range"
    NUMBER_RANGE = "number_range"
    BOOLEAN = "boolean"


@dataclass
class FilterField:
    """Base filter field configuration."""

    name: str
    label: str | None = None
    filter_type: FilterType = FilterType.INPUT
    choices: dict[Any, str] | None = None
    multiple: bool = False
    placeholder: str | None = None
    operator: str = "icontains"
    related_model: type[Any] | None = None
    related_key: str | None = None

    def __post_init__(self):
        if self.label is None:
            self.label = self.name.replace("_", " ").title()

    def to_dict(self) -> dict:
        """Serialize filter config for frontend usage."""
        data = {
            "name": self.name,
            "label": self.label,
            "type": self.filter_type.value,
            "choices": self.choices,
            "placeholder": self.placeholder,
            "multiple": self.multiple,
            "operator": self.operator,
        }

        if self.related_model:
            data.update({"related_model": self.related_model.__name__})

        return data

    async def build_filter_query(self, filter_value: str) -> dict:
        """Build backend filter expressions from frontend values."""
        if not filter_value:
            return {}

        if self.related_model and self.related_key:
            related_field = _resolve_related_field_name(
                self.name, self.related_model
            )
            related_objects = await _query_related_objects(
                self.related_model,
                f"{related_field}__icontains",
                filter_value,
            )
            related_ids = _extract_related_ids(related_objects)
            if not related_ids:
                return {"id": None}
            return {f"{self.related_key}__in": related_ids}

        return {f"{self.name}__{self.operator}": filter_value}


class InputFilter(FilterField):
    """Text input filter."""

    def __init__(
        self,
        name: str,
        label: str | None = None,
        placeholder: str | None = None,
        operator: str = "icontains",
        related_model: type[Any] | None = None,
        related_key: str | None = None,
    ):
        super().__init__(
            name=name,
            label=label,
            filter_type=FilterType.INPUT,
            placeholder=placeholder,
            operator=operator,
            related_model=related_model,
            related_key=related_key,
        )


class SelectFilter(FilterField):
    """Select filter."""

    def __init__(
        self,
        name: str,
        choices: dict[Any, str],
        label: str | None = None,
        multiple: bool = False,
        related_model: type[Any] | None = None,
        related_key: str | None = None,
    ):
        super().__init__(
            name=name,
            label=label,
            filter_type=FilterType.SELECT,
            choices=choices,
            multiple=multiple,
            related_model=related_model,
            related_key=related_key,
        )


class DateRangeFilter(FilterField):
    """Date range filter."""

    def __init__(self, name: str, label: str | None = None):
        super().__init__(
            name=name, label=label, filter_type=FilterType.DATE_RANGE
        )


class NumberRangeFilter(FilterField):
    """Number range filter."""

    def __init__(self, name: str, label: str | None = None):
        super().__init__(
            name=name, label=label, filter_type=FilterType.NUMBER_RANGE
        )


class BooleanFilter(FilterField):
    """Boolean filter."""

    def __init__(self, name: str, label: str | None = None):
        super().__init__(
            name=name,
            label=label,
            filter_type=FilterType.BOOLEAN,
            choices={True: "Yes", False: "No"},
        )
