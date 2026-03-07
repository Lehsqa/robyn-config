"""Integration tests for the 'adminpanel' command."""

from __future__ import annotations

import os
import shutil
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


def run_cli_adminpanel(
    project_path: Path,
    *,
    username: str | None = None,
    password: str | None = None,
    input_text: str | None = None,
) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    cmd = [
        sys.executable,
        "-m",
        "cli",
        "adminpanel",
    ]
    if username is not None:
        cmd.extend(["-u", username])
    if password is not None:
        cmd.extend(["-p", password])
    cmd.append(str(project_path))
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        input=input_text,
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
            / "tables"
            / "adminpanel.py"
        )
    return project_dir / "src" / "app" / "models" / "tables" / "adminpanel.py"


def _tables_init_file(project_dir: Path, design: str) -> Path:
    if design == "ddd":
        return (
            project_dir
            / "src"
            / "app"
            / "infrastructure"
            / "database"
            / "tables"
            / "__init__.py"
        )
    return project_dir / "src" / "app" / "models" / "tables" / "__init__.py"


def _admin_form_modal_file(project_dir: Path, design: str) -> Path:
    return (
        _admin_root(project_dir, design)
        / "templates"
        / "admin"
        / "components"
        / "form_modal.html"
    )


def _admin_data_table_file(project_dir: Path, design: str) -> Path:
    return (
        _admin_root(project_dir, design)
        / "templates"
        / "admin"
        / "components"
        / "data_table.html"
    )


def _admin_model_change_file(project_dir: Path, design: str) -> Path:
    return (
        _admin_root(project_dir, design)
        / "templates"
        / "admin"
        / "model_change.html"
    )


def _authentication_table_file(project_dir: Path, design: str) -> Path:
    if design == "ddd":
        return (
            project_dir
            / "src"
            / "app"
            / "infrastructure"
            / "database"
            / "tables"
            / "authentication.py"
        )
    return (
        project_dir / "src" / "app" / "models" / "tables" / "authentication.py"
    )


def _project_tables_dir(project_dir: Path, design: str) -> Path:
    if design == "ddd":
        return (
            project_dir
            / "src"
            / "app"
            / "infrastructure"
            / "database"
            / "tables"
        )
    return project_dir / "src" / "app" / "models" / "tables"


def _default_database_table_path(design: str) -> str:
    if design == "ddd":
        return "src/app/infrastructure/database/tables/__init__.py"
    return "src/app/models/tables/__init__.py"


