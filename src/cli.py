"""Project scaffolding CLI based on the local Robyn template."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import click
from jinja2 import Environment, StrictUndefined


ORM_CHOICES: Sequence[str] = ("sqlalchemy", "tortoise")
DESIGN_CHOICES: Sequence[str] = ("ddd", "mvc")
PACKAGE_ROOT = Path(__file__).resolve().parent
SRC_DIR = PACKAGE_ROOT.resolve()
COMMON_DIR = (SRC_DIR / "common").resolve()
COMPOSE_APP_DIR = (COMMON_DIR / "compose" / "app").resolve()

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
TEMPLATE_FILES = {"alembic.ini", "pyproject.toml", "README.md", "Makefile"}

TEMPLATE_CONFIGS: Mapping[str, dict[str, str]] = {
    "ddd:sqlalchemy": {
        "design": "ddd",
        "orm": "sqlalchemy",
        "alembic_script_location": "src/app/infrastructure/database/migrations",
    },
    "ddd:tortoise": {
        "design": "ddd",
        "orm": "tortoise",
        "tortoise_orm_path": "src.app.infrastructure.database.services.engine.TORTOISE_ORM",
        "tortoise_migrations_location": "./src/app/infrastructure/database/migrations",
    },
    "mvc:sqlalchemy": {
        "design": "mvc",
        "orm": "sqlalchemy",
        "alembic_script_location": "src/app/models/migrations",
    },
    "mvc:tortoise": {
        "design": "mvc",
        "orm": "tortoise",
        "tortoise_orm_path": "app.models.database.TORTOISE_ORM",
        "tortoise_migrations_location": "./src/app/models/migrations",
    },
}

JINJA_ENV = Environment(undefined=StrictUndefined)


def _collect_existing_items(destination: Path) -> set[Path]:
    items: set[Path] = set()
    for current, dirs, files in os.walk(destination):
        rel_base = Path(current).relative_to(destination)
        for name in dirs:
            items.add(rel_base / name)
        for name in files:
            items.add(rel_base / name)
    return items


def _collect_common_items(orm_type: str) -> set[Path]:
    items: set[Path] = set()
    for relative in COMMON_FILES:
        if orm_type == "tortoise" and relative == "alembic.ini":
            continue
        items.add(Path(relative))
    return items


def _collect_compose_items(_orm_type: str) -> set[Path]:
    items: set[Path] = set()
    target_dir = Path("compose") / "app"

    items.update(
        {
            target_dir / "dev.sh",
            target_dir / "prod.py",
            target_dir / "Dockerfile",
        }
    )

    return items


def _collect_generated_items(orm_type: str, design: str) -> set[Path]:
    items: set[Path] = set()
    items.update(_collect_common_items(orm_type))
    items.update({Path("src")})
    items.update(_collect_compose_items(orm_type))
    return items


def _prepare_destination(path_arg: str | None, orm_type: str, design: str) -> Path:
    destination = Path(path_arg or ".").expanduser().resolve()
    generated_items = _collect_generated_items(orm_type, design)

    if destination.exists():
        if not destination.is_dir():
            print(f"Target path '{destination}' is not a directory.")
            raise SystemExit(1)
        existing_items = _collect_existing_items(destination)
        if existing_items:
            overlapping_items = existing_items & generated_items

            if overlapping_items:
                print(f"Target directory '{destination}' is not empty.")
                print("The following items will be replaced:")
                for item in sorted(overlapping_items):
                    print(f"- {item.as_posix()}")
            else:
                print(
                    f"Target directory '{destination}' is not empty, "
                    "but no existing items conflict with the template."
                )

            proceed = click.confirm(
                "Proceed with applying the template to this directory?",
                default=False,
            )
            if not proceed:
                print("Operation cancelled by user.")
                raise SystemExit(1)
    else:
        destination.mkdir(parents=True, exist_ok=True)
    return destination


def _get_template_config(design: str, orm_type: str) -> dict[str, str]:
    key = f"{design}:{orm_type}"
    config = TEMPLATE_CONFIGS.get(key)
    if config is None:
        print(
            f"Unsupported configuration '{key}'. "
            f"Valid options: {', '.join(TEMPLATE_CONFIGS.keys())}."
        )
        raise SystemExit(1)
    return dict(config)


def _render_template(source: Path, target: Path, context: Mapping[str, str]) -> None:
    template = JINJA_ENV.from_string(source.read_text())
    rendered = template.render(**context)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(rendered)


def _copy_common_files(
    destination: Path, orm_type: str, context: Mapping[str, str]
) -> None:
    for relative in COMMON_FILES:
        if orm_type == "tortoise" and relative == "alembic.ini":
            continue

        source = COMMON_DIR / relative
        target = destination / relative

        if relative in TEMPLATE_FILES:
            _render_template(source, target, context)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)


def _copy_src_app(destination: Path, orm_type: str, design: str) -> None:
    target_dir = destination / "src" / "app"
    target_dir.parent.mkdir(parents=True, exist_ok=True)

    source_app_dir = SRC_DIR / design
    infra_dir = (source_app_dir / "infrastructure").resolve()
    models_dir = (source_app_dir / "models").resolve()

    def copy_tree_with_skip(
        source: Path, target: Path, skip_map: Mapping[Path, set[str]]
    ) -> None:
        def ignore(current: str, names: Iterable[str]) -> Iterable[str]:
            current_path = Path(current).resolve()
            for root, skip_names in skip_map.items():
                if current_path == root:
                    return [name for name in names if name in skip_names]
            return []

        shutil.copytree(source, target, dirs_exist_ok=True, ignore=ignore)

    if design == "ddd":
        skip = {infra_dir: set(ORM_CHOICES)}
        copy_tree_with_skip(source_app_dir, target_dir, skip)

        source_database = infra_dir / orm_type
        target_database = target_dir / "infrastructure" / "database"
        shutil.copytree(source_database, target_database, dirs_exist_ok=True)

    elif design == "mvc":
        skip = {source_app_dir.resolve(): {"models"}}
        copy_tree_with_skip(source_app_dir, target_dir, skip)

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


def _copy_compose_app(
    destination: Path, orm_type: str, context: Mapping[str, str]
) -> None:
    target_dir = destination / "compose" / "app"

    def ignore(source: str, names: Iterable[str]) -> Iterable[str]:
        source_path = Path(source).resolve()
        if source_path == COMPOSE_APP_DIR:
            templates = {
                "dev.sqlalchemy.sh",
                "dev.tortoise.sh",
                "prod.sqlalchemy.py",
                "prod.tortoise.py",
                "Dockerfile",
            }
            return [name for name in names if name in templates]
        return []

    shutil.copytree(COMPOSE_APP_DIR, target_dir, dirs_exist_ok=True, ignore=ignore)

    dev_source = _resolve_compose_file("dev", "sh", orm_type)
    prod_source = _resolve_compose_file("prod", "py", orm_type)
    shutil.copy2(dev_source, target_dir / "dev.sh")
    shutil.copy2(prod_source, target_dir / "prod.py")

    dockerfile_source = COMPOSE_APP_DIR / "Dockerfile"
    _render_template(dockerfile_source, target_dir / "Dockerfile", context)


def _copy_template(
    destination: Path, orm_type: str, design: str, project_name: str
) -> None:
    context = _get_template_config(design, orm_type)
    context["name"] = project_name
    _copy_src_app(destination, orm_type, design)
    _copy_compose_app(destination, orm_type, context)
    _copy_common_files(destination, orm_type, context)


@click.group(name="robyn-config")
def cli() -> None:
    """Robyn configuration utilities."""


@cli.command("create")
@click.argument("name")
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
def create(
    name: str, destination: str | None, orm_type: str, design: str
) -> None:
    """Copy the template into DESTINATION with ORM-specific adjustments."""
    normalized_orm = orm_type.lower()
    if normalized_orm not in ORM_CHOICES:
        print(f"Unsupported ORM '{orm_type}'. Valid options: {', '.join(ORM_CHOICES)}.")
        raise SystemExit(1)

    normalized_design = design.lower()
    if normalized_design not in DESIGN_CHOICES:
        print(f"Unsupported design '{design}'. Valid options: {', '.join(DESIGN_CHOICES)}.")
        raise SystemExit(1)

    target_dir = _prepare_destination(destination, normalized_orm, normalized_design)
    _copy_template(target_dir, normalized_orm, normalized_design, name)
    print(f"Robyn template ({normalized_design}/{normalized_orm}) copied to {target_dir}")


if __name__ == "__main__":
    cli()
