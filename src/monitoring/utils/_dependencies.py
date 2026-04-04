"""pyproject dependency helpers for the 'monitoring' command."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Mapping

_SUPPORTED_PACKAGE_MANAGERS = ("poetry", "uv")


def _detect_package_manager(
    config: Mapping[str, str], pyproject_text: str
) -> str:
    configured_raw = config.get("package_manager")
    configured = (
        configured_raw.strip().lower()
        if isinstance(configured_raw, str)
        else None
    )
    if configured in _SUPPORTED_PACKAGE_MANAGERS:
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


def _extract_dependency_name(line: str) -> str | None:
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

    normalized = _normalize_dependency_name(dependency)
    for line in lines[start_index + 1 : end_index]:
        existing = _extract_dependency_name(line)
        if (
            existing is not None
            and _normalize_dependency_name(existing) == normalized
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


def _install_dependency(
    project_path: Path, package_manager: str, dependency: str, version: str
) -> None:
    """Add and install a dependency via the project's package manager.

    Runs ``uv add <dep><version>`` or ``poetry add <dep><version>`` so that
    pyproject.toml, the lock file, and the active virtual environment are all
    updated in one step.
    """
    spec = f"{dependency}{version}"
    if package_manager == "poetry":
        cmd = ["poetry", "add", spec, "--no-interaction"]
    else:
        cmd = ["uv", "add", spec]

    result = subprocess.run(
        cmd,
        cwd=project_path,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        message = (
            result.stderr.strip() or result.stdout.strip() or "unknown error"
        )
        raise RuntimeError(
            f"Failed to install '{spec}' with {package_manager}: {message}"
        )
