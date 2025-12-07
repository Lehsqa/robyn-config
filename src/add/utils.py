"""Utility functions for the 'add' command."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:
    import tomli as tomllib

from jinja2 import Environment, StrictUndefined

ADD_MODULE_ROOT = Path(__file__).resolve().parent
JINJA_ENV = Environment(undefined=StrictUndefined)


def _normalize_entity_name(name: str) -> tuple[str, str]:
    """Normalize entity name to snake_case and PascalCase variants."""
    normalized = name.lower().replace("-", "_").replace(" ", "_")
    capitalized = "".join(word.capitalize() for word in normalized.split("_"))
    return normalized, capitalized


def _format_comment(comment: str) -> str:
    """Normalize inline comment formatting (adds leading space and #)."""
    if not comment:
        return ""

    cleaned = comment.strip()
    if not cleaned.startswith("#"):
        cleaned = f"# {cleaned}"
    return f" {cleaned}"


def read_project_config(project_path: Path) -> dict[str, Any]:
    """Read pyproject.toml and extract [tool.robyn-config] section."""
    pyproject_path = project_path / "pyproject.toml"

    if not pyproject_path.exists():
        raise FileNotFoundError(
            f"pyproject.toml not found in {project_path}. "
            "Make sure you're in a robyn-config project directory."
        )

    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)

    robyn_config = data.get("tool", {}).get("robyn-config", {})
    if not robyn_config:
        raise ValueError(
            "No [tool.robyn-config] section found in pyproject.toml. "
            "This project was not created with robyn-config."
        )

    return robyn_config


def validate_project(project_path: Path) -> tuple[str, str]:
    """Validate project has robyn-config metadata and return (design, orm)."""
    config = read_project_config(project_path)

    design = config.get("design")
    orm = config.get("orm")

    if not design or not orm:
        raise ValueError(
            "Invalid [tool.robyn-config] section. "
            "Missing 'design' or 'orm' fields."
        )

    return design, orm


def _render_template_file(
    source: Path, target: Path, context: dict[str, str]
) -> None:
    """Render a Jinja2 template file to target location."""
    template_content = source.read_text()
    template = JINJA_ENV.from_string(template_content)
    rendered = template.render(**context)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(rendered)


def _render_template_string(template_str: str, context: dict[str, str]) -> str:
    """Render a Jinja2 template string."""
    template = JINJA_ENV.from_string(template_str)
    return template.render(**context)


def _render_templates_from_directory(
    template_dir: Path,
    target_dir: Path,
    context: dict[str, str],
    project_root: Path,
    created_files: list[str],
) -> None:
    """Render all Jinja2 templates in a directory to the target directory."""
    for template_file in template_dir.glob("*.jinja2"):
        target_path = target_dir / template_file.stem
        _render_template_file(template_file, target_path, context)
        created_files.append(str(target_path.relative_to(project_root)))


def _update_init_file(
    init_path: Path, import_line: str, export_name: str
) -> None:
    """Add import (and optionally __all__ export) to a module file."""
    init_path.parent.mkdir(parents=True, exist_ok=True)
    content = init_path.read_text() if init_path.exists() else ""

    if import_line not in content:
        lines = content.split("\n") if content else []
        insert_pos = 0
        for i, line in enumerate(lines):
            if line.startswith("from ") or line.startswith("import "):
                insert_pos = i + 1
        lines.insert(insert_pos, import_line)
        content = "\n".join(lines)
        init_path.write_text(content)

    if export_name:
        content = init_path.read_text()
        if "__all__" in content:
            _add_to_all_list(init_path, export_name)
        else:
            suffix = f'\n__all__ = (\n    "{export_name}",\n)\n'
            if content and not content.endswith("\n"):
                suffix = "\n" + suffix.lstrip("\n")
            init_path.write_text(f"{content}{suffix}")


def _find_closing_parenthesis(lines: list[str], start_index: int) -> int:
    """Locate the index of the closing parenthesis in a multiline import."""
    for idx in range(start_index, len(lines)):
        if ")" in lines[idx]:
            return idx
    return len(lines)


