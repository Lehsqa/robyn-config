"""Project scaffolding CLI based on the local Robyn template."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Iterable, Sequence

import click


ORM_CHOICES: Sequence[str] = ("sqlalchemy", "tortoise")
DESIGN_CHOICES: Sequence[str] = ("ddd", "mvc")
REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = (REPO_ROOT / "src").resolve()
COMPOSE_APP_DIR = (REPO_ROOT / "compose" / "app").resolve()

COMMON_FILES: Sequence[str] = (
    ".dockerignore",
    ".env.example",
    ".gitignore",
    "Makefile",
    "README.md",
    "alembic.ini",
    "docker-compose.yml",
    "pyproject.toml",
    "uv.lock",
)


def _prepare_destination(path_arg: str | None) -> Path:
    destination = Path(path_arg or ".").expanduser().resolve()
    if destination.exists():
        if not destination.is_dir():
            print(f"Target path '{destination}' is not a directory.")
            raise SystemExit(1)
        if any(destination.iterdir()):
            print(f"Target directory '{destination}' must be empty.")
            raise SystemExit(1)
    else:
        destination.mkdir(parents=True, exist_ok=True)
    return destination


def _copy_common_files(destination: Path, orm_type: str) -> None:
    for relative in COMMON_FILES:
        source = REPO_ROOT / relative
        shutil.copy2(source, destination / relative)


def _copy_src_app(destination: Path, orm_type: str, design: str) -> None:
    target_dir = destination / "src" / "app"
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    
    source_app_dir = SRC_DIR / f"app_{design}"

    if design == "ddd":
        infrastructure_dir = (source_app_dir / "infrastructure").resolve()
        
        def ignore(source: str, names: Iterable[str]) -> Iterable[str]:
            source_path = Path(source).resolve()
            if source_path == infrastructure_dir:
                database_folders = {f"database_{choice}" for choice in ORM_CHOICES}
                return [name for name in names if name in database_folders]
            return []

        shutil.copytree(source_app_dir, target_dir, dirs_exist_ok=True, ignore=ignore)

        source_database = infrastructure_dir / f"database_{orm_type}"
        target_database = target_dir / "infrastructure" / "database"
        shutil.copytree(source_database, target_database, dirs_exist_ok=True)

    elif design == "mvc":
        models_dir = (source_app_dir / "models").resolve()

        def ignore(source: str, names: Iterable[str]) -> Iterable[str]:
            source_path = Path(source).resolve()
            if source_path == source_app_dir:
                return [name for name in names if name == "models"]
            return []

        shutil.copytree(source_app_dir, target_dir, dirs_exist_ok=True, ignore=ignore)

        source_models = models_dir / orm_type
        target_models = target_dir / "models"
        shutil.copytree(source_models, target_models, dirs_exist_ok=True)


def _resolve_compose_file(base: str, extension: str, orm_type: str) -> Path:
    candidates = (
        COMPOSE_APP_DIR / f"{base}.{orm_type}.{extension}",
        COMPOSE_APP_DIR / f"{base}_{orm_type}.{extension}",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"Could not find compose script for '{base}' with ORM '{orm_type}'."
    )


def _copy_compose_app(destination: Path, orm_type: str) -> None:
    target_dir = destination / "compose" / "app"

    def ignore(source: str, names: Iterable[str]) -> Iterable[str]:
        source_path = Path(source).resolve()
        if source_path == COMPOSE_APP_DIR:
            templates = {
                "dev.sqlalchemy.sh",
                "dev.tortoise.sh",
                "prod.sqlalchemy.py",
                "prod.tortoise.py",
            }
            return [name for name in names if name in templates]
        return []

    shutil.copytree(COMPOSE_APP_DIR, target_dir, dirs_exist_ok=True, ignore=ignore)

    dev_source = _resolve_compose_file("dev", "sh", orm_type)
    prod_source = _resolve_compose_file("prod", "py", orm_type)
    shutil.copy2(dev_source, target_dir / "dev.sh")
    shutil.copy2(prod_source, target_dir / "prod.py")


def _copy_template(destination: Path, orm_type: str, design: str) -> None:
    _copy_src_app(destination, orm_type, design)
    _copy_compose_app(destination, orm_type)
    _copy_common_files(destination, orm_type)

    if design == "mvc" and orm_type == "sqlalchemy":
        alembic_ini = destination / "alembic.ini"
        content = alembic_ini.read_text()
        content = content.replace(
            "script_location = src/app/infrastructure/database/migrations",
            "script_location = src/app/models/migrations",
        )
        alembic_ini.write_text(content)


@click.group(name="robyn-config")
def cli() -> None:
    """Robyn configuration utilities."""


@cli.command("create")
@click.option(
    "-orm",
    "--orm",
    "orm_type",
    type=str,
    required=True,
    help="Select the ORM implementation to copy (sqlalchemy or tortoise).",
)
@click.option(
    "-design",
    "--design",
    "design",
    type=str,
    required=True,
    help="Select the design pattern (ddd or mvc)",
)
@click.argument("destination", required=False)
def create(destination: str | None, orm_type: str, design: str) -> None:
    """Copy the template into DESTINATION with ORM-specific adjustments."""
    normalized_orm = orm_type.lower()
    if normalized_orm not in ORM_CHOICES:
        print(f"Unsupported ORM '{orm_type}'. Valid options: {', '.join(ORM_CHOICES)}.")
        raise SystemExit(1)

    normalized_design = design.lower()
    if normalized_design not in DESIGN_CHOICES:
        print(f"Unsupported design '{design}'. Valid options: {', '.join(DESIGN_CHOICES)}.")
        raise SystemExit(1)

    target_dir = _prepare_destination(destination)
    _copy_template(target_dir, normalized_orm, normalized_design)
    print(f"Robyn template ({normalized_design}) copied to {target_dir}")


if __name__ == "__main__":
    cli()
