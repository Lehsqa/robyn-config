"""Database table and model wiring helpers for adminpanel scaffolding."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Mapping

from add.utils import _ensure_import_from

from ._constants import (
    DDD_APP_PANEL_TEMPLATE,
    DEFAULT_DDD_DB_TABLE_PATH,
    DEFAULT_MVC_DB_TABLE_PATH,
    LEGACY_DDD_DB_TABLE_PATHS,
    LEGACY_MVC_DB_TABLE_PATHS,
    SQLALCHEMY_ADMIN_TABLES_LEGACY_SNIPPET,
    SQLALCHEMY_ADMIN_TABLES_SNIPPET,
    TORTOISE_ADMIN_TABLES_LEGACY_SNIPPET,
    TORTOISE_ADMIN_TABLES_SNIPPET,
)


def _repair_sqlalchemy_adminpanel_imports(target_root: Path) -> bool:
    init_file = target_root / "__init__.py"
    if not init_file.exists():
        return False

    content = init_file.read_text()
    broken_import = (
        "from .auth_models_sqlalchemy import AdminUser, Role, UserRole"
    )
    fixed_import = "from .auth_models import AdminUser, Role, UserRole"

    if broken_import not in content:
        return False

    updated = content.replace(broken_import, fixed_import)
    init_file.write_text(updated)
    return True


def _resolve_db_tables_path(
    project_path: Path, config: Mapping[str, object], design: str
) -> Path:
    add_config = config.get("add")
    configured_path: str | None = None
    if isinstance(add_config, Mapping):
        raw = add_config.get("database_table_path")
        if isinstance(raw, str) and raw.strip():
            configured_path = raw

    if configured_path:
        return project_path / configured_path

    if design == "ddd":
        preferred = project_path / DEFAULT_DDD_DB_TABLE_PATH
        legacy_paths = LEGACY_DDD_DB_TABLE_PATHS
    elif design == "mvc":
        preferred = project_path / DEFAULT_MVC_DB_TABLE_PATH
        legacy_paths = LEGACY_MVC_DB_TABLE_PATHS
    else:
        raise ValueError(f"Unsupported design pattern: {design}")

    if preferred.exists():
        return preferred
    for legacy in legacy_paths:
        legacy_path = project_path / legacy
        if legacy_path.exists():
            return legacy_path
    return preferred


def _select_admin_table_snippets(orm: str) -> tuple[str, str]:
    if orm == "sqlalchemy":
        return (
            SQLALCHEMY_ADMIN_TABLES_SNIPPET,
            SQLALCHEMY_ADMIN_TABLES_LEGACY_SNIPPET,
        )
    if orm == "tortoise":
        return (
            TORTOISE_ADMIN_TABLES_SNIPPET,
            TORTOISE_ADMIN_TABLES_LEGACY_SNIPPET,
        )
    raise ValueError(f"Unsupported ORM: {orm}")


def _ensure_symbols_in_all(content: str, symbols: tuple[str, ...]) -> str:
    all_pattern = r"(__all__\s*=\s*\(\s*)(.*?)(\s*\))"
    match = re.search(all_pattern, content, re.DOTALL)
    if not match:
        return content

    current_items = match.group(2)
    missing = [
        symbol
        for symbol in symbols
        if f'"{symbol}"' not in current_items
        and f"'{symbol}'" not in current_items
    ]
    if not missing:
        return content

    updated_items = current_items.rstrip()
    if updated_items and not updated_items.endswith(","):
        updated_items += ","
    for symbol in missing:
        updated_items += f'\n    "{symbol}",'

    updated_all = f"{match.group(1)}{updated_items}{match.group(3)}"
    return content[: match.start()] + updated_all + content[match.end() :]


def _append_admin_models_to_shared_tables(
    project_path: Path,
    config: Mapping[str, object],
    design: str,
    orm: str,
) -> None:
    tables_path = _resolve_db_tables_path(project_path, config, design)
    if not tables_path.exists():
        raise FileNotFoundError(
            f"Database table module not found at {tables_path.as_posix()}"
        )

    package_snippet, legacy_snippet = _select_admin_table_snippets(orm)
    symbols = ("Role", "UserRole")

    if tables_path.name == "__init__.py":
        module_file = tables_path.parent / "adminpanel.py"
        if module_file.exists():
            module_content = module_file.read_text()
            if all(f"class {symbol}" in module_content for symbol in symbols):
                _ensure_import_from(tables_path, ".adminpanel", "Role")
                _ensure_import_from(tables_path, ".adminpanel", "UserRole")
                init_content = tables_path.read_text()
                updated_init = _ensure_symbols_in_all(init_content, symbols)
                if updated_init != init_content:
                    tables_path.write_text(updated_init)
                return

        module_file.write_text(package_snippet.rstrip() + "\n")
        _ensure_import_from(tables_path, ".adminpanel", "Role")
        _ensure_import_from(tables_path, ".adminpanel", "UserRole")
        init_content = tables_path.read_text()
        updated_init = _ensure_symbols_in_all(init_content, symbols)
        if updated_init != init_content:
            tables_path.write_text(updated_init)
        return

    # Legacy single-file tables.py/models.py projects.
    content = tables_path.read_text()
    if all(f"class {symbol}" in content for symbol in symbols):
        updated = _ensure_symbols_in_all(content, symbols)
        if updated != content:
            tables_path.write_text(updated)
        return

    updated_content = content.rstrip() + f"\n\n\n{legacy_snippet}\n"
    updated_content = _ensure_symbols_in_all(updated_content, symbols)
    tables_path.write_text(updated_content)


def _ensure_application_adminpanel(project_path: Path) -> None:
    target_path = (
        project_path
        / "src"
        / "app"
        / "infrastructure"
        / "application"
        / "adminpanel.py"
    )
    if target_path.exists():
        return
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(DDD_APP_PANEL_TEMPLATE)
