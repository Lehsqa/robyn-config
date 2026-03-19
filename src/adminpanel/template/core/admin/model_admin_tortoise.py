from __future__ import annotations

import logging
import operator
from functools import reduce
from typing import Any, Callable, Dict, Type
from urllib.parse import unquote

from robyn import Request
from tortoise import fields
from tortoise.expressions import Q
from tortoise.models import Model
from tortoise.queryset import QuerySet

from ..fields import DisplayType, TableField
from ..inline import InlineModelAdmin
from .base import BaseModelAdmin

logger = logging.getLogger(__name__)


class ModelAdmin(BaseModelAdmin):
    inlines: list[Type[InlineModelAdmin]] = []

    def __init__(
        self, model: Type[Model], transaction: Callable | None = None
    ):
        self._initialize_common_attributes(model)
        self.transaction = transaction
        self.pk_name = getattr(self.model._meta, "pk_attr", "id")

        self._process_fields()
        self.ordering = [
            f"-{field.name}" if not field.sortable else field.name
            for field in self.table_fields
            if field.sortable
        ]
        self._inline_instances = [
            inline_class(self.model) for inline_class in self.inlines
        ]

    def _get_default_table_fields(self):
        return [
            TableField(name=field_name)
            for field_name in self.model._meta.fields_map.keys()
        ]

    def _is_pk_field(self, field_name: str) -> bool:
        model_field = self.model._meta.fields_map.get(field_name)
        return model_field is not None and model_field.pk

    def _is_datetime_field(self, field_name: str) -> bool:
        model_field = self.model._meta.fields_map.get(field_name)
        return isinstance(model_field, fields.DatetimeField)

    def _is_boolean_field(self, field_name: str) -> bool:
        model_field = self.model._meta.fields_map.get(field_name)
        return isinstance(model_field, fields.BooleanField)

    async def get_queryset(self, request: Request, params: dict) -> QuerySet:
        queryset = self.model.all()
        normalized_params: dict[str, Any] = {}
        for key, value in params.items():
            normalized_params[key] = (
                unquote(value) if isinstance(value, str) else value
            )

        for inline in self._inline_instances:
            if inline.model != self.model:
                continue
            parent_id = normalized_params.get(inline.fk_field)
            if parent_id:
                queryset = queryset.filter(
                    **{f"{inline.fk_field}_id": parent_id}
                )
                break

        search_value = normalized_params.get("search", "")
        if search_value and self.search_fields:
            search_conditions: list[Any] = []
            for field in self.search_fields:
                try:
                    query_dict = await field.build_search_query(search_value)
                except Exception:
                    logger.exception(
                        "Error building search query for %s", field.name
                    )
                    continue

                if not query_dict:
                    continue
                if (
                    len(query_dict) == 1
                    and "id" in query_dict
                    and query_dict["id"] is None
                ):
                    continue
                if "_q_object" in query_dict:
                    search_conditions.append(query_dict["_q_object"])
                else:
                    search_conditions.append(Q(**query_dict))

            if search_conditions:
                queryset = queryset.filter(
                    reduce(operator.or_, search_conditions)
                )

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
                logger.exception(
                    "Error building filter query for %s", filter_field.name
                )
                continue

            if not query_dict:
                continue
            if (
                len(query_dict) == 1
                and "id" in query_dict
                and query_dict["id"] is None
            ):
                continue
            if "_q_object" in query_dict:
                queryset = queryset.filter(query_dict["_q_object"])
            else:
                queryset = queryset.filter(**query_dict)

        return queryset

    def get_filter_choices(self, field_name: str) -> list[tuple]:
        choices = self._get_declared_filter_choices(field_name)
        if choices:
            return choices

        model_field = self.model._meta.fields_map.get(field_name)
        if isinstance(model_field, fields.BooleanField):
            return [("True", "Yes"), ("False", "No")]

        if field_name.endswith("_id") and isinstance(
            model_field, fields.IntField
        ):
            return []

        return []

    async def get_object(self, pk: Any):
        return await self.model.get(**{self.pk_name: pk})

    def get_list_fields(self) -> list[str]:
        return self.list_display or [field.name for field in self.table_fields]

    def format_field_value(self, obj: Model, field_name: str) -> str:
        field = self.get_field(field_name)
        if not field:
            return str(getattr(obj, field_name, ""))
        return field.format_value(getattr(obj, field_name, ""))

    async def serialize_object(
        self, obj: Model, for_display: bool = True
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for field in self.table_fields:
            try:
                value = getattr(obj, field.name, None)

                if field.display_type == DisplayType.SWITCH:
                    result[field.name] = value
                    continue

                if field.related_model and field.related_key:
                    try:
                        fk_value = getattr(obj, field.related_key, None)
                        if fk_value:
                            related_obj = await field.related_model.get(
                                id=fk_value
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
                    except Exception:
                        logger.exception(
                            "Error resolving related field '%s' for '%s'",
                            field.related_key,
                            field.name,
                        )
                    result[field.name] = ""
                    continue

                result[field.name] = await self._format_serialized_value(
                    field, value, for_display=for_display
                )
            except Exception:
                logger.exception("Error serializing field '%s'", field.name)
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
            model_field = self.model._meta.fields_map.get(field.name)
            is_fk = isinstance(
                model_field, fields.relational.ForeignKeyFieldInstance
            )
            fk_key = f"{field.name}_id"

            if is_fk:
                source_key = None
                if fk_key in data:
                    source_key = fk_key
                elif field.name in data:
                    source_key = field.name

                if source_key is not None:
                    processed_data[fk_key] = field.process_value(
                        data[source_key]
                    )
                continue

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

    def serialize_field(self, field: TableField) -> Dict[str, Any]:
        return {
            "name": field.name,
            "label": field.label,
            "display_type": (
                field.display_type.value if field.display_type else "text"
            ),
            "sortable": field.sortable,
            "readonly": field.readonly,
            "editable": field.editable,
            "filterable": field.filterable,
            "width": field.width,
            "is_link": field.is_link,
            "hidden": field.hidden,
            "formatter": bool(field.formatter),
        }

    def _build_frontend_inlines(self) -> list[dict[str, Any]]:
        def _inline_title(inline: Type[InlineModelAdmin]) -> str:
            meta = getattr(inline.model, "Meta", None)
            return getattr(meta, "description", inline.verbose_name)

        return [
            {
                "model": inline.model.__name__,
                "fields": [field.to_dict() for field in inline.table_fields],
                "title": _inline_title(inline),
            }
            for inline in getattr(self, "inlines", [])
        ]

    async def get_inline_formsets(self, instance=None):
        formsets = []
        for inline in self._inline_instances:
            formset = inline.get_formset()
            if instance:
                queryset = await inline.get_queryset(instance)
                formset["initial_data"] = [
                    await inline.serialize_object(obj, for_display=False)
                    for obj in await queryset
                ]
            formsets.append(formset)
        return formsets

    async def get_inline_data(self, parent_id: str, inline_model: str):
        try:
            inline = next(
                (
                    instance
                    for instance in self._inline_instances
                    if instance.model.__name__ == inline_model
                ),
                None,
            )
            if not inline:
                return []

            parent_instance = await self.model.get(**{self.pk_name: parent_id})
            if not parent_instance:
                return []

            queryset = await inline.get_queryset(parent_instance)
            data = []
            async for obj in queryset:
                try:
                    serialized = await inline.serialize_object(obj)
                    data.append({"data": serialized, "display": serialized})
                except Exception:
                    logger.exception(
                        "Error serializing inline object for '%s'",
                        inline_model,
                    )
            return data
        except Exception:
            logger.exception(
                "Error fetching inline data for model '%s'", inline_model
            )
            return []

    async def get_list_config(self) -> dict:
        config = await self.get_frontend_config()

        inlines = []
        for inline in self._inline_instances:
            inline_config = inline.get_formset()
            if hasattr(inline.model, "Meta") and hasattr(
                inline.model.Meta, "description"
            ):
                inline_config["title"] = inline.model.Meta.description
            else:
                inline_config["title"] = getattr(
                    inline, "verbose_name", inline.model.__name__
                )
            inlines.append(inline_config)

        config["inlines"] = inlines
        return config

    async def handle_edit(
        self, request: Request, object_id: str, data: dict
    ) -> tuple[bool, str]:
        try:
            async with self.transaction() as connection:
                obj = await self.model.get_or_none(
                    **{self.pk_name: object_id}, using_db=connection
                )
                if not obj:
                    return False, "Record not found"
                processed_data = await self.process_form_data(
                    data,
                    skip_empty_password=True,
                    current_object=obj,
                )
                for field, value in processed_data.items():
                    setattr(obj, field, value)
                await obj.save(using_db=connection)
            return True, "Updated successfully"
        except Exception as exc:
            logger.exception("Edit failed for object '%s'", object_id)
            return False, f"Update failed: {exc}"

    async def handle_add(
        self, request: Request, data: dict
    ) -> tuple[bool, str]:
        try:
            async with self.transaction() as connection:
                processed_data = await self.process_form_data(data)
                await self.model.create(**processed_data, using_db=connection)
            return True, "Created successfully"
        except Exception as exc:
            logger.exception("Create failed for model '%s'", self.model)
            return False, f"Create failed: {exc}"

    async def handle_delete(
        self, request: Request, object_id: str
    ) -> tuple[bool, str]:
        try:
            async with self.transaction() as connection:
                obj = await self.model.get_or_none(
                    **{self.pk_name: object_id}, using_db=connection
                )
                if not obj:
                    return False, "Record not found"
                await obj.delete(using_db=connection)
            return True, "Deleted successfully"
        except Exception as exc:
            logger.exception("Delete failed for object '%s'", object_id)
            return False, f"Delete failed: {exc}"

    async def handle_batch_delete(
        self, request: Request, ids: list
    ) -> tuple[bool, str, int]:
        try:
            deleted_count = 0
            for object_id in ids:
                success, _ = await self.handle_delete(request, object_id)
                if success:
                    deleted_count += 1

            if deleted_count > 0:
                return True, f"Deleted {deleted_count} records", deleted_count
            return False, "No records were deleted", 0
        except Exception as exc:
            logger.exception("Batch delete failed")
            return False, f"Batch delete failed: {exc}", 0

    async def handle_query(
        self, request: Request, params: dict
    ) -> tuple[QuerySet, int]:
        try:
            queryset = await self.get_queryset(request, params)

            if params.get("sort"):
                order = "-" if params.get("order") == "desc" else ""
                queryset = queryset.order_by(f"{order}{params['sort']}")
            elif self.default_ordering:
                queryset = queryset.order_by(*self.default_ordering)

            total = await queryset.count()
            limit = max(1, int(params.get("limit", self.per_page)))
            offset = max(0, int(params.get("offset", 0)))
            queryset = queryset.offset(offset).limit(limit)
            return queryset, total
        except Exception:
            logger.exception("Query failed for model '%s'", self.model)
            return self.model.all(), 0

    async def bulk_import(
        self, rows: list[dict]
    ) -> tuple[int, int, list[str]]:
        success_count = 0
        error_count = 0
        errors: list[str] = []
        async with self.transaction() as connection:
            for payload in rows:
                try:
                    await self.model.create(**payload, using_db=connection)
                    success_count += 1
                except Exception as exc:
                    error_count += 1
                    errors.append(str(exc))
        return success_count, error_count, errors
