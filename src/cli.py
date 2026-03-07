"""Project scaffolding CLI based on the local Robyn template."""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

import click

from add import add_business_logic
from add import read_project_config
from adminpanel import add_adminpanel
from create import (
    DESIGN_CHOICES,
    InteractiveCreateConfig,
    ORM_CHOICES,
    PACKAGE_MANAGER_CHOICES,
    apply_package_manager,
    collect_existing_items,
    copy_template,
    ensure_package_manager_available,
    get_generated_items,
    prepare_destination,
    run_create_interactive,
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


def _interactive_terminal_available() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _is_adminpanel_marked_created(config: dict) -> bool:
    adminpanel_config = config.get("adminpanel")
    if not isinstance(adminpanel_config, dict):
        return False

    created_value = adminpanel_config.get("created")
    if isinstance(created_value, bool):
        return created_value
    if isinstance(created_value, str):
        return created_value.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(created_value, int):
        return created_value != 0
    return bool(created_value)


@click.group(name="robyn-config")
def cli() -> None:
    """Robyn configuration utilities."""


@cli.command("create")
@click.argument("name", required=False)
@click.option(
    "-i",
    "--interactive",
    is_flag=True,
    help="Launch interactive mode for collecting create options.",
)
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
    required=False,
    default=Path("."),
)
def create(
    name: str | None,
    destination: Path | None,
    interactive: bool,
    orm_type: str,
    design: str,
    package_manager: str,
) -> None:
    """Copy the template into destination with specific configurations."""
    destination = destination or Path(".")

    if interactive:
        if not _interactive_terminal_available():
            raise click.ClickException(
                "Interactive mode requires a TTY terminal. "
                "Use non-interactive mode: "
                "robyn-config create NAME [DESTINATION]."
            )

        try:
            selected = run_create_interactive(
                InteractiveCreateConfig(
                    name=name or "",
                    destination=str(destination),
                    orm=orm_type,
                    design=design,
                    package_manager=package_manager,
                )
            )
        except RuntimeError as exc:
            raise click.ClickException(str(exc)) from exc
        if selected is None:
            raise click.ClickException("Create command cancelled.")

        name = selected.name
        destination = Path(selected.destination).expanduser()
        orm_type = selected.orm
        design = selected.design
        package_manager = selected.package_manager

    if not name:
        raise click.UsageError("Missing argument 'NAME'.")

    orm_type = orm_type.lower()
    design = design.lower()
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


@cli.command("adminpanel")
@click.option(
    "-u",
    "--username",
    "admin_username",
    default="admin",
    show_default=True,
    help="Default superadmin username for generated admin panel.",
)
@click.option(
    "-p",
    "--password",
    "admin_password",
    default="admin",
    show_default=True,
    help="Default superadmin password for generated admin panel.",
)
@click.argument(
    "project_path",
    type=click.Path(
        exists=True, file_okay=False, dir_okay=True, path_type=Path
    ),
    default=".",
)
def adminpanel(
    admin_username: str, admin_password: str, project_path: Path
) -> None:
    """Add admin panel scaffolding to an existing robyn-config project."""
    backup_dir: Path | None = None
    backup_path: Path | None = None
    project_path = project_path.resolve()

    try:
        if not admin_username.strip():
            raise click.ClickException("Admin username cannot be empty.")
        if not admin_password:
            raise click.ClickException("Admin password cannot be empty.")

        project_config = read_project_config(project_path)
        if _is_adminpanel_marked_created(project_config):
            should_update = click.confirm(
                "Admin panel is already marked as created. Do you want to update the existing adminpanel module?",
                default=False,
            )
            if not should_update:
                click.echo(
                    click.style(
                        "Skipped admin panel update.",
                        fg="yellow",
                    )
                )
                return

        backup_dir, backup_path = _backup_project(project_path)
        add_adminpanel(
            project_path,
            admin_username=admin_username,
            admin_password=admin_password,
        )
        click.echo(
            click.style(
                "Successfully added admin panel scaffolding!",
                fg="green",
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
