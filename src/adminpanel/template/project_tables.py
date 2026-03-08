from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType

try:
    import tomllib
except ImportError:  # pragma: no cover
    import tomli as tomllib

FALLBACK_TABLE_MODULES: tuple[str, ...] = (
    "app.infrastructure.database.tables",
    "app.models.tables",
    "app.infrastructure.database.table",
    "app.models.table",
    "app.models.models",
)


def _path_to_module(path_value: str) -> str | None:
    normalized = path_value.strip().replace("\\", "/")
    if not normalized:
        return None

    parts = [part for part in normalized.split("/") if part and part != "."]
    if "src" not in parts:
        return None

    src_idx = parts.index("src")
    module_parts = parts[src_idx + 1 :]
    if not module_parts:
        return None

    tail = module_parts[-1]
    if tail == "__init__.py":
        module_parts = module_parts[:-1]
    elif tail.endswith(".py"):
        module_parts[-1] = tail[:-3]
    else:
        return None

    if not module_parts or not all(
        part and part.isidentifier() for part in module_parts
    ):
        return None
    return ".".join(module_parts)


def _iter_pyproject_paths() -> tuple[Path, ...]:
    seen: set[Path] = set()
    found: list[Path] = []
    for root in (Path.cwd(), Path(__file__).resolve().parent):
        for candidate_dir in (root, *root.parents):
            pyproject_path = candidate_dir / "pyproject.toml"
            if pyproject_path in seen:
                continue
            seen.add(pyproject_path)
            if pyproject_path.exists():
                found.append(pyproject_path)
    return tuple(found)


def _configured_tables_module() -> str | None:
    for pyproject_path in _iter_pyproject_paths():
        try:
            data = tomllib.loads(pyproject_path.read_text())
        except Exception:
            continue

        raw = (
            data.get("tool", {})
            .get("robyn-config", {})
            .get("add", {})
            .get("database_table_path")
        )
        if isinstance(raw, str):
            module_name = _path_to_module(raw)
            if module_name:
                return module_name
    return None


def _candidate_modules() -> tuple[str, ...]:
    configured = _configured_tables_module()
    candidates: list[str] = []
    if configured:
        candidates.append(configured)
    for module_name in FALLBACK_TABLE_MODULES:
        if module_name not in candidates:
            candidates.append(module_name)
    return tuple(candidates)


def load_project_tables_module() -> ModuleType:
    modules = _candidate_modules()
    for module_name in modules:
        try:
            return importlib.import_module(module_name)
        except ModuleNotFoundError as exc:
            missing_name = exc.name or ""
            expected_missing = {module_name, module_name.split(".")[0]}
            if missing_name not in expected_missing:
                raise
            continue

    raise ModuleNotFoundError(
        "Unable to import project tables module. Expected one of: "
        + ", ".join(modules)
    )
