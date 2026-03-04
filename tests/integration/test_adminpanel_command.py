"""Integration tests for the 'adminpanel' command."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.integration.test_create_command import create_fake_package_managers

ROOT = Path(__file__).resolve().parents[2]
COMBINATIONS = [
    ("ddd", "sqlalchemy"),
    ("ddd", "tortoise"),
    ("mvc", "sqlalchemy"),
    ("mvc", "tortoise"),
]


def run_cli_create(
    destination: Path, design: str, orm: str, bin_dir: Path | None = None
) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    if bin_dir:
        env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "cli",
            "create",
            "admin-app",
            "--orm",
            orm,
            "--design",
            design,
            str(destination),
        ],
        check=True,
        env=env,
    )


def run_cli_adminpanel(project_path: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "cli",
            "adminpanel",
            str(project_path),
        ],
        capture_output=True,
        text=True,
        env=env,
    )


def _admin_root(project_dir: Path, design: str) -> Path:
    if design == "ddd":
        return project_dir / "src" / "app" / "infrastructure" / "adminpanel"
    return project_dir / "src" / "app" / "adminpanel"


def _sqlalchemy_versions_dir(project_dir: Path, design: str) -> Path:
    if design == "ddd":
        return (
            project_dir
            / "src"
            / "app"
            / "infrastructure"
            / "database"
            / "migrations"
            / "versions"
        )
    return project_dir / "src" / "app" / "models" / "migrations" / "versions"


def _adminpanel_tables_file(project_dir: Path, design: str) -> Path:
    if design == "ddd":
        return (
            project_dir
            / "src"
            / "app"
            / "infrastructure"
            / "database"
            / "table"
            / "adminpanel.py"
        )
    return project_dir / "src" / "app" / "models" / "table" / "adminpanel.py"


def _tables_init_file(project_dir: Path, design: str) -> Path:
    if design == "ddd":
        return (
            project_dir
            / "src"
            / "app"
            / "infrastructure"
            / "database"
            / "table"
            / "__init__.py"
        )
    return project_dir / "src" / "app" / "models" / "table" / "__init__.py"


def _admin_form_modal_file(project_dir: Path, design: str) -> Path:
    return (
        _admin_root(project_dir, design)
        / "templates"
        / "admin"
        / "components"
        / "form_modal.html"
    )


@pytest.mark.integration
@pytest.mark.parametrize("design,orm", COMBINATIONS)
def test_adminpanel_command_scaffolds_for_all_design_and_orm_combinations(
    tmp_path: Path, design: str, orm: str
) -> None:
    project_dir = tmp_path / f"{design}-{orm}-admin"
    fake_bin = create_fake_package_managers(tmp_path)

    run_cli_create(project_dir, design, orm, fake_bin)
    result = run_cli_adminpanel(project_dir)

    assert result.returncode == 0, result.stderr
    assert "requires a Tortoise ORM project" not in result.stderr

    admin_root = _admin_root(project_dir, design)
    assert admin_root.exists()
    admin_init = admin_root / "__init__.py"
    assert admin_init.exists()
    assert (admin_root / "core" / "site.py").exists()
    assert (admin_root / "core" / "admin.py").exists()
    assert (admin_root / "templates" / "admin" / "login.html").exists()
    tables_file = _adminpanel_tables_file(project_dir, design)
    tables_content = tables_file.read_text()
    assert "class Role" in tables_content
    assert "class UserRole" in tables_content
    assert "class AdminUser" not in tables_content

    table_init = _tables_init_file(project_dir, design).read_text()
    assert "Role" in table_init
    assert "UserRole" in table_init

    fields_content = (admin_root / "core" / "fields.py").read_text()
    assert "self.field_type in {DisplayType.BOOLEAN, DisplayType.SWITCH}" in fields_content
    assert "normalized in {\"1\", \"true\", \"t\", \"yes\", \"y\", \"on\"}" in fields_content

    form_modal_content = _admin_form_modal_file(project_dir, design).read_text()
    assert (
        "field.field_type === 'boolean' || field.field_type === 'switch'"
        in form_modal_content
    )
    assert "data.set(field.name, input.checked ? 'true' : 'false');" in form_modal_content

    init_content = admin_init.read_text()
    if orm == "sqlalchemy":
        assert "TORTOISE_ORM" not in init_content
        assert "MODEL_MODULES" not in init_content
        assert "create_session" in init_content
        assert "from .models_sqlalchemy import AdminUser" in init_content
        assert "from .auth_models_sqlalchemy import Role, UserRole" in init_content
        assert "from .auth_models_sqlalchemy import AdminUser" not in init_content
        assert (admin_root / "core" / "sqlalchemy_admin.py").exists()
        assert (admin_root / "core" / "sqlalchemy_site.py").exists()
        assert (admin_root / "auth_models_sqlalchemy.py").exists()
        assert (admin_root / "auth_admin_sqlalchemy.py").exists()
        assert (admin_root / "models_sqlalchemy.py").exists()
        sqlalchemy_site_content = (
            admin_root / "core" / "sqlalchemy_site.py"
        ).read_text()
        assert "or_(" in sqlalchemy_site_content
        assert "except IntegrityError" in sqlalchemy_site_content

        versions_dir = _sqlalchemy_versions_dir(project_dir, design)
        migration_files = sorted(versions_dir.glob("*adminpanel*.py"))
        assert (
            not migration_files
        ), "Adminpanel command should not auto-generate SQLAlchemy migration files"
    else:
        assert "TORTOISE_ORM" in init_content
        assert "MODEL_MODULES" in init_content
        assert 'orm="tortoise"' not in init_content

    server_path = project_dir / "src" / "app" / "server.py"
    server_content = server_path.read_text()
    assert "adminpanel.register" in server_content
    assert "adminpanel.register))" not in server_content
