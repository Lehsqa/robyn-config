from __future__ import annotations

from .models_sqlalchemy import AdminUser
from .project_tables import load_project_tables_module


_tables = load_project_tables_module()

Role = _tables.Role
UserRole = _tables.UserRole

__all__ = ["AdminUser", "Role", "UserRole"]
