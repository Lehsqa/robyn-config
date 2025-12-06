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


def _update_init_file(
    init_path: Path, import_line: str, export_name: str
) -> None:
    """Add import and export to an __init__.py file."""
    if not init_path.exists():
        init_path.parent.mkdir(parents=True, exist_ok=True)
        init_path.write_text(f"{import_line}\n")
        return

    content = init_path.read_text()

    # Add import if not present
    if import_line not in content:
        lines = content.split("\n")
        # Find position after existing imports
        insert_pos = 0
        for i, line in enumerate(lines):
            if line.startswith("from ") or line.startswith("import "):
                insert_pos = i + 1
        lines.insert(insert_pos, import_line)
        content = "\n".join(lines)
        init_path.write_text(content)


def _append_to_from_import(init_path: Path, module_name: str) -> None:
    """Append a module to an existing 'from . import ...' line or tuple."""
    if not init_path.exists():
        init_path.parent.mkdir(parents=True, exist_ok=True)
        init_path.write_text(f"from . import {module_name}  # noqa: F401\n")
        return

    content = init_path.read_text()

    # Check if module already imported
    if re.search(rf"\b{module_name}\b", content):
        return

    lines = content.split("\n")
    updated = False

    # First, check for tuple-style import: from . import (...)
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("from . import ("):
            # Find the closing parenthesis
            for j in range(i, len(lines)):
                if ")" in lines[j]:
                    # Insert before the closing paren
                    closing_line = lines[j]
                    indent = "    "  # Standard indent
                    # Insert new module before the closing paren
                    paren_pos = closing_line.find(")")
                    before_paren = closing_line[:paren_pos].rstrip()
                    after_paren = closing_line[paren_pos:]

                    if before_paren.strip():
                        # There's content on the same line as )
                        lines[j] = (
                            f"{before_paren},\n{indent}{module_name},  # noqa: F401\n{after_paren}"
                        )
                    else:
                        # ) is on its own line or with just whitespace
                        lines.insert(
                            j, f"{indent}{module_name},  # noqa: F401"
                        )
                    updated = True
                    break
            break
        # Check for single-line from . import
        elif stripped.startswith("from . import ") and "(" not in stripped:
            # Single line import, append to it
            comment = ""
            if "#" in line:
                line_parts = line.split("#", 1)
                line = line_parts[0].rstrip()
                comment = "  #" + line_parts[1]

            lines[i] = f"{line}, {module_name}{comment}"
            updated = True
            break

    if not updated:
        # No existing from . import line, add new one
        insert_pos = 0
        for i, line in enumerate(lines):
            if line.startswith("from ") or line.startswith("import "):
                insert_pos = i + 1
        lines.insert(insert_pos, f"from . import {module_name}  # noqa: F401")

    content = "\n".join(lines)
    init_path.write_text(content)


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
        / f"__name___table.py.jinja2"
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


def _register_routes_ddd(
    app_path: Path, name: str, name_capitalized: str
) -> None:
    """Register routes in DDD presentation/__init__.py."""
    pres_init = app_path / "presentation" / "__init__.py"
    if not pres_init.exists():
        return

    content = pres_init.read_text()

    # Add import
    import_line = f"from . import {name}"
    if import_line not in content:
        # Find existing imports from . import ...
        lines = content.split("\n")
        insert_pos = 0
        for i, line in enumerate(lines):
            if line.startswith("from . import ") or line.startswith("from ."):
                insert_pos = i + 1
        lines.insert(insert_pos, import_line)
        content = "\n".join(lines)

    # Add route registration call
    register_call = f"    {name}.register(app)"
    if register_call not in content:
        # Find register_routes function and add before the last line
        lines = content.split("\n")
        for i in range(len(lines) - 1, -1, -1):
            line = lines[i].strip()
            if line and line.endswith(".register(app)"):
                lines.insert(i + 1, register_call)
                break
        content = "\n".join(lines)

    pres_init.write_text(content)


