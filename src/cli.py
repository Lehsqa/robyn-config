"""Project scaffolding CLI based on the local Robyn template."""

from __future__ import annotations

from pathlib import Path

import click

from add import add_business_logic
from create import (
    DESIGN_CHOICES,
    ORM_CHOICES,
    copy_template,
    prepare_destination,
)


def _echo_add_summary(name: str, created_files: list[str]) -> None:
    """Render a consistent summary for the add command."""
    click.echo(f"Successfully added '{name}' business logic!")
    click.echo("Created/updated files:")
    for file_path in created_files:
        click.echo(f"  - {file_path}")
    click.echo("")
    click.echo("Automatic updates:")
    click.echo("  ✓ Table added to tables.py")
    click.echo("  ✓ Routes registered automatically")
    click.echo("")
    click.echo("Next step:")
    click.echo("  - Create a database migration (make makemigrations)")


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
    required=True,
    help="Select the ORM implementation to copy (sqlalchemy or tortoise).",
)
@click.option(
    "-design",
    "--design",
    "design",
    type=click.Choice(DESIGN_CHOICES, case_sensitive=False),
    required=True,
    help="Select the design pattern (ddd or mvc)",
)
@click.argument(
    "destination",
    required=False,
    type=click.Path(
        exists=False, file_okay=False, dir_okay=True, path_type=Path
    ),
)
def create(
    name: str, destination: Path | None, orm_type: str, design: str
) -> None:
    """Copy the template into DESTINATION with ORM-specific adjustments."""
    target_dir = prepare_destination(destination, orm_type, design)
    copy_template(target_dir, orm_type, design, name)
    click.echo(f"Robyn template ({design}/{orm_type}) copied to {target_dir}")


@cli.command("add")
@click.argument("name")
@click.option(
    "-p",
    "--path",
    "project_path",
    type=click.Path(
        exists=True, file_okay=False, dir_okay=True, path_type=Path
    ),
    default=".",
    help="Path to the project directory (default: current directory).",
)
def add(name: str, project_path: Path) -> None:
    """Add new business logic to an existing robyn-config project.

    NAME is the name of the business entity to add (e.g., 'product', 'order').
    The command reads the project's pyproject.toml to determine the design pattern
    and ORM type, then generates appropriate template files.
    """
    try:
        project_path = project_path.resolve()
        created_files = add_business_logic(project_path, name)
        _echo_add_summary(name, created_files)
    except (FileNotFoundError, ValueError) as e:
        raise click.ClickException(str(e)) from e


if __name__ == "__main__":
    cli()
