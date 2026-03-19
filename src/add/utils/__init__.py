"""Utility functions for the 'add' command."""

from __future__ import annotations

from pathlib import Path

from ._entity import _format_comment, _normalize_entity_name
from ._injection import (
    _add_table_to_module_package,
    _add_table_to_tables_py,
    _add_to_all_list,
    _append_class_to_file,
    _ensure_import_from,
    _ensure_register_call,
    _register_routes_ddd,
    _register_routes_mvc,
    _update_init_file,
)
from ._paths import (
    DDDAddPaths,
    DEFAULT_DDD_DB_TABLE_PATH,
    DEFAULT_MVC_DB_TABLE_PATH,
    LEGACY_DDD_DB_TABLE_PATHS,
    LEGACY_MVC_DB_TABLE_PATHS,
    MVCAddPaths,
    _extract_design_orm,
    _load_add_paths,
    _resolve_db_table_path,
    _resolve_path,
    read_project_config,
    validate_project,
)
from ._templates import (
    _add_ddd_templates,
    _add_mvc_templates,
    _render_template_file,
    _render_template_string,
    _render_templates_from_directory,
)

__all__ = [
    "add_business_logic",
    "read_project_config",
    "validate_project",
    "_normalize_entity_name",
    "_format_comment",
    "_ensure_import_from",
    "_ensure_register_call",
    "_update_init_file",
    "_add_table_to_module_package",
    "_add_table_to_tables_py",
    "_add_to_all_list",
    "_append_class_to_file",
    "_register_routes_ddd",
    "_register_routes_mvc",
    "_render_template_file",
    "_render_template_string",
    "_render_templates_from_directory",
    "_add_ddd_templates",
    "_add_mvc_templates",
    "DDDAddPaths",
    "MVCAddPaths",
    "_extract_design_orm",
    "_load_add_paths",
    "_resolve_path",
    "_resolve_db_table_path",
    "DEFAULT_DDD_DB_TABLE_PATH",
    "DEFAULT_MVC_DB_TABLE_PATH",
    "LEGACY_DDD_DB_TABLE_PATHS",
    "LEGACY_MVC_DB_TABLE_PATHS",
]


def add_business_logic(project_path: Path, name: str) -> list[str]:
    """Add business logic templates to an existing project."""
    config = read_project_config(project_path)
    design, orm = _extract_design_orm(config)
    add_paths = _load_add_paths(project_path, design, config)
    name_lower, name_capitalized = _normalize_entity_name(name)

    if design == "ddd":
        return _add_ddd_templates(
            project_path, add_paths, name_lower, name_capitalized, orm
        )
    elif design == "mvc":
        return _add_mvc_templates(
            project_path, add_paths, name_lower, name_capitalized, orm
        )
    else:
        raise ValueError(f"Unsupported design pattern: {design}")
