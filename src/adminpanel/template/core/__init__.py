from __future__ import annotations

from typing import Any

from .admin import ModelAdmin
from .fields import DisplayType, FormField, SearchField, TableField
from .filters import (
    BooleanFilter,
    DateRangeFilter,
    FilterType,
    InputFilter,
    NumberRangeFilter,
    SelectFilter,
)
from .menu import MenuItem

__all__ = [
    "ModelAdmin",
    "AdminSite",
    "MenuItem",
    "TableField",
    "SearchField",
    "DisplayType",
    "FormField",
    "FilterType",
    "InputFilter",
    "SelectFilter",
    "DateRangeFilter",
    "BooleanFilter",
    "NumberRangeFilter",
]


def __getattr__(name: str) -> Any:
    if name == "AdminSite":
        # Lazy import prevents circular import between core.site and auth_admin.
        from .site import AdminSite

        return AdminSite
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
