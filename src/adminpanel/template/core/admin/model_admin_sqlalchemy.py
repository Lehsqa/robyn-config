from __future__ import annotations

from typing import Any, Callable, Type
from urllib.parse import unquote

from robyn import Request
from sqlalchemy import DateTime, String, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.inspection import inspect as sa_inspect

from ..fields import DisplayType, SearchField, TableField
from ..inline import InlineModelAdmin
from .base import BaseModelAdmin
from .helpers import (
    _build_filter_expression,
    _coerce_pk,
    _get_model_column,
    _is_boolean_column,
)
from .queryset import SQLAlchemyQuerySet


class ModelAdmin(BaseModelAdmin):
    inlines: list[Type[InlineModelAdmin]] = []

    def __init__(
        self,
        model: type[Any],
        session_factory: Callable[[], AsyncSession] | None = None,
    ) -> None:
        if session_factory is None:
            raise ValueError(
                "session_factory is required for SQLAlchemy admin"
            )

        self._initialize_common_attributes(model)
        self.session_factory = session_factory
        mapper = sa_inspect(self.model)
        self._columns = {col.name: col for col in mapper.columns}
        pk_columns = [col.name for col in mapper.primary_key]
        self.pk_name = pk_columns[0] if pk_columns else "id"

        self._process_fields()
        self._inline_instances = [
            inline_class(self.model) for inline_class in self.inlines
        ]

    def _process_fields(self) -> None:
        if not self.table_fields:
            self.table_fields = [
                TableField(name=name) for name in self._columns.keys()
            ]

        for field in self.table_fields:
            model_field = self._columns.get(field.name)
            if model_field is None:
                continue
            if model_field.primary_key:
                field.readonly = True
                field.editable = False
            elif isinstance(model_field.type, DateTime):
                field.readonly = True
                field.sortable = True
                if not field.display_type:
                    field.display_type = DisplayType.DATETIME
            elif _is_boolean_column(model_field):
                if not field.display_type:
                    field.display_type = DisplayType.BOOLEAN

            if not hasattr(field, "editable") or field.editable is None:
                field.editable = False

        self._finalize_field_configuration()

    async def get_queryset(
        self, request: Request, params: dict
    ) -> SQLAlchemyQuerySet:
        queryset = SQLAlchemyQuerySet(self.model, self.session_factory)
        normalized_params: dict[str, Any] = {}
        for key, value in params.items():
            normalized_params[key] = (
                unquote(value) if isinstance(value, str) else value
            )

        search_value = normalized_params.get("search", "")
        if search_value:
            search_conditions: list[Any] = []
            search_fields = self.search_fields or [
                SearchField(name=name)
                for name, col in self._columns.items()
                if isinstance(col.type, String)
            ]
            for field in search_fields:
                column = _get_model_column(self.model, field.name)
                if column is None:
                    continue
                search_conditions.append(column.ilike(f"%{search_value}%"))
            if search_conditions:
                queryset = queryset.filter(or_(*search_conditions))

        filter_fields = await self.get_filter_fields()
        for filter_field in filter_fields:
            filter_value = normalized_params.get(filter_field.name)
            if not filter_value:
                continue
            try:
                query_dict = await filter_field.build_filter_query(
                    filter_value
                )
            except Exception:
                query_dict = {}
            if isinstance(query_dict, dict):
                query_dict = {
                    k: v
                    for k, v in query_dict.items()
                    if not k.startswith("_")
                }
                if query_dict:
                    queryset = queryset.filter(**query_dict)

        for key, value in normalized_params.items():
            if key in {"limit", "offset", "search", "sort", "order", "_"}:
                continue
            if any(key == field.name for field in filter_fields):
                continue
            condition = _build_filter_expression(self.model, key, value)
            if condition is not None:
                queryset = queryset.filter(condition)

        return queryset

    def get_filter_choices(self, field_name: str) -> list[tuple]:
        choices = self._get_declared_filter_choices(field_name)
        if choices:
            return choices

        model_field = self._columns.get(field_name)
        if model_field is not None and model_field.type.python_type is bool:
            return [("True", "Yes"), ("False", "No")]
        return []

    async def get_object(self, pk: Any):
        pk_value = _coerce_pk(pk, self._columns.get(self.pk_name))
        session = self.session_factory()
        try:
            return await session.get(self.model, pk_value)
        finally:
            await session.close()

    async def serialize_object(
        self, obj: Any, for_display: bool = True
    ) -> dict:
        result: dict[str, Any] = {}
        for field in self.table_fields:
            try:
                value = getattr(obj, field.name, None)
                if field.display_type == DisplayType.SWITCH:
                    result[field.name] = value
                    continue

                if field.related_model and field.related_key:
                    fk_value = getattr(obj, field.related_key, None)
                    if fk_value:
                        session = self.session_factory()
                        try:
                            related_obj = await session.get(
                                field.related_model, fk_value
                            )
                            if related_obj:
                                related_field = (
                                    self._resolve_related_field_name(field)
                                )
                                related_value = getattr(
                                    related_obj, related_field, None
                                )
                                result[field.name] = (
                                    str(related_value)
                                    if related_value is not None
                                    else ""
                                )
                                continue
                        finally:
                            await session.close()
                    result[field.name] = ""
                    continue

                result[field.name] = await self._format_serialized_value(
                    field, value, for_display=for_display
                )
            except Exception:
                result[field.name] = ""
        return result

    async def process_form_data(
        self,
        data: dict[str, Any],
        *,
        skip_empty_password: bool = False,
        current_object: Any | None = None,
    ) -> dict[str, Any]:
        processed_data: dict[str, Any] = {}
        form_fields = await self.get_add_form_fields()
        for field in form_fields:
            if field.name not in data:
                continue
            field_value = data[field.name]
            if self._should_skip_password_value(
                field=field,
                field_value=field_value,
                skip_empty_password=skip_empty_password,
                current_object=current_object,
            ):
                continue
            processed_value = field.process_value(field_value)
            processed_data[field.name] = self._hash_password_if_needed(
                field, processed_value
            )
        return processed_data

    async def handle_edit(
        self, request: Request, object_id: str, data: dict
    ) -> tuple[bool, str]:
        session = self.session_factory()
        try:
            obj = await session.get(
                self.model,
                _coerce_pk(object_id, self._columns.get(self.pk_name)),
            )
            if not obj:
                return False, "Record not found"
            processed = await self.process_form_data(
                data,
                skip_empty_password=True,
                current_object=obj,
            )
            for field, value in processed.items():
                if field in self._columns:
                    setattr(obj, field, value)
            await session.commit()
            return True, "Updated successfully"
        except SQLAlchemyError as exc:
            await session.rollback()
            return False, f"Update failed: {exc}"
        finally:
            await session.close()

    async def handle_add(
        self, request: Request, data: dict
    ) -> tuple[bool, str]:
        session = self.session_factory()
        try:
            payload = await self.process_form_data(data)
            obj = self.model(**payload)
            session.add(obj)
            await session.commit()
            return True, "Created successfully"
        except SQLAlchemyError as exc:
            await session.rollback()
            return False, f"Create failed: {exc}"
        finally:
            await session.close()

    async def handle_delete(
        self, request: Request, object_id: str
    ) -> tuple[bool, str]:
        session = self.session_factory()
        try:
            obj = await session.get(
                self.model,
                _coerce_pk(object_id, self._columns.get(self.pk_name)),
            )
            if not obj:
                return False, "Record not found"
            await session.delete(obj)
            await session.commit()
            return True, "Deleted successfully"
        except SQLAlchemyError as exc:
            await session.rollback()
            return False, f"Delete failed: {exc}"
        finally:
            await session.close()

    async def handle_batch_delete(
        self, request: Request, ids: list
    ) -> tuple[bool, str, int]:
        deleted = 0
        for item in ids:
            success, _ = await self.handle_delete(request, item)
            if success:
                deleted += 1
        if deleted > 0:
            return True, f"Deleted {deleted} records", deleted
        return False, "No records were deleted", 0

    async def handle_query(
        self, request: Request, params: dict
    ) -> tuple[SQLAlchemyQuerySet, int]:
        queryset = await self.get_queryset(request, params)
        if params.get("sort"):
            direction = "-" if params.get("order") == "desc" else ""
            queryset = queryset.order_by(f"{direction}{params['sort']}")
        elif self.default_ordering:
            queryset = queryset.order_by(*self.default_ordering)
        total = await queryset.count()
        offset = max(0, int(params.get("offset", 0)))
        limit = max(1, int(params.get("limit", self.per_page)))
        queryset = queryset.offset(offset).limit(limit)
        return queryset, total
