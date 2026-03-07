from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Callable, List, Optional, Type
from urllib.parse import unquote

from robyn import Request
from sqlalchemy import (
    DateTime,
    Integer,
    String,
    and_,
    delete,
    func,
    or_,
    select,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.inspection import inspect as sa_inspect

from .fields import FormField, SearchField, TableField, DisplayType
from .filters import FilterField
from .inline import InlineModelAdmin


@dataclass
class _QueryState:
    filters: list[Any]
    order: list[Any]
    offset: int
    limit: int | None


class SQLAlchemyQuerySet:
    def __init__(
        self,
        model: type[Any],
        session_factory: Callable[[], AsyncSession],
        state: _QueryState | None = None,
    ) -> None:
        self.model = model
        self.session_factory = session_factory
        self._state = state or _QueryState(
            filters=[], order=[], offset=0, limit=None
        )

    def _clone(self) -> "SQLAlchemyQuerySet":
        return SQLAlchemyQuerySet(
            self.model,
            self.session_factory,
            _QueryState(
                filters=list(self._state.filters),
                order=list(self._state.order),
                offset=self._state.offset,
                limit=self._state.limit,
            ),
        )

    def filter(self, *conditions: Any, **kwargs: Any) -> "SQLAlchemyQuerySet":
        clone = self._clone()
        for condition in conditions:
            if condition is None:
                continue
            clone._state.filters.append(condition)
        for key, value in kwargs.items():
            condition = _build_filter_expression(self.model, key, value)
            if condition is not None:
                clone._state.filters.append(condition)
        return clone

    def order_by(self, *order_fields: str) -> "SQLAlchemyQuerySet":
        clone = self._clone()
        for item in order_fields:
            if not item:
                continue
            if item.startswith("-"):
                column = _get_model_column(self.model, item[1:])
                if column is not None:
                    clone._state.order.append(column.desc())
            else:
                column = _get_model_column(self.model, item)
                if column is not None:
                    clone._state.order.append(column.asc())
        return clone

    def offset(self, value: int) -> "SQLAlchemyQuerySet":
        clone = self._clone()
        clone._state.offset = max(0, int(value))
        return clone

    def limit(self, value: int) -> "SQLAlchemyQuerySet":
        clone = self._clone()
        clone._state.limit = max(0, int(value))
        return clone

    async def count(self) -> int:
        stmt = select(func.count()).select_from(self.model)
        if self._state.filters:
            stmt = stmt.where(and_(*self._state.filters))
        session = self.session_factory()
        try:
            result = await session.execute(stmt)
            count = result.scalar_one_or_none()
            return int(count or 0)
        finally:
            await session.close()

    async def delete(self) -> int:
        stmt = delete(self.model)
        if self._state.filters:
            stmt = stmt.where(and_(*self._state.filters))
        session = self.session_factory()
        try:
            result = await session.execute(stmt)
            await session.commit()
            return int(result.rowcount or 0)
        finally:
            await session.close()

    async def all(self) -> list[Any]:
        stmt = select(self.model)
        if self._state.filters:
            stmt = stmt.where(and_(*self._state.filters))
        if self._state.order:
            stmt = stmt.order_by(*self._state.order)
        if self._state.offset:
            stmt = stmt.offset(self._state.offset)
        if self._state.limit is not None:
            stmt = stmt.limit(self._state.limit)

        session = self.session_factory()
        try:
            result = await session.execute(stmt)
            return list(result.scalars().all())
        finally:
            await session.close()

    async def first(self) -> Any | None:
        rows = await self.limit(1).all()
        return rows[0] if rows else None

    def __await__(self):
        return self.all().__await__()

    def __aiter__(self):
        async def _generator():
            for row in await self.all():
                yield row

        return _generator()


class ModelAdmin:
    inlines: List[Type[InlineModelAdmin]] = []

    def __init__(
        self,
        model: type[Any],
        session_factory: Callable[[], AsyncSession] | None = None,
    ) -> None:
        if session_factory is None:
            raise ValueError(
                "session_factory is required for SQLAlchemy admin"
            )

        self.model = model
        self.session_factory = session_factory
        self.is_inline = False

        self.verbose_name = getattr(self, "verbose_name", model.__name__)
        self.enable_edit = getattr(self, "enable_edit", True)
        self.allow_add = getattr(self, "allow_add", True)
        self.allow_delete = getattr(self, "allow_delete", True)
        self.allow_export = getattr(self, "allow_export", True)
        self.per_page = getattr(self, "per_page", 10)
        self.default_ordering = getattr(self, "default_ordering", [])
        self.add_form_title = getattr(
            self, "add_form_title", f"Add {self.verbose_name}"
        )
        self.edit_form_title = getattr(
            self, "edit_form_title", f"Edit {self.verbose_name}"
        )
        self.allow_import = getattr(self, "allow_import", False)
        self.import_fields = getattr(self, "import_fields", [])

        if not hasattr(self, "table_fields"):
            self.table_fields = []
        if not hasattr(self, "form_fields"):
            self.form_fields = []
        if not hasattr(self, "add_form_fields"):
            self.add_form_fields = []
        if not hasattr(self, "search_fields"):
            self.search_fields = []
        if not hasattr(self, "filter_fields"):
            self.filter_fields = []
        if not hasattr(self, "menu_group") or not self.menu_group:
            self.menu_group = "System Management"

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

        self.table_field_map = {
            field.name: field for field in self.table_fields
        }

        if not self.form_fields:
            self.form_fields = [
                FormField(
                    name=field.name,
                    label=field.label,
                    field_type=field.display_type,
                    readonly=field.readonly,
                )
                for field in self.table_fields
                if not field.readonly
            ]

        self.list_display = [
            field.name for field in self.table_fields if field.visible
        ]
        self.list_display_links = [
            field.name
            for field in self.table_fields
            if field.visible and field.is_link
        ]
        self.list_filter = [
            field.name for field in self.table_fields if field.filterable
        ]
        self.list_editable = [
            field.name
            for field in self.table_fields
            if field.editable and not field.readonly
        ]
        self.readonly_fields = [
            field.name for field in self.table_fields if field.readonly
        ]

        if not self.add_form_fields:
            self.add_form_fields = self.form_fields

    def get_field(self, field_name: str) -> Optional[TableField]:
        return self.table_field_map.get(field_name)

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

    def get_field_label(self, field_name: str) -> str:
        for field in self.table_fields:
            if field.name == field_name and field.label:
                return field.label
        return field_name.replace("_", " ").title()

    def get_list_display_links(self) -> List[str]:
        if self.list_display_links:
            return self.list_display_links
        if self.list_display:
            return [self.list_display[0]]
        return [self.pk_name]

    def is_field_editable(self, field_name: str) -> bool:
        for field in self.table_fields:
            if field.name == field_name:
                return field.editable and not field.readonly
        return False

    def get_filter_choices(self, field_name: str) -> List[tuple]:
        for field in self.filter_fields:
            if field.name == field_name and field.choices:
                return [(str(k), v) for k, v in field.choices.items()]

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
                                model_name = field.related_model.__name__
                                if field.name.startswith(model_name + "_"):
                                    related_field = field.name[
                                        len(model_name + "_") :
                                    ]
                                else:
                                    related_field = "id"
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

                if for_display and field.formatter and value is not None:
                    if asyncio.iscoroutinefunction(field.formatter):
                        result[field.name] = await field.formatter(value)
                    else:
                        result[field.name] = field.formatter(value)
                else:
                    result[field.name] = (
                        str(value) if value is not None else ""
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
            if field.name in data:
                field_value = data[field.name]
                is_password_field = (
                    field.field_type == DisplayType.PASSWORD
                    or "password" in str(field.name).lower()
                )
                if (
                    skip_empty_password
                    and is_password_field
                    and isinstance(field_value, str)
                    and field_value.strip() == ""
                ):
                    continue
                if (
                    skip_empty_password
                    and is_password_field
                    and current_object is not None
                    and isinstance(field_value, str)
                ):
                    current_password = getattr(
                        current_object, field.name, None
                    )
                    if (
                        isinstance(current_password, str)
                        and field_value == current_password
                    ):
                        continue
                processed_value = field.process_value(field_value)
                if (
                    is_password_field
                    and isinstance(processed_value, str)
                    and processed_value.strip()
                    and field.processor is None
                ):
                    hash_password = getattr(self.model, "hash_password", None)
                    if callable(hash_password):
                        processed_value = hash_password(processed_value)
                processed_data[field.name] = processed_value
        return processed_data

    async def get_filter_fields(self) -> List[FilterField]:
        return self.filter_fields

    async def get_search_fields(self) -> list[SearchField]:
        return self.search_fields

    async def get_frontend_config(self) -> dict:
        form_fields = await self.get_form_fields()
        add_form_fields = await self.get_add_form_fields()
        filter_fields = await self.get_filter_fields()
        search_fields = await self.get_search_fields()

        return {
            "tableFields": [field.to_dict() for field in self.table_fields],
            "modelName": self.model.__name__,
            "pkName": self.pk_name,
            "route_id": self.route_id,
            "pageSize": self.per_page,
            "formFields": [field.to_dict() for field in form_fields],
            "addFormFields": [field.to_dict() for field in add_form_fields],
            "addFormTitle": self.add_form_title or f"Add {self.verbose_name}",
            "editFormTitle": self.edit_form_title
            or f"Edit {self.verbose_name}",
            "searchFields": [field.to_dict() for field in search_fields],
            "filterFields": [field.to_dict() for field in filter_fields],
            "enableEdit": self.enable_edit,
            "allowAdd": self.allow_add,
            "allowDelete": self.allow_delete,
            "allowExport": self.allow_export,
            "allowImport": self.allow_import,
            "import_fields": self.import_fields,
            "verbose_name": self.verbose_name,
            "is_inline": self.is_inline,
            "inlines": [],
        }

    async def get_list_config(self) -> dict:
        return await self.get_frontend_config()

    async def get_inline_formsets(self, instance=None):
        return []

    async def get_inline_data(self, parent_id: str, inline_model: str):
        return []

    async def get_form_fields(self):
        return getattr(self, "form_fields", [])

    async def get_add_form_fields(self):
        if hasattr(self, "add_form_fields") and self.add_form_fields:
            return self.add_form_fields
        return await self.get_form_fields()

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


def _get_model_column(model: type[Any], name: str):
    mapper = sa_inspect(model)
    for column in mapper.columns:
        if column.name == name:
            return getattr(model, column.name)
    return None


def _coerce_pk(value: Any, column: Any | None) -> Any:
    if column is None:
        return value
    try:
        if isinstance(column.type, Integer):
            return int(value)
    except Exception:
        return value
    return value


def _build_filter_expression(model: type[Any], key: str, value: Any):
    if "__" in key:
        name, operator_name = key.split("__", 1)
    else:
        name, operator_name = key, "exact"

    column = _get_model_column(model, name)
    if column is None:
        return None

    if isinstance(value, str) and value.lower() in {"true", "false"}:
        value = value.lower() == "true"

    if operator_name == "exact":
        return column == value
    if operator_name == "icontains":
        return column.ilike(f"%{value}%")
    if operator_name == "contains":
        return column.contains(value)
    if operator_name == "in":
        if isinstance(value, str):
            value = [item for item in value.split(",") if item]
        return column.in_(value)
    if operator_name == "gte":
        return column >= value
    if operator_name == "lte":
        return column <= value
    if operator_name == "gt":
        return column > value
    if operator_name == "lt":
        return column < value
    return None


def _is_boolean_column(column: Any) -> bool:
    try:
        return column.type.python_type is bool
    except Exception:
        return False