def _detect_indent(lines: list[str], closing_index: int) -> str:
    """Detect indentation level for items inside a multiline import."""
    if closing_index >= len(lines):
        return "    "

    closing_line = lines[closing_index]
    match = re.match(r"(\s*)\)", closing_line)
    if match:
        return match.group(1) or "    "

    match = re.match(r"(\s*)", closing_line)
    return (match.group(1) if match else "") or "    "


def _append_inline_paren_import(
    line: str, import_item: str, trailing_comment: str
) -> str:
    """Append an import item to a single-line parenthesized import."""
    comment = ""
    base_line = line
    if "#" in line:
        base_line, existing_comment = line.split("#", 1)
        comment = "  #" + existing_comment

    before_paren, after_paren = base_line.split("(", 1)
    inside, after = after_paren.split(")", 1)
    inside = inside.strip()
    updated_inside = f"{inside}, {import_item}" if inside else f"{import_item}"
    comment = comment or _format_comment(trailing_comment)
    return f"{before_paren}({updated_inside}){after}{comment}"


def _ensure_import_from(
    file_path: Path,
    module: str,
    import_item: str,
    *,
    trailing_comment: str = "",
) -> None:
    """Ensure `from {module} import {import_item}` exists in file_path."""
    formatted_comment = _format_comment(trailing_comment)

    if not file_path.exists():
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(
            f"from {module} import {import_item}{formatted_comment}\n"
        )
        return

    lines = file_path.read_text().split("\n")
    prefix = f"from {module} import "

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith(prefix):
            continue

        if "(" in stripped and ")" in stripped:
            inside = stripped.split("(", 1)[1].rsplit(")", 1)[0]
            if re.search(rf"\b{re.escape(import_item)}\b", inside):
                return
            lines[i] = _append_inline_paren_import(
                line, import_item, trailing_comment
            )
            file_path.write_text("\n".join(lines))
            return

        if "(" in stripped:
            closing_index = _find_closing_parenthesis(lines, i)
            block = "\n".join(lines[i : closing_index + 1])
            if re.search(rf"\b{re.escape(import_item)}\b", block):
                return
            indent = _detect_indent(lines, closing_index)
            lines.insert(closing_index, f"{indent}{import_item},")
            file_path.write_text("\n".join(lines))
            return

        if re.search(rf"\b{re.escape(import_item)}\b", stripped):
            return

        comment = ""
        if "#" in line:
            base, existing_comment = line.split("#", 1)
            line = base.rstrip()
            comment = "  #" + existing_comment
        elif formatted_comment:
            comment = formatted_comment

        lines[i] = f"{line.rstrip()}, {import_item}{comment}"
        file_path.write_text("\n".join(lines))
        return

    insert_pos = 0
    for i, line in enumerate(lines):
        if line.startswith("from ") or line.startswith("import "):
            insert_pos = i + 1
    lines.insert(insert_pos, f"{prefix}{import_item}{formatted_comment}")
    file_path.write_text("\n".join(lines))


def _ensure_register_call(target_file: Path, register_call: str) -> None:
    """Ensure register(app) call is present after existing registrations."""
    if not target_file.exists():
        return

    lines = target_file.read_text().split("\n")
    stripped_call = register_call.strip()
    if stripped_call in (line.strip() for line in lines):
        return

    inserted = False
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip().endswith(".register(app)"):
            lines.insert(i + 1, register_call)
            inserted = True
            break

    if inserted:
        target_file.write_text("\n".join(lines))


