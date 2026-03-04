"""Utility functions for the 'adminpanel' command."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Mapping

from jinja2 import Environment, StrictUndefined

from add import read_project_config, validate_project
from add.utils import _ensure_import_from

ADMINPANEL_ROOT = Path(__file__).resolve().parent
JINJA_ENV = Environment(undefined=StrictUndefined)

TEMPLATE_ROOT = ADMINPANEL_ROOT / "template"

LEGACY_DDD_DB_TABLE_PATH = Path("src/app/infrastructure/database/tables.py")
DEFAULT_DDD_DB_TABLE_PATH = Path(
    "src/app/infrastructure/database/table/__init__.py"
)
LEGACY_MVC_DB_TABLE_PATH = Path("src/app/models/models.py")
DEFAULT_MVC_DB_TABLE_PATH = Path("src/app/models/table/__init__.py")

ADMIN_DEPENDENCIES: tuple[tuple[str, str], ...] = (
    ("jinja2", ">=3.0.0"),
    ("aiosqlite", ">=0.17.0"),
    ("pandas", ">=1.0.0"),
    ("openpyxl", ">=3.0.0"),
)

SUPPORTED_DESIGNS = ("ddd", "mvc")
SUPPORTED_ORMS = ("tortoise", "sqlalchemy")

DDD_APP_PANEL_TEMPLATE = """\
from __future__ import annotations

from robyn import Robyn

from app.infrastructure import adminpanel as adminpanel_module


def register(app: Robyn) -> None:
    adminpanel_module.register(app)
"""

SQLALCHEMY_ADMIN_TABLES_SNIPPET = """\
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from .authentication import UsersTable
from .base import Base


class Role(Base):
    __tablename__ = "robyn_admin_roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    accessible_models: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.CURRENT_TIMESTAMP(),
    )


class UserRole(Base):
    __tablename__ = "robyn_admin_user_roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(f"{UsersTable.__tablename__}.id", ondelete="CASCADE"),
        index=True,
    )
    role_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("robyn_admin_roles.id", ondelete="CASCADE"),
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.CURRENT_TIMESTAMP(),
    )
"""

TORTOISE_ADMIN_TABLES_SNIPPET = """\
from __future__ import annotations

from tortoise import fields

from .base import BaseTable


class Role(BaseTable):
    name = fields.CharField(max_length=150, unique=True)
    description = fields.CharField(max_length=200, null=True)
    accessible_models = fields.JSONField(default=list)

    class Meta:
        table = "robyn_admin_roles"
        ordering = ("id",)


class UserRole(BaseTable):
    user = fields.ForeignKeyField("models.UsersTable", related_name="user_roles")
    role = fields.ForeignKeyField("models.Role", related_name="role_users")

    class Meta:
        table = "robyn_admin_user_roles"
        ordering = ("id",)
"""

SQLALCHEMY_ADMIN_TABLES_LEGACY_SNIPPET = """\
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column


class Role(Base):
    __tablename__ = "robyn_admin_roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    accessible_models: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.CURRENT_TIMESTAMP(),
    )


class UserRole(Base):
    __tablename__ = "robyn_admin_user_roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    role_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("robyn_admin_roles.id", ondelete="CASCADE"),
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.CURRENT_TIMESTAMP(),
    )
"""

TORTOISE_ADMIN_TABLES_LEGACY_SNIPPET = """\
from __future__ import annotations

from tortoise import fields


class Role(BaseTable):
    name = fields.CharField(max_length=150, unique=True)
    description = fields.CharField(max_length=200, null=True)
    accessible_models = fields.JSONField(default=list)

    class Meta:
        table = "robyn_admin_roles"
        ordering = ("id",)


class UserRole(BaseTable):
    user = fields.ForeignKeyField("models.UsersTable", related_name="user_roles")
    role = fields.ForeignKeyField("models.Role", related_name="role_users")

    class Meta:
        table = "robyn_admin_user_roles"
        ordering = ("id",)
