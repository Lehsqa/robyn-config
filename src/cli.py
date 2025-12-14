"""Project scaffolding CLI based on the local Robyn template."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import click

from add import add_business_logic
from create import (
    DESIGN_CHOICES,
    ORM_CHOICES,
    PACKAGE_MANAGER_CHOICES,
    apply_package_manager,
    collect_existing_items,
    copy_template,
    ensure_package_manager_available,
    get_generated_items,
    prepare_destination,
)


def _remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
    else:
        path.unlink(missing_ok=True)


def _cleanup_create_failure(
    target_dir: Path,
    generated_items: set[Path],
    existing_items: set[Path],
    created_new_dir: bool,
) -> None:
    """Attempt to remove files created during a failed create command."""
    if created_new_dir and target_dir.exists():
        shutil.rmtree(target_dir, ignore_errors=True)
        return

    for rel_path in generated_items:
        if rel_path in existing_items:
            continue
        candidate = target_dir / rel_path
        if candidate.exists():
            _remove_path(candidate)


def _backup_project(project_path: Path) -> tuple[Path, Path]:
    """Create a backup of the project directory for rollback."""
    temp_dir = Path(tempfile.mkdtemp(prefix="robyn-config-add-backup-"))
    backup_path = temp_dir / "project"
    shutil.copytree(project_path, backup_path, dirs_exist_ok=True)
    return temp_dir, backup_path


def _restore_project_backup(project_path: Path, backup_path: Path) -> None:
    """Restore project directory from backup."""
    if project_path.exists():
        for child in project_path.iterdir():
            _remove_path(child)
    shutil.copytree(backup_path, project_path, dirs_exist_ok=True)


@click.group(name="robyn-config")
def cli() -> None:
    """Robyn configuration utilities."""


@cli.command("create")
@click.argument("name")
@click.option(
    "-orm",
    "--orm",
    "orm_type",
    type=click.Choice(ORM_CHOICES, case_sensitive=False),
    default="sqlalchemy",
    show_default=True,
    help="Select the ORM implementation to copy.",
)
@click.option(
    "-design",
    "--design",
    "design",
    type=click.Choice(DESIGN_CHOICES, case_sensitive=False),
    default="ddd",
    show_default=True,
    help="Select the design pattern.",
)
@click.option(
    "-package-manager",
    "--package-manager",
    "package_manager",
    type=click.Choice(PACKAGE_MANAGER_CHOICES, case_sensitive=False),
    default="uv",
    show_default=True,
    help="Select the package manager to use.",
)
@click.argument(
    "destination",
    type=click.Path(
        exists=False, file_okay=False, dir_okay=True, path_type=Path
    ),
    default=".",
)
def create(
    name: str,
    destination: Path,
    orm_type: str,
    design: str,
    package_manager: str,
) -> None:
    """Copy the template into destination with specific configurations."""
    package_manager = package_manager.lower()
    ensure_package_manager_available(package_manager)

    destination_resolved = destination.expanduser().resolve()
    destination_exists_before = destination_resolved.exists()
    existing_items: set[Path] = set()
    if destination_exists_before:
        existing_items = collect_existing_items(destination_resolved)

    target_dir: Path | None = None
    generated_items: set[Path] = set()
    created_new_dir = False

    try:
        click.echo(f"Creating Robyn template ({design}/{orm_type})...")
        target_dir = prepare_destination(
            destination, orm_type, design, package_manager
        )
        generated_items = get_generated_items(
            orm_type, design, package_manager
        )
        created_new_dir = not destination_exists_before and target_dir.exists()

        copy_template(target_dir, orm_type, design, name, package_manager)

        click.echo("Installing dependencies...")
        apply_package_manager(target_dir, package_manager)

        click.echo(
            click.style("Successfully created Robyn template", fg="green")
        )
    except Exception as e:
        if target_dir:
            _cleanup_create_failure(
                target_dir, generated_items, existing_items, created_new_dir
            )
        raise click.ClickException(click.style(str(e), fg="red")) from e


@cli.command("add")
@click.argument("name")
@click.argument(
    "project_path",
    type=click.Path(
        exists=True, file_okay=False, dir_okay=True, path_type=Path
    ),
    default=".",
)
def add(name: str, project_path: Path) -> None:
    """Add new business logic to an existing robyn-config project."""
    backup_dir: Path | None = None
    backup_path: Path | None = None
    project_path = project_path.resolve()

    try:
        backup_dir, backup_path = _backup_project(project_path)
        add_business_logic(project_path, name)
        click.echo(
            click.style(
                f"Successfully added '{name}' business logic!", fg="green"
            )
        )
    except Exception as e:
        if backup_path:
            _restore_project_backup(project_path, backup_path)
        raise click.ClickException(click.style(str(e), fg="red")) from e
    finally:
        if backup_dir:
            shutil.rmtree(backup_dir, ignore_errors=True)


if __name__ == "__main__":
    cli()