def _add_table_to_tables_py(
    tables_path: Path,
    name: str,
    name_capitalized: str,
    orm: str,
    context: dict[str, str],
) -> None:
    """Add table class to tables.py file."""
    if not tables_path.exists():
        return

    content = tables_path.read_text()
    table_class_name = f"{name_capitalized}Table"

    # Check if table already exists
    if table_class_name in content:
        return

    # Get the table template
    template_file = (
        ADD_MODULE_ROOT
        / "ddd"
        / "infrastructure"
        / orm
        / "__name___table.py.jinja2"
    )
    if not template_file.exists():
        return

    template_content = template_file.read_text()
    # Extract just the class definition (skip imports)
    lines = template_content.split("\n")
    class_start = None
    for i, line in enumerate(lines):
        if line.startswith("class "):
            class_start = i
            break

    if class_start is not None:
        class_definition = "\n".join(lines[class_start:])
        rendered_class = _render_template_string(class_definition, context)

        # Add to end of file
        if not content.endswith("\n"):
            content += "\n"
        content += f"\n\n{rendered_class}\n"
        tables_path.write_text(content)

        # Update __all__ if it exists
        if "__all__" in content:
            # Use regex to add to __all__ tuple
            content = tables_path.read_text()
            all_pattern = r"(__all__\s*=\s*\(\s*)(.*?)(\s*\))"
            match = re.search(all_pattern, content, re.DOTALL)
            if match:
                current_items = match.group(2).strip()
                if current_items.endswith(","):
                    new_items = f'{current_items}\n    "{table_class_name}",'
                else:
                    new_items = f'{current_items},\n    "{table_class_name}",'
                new_all = f"{match.group(1)}{new_items}{match.group(3)}"
                content = (
                    content[: match.start()] + new_all + content[match.end() :]
                )
                tables_path.write_text(content)


def _register_routes_ddd(app_path: Path, name: str) -> None:
    """Register routes in DDD presentation/__init__.py."""
    pres_init = app_path / "presentation" / "__init__.py"
    if not pres_init.exists():
        return

    _ensure_import_from(pres_init, ".", name)
    _ensure_register_call(pres_init, f"    {name}.register(app)")


def _register_routes_mvc(app_path: Path, name: str) -> None:
    """Register routes in MVC urls.py."""
    urls_path = app_path / "urls.py"
    if not urls_path.exists():
        return

    _ensure_import_from(urls_path, ".views", name)
    _ensure_register_call(urls_path, f"    {name}.register(app)")


def _add_ddd_templates(
    project_path: Path, name: str, name_capitalized: str, orm: str
) -> list[str]:
    """Add DDD templates to the project."""
    app_path = project_path / "src" / "app"
    templates_path = ADD_MODULE_ROOT / "ddd"
    created_files = []

    context = {
        "name": name,
        "Name": name_capitalized,
        "orm": orm,
    }

    # Domain layer
    domain_dir = app_path / "domain" / name
    domain_templates = templates_path / "domain" / "__name__"
    _render_templates_from_directory(
        domain_templates, domain_dir, context, project_path, created_files
    )

    # Update domain __init__.py
    domain_init = app_path / "domain" / "__init__.py"
    _ensure_import_from(
        domain_init, ".", name, trailing_comment="# noqa: F401"
    )

    # Add table to tables.py
    tables_path = app_path / "infrastructure" / "database" / "tables.py"
    _add_table_to_tables_py(tables_path, name, name_capitalized, orm, context)

    # Infrastructure repository
    repo_template = (
        templates_path
        / "infrastructure"
        / orm
        / "repository"
        / "__name__.py.jinja2"
    )
    if repo_template.exists():
        repo_target = (
            app_path
            / "infrastructure"
            / "database"
            / "repository"
            / f"{name}.py"
        )
        _render_template_file(repo_template, repo_target, context)
        created_files.append(str(repo_target.relative_to(project_path)))

        # Update repository __init__.py
        repo_init = (
            app_path
            / "infrastructure"
            / "database"
            / "repository"
            / "__init__.py"
        )
        _update_init_file(
            repo_init,
            f"from .{name} import {name_capitalized}Repository  # noqa: F401",
            f"{name_capitalized}Repository",
        )

    # Operational layer
    ops_template = templates_path / "operational" / "__name__.py.jinja2"
    if ops_template.exists():
        ops_target = app_path / "operational" / f"{name}.py"
        _render_template_file(ops_template, ops_target, context)
        created_files.append(str(ops_target.relative_to(project_path)))

        # Update operational __init__.py
        ops_init = app_path / "operational" / "__init__.py"
        _ensure_import_from(
            ops_init, ".", name, trailing_comment="# noqa: F401"
        )

    # Presentation layer
    pres_dir = app_path / "presentation" / name
    pres_templates = templates_path / "presentation" / "__name__"
    _render_templates_from_directory(
        pres_templates, pres_dir, context, project_path, created_files
    )

    # Auto-register routes in presentation/__init__.py
    _register_routes_ddd(app_path, name)

    return created_files


