from pathlib import Path

import pytest
from jinja2 import UndefinedError

from src.adminpanel import utils as admin_utils


def test_detect_package_manager_normalizes_supported_configured_value() -> None:
    package_manager = admin_utils._detect_package_manager(
        {"package_manager": " UV "},
        "",
    )

    assert package_manager == "uv"


def test_detect_package_manager_falls_back_when_configured_value_is_unknown() -> None:
    package_manager = admin_utils._detect_package_manager(
        {"package_manager": "pipenv"},
        "[tool.poetry]",
    )

    assert package_manager == "poetry"


def test_resolve_db_tables_path_uses_add_database_table_path(tmp_path: Path) -> None:
    path = admin_utils._resolve_db_tables_path(
        tmp_path,
        {"add": {"database_table_path": "src/app/models/custom/__init__.py"}},
        "mvc",
    )

    assert path == tmp_path / "src" / "app" / "models" / "custom" / "__init__.py"


def test_resolve_db_tables_path_rejects_unknown_design(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="Unsupported design pattern"):
        admin_utils._resolve_db_tables_path(tmp_path, {}, "hexagonal")


def test_append_admin_models_to_shared_tables_rejects_unknown_orm(
    tmp_path: Path,
) -> None:
    tables_path = tmp_path / "src" / "app" / "models" / "tables" / "__init__.py"
    tables_path.parent.mkdir(parents=True, exist_ok=True)
    tables_path.write_text("")

    with pytest.raises(ValueError, match="Unsupported ORM"):
        admin_utils._append_admin_models_to_shared_tables(
            project_path=tmp_path,
            config={},
            design="mvc",
            orm="peewee",
        )


def test_ensure_project_dependency_adds_when_only_prefixed_name_exists(
    tmp_path: Path,
) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """[project]
dependencies = [
  "jinja2-cli>=0.1.0",
]
"""
    )

    admin_utils._ensure_project_dependency(pyproject, "jinja2", ">=3.0.0")

    content = pyproject.read_text()
    assert '"jinja2-cli>=0.1.0",' in content
    assert '"jinja2>=3.0.0",' in content


def test_ensure_route_registrar_single_line_empty_tuple_uses_valid_tuple_syntax(
    tmp_path: Path,
) -> None:
    server_file = tmp_path / "server.py"
    server_file.write_text(
        """def create_app():
    app = factory(route_registrars=())
"""
    )

    inserted = admin_utils._ensure_route_registrar(
        server_file,
        "adminpanel.register",
    )

    assert inserted is True
    assert "route_registrars=(adminpanel.register,)" in server_file.read_text()


def test_ensure_dependency_does_not_skip_on_substring_match(
    tmp_path: Path,
) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """[project]
dependencies = [
  "openpyxl-helper>=0.1.0",
]
"""
    )

    admin_utils._ensure_dependency(pyproject, "uv", "openpyxl", ">=3.0.0")

    content = pyproject.read_text()
    assert '"openpyxl-helper>=0.1.0",' in content
    assert '"openpyxl>=3.0.0",' in content


def test_render_template_file_uses_jinja2_strict_undefined(
    tmp_path: Path,
) -> None:
    source = tmp_path / "snippet.py.jinja2"
    target = tmp_path / "snippet.py"
    source.write_text("value={{ missing_key }}")

    with pytest.raises(UndefinedError):
        admin_utils._render_template_file(source, target, {})

    assert not target.exists()


def test_copy_template_tree_selects_sqlalchemy_variant_and_strips_suffix(
    tmp_path: Path,
) -> None:
    template_root = tmp_path / "template"
    target_root = tmp_path / "generated"
    template_root.mkdir()
    (template_root / "models_sqlalchemy.py").write_text("sqlalchemy")
    (template_root / "models_tortoise.py").write_text("tortoise")
    (template_root / "shared.py").write_text("shared")

    created = admin_utils._copy_template_tree(
        template_root,
        target_root,
        tmp_path,
        "sqlalchemy",
    )

    assert (target_root / "models.py").read_text() == "sqlalchemy"
    assert not (target_root / "models_sqlalchemy.py").exists()
    assert not (target_root / "models_tortoise.py").exists()
    assert (target_root / "shared.py").read_text() == "shared"
    assert "generated/models.py" in created
    assert "generated/shared.py" in created


def test_render_template_tree_selects_tortoise_variant_and_strips_suffix(
    tmp_path: Path,
) -> None:
    template_root = tmp_path / "template"
    target_root = tmp_path / "generated"
    template_root.mkdir()
    (template_root / "auth_tortoise.py.jinja2").write_text(
        "value={{ admin_username }}"
    )
    (template_root / "auth_sqlalchemy.py.jinja2").write_text("ignored")

    created = admin_utils._render_template_tree(
        template_root,
        target_root,
        {
            "orm": "tortoise",
            "admin_username": "root",
            "admin_password": "secret",
            "design": "mvc",
        },
        tmp_path,
    )

    assert (target_root / "auth.py").read_text() == "value=root"
    assert not (target_root / "auth_tortoise.py").exists()
    assert not (target_root / "auth_sqlalchemy.py").exists()
    assert "generated/auth.py" in created


def test_copy_template_tree_filters_orm_adapter_files_by_selected_orm(
    tmp_path: Path,
) -> None:
    template_root = tmp_path / "template"
    target_root = tmp_path / "generated"
    orm_dir = template_root / "orm"
    orm_dir.mkdir(parents=True)
    (orm_dir / "base.py").write_text("base")
    (orm_dir / "sqlalchemy.py").write_text("sqlalchemy")
    (orm_dir / "tortoise.py").write_text("tortoise")

    created = admin_utils._copy_template_tree(
        template_root,
        target_root,
        tmp_path,
        "sqlalchemy",
    )

    assert (target_root / "orm" / "base.py").read_text() == "base"
    assert (target_root / "orm" / "sqlalchemy.py").read_text() == "sqlalchemy"
    assert not (target_root / "orm" / "tortoise.py").exists()
    assert "generated/orm/base.py" in created
    assert "generated/orm/sqlalchemy.py" in created


def test_copy_template_tree_filters_sqlalchemy_admin_internal_files(
    tmp_path: Path,
) -> None:
    template_root = tmp_path / "template"
    target_root = tmp_path / "generated"
    admin_dir = template_root / "core" / "admin"
    admin_dir.mkdir(parents=True)
    (admin_dir / "helpers.py").write_text("helpers")
    (admin_dir / "queryset.py").write_text("queryset")
    (admin_dir / "base.py").write_text("base")

    created = admin_utils._copy_template_tree(
        template_root,
        target_root,
        tmp_path,
        "tortoise",
    )

    assert not (target_root / "core" / "admin" / "helpers.py").exists()
    assert not (target_root / "core" / "admin" / "queryset.py").exists()
    assert (target_root / "core" / "admin" / "base.py").read_text() == "base"
    assert "generated/core/admin/base.py" in created


def test_repair_sqlalchemy_adminpanel_imports_maps_to_shared_modules(
    tmp_path: Path,
) -> None:
    target_root = tmp_path / "adminpanel"
    target_root.mkdir()
    init_file = target_root / "__init__.py"
    init_file.write_text(
        "from .auth_models_sqlalchemy import AdminUser, Role, UserRole\n"
    )

    repaired = admin_utils._repair_sqlalchemy_adminpanel_imports(target_root)

    assert repaired is True
    assert (
        init_file.read_text()
        == "from .auth_models import AdminUser, Role, UserRole\n"
    )
