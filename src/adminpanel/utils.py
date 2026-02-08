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

ADMIN_DEPENDENCIES: tuple[tuple[str, str], ...] = (
    ("jinja2", ">=3.0.0"),
    ("aiosqlite", ">=0.17.0"),
    ("pandas", ">=1.0.0"),
    ("openpyxl", ">=3.0.0"),
)

SUPPORTED_DESIGNS = ("ddd", "mvc")
SUPPORTED_ORM = "tortoise"

DDD_APP_PANEL_TEMPLATE = """\
from __future__ import annotations

from robyn import Robyn

from app.infrastructure import adminpanel as adminpanel_module


def register(app: Robyn) -> None:
    adminpanel_module.register(app)
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


def _ensure_call_before_main_guard(
    file_path: Path, call_line: str
) -> None:
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


def _ensure_route_registrar(
    file_path: Path, registrar: str
) -> bool:
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
            suffix = ")," if line.rstrip().endswith("),") else ")"
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

        if any(
            registrar in lines[j]
            for j in range(start_idx + 1, end_idx)
        ):
            return True

        indent = None
        for j in range(start_idx + 1, end_idx):
            if lines[j].strip():
                indent = re.match(r"(\s*)", lines[j]).group(1)
                break
        if indent is None:
            indent = (
                re.match(r"(\s*)", lines[start_idx]).group(1) + "    "
            )

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
    if orm != SUPPORTED_ORM:
        raise ValueError(
            "Admin panel scaffolding requires a Tortoise ORM project."
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
        TEMPLATE_ROOT, target_root, {"design": design}, project_path
    )

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
        inserted = _ensure_route_registrar(
            server_path, "adminpanel.register"
        )
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
        _ensure_dependency(pyproject_path, package_manager, dependency, version)

    return created_files