"""


def _render_template_file(
    source: Path, target: Path, context: Mapping[str, str]
) -> bool:
    """Render a Jinja2 template file to target location if missing."""
    if target.exists():
        return False
    template_content = source.read_text()
    template = JINJA_ENV.from_string(template_content)
    rendered = template.render(**context)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(rendered)
    return True


def _render_template_tree(
    template_root: Path,
    target_root: Path,
    context: Mapping[str, str],
    project_root: Path,
) -> list[str]:
    created_files: list[str] = []
    for template_file in template_root.rglob("*.jinja2"):
        rel_path = template_file.relative_to(template_root)
        if "migrations" in rel_path.parts:
            continue
        target_path = (target_root / rel_path).with_suffix("")
        if _render_template_file(template_file, target_path, context):
            created_files.append(str(target_path.relative_to(project_root)))
    return created_files


def _copy_template_tree(
    template_root: Path, target_root: Path, project_root: Path
) -> list[str]:
    created_files: list[str] = []
    for source in template_root.rglob("*"):
        if "__pycache__" in source.parts:
            continue
        if source.is_dir():
            (target_root / source.relative_to(template_root)).mkdir(
                parents=True, exist_ok=True
            )
            continue
        if source.name == ".DS_Store" or source.suffix == ".jinja2":
            continue
        target = target_root / source.relative_to(template_root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        created_files.append(str(target.relative_to(project_root)))
    return created_files


def _ensure_call_before_main_guard(file_path: Path, call_line: str) -> None:
    if not file_path.exists():
        return

    lines = file_path.read_text().split("\n")
    stripped_call = call_line.strip()
    if any(line.strip() == stripped_call for line in lines):
        return

    for idx, line in enumerate(lines):
        if line.startswith("if __name__") and "__main__" in line:
            lines.insert(idx, call_line)
            if idx + 1 < len(lines) and lines[idx + 1].strip():
                lines.insert(idx + 1, "")
            file_path.write_text("\n".join(lines))
            return

    if lines and lines[-1].strip():
        lines.append("")
    lines.append(call_line)
    file_path.write_text("\n".join(lines))


def _ensure_route_registrar(file_path: Path, registrar: str) -> bool:
    if not file_path.exists():
        return False

    lines = file_path.read_text().split("\n")
    if any(registrar in line for line in lines):
        return True

    for idx, line in enumerate(lines):
        if "route_registrars=" not in line:
            continue

        if "(" in line and ")" in line:
            indent = line.split("route_registrars=")[0]
            inner = line.split("route_registrars=", 1)[1]
            inner = inner[inner.find("(") + 1 : inner.rfind(")")]
            items = [item.strip() for item in inner.split(",") if item.strip()]
            items.append(registrar)
            suffix = "," if line.rstrip().endswith("),") else ""
            lines[idx] = (
                f"{indent}route_registrars=({', '.join(items)}){suffix}"
            )
            file_path.write_text("\n".join(lines))
            return True

        start_idx = idx
        end_idx = None
        for j in range(start_idx + 1, len(lines)):
            if ")" in lines[j]:
                end_idx = j
                break
        if end_idx is None:
            return False

        if any(registrar in lines[j] for j in range(start_idx + 1, end_idx)):
            return True

        indent = None
        for j in range(start_idx + 1, end_idx):
            if lines[j].strip():
                indent = re.match(r"(\s*)", lines[j]).group(1)
                break
        if indent is None:
            indent = re.match(r"(\s*)", lines[start_idx]).group(1) + "    "

        lines.insert(end_idx, f"{indent}{registrar},")
        file_path.write_text("\n".join(lines))
        return True

    return False


def _detect_package_manager(
    config: Mapping[str, str], pyproject_text: str
) -> str:
    configured = config.get("package_manager")
    if configured:
        return configured
    if "[tool.poetry]" in pyproject_text:
        return "poetry"
    return "uv"


def _ensure_poetry_dependency(
    pyproject_path: Path, dependency: str, version_spec: str
) -> None:
    lines = pyproject_path.read_text().split("\n")
    header = "[tool.poetry.dependencies]"
    start_index = None
    end_index = None

    for idx, line in enumerate(lines):
        if line.strip() == header:
            start_index = idx
            continue
        if (
            start_index is not None
            and line.startswith("[")
            and line.strip().endswith("]")
        ):
            end_index = idx
            break

    if start_index is None:
        return
    if end_index is None:
        end_index = len(lines)

    for line in lines[start_index + 1 : end_index]:
        if line.strip().startswith(f"{dependency} "):
            return
        if line.strip().startswith(f"{dependency}="):
            return
        if line.strip().startswith(f"{dependency} ="):
            return

    insert_at = end_index
    for idx in range(start_index + 1, end_index):
        if lines[idx].strip().startswith("python"):
            insert_at = idx + 1
            break

    lines.insert(insert_at, f'{dependency} = "{version_spec}"')
    pyproject_path.write_text("\n".join(lines))


def _ensure_project_dependency(
    pyproject_path: Path, dependency: str, version_spec: str
) -> None:
    lines = pyproject_path.read_text().split("\n")
    start_index = None
    end_index = None

    for idx, line in enumerate(lines):
        if line.strip().startswith("dependencies = ["):
            start_index = idx
            break

    if start_index is None:
        return

    for idx in range(start_index + 1, len(lines)):
        if lines[idx].strip().startswith("]"):
            end_index = idx
            break

    if end_index is None:
        return

    entry_token = f'"{dependency}'
    for line in lines[start_index + 1 : end_index]:
        if entry_token in line:
            return

    indent = "  "
    for idx in range(start_index + 1, end_index):
        if lines[idx].strip():
            match = re.match(r"(\s*)", lines[idx])
            if match:
                indent = match.group(1)
            break

    lines.insert(end_index, f'{indent}"{dependency}{version_spec}",')
    pyproject_path.write_text("\n".join(lines))


def _repair_sqlalchemy_adminpanel_imports(target_root: Path) -> bool:
    init_file = target_root / "__init__.py"
    if not init_file.exists():
        return False

    content = init_file.read_text()
    broken_import = (
        "from .auth_models_sqlalchemy import AdminUser, Role, UserRole"
    )
    fixed_models_import = "from .models_sqlalchemy import AdminUser"
    fixed_auth_import = "from .auth_models_sqlalchemy import Role, UserRole"

    if broken_import not in content:
        return False

    updated = content.replace(
        broken_import,
        f"{fixed_models_import}\n{fixed_auth_import}",
    )
    init_file.write_text(updated)
    return True


def _ensure_dependency(
    pyproject_path: Path, package_manager: str, dependency: str, version: str
) -> None:
    if not pyproject_path.exists():
        return
    text = pyproject_path.read_text()
    if dependency in text:
        return

    if package_manager == "poetry":
        _ensure_poetry_dependency(pyproject_path, dependency, version)
    else:
        _ensure_project_dependency(pyproject_path, dependency, version)


def _resolve_db_tables_path(
    project_path: Path, config: Mapping[str, object], design: str
) -> Path:
    add_config = config.get("add")
    configured_path: str | None = None
    if isinstance(add_config, Mapping):
        raw = add_config.get("database_table_path")
        if isinstance(raw, str) and raw.strip():
            configured_path = raw

    if configured_path:
        return project_path / configured_path

    if design == "ddd":
        preferred = project_path / DEFAULT_DDD_DB_TABLE_PATH
        if preferred.exists():
            return preferred
        legacy = project_path / LEGACY_DDD_DB_TABLE_PATH
        if legacy.exists():
            return legacy
        return preferred

    preferred = project_path / DEFAULT_MVC_DB_TABLE_PATH
    if preferred.exists():
        return preferred
    legacy = project_path / LEGACY_MVC_DB_TABLE_PATH
    if legacy.exists():
        return legacy
    return preferred


def _ensure_symbols_in_all(content: str, symbols: tuple[str, ...]) -> str:
    all_pattern = r"(__all__\s*=\s*\(\s*)(.*?)(\s*\))"
    match = re.search(all_pattern, content, re.DOTALL)
    if not match:
        return content

    current_items = match.group(2)
    missing = [
        symbol
        for symbol in symbols
        if f'"{symbol}"' not in current_items
        and f"'{symbol}'" not in current_items
    ]
    if not missing:
        return content

    updated_items = current_items.rstrip()
    if updated_items and not updated_items.endswith(","):
        updated_items += ","
    for symbol in missing:
        updated_items += f'\n    "{symbol}",'

    updated_all = f"{match.group(1)}{updated_items}{match.group(3)}"
    return content[: match.start()] + updated_all + content[match.end() :]


def _append_admin_models_to_shared_tables(
    project_path: Path,
    config: Mapping[str, object],
    design: str,
    orm: str,
) -> None:
    tables_path = _resolve_db_tables_path(project_path, config, design)
    if not tables_path.exists():
        raise FileNotFoundError(
            f"Database table module not found at {tables_path.as_posix()}"
        )

    package_snippet = (
        SQLALCHEMY_ADMIN_TABLES_SNIPPET
        if orm == "sqlalchemy"
        else TORTOISE_ADMIN_TABLES_SNIPPET
    )
    legacy_snippet = (
        SQLALCHEMY_ADMIN_TABLES_LEGACY_SNIPPET
        if orm == "sqlalchemy"
        else TORTOISE_ADMIN_TABLES_LEGACY_SNIPPET
    )
    symbols = ("Role", "UserRole")

    if tables_path.name == "__init__.py":
        module_file = tables_path.parent / "adminpanel.py"
        if module_file.exists():
            module_content = module_file.read_text()
            if all(f"class {symbol}" in module_content for symbol in symbols):
                _ensure_import_from(tables_path, ".adminpanel", "Role")
                _ensure_import_from(tables_path, ".adminpanel", "UserRole")
                init_content = tables_path.read_text()
                updated_init = _ensure_symbols_in_all(init_content, symbols)
                if updated_init != init_content:
                    tables_path.write_text(updated_init)
                return

        module_file.write_text(package_snippet.rstrip() + "\n")
        _ensure_import_from(tables_path, ".adminpanel", "Role")
        _ensure_import_from(tables_path, ".adminpanel", "UserRole")
        init_content = tables_path.read_text()
        updated_init = _ensure_symbols_in_all(init_content, symbols)
        if updated_init != init_content:
            tables_path.write_text(updated_init)
        return

    # Legacy single-file tables.py/models.py projects.
    content = tables_path.read_text()
    if all(f"class {symbol}" in content for symbol in symbols):
        updated = _ensure_symbols_in_all(content, symbols)
        if updated != content:
            tables_path.write_text(updated)
        return

    updated_content = content.rstrip() + f"\n\n\n{legacy_snippet}\n"
    updated_content = _ensure_symbols_in_all(updated_content, symbols)
    tables_path.write_text(updated_content)


def _ensure_application_adminpanel(project_path: Path) -> None:
    target_path = (
        project_path
        / "src"
        / "app"
        / "infrastructure"
        / "application"
        / "adminpanel.py"
    )
    if target_path.exists():
        return
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(DDD_APP_PANEL_TEMPLATE)


def add_adminpanel(project_path: Path) -> list[str]:
    """Add admin panel scaffolding to an existing robyn-config project."""
    config = read_project_config(project_path)
    design, orm = validate_project(project_path)
    if design not in SUPPORTED_DESIGNS:
        raise ValueError(f"Unsupported design pattern: {design}")
    if orm not in SUPPORTED_ORMS:
        raise ValueError(
            "Admin panel scaffolding requires a supported ORM project."
        )

    if not TEMPLATE_ROOT.exists():
        raise FileNotFoundError("Admin panel template package not found.")

    if design == "ddd":
        target_root = (
            project_path / "src" / "app" / "infrastructure" / "adminpanel"
        )
    else:
        target_root = project_path / "src" / "app" / "adminpanel"
    created_files = _copy_template_tree(
        TEMPLATE_ROOT, target_root, project_path
    )
    created_files += _render_template_tree(
        TEMPLATE_ROOT,
        target_root,
        {"design": design, "orm": orm},
        project_path,
    )

    _append_admin_models_to_shared_tables(
        project_path=project_path,
        config=config,
        design=design,
        orm=orm,
    )

    if orm == "sqlalchemy":
        _repair_sqlalchemy_adminpanel_imports(target_root)

    if design == "ddd":
        infra_dir = project_path / "src" / "app" / "infrastructure"
        init_file = infra_dir / "__init__.py"
        if not init_file.exists():
            init_file.parent.mkdir(parents=True, exist_ok=True)
            init_file.write_text("")
        _ensure_application_adminpanel(project_path)

    server_path = project_path / "src" / "app" / "server.py"
    if not server_path.exists():
        raise FileNotFoundError(
            f"server.py not found at {server_path.as_posix()}"
        )
    if design == "ddd":
        _ensure_import_from(
            server_path,
            "app.infrastructure.application",
            "adminpanel",
        )
        inserted = _ensure_route_registrar(server_path, "adminpanel.register")
        if not inserted:
            _ensure_call_before_main_guard(
                server_path, "adminpanel.register(app)"
            )
    else:
        _ensure_import_from(server_path, "app", "adminpanel")
        _ensure_call_before_main_guard(server_path, "adminpanel.register(app)")

    pyproject_path = project_path / "pyproject.toml"
    package_manager = _detect_package_manager(
        config, pyproject_path.read_text() if pyproject_path.exists() else ""
    )
    for dependency, version in ADMIN_DEPENDENCIES:
        _ensure_dependency(
            pyproject_path, package_manager, dependency, version
        )

    return created_files
