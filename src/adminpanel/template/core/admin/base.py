from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..fields import DisplayType, FormField, SearchField, TableField
from ..filters import FilterField
from ..inline import InlineModelAdmin


class _AdminPanelConfig(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    verbose_name: str | None = None
    enable_edit: bool = True
    allow_add: bool = True
    allow_delete: bool = True
    allow_export: bool = True
    allow_import: bool = False
    per_page: int = 10
    default_ordering: list[str] = Field(default_factory=list)
    import_fields: list[str] = Field(default_factory=list)
    add_form_title: str | None = None
    edit_form_title: str | None = None
    table_fields: list[TableField] = Field(default_factory=list)
    form_fields: list[FormField] = Field(default_factory=list)
    add_form_fields: list[FormField] = Field(default_factory=list)
    search_fields: list[SearchField] = Field(default_factory=list)
    filter_fields: list[FilterField] = Field(default_factory=list)
    menu_group: str = "System Management"

    @classmethod
    def from_admin_class(
        cls, admin_class: type[Any], model: type[Any]
    ) -> "_AdminPanelConfig":
        class_attributes: dict[str, Any] = {}
        for base in reversed(admin_class.mro()):
            class_attributes.update(vars(base))

        payload: dict[str, Any] = {}
        for field_name in cls.model_fields:
            if field_name not in class_attributes:
                continue
            value = class_attributes[field_name]
            if isinstance(value, list):
                value = list(value)
            payload[field_name] = value

        payload.setdefault("verbose_name", model.__name__)
        payload.setdefault("add_form_title", f"Add {payload['verbose_name']}")
        payload.setdefault(
            "edit_form_title", f"Edit {payload['verbose_name']}"
        )
        if not payload.get("menu_group"):
            payload["menu_group"] = "System Management"
        return cls.model_validate(payload)


class BaseModelAdmin(ABC):
    """Shared, ORM-agnostic behaviour for admin model handlers."""

    inlines: list[type[InlineModelAdmin]] = []

    # ---- abstract hooks for ORM-specific type detection ----

    @abstractmethod
    def _get_default_table_fields(self) -> list: ...

    @abstractmethod
    def _is_pk_field(self, field_name: str) -> bool: ...

    @abstractmethod
    def _is_datetime_field(self, field_name: str) -> bool: ...

    @abstractmethod
    def _is_boolean_field(self, field_name: str) -> bool: ...

    # ---- abstract CRUD methods ----

    @abstractmethod
    async def get_queryset(self, request, params: dict): ...

    @abstractmethod
    async def serialize_object(
        self, obj, for_display: bool = True
    ) -> dict: ...

    @abstractmethod
    async def handle_add(self, request, data: dict) -> tuple[bool, str]: ...

    @abstractmethod
    async def handle_edit(
        self, request, object_id: str, data: dict
    ) -> tuple[bool, str]: ...

    @abstractmethod
    async def handle_delete(
        self, request, object_id: str
    ) -> tuple[bool, str]: ...

    @abstractmethod
    async def handle_batch_delete(
        self, request, ids: list
    ) -> tuple[bool, str, int]: ...

    @abstractmethod
    async def handle_query(self, request, params: dict) -> tuple:
        """Return (queryset, total_count).

        Implementations should catch ORM errors internally and return a safe
        fallback (e.g. an empty queryset with count 0) rather than propagating
        exceptions, so that route handlers are not crashed by query failures.
        """
        ...

    @abstractmethod
    async def get_object(self, pk) -> object: ...

    @abstractmethod
    async def bulk_import(
        self, rows: list[dict]
    ) -> tuple[int, int, list[str]]: ...

    # ---- concrete methods ----

    def _initialize_common_attributes(self, model: type[Any]) -> None:
        config = _AdminPanelConfig.from_admin_class(self.__class__, model)

        self.model = model
        self.is_inline = False
        for field_name, value in config.model_dump(mode="python").items():
            setattr(self, field_name, value)

    def _finalize_field_configuration(self) -> None:
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

    def _process_fields(self) -> None:
        """Process model fields using ORM-specific type detection hooks."""
        if not self.table_fields:
            self.table_fields = self._get_default_table_fields()

        for field in self.table_fields:
            if self._is_pk_field(field.name):
                field.readonly = True
                field.editable = False
            elif self._is_datetime_field(field.name):
                field.readonly = True
                field.sortable = True
                if not field.display_type:
                    field.display_type = DisplayType.DATETIME
            elif self._is_boolean_field(field.name):
                if not field.display_type:
                    field.display_type = DisplayType.BOOLEAN

            if not hasattr(field, "editable") or field.editable is None:
                field.editable = False

        self._finalize_field_configuration()

    def get_field(self, field_name: str) -> TableField | None:
        return self.table_field_map.get(field_name)

    def get_field_label(self, field_name: str) -> str:
        for field in self.table_fields:
            if field.name == field_name and field.label:
                return field.label
        return field_name.replace("_", " ").title()

    def get_list_display_links(self) -> list[str]:
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

    def _get_declared_filter_choices(
        self, field_name: str
    ) -> list[tuple[str, str]]:
        for field in self.filter_fields:
            if field.name == field_name and field.choices:
                return [(str(k), v) for k, v in field.choices.items()]
        return []

    @staticmethod
    def _resolve_related_field_name(field: TableField) -> str:
        if not field.related_model:
            return "id"
        model_prefix = f"{field.related_model.__name__}_"
        if field.name.startswith(model_prefix):
            return field.name[len(model_prefix) :]
        return "id"

    async def _format_serialized_value(
        self, field: TableField, value: Any, *, for_display: bool
    ) -> str | Any:
        if for_display and field.formatter and value is not None:
            if asyncio.iscoroutinefunction(field.formatter):
                return await field.formatter(value)
            return field.formatter(value)
        return str(value) if value is not None else ""

    @staticmethod
    def _is_password_form_field(field: FormField) -> bool:
        return (
            field.field_type == DisplayType.PASSWORD
            or "password" in str(field.name).lower()
        )

    def _should_skip_password_value(
        self,
        *,
        field: FormField,
        field_value: Any,
        skip_empty_password: bool,
        current_object: Any | None,
    ) -> bool:
        if not skip_empty_password or not self._is_password_form_field(field):
            return False

        if isinstance(field_value, str) and field_value.strip() == "":
            return True

        if current_object is None or not isinstance(field_value, str):
            return False

        current_password = getattr(current_object, field.name, None)
        return (
            isinstance(current_password, str)
            and field_value == current_password
        )

    def _hash_password_if_needed(
        self, field: FormField, processed_value: Any
    ) -> Any:
        if (
            not self._is_password_form_field(field)
            or not isinstance(processed_value, str)
            or not processed_value.strip()
            or field.processor is not None
        ):
            return processed_value

        hash_password = getattr(self.model, "hash_password", None)
        if callable(hash_password):
            return hash_password(processed_value)
        return processed_value

    async def get_filter_fields(self) -> list[FilterField]:
        return self.filter_fields

    async def get_search_fields(self) -> list[SearchField]:
        return self.search_fields

    def _build_frontend_inlines(self) -> list[dict[str, Any]]:
        return []

    async def get_frontend_config(self) -> dict[str, Any]:
        form_fields = await self.get_form_fields()
        add_form_fields = await self.get_add_form_fields()
        filter_fields = await self.get_filter_fields()
        search_fields = await self.get_search_fields()

        return {
            "tableFields": [field.to_dict() for field in self.table_fields],
            "modelName": self.model.__name__,
            "pkName": self.pk_name,
            "route_id": getattr(self, "route_id", ""),
            "pageSize": self.per_page,
            "formFields": [field.to_dict() for field in form_fields],
            "addFormFields": [field.to_dict() for field in add_form_fields],
            "addFormTitle": self.add_form_title,
            "editFormTitle": self.edit_form_title,
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
            "inlines": self._build_frontend_inlines(),
        }

    async def get_list_config(self) -> dict[str, Any]:
        return await self.get_frontend_config()

    async def get_inline_formsets(self, instance=None) -> list[dict[str, Any]]:
        return []

    async def get_inline_data(
        self, parent_id: str, inline_model: str
    ) -> list[dict[str, Any]]:
        return []

    async def get_form_fields(self) -> list[FormField]:
        return self.form_fields

    async def get_add_form_fields(self) -> list[FormField]:
        if self.add_form_fields:
            return self.add_form_fields
        return await self.get_form_fields()
