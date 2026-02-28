from __future__ import annotations

import importlib
from types import ModuleType


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

AdminUser = _tables.UsersTable

__all__ = ["AdminUser"]
