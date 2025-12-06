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
        print(
            f"Unsupported ORM '{orm_type}'. Valid options: {', '.join(ORM_CHOICES)}."
        )
        raise SystemExit(1)

    normalized_design = design.lower()
    if normalized_design not in DESIGN_CHOICES:
        print(
            f"Unsupported design '{design}'. Valid options: {', '.join(DESIGN_CHOICES)}."
        )
        raise SystemExit(1)

    target_dir = prepare_destination(
        destination, normalized_orm, normalized_design
    )
    copy_template(target_dir, normalized_orm, normalized_design, name)
    print(
        f"Robyn template ({normalized_design}/{normalized_orm}) copied to {target_dir}"
    )


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
        print(f"Successfully added '{name}' business logic!")
        print("Created/updated files:")
        for f in created_files:
            print(f"  - {f}")
        print("\nAutomatic updates:")
        print("  ✓ Table added to tables.py")
        print("  ✓ Routes registered automatically")
        print("\nNext step:")
        print(
            "  - Create a database migration (alembic revision --autogenerate)"
        )
    except FileNotFoundError as e:
        print(f"Error: {e}")
        raise SystemExit(1)
    except ValueError as e:
        print(f"Error: {e}")
        raise SystemExit(1)


if __name__ == "__main__":
    cli()
