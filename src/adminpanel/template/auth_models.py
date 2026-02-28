from __future__ import annotations

import importlib
from types import ModuleType

from .models import AdminUser


def _load_project_tables_module() -> ModuleType:
    for module_name in (
        "app.infrastructure.database.table",
        "app.models.table",
        "app.infrastructure.database.tables",
        "app.models.models",
    ):
        try:
            return importlib.import_module(module_name)
        except ModuleNotFoundError:
            continue
    raise ModuleNotFoundError(
        "Unable to import project tables module. Expected one of: "
        "app.infrastructure.database.table, app.models.table, "
        "app.infrastructure.database.tables, app.models.models"
    )


_tables = _load_project_tables_module()

Role = _tables.Role
UserRole = _tables.UserRole

__all__ = ["AdminUser", "Role", "UserRole"]
