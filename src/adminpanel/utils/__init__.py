"""Utility functions for the 'adminpanel' command."""

from __future__ import annotations

from pathlib import Path

from add import read_project_config, validate_project
from add.utils import _ensure_import_from

from ._constants import (
    ADMIN_DEPENDENCIES,
    ADMINPANEL_ROOT,
    DDD_APP_PANEL_TEMPLATE,
    DEFAULT_DDD_DB_TABLE_PATH,
    DEFAULT_MVC_DB_TABLE_PATH,
    LEGACY_DDD_DB_TABLE_PATHS,
    LEGACY_MVC_DB_TABLE_PATHS,
    SQLALCHEMY_ADMIN_TABLES_LEGACY_SNIPPET,
    SQLALCHEMY_ADMIN_TABLES_SNIPPET,
    SUPPORTED_DESIGNS,
    SUPPORTED_ORMS,
    SUPPORTED_PACKAGE_MANAGERS,
    TEMPLATE_ROOT,
    TORTOISE_ADMIN_TABLES_LEGACY_SNIPPET,
    TORTOISE_ADMIN_TABLES_SNIPPET,
)
from ._dependencies import (
    _detect_package_manager,
    _ensure_dependency,
    _ensure_poetry_dependency,
    _ensure_project_dependency,
    _extract_dependency_name_from_project_entry,
    _normalize_dependency_name,
    _set_adminpanel_created,
)
from ._routing import _ensure_call_before_main_guard, _ensure_route_registrar
from ._tables import (
    _append_admin_models_to_shared_tables,
    _ensure_application_adminpanel,
    _ensure_symbols_in_all,
    _repair_sqlalchemy_adminpanel_imports,
    _resolve_db_tables_path,
    _select_admin_table_snippets,
)
from ._template_io import (
    _copy_template_tree,
    _render_template_file,
    _render_template_tree,
)

__all__ = [
    "add_adminpanel",
    "ADMIN_DEPENDENCIES",
    "ADMINPANEL_ROOT",
    "DDD_APP_PANEL_TEMPLATE",
    "DEFAULT_DDD_DB_TABLE_PATH",
    "DEFAULT_MVC_DB_TABLE_PATH",
    "LEGACY_DDD_DB_TABLE_PATHS",
    "LEGACY_MVC_DB_TABLE_PATHS",
    "SQLALCHEMY_ADMIN_TABLES_LEGACY_SNIPPET",
    "SQLALCHEMY_ADMIN_TABLES_SNIPPET",
    "SUPPORTED_DESIGNS",
    "SUPPORTED_ORMS",
    "SUPPORTED_PACKAGE_MANAGERS",
    "TEMPLATE_ROOT",
    "TORTOISE_ADMIN_TABLES_LEGACY_SNIPPET",
    "TORTOISE_ADMIN_TABLES_SNIPPET",
    "_append_admin_models_to_shared_tables",
    "_copy_template_tree",
    "_detect_package_manager",
    "_ensure_application_adminpanel",
    "_ensure_call_before_main_guard",
    "_ensure_dependency",
    "_ensure_poetry_dependency",
    "_ensure_project_dependency",
    "_ensure_route_registrar",
    "_ensure_symbols_in_all",
    "_extract_dependency_name_from_project_entry",
    "_normalize_dependency_name",
    "_render_template_file",
    "_render_template_tree",
    "_repair_sqlalchemy_adminpanel_imports",
    "_resolve_db_tables_path",
    "_select_admin_table_snippets",
    "_set_adminpanel_created",
]


def add_adminpanel(
    project_path: Path,
    *,
    admin_username: str = "admin",
    admin_password: str = "admin",
) -> list[str]:
    """Add admin panel scaffolding to an existing robyn-config project."""
    config = read_project_config(project_path)
    design, orm = validate_project(project_path)
    if design not in SUPPORTED_DESIGNS:
        raise ValueError(f"Unsupported design pattern: {design}")
    if orm not in SUPPORTED_ORMS:
        raise ValueError(
            "Admin panel scaffolding requires a supported ORM project."
        )

    if not TEMPLATE_ROOT.exists():
        raise FileNotFoundError("Admin panel template package not found.")

    if design == "ddd":
        target_root = (
            project_path / "src" / "app" / "infrastructure" / "adminpanel"
        )
    else:
        target_root = project_path / "src" / "app" / "adminpanel"
    created_files = _copy_template_tree(
        TEMPLATE_ROOT, target_root, project_path, orm
    )
    created_files += _render_template_tree(
        TEMPLATE_ROOT,
        target_root,
        {
            "design": design,
            "orm": orm,
            "admin_username": admin_username,
            "admin_password": admin_password,
        },
        project_path,
    )

    _append_admin_models_to_shared_tables(
        project_path=project_path,
        config=config,
        design=design,
        orm=orm,
    )

    if orm == "sqlalchemy":
        _repair_sqlalchemy_adminpanel_imports(target_root)

    if design == "ddd":
        infra_dir = project_path / "src" / "app" / "infrastructure"
        init_file = infra_dir / "__init__.py"
        if not init_file.exists():
            init_file.parent.mkdir(parents=True, exist_ok=True)
            init_file.write_text("")
        _ensure_application_adminpanel(project_path)

    server_path = project_path / "src" / "app" / "server.py"
    if not server_path.exists():
        raise FileNotFoundError(
            f"server.py not found at {server_path.as_posix()}"
        )
    if design == "ddd":
        _ensure_import_from(
            server_path,
            "app.infrastructure.application",
            "adminpanel",
        )
        inserted = _ensure_route_registrar(server_path, "adminpanel.register")
        if not inserted:
            _ensure_call_before_main_guard(
                server_path, "adminpanel.register(app)"
            )
    else:
        _ensure_import_from(server_path, "app", "adminpanel")
        _ensure_call_before_main_guard(server_path, "adminpanel.register(app)")

    pyproject_path = project_path / "pyproject.toml"
    package_manager = _detect_package_manager(
        config, pyproject_path.read_text() if pyproject_path.exists() else ""
    )
    for dependency, version in ADMIN_DEPENDENCIES:
        _ensure_dependency(
            pyproject_path, package_manager, dependency, version
        )
    _set_adminpanel_created(pyproject_path)

    return created_files
