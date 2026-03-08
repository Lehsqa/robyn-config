from __future__ import annotations

import asyncio
from typing import Any

from .fields import FormField, TableField


class InlineModelAdmin:
    """Base class for inline admin sections."""

    model: type[Any] | None = None
    fk_field: str | None = None
    extra: int = 1
    max_num: int | None = None
    can_delete: bool = True
    verbose_name: str | None = None

    table_fields: list[TableField] = []
    form_fields: list[FormField] = []

    default_ordering: list[str] | None = None

    def __init__(self, parent_model: type[Any]):
        if not self.model:
            raise ValueError("Inline model is required")
        if not self.fk_field:
            raise ValueError("Inline fk_field is required")

        self.parent_model = parent_model
        if not self.verbose_name:
            if hasattr(self.model, "Meta") and hasattr(
                self.model.Meta, "description"
            ):
                self.verbose_name = self.model.Meta.description
            else:
                self.verbose_name = self.model.__name__

        if self.default_ordering is None:
            self.default_ordering = []
        self.is_inline = True

    async def get_queryset(self, parent_instance: Any):
        """Return related rows for a parent instance when supported."""
        if not parent_instance:
            return []

        parent_id = getattr(parent_instance, "id", None)
        if parent_id is None:
            return []

        filter_method = getattr(self.model, "filter", None)
        if not callable(filter_method):
            return []

        queryset = filter_method(**{self.fk_field: parent_id})
        if self.default_ordering and hasattr(queryset, "order_by"):
            queryset = queryset.order_by(*self.default_ordering)

        return queryset

    def get_formset(self):
        """Build frontend metadata for inline form rendering."""
        ordering_fields = [
            field.name for field in self.table_fields if field.sortable
        ]
        return {
            "model": self.model.__name__,
            "fk_field": self.fk_field,
            "extra": self.extra,
            "max_num": self.max_num,
            "can_delete": self.can_delete,
            "fields": [field.to_dict() for field in self.form_fields],
            "table_fields": [field.to_dict() for field in self.table_fields],
            "verbose_name": self.verbose_name,
            "title": self.verbose_name,
            "default_ordering": self.default_ordering,
            "ordering_fields": ordering_fields,
        }

    async def serialize_object(
        self, obj: Any, for_display: bool = True
    ) -> dict:
        """Serialize inline object values for API responses."""
        result = {"id": str(getattr(obj, "id", ""))}

        for field in self.table_fields:
            try:
                if field.related_model and field.related_key:
                    fk_value = getattr(obj, field.related_key)
                    if fk_value:
                        try:
                            getter = getattr(field.related_model, "get", None)
                            if not callable(getter):
                                raise AttributeError("get")
                            related_obj = getter(id=fk_value)
                            if asyncio.iscoroutine(related_obj) or hasattr(
                                related_obj, "__await__"
                            ):
                                related_obj = await related_obj
                            if related_obj:
                                related_field = field.name.split("_")[-1]
                                related_value = getattr(
                                    related_obj, related_field
                                )
                                result[field.name] = (
                                    str(related_value)
                                    if related_value is not None
                                    else ""
                                )
                                continue
                        except Exception as exc:
                            print(f"Error getting related object: {exc}")
                    result[field.name] = ""
                else:
                    value = getattr(obj, field.name, None)
                    if for_display and field.formatter and value is not None:
                        try:
                            if asyncio.iscoroutinefunction(field.formatter):
                                result[field.name] = await field.formatter(
                                    value
                                )
                            else:
                                result[field.name] = field.formatter(value)
                        except Exception as exc:
                            print(
                                f"Error formatting field {field.name}: {exc}"
                            )
                            result[field.name] = (
                                str(value) if value is not None else ""
                            )
                    else:
                        result[field.name] = (
                            str(value) if value is not None else ""
                        )
            except Exception as exc:
                print(f"Error processing field {field.name}: {exc}")
                result[field.name] = ""

        return result