def _custom_database_table_path(design: str) -> str:
    if design == "ddd":
        return "src/app/infrastructure/database/custom_tables/__init__.py"
    return "src/app/models/custom_tables/__init__.py"


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
    pyproject_content = (project_dir / "pyproject.toml").read_text()
    assert "[tool.robyn-config.adminpanel]" in pyproject_content
    assert "created = true" in pyproject_content
    if design == "ddd":
        assert (
            project_dir
            / "src"
            / "app"
            / "infrastructure"
            / "database"
            / "tables"
            / "__init__.py"
        ).exists()
        assert not (
            project_dir
            / "src"
            / "app"
            / "infrastructure"
            / "database"
            / "tables.py"
        ).exists()
    else:
        assert (
            project_dir
            / "src"
            / "app"
            / "models"
            / "tables"
            / "__init__.py"
        ).exists()

    admin_root = _admin_root(project_dir, design)
    assert admin_root.exists()
    admin_init = admin_root / "__init__.py"
    assert admin_init.exists()
    assert (admin_root / "core" / "site.py").exists()
    assert (admin_root / "core" / "admin.py").exists()
    assert (admin_root / "templates" / "admin" / "login.html").exists()
    assert not (admin_root / "templates" / "admin" / "users.html").exists()
    models_template_content = (
        admin_root / "templates" / "admin" / "models.html"
    ).read_text()
    assert "admin-model-search-shell" in models_template_content
    assert "data-category=" in models_template_content
    assert "model_categories" in models_template_content
    assert "id=\"modelsSearch\"" in models_template_content
    assert "admin-themed-input" in models_template_content

    settings_template_content = (
        admin_root / "templates" / "admin" / "settings.html"
    ).read_text()
    assert settings_template_content.count("admin-themed-input") >= 3

    login_template_content = (
        admin_root / "templates" / "admin" / "login.html"
    ).read_text()
    assert login_template_content.count("admin-themed-input") >= 2

    base_template_content = (
        admin_root / "templates" / "admin" / "base.html"
    ).read_text()
    assert ".admin-themed-input" in base_template_content
    assert ".dark .admin-themed-input" in base_template_content
    assert "--admin-border-soft-light" in base_template_content
    assert "--admin-table-border-dark" in base_template_content
    assert ".admin-border-soft" in base_template_content
    assert ".admin-border-soft-divider" in base_template_content
    assert ".bootstrap-table .table tr > *:first-child" in base_template_content
    assert "border-width: 1px 1px 1px 0" in base_template_content
    assert ".admin-model-search-shell" in base_template_content
    assert ".bootstrap-table .table th," in base_template_content
    assert ".dark .bootstrap-table .table td" in base_template_content
    assert (
        ".dark .bootstrap-table .table > tbody > tr > td"
        in base_template_content
    )
    assert ".models-search-icon-shell" in base_template_content
    assert ".dark .models-search-icon-shell" in base_template_content
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

    data_table_content = _admin_data_table_file(project_dir, design).read_text()
    assert "admin-border-soft bg-surface-light" in data_table_content
    assert "admin-border-soft-divider" in data_table_content
    assert (
        "/admin/${config.route_id}/${encodedId}/change" in data_table_content
    )
    assert "title: translations.operation" not in data_table_content
    assert "syncCurrentPageSelectionCache" in data_table_content

    assert _admin_model_change_file(project_dir, design).exists()
    model_list_template_content = (
        admin_root / "templates" / "admin" / "model_list.html"
    ).read_text()
    assert "admin-border-soft bg-surface-light" in model_list_template_content
    assert (
        '<a href="/admin/models" class="admin-action-btn admin-action-btn-neutral">'
        in model_list_template_content
    )
    assert 'href="/admin/{{ current_model }}/add"' in model_list_template_content
    assert "showFormModal('add')" not in model_list_template_content

    model_change_template_content = (
        admin_root / "templates" / "admin" / "model_change.html"
    ).read_text()
    assert "is_add_mode" in model_change_template_content
    assert (
        "data-save-url=\"{% if is_add_mode %}/admin/{{ route_id }}/add{% else %}/admin/{{ route_id }}/{{ object_id }}/edit{% endif %}\""
        in model_change_template_content
    )
    assert "model-change-breadcrumb" in model_change_template_content
    assert "admin-form-section" in model_change_template_content
    assert "admin-json-editor" in model_change_template_content
    assert "admin-longtext-editor" in model_change_template_content
    assert "admin-boolean-switch" in model_change_template_content
    assert "admin-boolean-switch admin-themed-input" in model_change_template_content
    assert "modelChangeActionBar" in model_change_template_content
    assert "admin-change-actionbar" in model_change_template_content
    assert "--admin-change-field-bg" in model_change_template_content
    assert "admin-themed-input" in model_change_template_content
    assert "Edit Details" not in model_change_template_content
    assert "History" not in model_change_template_content
    assert "Cancel" not in model_change_template_content
    assert "max-w-7xl" not in model_change_template_content

    init_content = admin_init.read_text()
    assert 'default_admin_username="admin"' in init_content
    assert 'default_admin_password="admin"' in init_content
    assert "_discover_project_models" in init_content
    assert "for model in _discover_project_models():" in init_content
    assert "register_model(project_tables.UsersTable" not in init_content
    assert (
        "register_model(\n        project_tables.NewsLetterSubscriptionsTable"
        not in init_content
    )

    authentication_table_content = _authentication_table_file(
        project_dir, design
    ).read_text()
    assert "from ...authentication import AuthProvider, pwd_context" in authentication_table_content
    assert "pwd_context.hash(" in authentication_table_content
    assert "pwd_context.verify(" in authentication_table_content
    assert "scheme=\"bcrypt\"" in authentication_table_content

    if orm == "sqlalchemy":
        assert "TORTOISE_ORM" not in init_content
        assert "MODEL_MODULES" not in init_content
        assert "create_session" in init_content
        assert "from .models_sqlalchemy import AdminUser" in init_content
        assert "from .auth_models_sqlalchemy import Role, UserRole" in init_content
        assert "from .auth_models_sqlalchemy import AdminUser" not in init_content
        assert "from sqlalchemy.inspection import inspect as sa_inspect" in init_content
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
        assert "def _get_session_dialect" in sqlalchemy_site_content
        assert "\"postgres\" in driver_name" in sqlalchemy_site_content
        assert "pg_advisory_lock" in sqlalchemy_site_content
        assert "pg_advisory_unlock" in sqlalchemy_site_content
        assert ".on_conflict_do_nothing()" in sqlalchemy_site_content
        assert (
            "if is_postgresql:\n"
            "                    await session.execute(\n"
            "                        pg_insert(AdminUser)"
            not in sqlalchemy_site_content
        )
        assert "self._default_admin_initialized = False" in sqlalchemy_site_content
        assert (
            "self._default_admin_init_lock = asyncio.Lock()"
            in sqlalchemy_site_content
        )
        assert (
            "if self._default_admin_initialized:\n            return"
            in sqlalchemy_site_content
        )
        assert "_build_model_categories" in sqlalchemy_site_content
        assert "MODEL_NAME_OVERRIDES" not in sqlalchemy_site_content
        assert "users_alias" in sqlalchemy_site_content
        assert "Users tab moved to models" in sqlalchemy_site_content
        assert '@self.app.get(f"/{self.prefix}/:route_id/add")' in sqlalchemy_site_content

        versions_dir = _sqlalchemy_versions_dir(project_dir, design)
        migration_files = sorted(versions_dir.glob("*adminpanel*.py"))
        assert (
            not migration_files
        ), "Adminpanel command should not auto-generate SQLAlchemy migration files"
    else:
        assert "TORTOISE_ORM" in init_content
        assert "MODEL_MODULES" in init_content
        assert "from tortoise import Model as TortoiseModel" in init_content
        assert 'orm="tortoise"' not in init_content
        site_content = (admin_root / "core" / "site.py").read_text()
        assert "self._default_admin_initialized = False" in site_content
        assert "self._default_admin_init_lock = asyncio.Lock()" in site_content
        assert "db_url.startswith(\"postgres\")" in site_content
        assert "pg_advisory_lock" in site_content
        assert "pg_advisory_unlock" in site_content
        assert (
            "if self._default_admin_initialized:\n                return"
            in site_content
        )
        assert "_build_model_categories" in site_content
        assert "MODEL_NAME_OVERRIDES" not in site_content
        assert "users_alias" in site_content
        assert "Users tab moved to models" in site_content
        assert '@self.app.get(f"/{self.prefix}/:route_id/add")' in site_content

    server_path = project_dir / "src" / "app" / "server.py"
    server_content = server_path.read_text()
    assert "adminpanel.register" in server_content
    assert "adminpanel.register))" not in server_content


