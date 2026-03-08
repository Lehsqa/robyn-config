from __future__ import annotations

import asyncio
from dataclasses import dataclass, field as dataclass_field
from enum import Enum
from typing import Any, Callable


class DisplayType(Enum):
    """Display types used by admin table and form fields."""

    TEXT = "text"
    DATE = "date"
    DATETIME = "datetime"
    IMAGE = "image"
    FILE_UPLOAD = "file_upload"
    STATUS = "status"
    BOOLEAN = "boolean"
    LINK = "link"
    HTML = "html"
    CUSTOM = "custom"
    PASSWORD = "password"
    EMAIL = "email"
    SELECT = "select"
    SWITCH = "switch"
    JSON = "json"


def _coerce_boolean(value: Any) -> bool:
    if isinstance(value, bool):
        return value

    if value is None:
        return False

    if isinstance(value, (int, float)):
        return bool(value)

    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "t", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "f", "no", "n", "off", ""}:
            return False

    return bool(value)


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


@dataclass
class TableAction:
    """Table action button configuration."""

    name: str
    label: str
    icon: str = ""
    btn_class: str = "btn-primary"
    inline_model: str | None = None


@dataclass
class TableField:
    """Table field configuration."""

    name: str
    label: str | None = None
    display_type: DisplayType | None = None
    sortable: bool = False
    searchable: bool = False
    filterable: bool = False
    editable: bool = True
    readonly: bool = False
    visible: bool = True
    is_link: bool = False
    width: int | str | None = None
    formatter: Callable[..., Any] | None = None
    hidden: bool = False
    choices: dict[Any, Any] | None = None
    labels: dict[Any, str] | None = None
    related_model: type[Any] | None = None
    related_key: str | None = None
    actions: list[TableAction] = dataclass_field(default_factory=list)

    def __post_init__(self):
        if self.label is None:
            self.label = self.name.replace("_", " ").title()

        if self.display_type == DisplayType.LINK:
            self.is_link = True

        if self.related_model and self.related_key:
            self.related_field = _resolve_related_field_name(
                self.name, self.related_model
            )
            self.display_name = self.name
        else:
            self.display_name = self.name

    async def format_value(
        self, value: Any, instance: Any | None = None
    ) -> str:
        """Format field values for rendering."""
        if value is None:
            return ""

        if self.related_model and self.related_key and instance:
            try:
                fk_value = getattr(instance, self.related_key, None)
                if not fk_value:
                    return ""

                getter = getattr(self.related_model, "get", None)
                if not callable(getter):
                    return ""

                related_obj = await _await_if_needed(getter(id=fk_value))
                if related_obj:
                    related_value = getattr(
                        related_obj, self.related_field, None
                    )
                    return (
                        str(related_value) if related_value is not None else ""
                    )
                return ""
            except Exception:
                return ""

        if self.formatter:
            try:
                formatted = self.formatter(value)
                formatted = await _await_if_needed(formatted)
                return str(formatted) if formatted is not None else ""
            except Exception:
                return str(value)

        return str(value)

    def to_dict(self) -> dict:
        """Serialize field config for frontend usage."""
        data = {
            "name": self.display_name,
            "label": self.label,
            "display_type": (
                self.display_type.value if self.display_type else "text"
            ),
            "sortable": self.sortable,
            "searchable": self.searchable,
            "filterable": self.filterable,
            "editable": self.editable,
            "readonly": self.readonly,
            "visible": self.visible,
            "is_link": self.is_link,
            "width": self.width,
            "hidden": self.hidden,
            "has_formatter": bool(self.formatter),
            "choices": self.choices,
            "labels": self.labels,
        }

        if self.related_model and self.related_key:
            data.update(
                {
                    "related_model": self.related_model.__name__,
                    "related_key": self.related_key,
                    "related_field": self.related_field,
                }
            )

        return data


@dataclass
class FormField:
    """Form field configuration."""

    name: str
    label: str | None = None
    field_type: DisplayType | None = None
    required: bool = False
    readonly: bool = False
    help_text: str | None = None
    placeholder: str | None = None
    validators: list[Callable[..., Any]] = dataclass_field(default_factory=list)
    choices: dict[Any, str] | None = None
    default: Any = None
    processor: Callable[..., Any] | None = None
    upload_path: str | None = None
    accept: str | None = None
    max_size: int | None = None
    multiple: bool = False
    preview: bool = True
    drag_text: str | None = None

    def __post_init__(self):
        if self.label is None:
            self.label = self.name.replace("_", " ").title()

    def process_value(self, value: Any) -> Any:
        """Apply built-in coercions and optional custom processing."""
        if self.field_type in {DisplayType.BOOLEAN, DisplayType.SWITCH}:
            value = _coerce_boolean(value)
        if self.processor:
            return self.processor(value)
        return value

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "label": self.label,
            "field_type": self.field_type.value if self.field_type else None,
            "required": self.required,
            "readonly": self.readonly,
            "help_text": self.help_text,
            "placeholder": self.placeholder,
            "choices": self.choices,
            "default": self.default,
            "upload_path": self.upload_path,
            "accept": self.accept,
            "max_size": self.max_size,
            "multiple": self.multiple,
            "preview": self.preview,
            "drag_text": self.drag_text,
        }


@dataclass
class SearchField:
    """Search field configuration."""

    name: str
    label: str | None = None
    placeholder: str = ""
    operator: str = "icontains"
    related_model: type[Any] | None = None
    related_key: str | None = None

    def __post_init__(self):
        if self.label is None:
            self.label = self.name.replace("_", " ").title()
        if not self.placeholder:
            self.placeholder = f"{self.label}"

    def to_dict(self) -> dict:
        data = {
            "name": self.name,
            "label": self.label,
            "placeholder": self.placeholder,
            "operator": self.operator,
        }
        if self.related_model:
            data.update(
                {
                    "related_model": self.related_model.__name__,
                }
            )
        return data

    async def build_search_query(self, search_value: str) -> dict:
        if not search_value:
            return {}

        if self.related_model and self.related_key:
            related_field = _resolve_related_field_name(
                self.name, self.related_model
            )
            related_objects = await _query_related_objects(
                self.related_model,
                f"{related_field}__icontains",
                search_value,
            )
            related_ids = _extract_related_ids(related_objects)
            if not related_ids:
                return {"id": None}
            return {f"{self.related_key}__in": related_ids}

        return {f"{self.name}": search_value}
