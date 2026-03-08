"""pyproject dependency and metadata helpers for adminpanel scaffolding."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Mapping

from ._constants import SUPPORTED_PACKAGE_MANAGERS


def _detect_package_manager(
    config: Mapping[str, str], pyproject_text: str
) -> str:
    configured_raw = config.get("package_manager")
    configured = (
        configured_raw.strip().lower()
        if isinstance(configured_raw, str)
        else None
    )
    if configured in SUPPORTED_PACKAGE_MANAGERS:
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


def _normalize_dependency_name(package_name: str) -> str:
    return re.sub(r"[-_.]+", "-", package_name).lower()


def _extract_dependency_name_from_project_entry(line: str) -> str | None:
    stripped = line.strip()
    if not stripped:
        return None

    quote_char = stripped[0]
    if quote_char not in {'"', "'"}:
        return None

    end_quote = stripped.find(quote_char, 1)
    if end_quote <= 1:
        return None

    dependency_spec = stripped[1:end_quote]
    match = re.match(r"([A-Za-z0-9][A-Za-z0-9._-]*)", dependency_spec)
    if not match:
        return None
    return match.group(1)


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

    normalized_dependency = _normalize_dependency_name(dependency)
    for line in lines[start_index + 1 : end_index]:
        existing_dependency = _extract_dependency_name_from_project_entry(
            line
        )
        if (
            existing_dependency is not None
            and _normalize_dependency_name(existing_dependency)
            == normalized_dependency
        ):
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

    if package_manager == "poetry":
        _ensure_poetry_dependency(pyproject_path, dependency, version)
    else:
        _ensure_project_dependency(pyproject_path, dependency, version)


def _set_adminpanel_created(pyproject_path: Path) -> None:
    if not pyproject_path.exists():
        return

    lines = pyproject_path.read_text().splitlines()
    add_section_header = "[tool.robyn-config.add]"
    section_header = "[tool.robyn-config.adminpanel]"
    created_line = "created = true"

    def _find_section_bounds(header: str) -> tuple[int, int] | None:
        start = None
        end = len(lines)
        for idx, line in enumerate(lines):
            if line.strip() == header:
                start = idx
                break
        if start is None:
            return None
        for idx in range(start + 1, len(lines)):
            stripped = lines[idx].strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                end = idx
                break
        return (start, end)

    section_bounds = _find_section_bounds(section_header)
    if section_bounds is not None:
        section_start, section_end = section_bounds

        for idx in range(section_start + 1, section_end):
            if lines[idx].strip().startswith("created"):
                lines[idx] = created_line
                pyproject_path.write_text("\n".join(lines) + "\n")
                return

        lines.insert(section_end, created_line)
        pyproject_path.write_text("\n".join(lines) + "\n")
        return

    new_section_lines = [section_header, created_line]
    add_bounds = _find_section_bounds(add_section_header)
    if add_bounds is not None:
        insert_at = add_bounds[1]
        if insert_at > 0 and lines[insert_at - 1].strip():
            new_section_lines.insert(0, "")
        if insert_at < len(lines) and lines[insert_at].strip():
            new_section_lines.append("")
        lines[insert_at:insert_at] = new_section_lines
        pyproject_path.write_text("\n".join(lines) + "\n")
        return

    content = "\n".join(lines).rstrip()
    if content:
        content += "\n\n"
    content += f"{section_header}\n{created_line}\n"
    pyproject_path.write_text(content)
