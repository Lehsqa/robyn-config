"""Utility functions for the 'create' command."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import click
from jinja2 import Environment, StrictUndefined

ORM_CHOICES: Sequence[str] = ("sqlalchemy", "tortoise")
DESIGN_CHOICES: Sequence[str] = ("ddd", "mvc")
PACKAGE_MANAGER_CHOICES: Sequence[str] = ("uv", "poetry")
PACKAGE_ROOT = Path(__file__).resolve().parent
SRC_DIR = PACKAGE_ROOT.resolve()
COMMON_DIR = (SRC_DIR / "common").resolve()
COMPOSE_APP_DIR = (COMMON_DIR / "compose" / "app").resolve()
LOCK_FILE_BY_MANAGER: Mapping[str, str] = {
    "uv": "uv.lock",
    "poetry": "poetry.lock",
}
PACKAGE_MANAGER_DOWNLOAD_URLS: Mapping[str, str] = {
    "uv": "https://docs.astral.sh/uv/getting-started/installation/",
    "poetry": "https://python-poetry.org/docs/#installation",
}

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


def _collect_common_items(orm_type: str, package_manager: str) -> set[Path]:
    items: set[Path] = set()
    for item in COMMON_DIR.iterdir():
        if item.is_dir() or item.name == ".DS_Store":
            continue

        name = item.name
        if item.suffix == ".jinja2":
            name = item.stem

        if orm_type == "tortoise" and name == "alembic.ini":
            continue
        if name in LOCK_FILE_BY_MANAGER.values():
            continue
        items.add(Path(name))
    lock_file = LOCK_FILE_BY_MANAGER.get(package_manager)
    if lock_file:
        items.add(Path(lock_file))
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


def _collect_generated_items(
    orm_type: str, design: str, package_manager: str
) -> set[Path]:
    items: set[Path] = set()
    items.update(_collect_common_items(orm_type, package_manager))
    items.update({Path("src")})
    items.update(_collect_compose_items(orm_type))
    return items


def prepare_destination(
    path_arg: str, orm_type: str, design: str, package_manager: str
) -> Path:
    """Prepare and validate the destination directory for the template."""
    destination = Path(path_arg).expanduser().resolve()
    generated_items = _collect_generated_items(
        orm_type, design, package_manager
    )

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
                return destination

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


def _get_template_config(
    design: str, orm_type: str, project_name: str, package_manager: str
) -> dict[str, str]:
    """Get the template configuration for the given design and ORM type."""
    key = f"{design}:{orm_type}"
    config = TEMPLATE_CONFIGS.get(key)
    if config is None:
        print(
            f"Unsupported configuration '{key}'. "
            f"Valid options: {', '.join(TEMPLATE_CONFIGS.keys())}."
        )
        raise SystemExit(1)
    return {
        **config,
        "name": project_name,
        "package_manager": package_manager,
    }


def _render_template(
    source: Path, target: Path, context: Mapping[str, str]
) -> None:
    """Render a Jinja2 template from source to target."""
    template = JINJA_ENV.from_string(source.read_text())
    rendered = template.render(**context)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(rendered)


def _copy_common_files(
    destination: Path,
    orm_type: str,
    package_manager: str,
    context: Mapping[str, str],
) -> None:
    """Copy common files to the destination directory."""
    lock_files = set(LOCK_FILE_BY_MANAGER.values())
    current_lock = LOCK_FILE_BY_MANAGER.get(package_manager)
    for source in COMMON_DIR.iterdir():
        if source.is_dir() or source.name == ".DS_Store":
            continue

        name = source.name
        is_template = source.suffix == ".jinja2"

        if is_template:
            name = source.stem

        if orm_type == "tortoise" and name == "alembic.ini":
            continue
        if name == current_lock:
            continue
        if name in lock_files:
            continue

        target = destination / name
        if is_template:
            _render_template(source, target, context)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)


def _copy_src_app(destination: Path, orm_type: str, design: str) -> None:
    """Copy the application source directory to the destination."""
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
    """Resolve the compose file path for the given ORM type."""
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
    """Copy the compose app files to the destination directory."""
    target_dir = destination / "compose" / "app"

    def ignore(source: str, names: Iterable[str]) -> Iterable[str]:
        source_path = Path(source).resolve()
        if source_path == COMPOSE_APP_DIR:
            templates = {
                "dev.sqlalchemy.sh",
                "dev.tortoise.sh",
                "prod.sqlalchemy.py",
                "prod.tortoise.py",
                "Dockerfile.jinja2",
            }
            return [name for name in names if name in templates]
        return []

    shutil.copytree(
        COMPOSE_APP_DIR, target_dir, dirs_exist_ok=True, ignore=ignore
    )

    dev_source = _resolve_compose_file("dev", "sh", orm_type)
    prod_source = _resolve_compose_file("prod", "py", orm_type)
    shutil.copy2(dev_source, target_dir / "dev.sh")
    shutil.copy2(prod_source, target_dir / "prod.py")

    dockerfile_source = COMPOSE_APP_DIR / "Dockerfile.jinja2"
    _render_template(dockerfile_source, target_dir / "Dockerfile", context)


def copy_template(
    destination: Path,
    orm_type: str,
    design: str,
    project_name: str,
    package_manager: str,
) -> None:
    """Copy the complete template to the destination directory."""
    context = _get_template_config(
        design, orm_type, project_name, package_manager
    )
    _copy_src_app(destination, orm_type, design)
    _copy_compose_app(destination, orm_type, context)
    _copy_common_files(destination, orm_type, package_manager, context)


def collect_existing_items(destination: Path) -> set[Path]:
    """Return the set of existing items in a destination for cleanup logic."""
    return _collect_existing_items(destination)


def get_generated_items(
    orm_type: str, design: str, package_manager: str
) -> set[Path]:
    """Return the set of items this template would generate."""
    return _collect_generated_items(orm_type, design, package_manager)


def ensure_package_manager_available(package_manager: str) -> None:
    """Validate the requested package manager is available on PATH."""
    if package_manager not in PACKAGE_MANAGER_CHOICES:
        raise click.ClickException(
            "Unsupported package manager "
            f"'{package_manager}'. Choose from: {', '.join(PACKAGE_MANAGER_CHOICES)}"
        )

    if shutil.which(package_manager) is None:
        download_url = PACKAGE_MANAGER_DOWNLOAD_URLS.get(package_manager)
        download_hint = (
            f" Download it from {download_url} before running the create command."
            if download_url
            else " Install it before running the create command."
        )
        raise click.ClickException(
            f"Package manager '{package_manager}' is not installed.{download_hint}"
        )


def apply_package_manager(destination: Path, package_manager: str) -> None:
    """Generate the lock file for the project using the chosen package manager."""
    ensure_package_manager_available(package_manager)

    lock_file = LOCK_FILE_BY_MANAGER.get(package_manager, "lock file")
    lock_path = destination / lock_file
    env = os.environ.copy()
    if package_manager == "uv":
        env.setdefault("UV_CACHE_DIR", str(destination / ".uv-cache"))
    else:
        env.setdefault("POETRY_CACHE_DIR", str(destination / ".poetry-cache"))
    if package_manager == "uv":
        command = ["uv", "lock"]
    else:
        command = ["poetry", "lock", "--no-interaction", "--quiet"]

    result = subprocess.run(
        command, cwd=destination, capture_output=True, text=True, env=env
    )
    if result.returncode != 0:
        message = (
            result.stderr.strip() or result.stdout.strip() or "Unknown error"
        )
        raise click.ClickException(
            f"Failed to generate {lock_file} with {package_manager}: {message}"
        )
    if lock_file and not lock_path.exists():
        output = result.stdout.strip() or result.stderr.strip()
        detail = f" ({output})" if output else ""
        raise click.ClickException(
            f"{package_manager} finished without creating {lock_file}{detail}"
        )