@pytest.mark.integration
@pytest.mark.parametrize("design,orm", COMBINATIONS)
def test_adminpanel_command_supports_custom_superadmin_credentials(
    tmp_path: Path, design: str, orm: str
) -> None:
    project_dir = tmp_path / f"{design}-{orm}-custom-admin"
    fake_bin = create_fake_package_managers(tmp_path)

    run_cli_create(project_dir, design, orm, fake_bin)
    result = run_cli_adminpanel(
        project_dir,
        username="superadmin",
        password="super-secret-password",
    )

    assert result.returncode == 0, result.stderr
    admin_init = _admin_root(project_dir, design) / "__init__.py"
    init_content = admin_init.read_text()
    assert 'default_admin_username="superadmin"' in init_content
    assert 'default_admin_password="super-secret-password"' in init_content


@pytest.mark.integration
def test_adminpanel_command_prompts_before_updating_existing_module(
    tmp_path: Path,
) -> None:
    project_dir = tmp_path / "ddd-sqlalchemy-admin-repeat"
    fake_bin = create_fake_package_managers(tmp_path)

    run_cli_create(project_dir, "ddd", "sqlalchemy", fake_bin)

    first_run = run_cli_adminpanel(project_dir)
    assert first_run.returncode == 0, first_run.stderr

    second_run = run_cli_adminpanel(project_dir, input_text="n\n")
    assert second_run.returncode == 0, second_run.stderr
    assert (
        "Do you want to update the existing adminpanel module?"
        in second_run.stdout
    )
    assert "Skipped admin panel update." in second_run.stdout

    third_run = run_cli_adminpanel(project_dir, input_text="y\n")
    assert third_run.returncode == 0, third_run.stderr
    assert (
        "Successfully added admin panel scaffolding!"
        in third_run.stdout
    )


