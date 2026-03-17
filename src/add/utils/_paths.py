"""Path resolution and project configuration for the 'add' command."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:
    import tomli as tomllib

# Default routes for code injection (overridable via [tool.robyn-config.add])
DEFAULT_DDD_DOMAIN_PATH = Path("src/app/domain")
DEFAULT_DDD_OPERATIONAL_PATH = Path("src/app/operational")
DEFAULT_DDD_PRESENTATION_PATH = Path("src/app/presentation")
DEFAULT_DDD_DB_REPOSITORY_PATH = Path(
    "src/app/infrastructure/database/repository"
)
DEFAULT_DDD_DB_TABLE_PATH = Path(
    "src/app/infrastructure/database/tables/__init__.py"
)
LEGACY_DDD_DB_TABLE_PATHS: tuple[Path, ...] = (
    Path("src/app/infrastructure/database/table/__init__.py"),
    Path("src/app/infrastructure/database/tables.py"),
)

DEFAULT_MVC_VIEWS_PATH = Path("src/app/views")
DEFAULT_MVC_DB_REPOSITORY_PATH = Path("src/app/models/repository.py")
DEFAULT_MVC_DB_TABLE_PATH = Path("src/app/models/tables/__init__.py")
LEGACY_MVC_DB_TABLE_PATHS: tuple[Path, ...] = (
    Path("src/app/models/table/__init__.py"),
    Path("src/app/models/models.py"),
)
DEFAULT_MVC_URLS_PATH = Path("src/app/urls.py")


@dataclass
class DDDAddPaths:
    domain: Path
    operational: Path
    presentation: Path
    db_repository: Path
    db_tables: Path


@dataclass
class MVCAddPaths:
    views: Path
    db_repository: Path
    db_tables: Path
    urls: Path


def read_project_config(project_path: Path) -> dict[str, Any]:
    """Read pyproject.toml and extract [tool.robyn-config] section."""
    pyproject_path = project_path / "pyproject.toml"

    if not pyproject_path.exists():
        raise FileNotFoundError(
            f"pyproject.toml not found in {project_path}. "
            "Make sure you're in a robyn-config project directory."
        )

    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)

    robyn_config = data.get("tool", {}).get("robyn-config", {})
    if not robyn_config:
        raise ValueError(
            "No [tool.robyn-config] section found in pyproject.toml. "
            "This project was not created with robyn-config."
        )

    return robyn_config


def _extract_design_orm(config: dict[str, Any]) -> tuple[str, str]:
    """Validate project has robyn-config metadata and return (design, orm)."""
    design = config.get("design")
    orm = config.get("orm")

    if not design or not orm:
        raise ValueError(
            "Invalid [tool.robyn-config] section. "
            "Missing 'design' or 'orm' fields."
        )
    return design, orm


def validate_project(project_path: Path) -> tuple[str, str]:
    """Validate project has robyn-config metadata and return (design, orm)."""
    config = read_project_config(project_path)
    return _extract_design_orm(config)


def _resolve_path(
    project_root: Path, raw_value: str | None, default: Path
) -> Path:
    """Resolve a configured path (relative to project root) or fall back to default."""
    return (
        (project_root / raw_value) if raw_value else (project_root / default)
    )


def _resolve_db_table_path(
    project_root: Path,
    raw_value: str | None,
    default: Path,
    legacy: tuple[Path, ...],
) -> Path:
    """Resolve table path and transparently support legacy single-file projects."""
    if raw_value:
        return project_root / raw_value

    preferred = project_root / default
    if preferred.exists():
        return preferred

    for fallback in legacy:
        fallback_path = project_root / fallback
        if fallback_path.exists():
            return fallback_path
    return preferred


def _load_add_paths(
    project_path: Path, design: str, config: dict[str, Any]
) -> DDDAddPaths | MVCAddPaths:
    """Resolve add-paths from pyproject config (with defaults)."""
    add_config = config.get("add") or {}
    if design == "ddd":
        return DDDAddPaths(
            domain=_resolve_path(
                project_path,
                add_config.get("domain_path"),
                DEFAULT_DDD_DOMAIN_PATH,
            ),
            operational=_resolve_path(
                project_path,
                add_config.get("operational_path"),
                DEFAULT_DDD_OPERATIONAL_PATH,
            ),
            presentation=_resolve_path(
                project_path,
                add_config.get("presentation_path"),
                DEFAULT_DDD_PRESENTATION_PATH,
            ),
            db_repository=_resolve_path(
                project_path,
                add_config.get("database_repository_path"),
                DEFAULT_DDD_DB_REPOSITORY_PATH,
            ),
            db_tables=_resolve_db_table_path(
                project_root=project_path,
                raw_value=add_config.get("database_table_path"),
                default=DEFAULT_DDD_DB_TABLE_PATH,
                legacy=LEGACY_DDD_DB_TABLE_PATHS,
            ),
        )

    if design == "mvc":
        return MVCAddPaths(
            views=_resolve_path(
                project_path,
                add_config.get("views_path"),
                DEFAULT_MVC_VIEWS_PATH,
            ),
            db_repository=_resolve_path(
                project_path,
                add_config.get("database_repository_path"),
                DEFAULT_MVC_DB_REPOSITORY_PATH,
            ),
            db_tables=_resolve_db_table_path(
                project_root=project_path,
                raw_value=add_config.get("database_table_path"),
                default=DEFAULT_MVC_DB_TABLE_PATH,
                legacy=LEGACY_MVC_DB_TABLE_PATHS,
            ),
            urls=_resolve_path(
                project_path,
                add_config.get("urls_path"),
                DEFAULT_MVC_URLS_PATH,
            ),
        )

    raise ValueError(f"Unsupported design pattern: {design}")
