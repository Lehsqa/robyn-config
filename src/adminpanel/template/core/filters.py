from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Any


async def _await_if_needed(value: Any) -> Any:
    if asyncio.iscoroutine(value):
        return await value
    if hasattr(value, "__await__"):
        return await value
    return value


def _normalize_collection(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    try:
        return list(value)
    except TypeError:
        return [value]


def _resolve_related_field_name(
    field_name: str, related_model: type[Any]
) -> str:
    model_prefix = f"{related_model.__name__}_"
    if field_name.startswith(model_prefix):
        resolved = field_name[len(model_prefix) :]
        if resolved:
            return resolved
    parts = field_name.split("_")
    if len(parts) > 1:
        return parts[-1]
    return "id"


async def _query_related_objects(
    related_model: type[Any], lookup: str, value: str
) -> list[Any]:
    filter_method = getattr(related_model, "filter", None)
    if not callable(filter_method):
        return []

    try:
        result = filter_method(**{lookup: value})
        resolved = await _await_if_needed(result)
    except Exception:
        return []

    return _normalize_collection(resolved)


def _extract_related_ids(objects: list[Any]) -> list[Any]:
    related_ids: list[Any] = []
    for obj in objects:
        obj_id = getattr(obj, "id", None)
        if obj_id is not None:
            related_ids.append(obj_id)
    return related_ids


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
