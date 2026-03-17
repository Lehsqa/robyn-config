"""Code injection utilities for the 'add' command."""

from __future__ import annotations

import re
from pathlib import Path

from ._entity import _format_comment
from ._templates import _render_template_string

ADD_MODULE_ROOT = Path(__file__).resolve().parent.parent


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


def _add_table_to_module_package(
    tables_init_path: Path,
    template_file: Path,
    module_name: str,
    table_class_name: str,
    context: dict[str, str],
) -> Path | None:
    """Create tables/<module_name>.py and export class from tables/__init__.py."""
    from ._templates import _render_template_file

    if not tables_init_path.exists() or tables_init_path.name != "__init__.py":
        return None
    if not template_file.exists():
        return None

    table_module_file = tables_init_path.parent / f"{module_name}.py"
    if table_module_file.exists():
        _update_init_file(
            tables_init_path,
            f"from .{module_name} import {table_class_name}",
            table_class_name,
        )
        return None

    _render_template_file(template_file, table_module_file, context)
    _update_init_file(
        tables_init_path,
        f"from .{module_name} import {table_class_name}",
        table_class_name,
    )
    return table_module_file


def _register_routes_ddd(presentation_path: Path, name: str) -> None:
    """Register routes in DDD presentation/__init__.py."""
    pres_init = presentation_path / "__init__.py"
    if not pres_init.exists():
        return

    _ensure_import_from(pres_init, ".", name)
    _ensure_register_call(pres_init, f"    {name}.register(app)")


def _register_routes_mvc(urls_path: Path, name: str) -> None:
    """Register routes in MVC urls.py."""
    if not urls_path.exists():
        return

    _ensure_import_from(urls_path, ".views", name)
    _ensure_register_call(urls_path, f"    {name}.register(app)")


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
