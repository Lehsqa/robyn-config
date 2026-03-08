from __future__ import annotations

from .project_tables import load_project_tables_module


_tables = load_project_tables_module()

AdminUser = _tables.UsersTable

__all__ = ["AdminUser"]