def _append_class_to_file(
    file_path: Path,
    template_path: Path,
    context: dict[str, str],
    class_name: str,
) -> None:
    """Append a class definition from a template to a file if it doesn't exist."""
    if not file_path.exists() or not template_path.exists():
        return

    content = file_path.read_text()
    if class_name in content:
        return

    class_def = _render_template_string(template_path.read_text(), context)

    if not content.endswith("\n"):
        content += "\n"
    content += f"\n{class_def}\n"
    file_path.write_text(content)


def _add_to_all_list(file_path: Path, item_name: str) -> None:
    """Add an item to the __all__ tuple in a file."""
    if not file_path.exists():
        return

    content = file_path.read_text()
    all_pattern = r"(__all__\s*=\s*\(\s*)(.*?)(\s*\))"
    match = re.search(all_pattern, content, re.DOTALL)
    if match and item_name not in match.group(2):
        current_items = match.group(2).strip()
        if current_items and not current_items.endswith(","):
            new_items = f'{current_items},\n    "{item_name}",'
        else:
            new_items = f'{current_items}\n    "{item_name}",'
        new_all = f"{match.group(1)}{new_items}{match.group(3)}"
        content = content[: match.start()] + new_all + content[match.end() :]
        file_path.write_text(content)


def _add_mvc_templates(
    project_path: Path, name: str, name_capitalized: str, orm: str
) -> list[str]:
    """Add MVC templates to the project."""
    app_path = project_path / "src" / "app"
    templates_path = ADD_MODULE_ROOT / "mvc"
    created_files = []

    context = {
        "name": name,
        "Name": name_capitalized,
        "orm": orm,
    }

    # Models layer - Append to existing files
    models_file = app_path / "models" / "models.py"
    repo_file = app_path / "models" / "repository.py"

    # 1. Append Table to models.py
    table_template = templates_path / "models" / orm / "table.py.jinja2"
    table_class = f"{name_capitalized}Table"
    if models_file.exists() and table_template.exists():
        _append_class_to_file(
            models_file, table_template, context, table_class
        )
        _add_to_all_list(models_file, table_class)
        created_files.append(str(models_file.relative_to(project_path)))

    # 2. Append Repository to repository.py
    repo_template = templates_path / "models" / orm / "repository.py.jinja2"
    repo_class = f"{name_capitalized}Repository"
    if repo_file.exists() and repo_template.exists():
        _ensure_import_from(repo_file, ".models", table_class)

        _append_class_to_file(repo_file, repo_template, context, repo_class)
        created_files.append(str(repo_file.relative_to(project_path)))

        # Update models __init__.py to export Repository
        models_init = app_path / "models" / "__init__.py"
        _update_init_file(
            models_init,
            f"from .repository import {repo_class}  # noqa: F401",
            repo_class,
        )

    # Views layer
    views_template = templates_path / "views" / "__name__.py.jinja2"
    if views_template.exists():
        views_target = app_path / "views" / f"{name}.py"
        _render_template_file(views_template, views_target, context)
        created_files.append(str(views_target.relative_to(project_path)))

        # Update views __init__.py
        views_init = app_path / "views" / "__init__.py"
        _update_init_file(
            views_init,
            f"from .{name} import register as register_{name}  # noqa: F401",
            f"register_{name}",
        )

    # Auto-register routes in urls.py
    _register_routes_mvc(app_path, name)

    return created_files


def add_business_logic(project_path: Path, name: str) -> list[str]:
    """Add business logic templates to an existing project."""
    design, orm = validate_project(project_path)

    name_lower, name_capitalized = _normalize_entity_name(name)

    if design == "ddd":
        return _add_ddd_templates(
            project_path, name_lower, name_capitalized, orm
        )
    elif design == "mvc":
        return _add_mvc_templates(
            project_path, name_lower, name_capitalized, orm
        )
    else:
        raise ValueError(f"Unsupported design pattern: {design}")