def _register_routes_mvc(
    app_path: Path, name: str, name_capitalized: str
) -> None:
    """Register routes in MVC urls.py."""
    urls_path = app_path / "urls.py"
    if not urls_path.exists():
        return

    content = urls_path.read_text()

    # Add import
    import_line = f"from .views import {name}"
    if import_line not in content and f", {name}" not in content:
        # Check if there's already a grouped import we can extend
        lines = content.split("\n")
        updated = False
        for i, line in enumerate(lines):
            if line.startswith("from .views import "):
                # Append to existing import
                if line.rstrip().endswith(")"):
                    # Multi-line import, find the closing paren
                    pass
                else:
                    lines[i] = line.rstrip() + f", {name}"
                    updated = True
                    break

        if not updated:
            # Add new import line
            insert_pos = 0
            for i, line in enumerate(lines):
                if line.startswith("from ") or line.startswith("import "):
                    insert_pos = i + 1
            lines.insert(insert_pos, import_line)

        content = "\n".join(lines)

    # Add route registration call
    register_call = f"    {name}.register(app)"
    if register_call not in content:
        lines = content.split("\n")
        for i in range(len(lines) - 1, -1, -1):
            line = lines[i].strip()
            if line and line.endswith(".register(app)"):
                lines.insert(i + 1, register_call)
                break
        content = "\n".join(lines)

    urls_path.write_text(content)


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
    for template_file in domain_templates.glob("*.jinja2"):
        target_name = template_file.stem  # removes .jinja2
        target_path = domain_dir / target_name
        _render_template_file(template_file, target_path, context)
        created_files.append(str(target_path.relative_to(project_path)))

    # Update domain __init__.py
    domain_init = app_path / "domain" / "__init__.py"
    _append_to_from_import(domain_init, name)

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
        _append_to_from_import(ops_init, name)

    # Presentation layer
    pres_dir = app_path / "presentation" / name
    pres_templates = templates_path / "presentation" / "__name__"
    for template_file in pres_templates.glob("*.jinja2"):
        target_name = template_file.stem  # removes .jinja2
        target_path = pres_dir / target_name
        _render_template_file(template_file, target_path, context)
        created_files.append(str(target_path.relative_to(project_path)))

    # Auto-register routes in presentation/__init__.py
    _register_routes_ddd(app_path, name, name_capitalized)

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


def _ensure_import_from(
    file_path: Path, module: str, import_item: str
) -> None:
    """Ensure a specific item is imported from a module in a file."""
    if not file_path.exists():
        return

    content = file_path.read_text()
    if import_item in content:
        return

    lines = content.split("\n")
    updated = False

    # Check for existing import from that module
    prefix = f"from {module} import "
    for i, line in enumerate(lines):
        if line.startswith(prefix):
            # Append to existing import
            if "(" in line and ")" not in line:
                # Multiline import - complicated, for now assume simplistic
                pass
            else:
                # Single line or simple multiline start
                # Just append to the end of the line (before comment)
                comment = ""
                clean_line = line
                if "#" in line:
                    parts = line.split("#", 1)
                    clean_line = parts[0].rstrip()
                    comment = "  #" + parts[1]

                lines[i] = f"{clean_line}, {import_item}{comment}"
                updated = True
                break

    if not updated:
        # Add new import
        insert_pos = 0
        for i, line in enumerate(lines):
            if line.startswith("from ") or line.startswith("import "):
                insert_pos = i + 1
        lines.insert(insert_pos, f"{prefix}{import_item}")

    file_path.write_text("\n".join(lines))


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
        # Ensure Table is imported in repository.py
        _update_init_file(
            repo_file,
            import_line=f"from .models import {table_class}",
            export_name="",
        )  # abusing _update_init_file for import injection

        # We need to manually fix import injection since _update_init_file is simple.
        # Let's inspect repository.py content and inject generic import if missing.
        repo_content = repo_file.read_text()
        if (
            f"from .models import" in repo_content
            and table_class not in repo_content
        ):
            # Just appending the class logic below handles the code, but imports need care.
            # _append_to_from_import handles 'from . import ...' but we need 'from .models import ...'
            pass

        # Using a custom import injector for repository.py
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
    _register_routes_mvc(app_path, name, name_capitalized)

    return created_files


def add_business_logic(project_path: Path, name: str) -> list[str]:
    """Add business logic templates to an existing project."""
    design, orm = validate_project(project_path)

    # Normalize name
    name_lower = name.lower().replace("-", "_").replace(" ", "_")
    name_capitalized = "".join(
        word.capitalize() for word in name_lower.split("_")
    )

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