@pytest.mark.integration
@pytest.mark.parametrize("design", ("ddd", "mvc"))
def test_adminpanel_command_uses_database_table_path_from_add_config(
    tmp_path: Path, design: str
) -> None:
    project_dir = tmp_path / f"{design}-sqlalchemy-admin-custom-table-path"
    fake_bin = create_fake_package_managers(tmp_path)

    run_cli_create(project_dir, design, "sqlalchemy", fake_bin)

    default_tables_dir = _project_tables_dir(project_dir, design)
    custom_tables_dir = default_tables_dir.parent / "custom_tables"
    shutil.copytree(default_tables_dir, custom_tables_dir)

    pyproject_path = project_dir / "pyproject.toml"
    pyproject_content = pyproject_path.read_text()
    pyproject_path.write_text(
        pyproject_content.replace(
            _default_database_table_path(design),
            _custom_database_table_path(design),
            1,
        )
    )

    result = run_cli_adminpanel(project_dir)

    assert result.returncode == 0, result.stderr
    assert (custom_tables_dir / "adminpanel.py").exists()
    assert (
        "from .adminpanel import Role, UserRole"
        in (custom_tables_dir / "__init__.py").read_text()
    )
    assert not (default_tables_dir / "adminpanel.py").exists()

    admin_loader_path = _admin_root(project_dir, design) / "project_tables.py"
    admin_loader_content = admin_loader_path.read_text()
    assert "database_table_path" in admin_loader_content
    assert "app.infrastructure.database.tables" in admin_loader_content
    assert "app.models.tables" in admin_loader_content


@pytest.mark.integration
def test_adminpanel_section_is_written_after_add_section(tmp_path: Path) -> None:
    project_dir = tmp_path / "ddd-sqlalchemy-admin-section-order"
    fake_bin = create_fake_package_managers(tmp_path)

    run_cli_create(project_dir, "ddd", "sqlalchemy", fake_bin)
    result = run_cli_adminpanel(project_dir)

    assert result.returncode == 0, result.stderr

    pyproject_lines = (project_dir / "pyproject.toml").read_text().splitlines()
    sections = [
        line.strip()
        for line in pyproject_lines
        if line.strip().startswith("[") and line.strip().endswith("]")
    ]
    add_idx = sections.index("[tool.robyn-config.add]")
    adminpanel_idx = sections.index("[tool.robyn-config.adminpanel]")
    assert adminpanel_idx == add_idx + 1
