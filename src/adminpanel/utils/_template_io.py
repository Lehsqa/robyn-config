"""Template rendering and copy helpers for adminpanel scaffolding."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Mapping

from jinja2 import Environment, StrictUndefined

JINJA_ENV = Environment(undefined=StrictUndefined)


def _resolve_variant_target_rel_path(rel_path: Path, orm: str) -> Path | None:
    if rel_path.suffix != ".py":
        return rel_path

    if rel_path.parts[:2] == ("core", "admin"):
        if rel_path.name in {"helpers.py", "queryset.py"}:
            if orm != "sqlalchemy":
                return None

    if rel_path.parts and rel_path.parts[0] == "orm":
        if rel_path.name == "sqlalchemy.py" and orm != "sqlalchemy":
            return None
        if rel_path.name == "tortoise.py" and orm != "tortoise":
            return None

    if rel_path.parts and "provider" in rel_path.parts:
        if rel_path.name == "sqlalchemy.py" and orm != "sqlalchemy":
            return None
        if rel_path.name == "tortoise.py" and orm != "tortoise":
            return None

    stem = rel_path.stem
    if stem.endswith("_sqlalchemy"):
        if orm != "sqlalchemy":
            return None
        return rel_path.with_name(
            f"{stem.removesuffix('_sqlalchemy')}{rel_path.suffix}"
        )
    if stem.endswith("_tortoise"):
        if orm != "tortoise":
            return None
        return rel_path.with_name(
            f"{stem.removesuffix('_tortoise')}{rel_path.suffix}"
        )
    return rel_path


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
    orm = context.get("orm")
    if not isinstance(orm, str):
        orm = ""

    created_files: list[str] = []
    for template_file in template_root.rglob("*.jinja2"):
        rel_path = template_file.relative_to(template_root)
        if "migrations" in rel_path.parts:
            continue
        mapped_rel_path = _resolve_variant_target_rel_path(
            rel_path.with_suffix(""),
            orm,
        )
        if mapped_rel_path is None:
            continue
        target_path = target_root / mapped_rel_path
        if _render_template_file(template_file, target_path, context):
            created_files.append(str(target_path.relative_to(project_root)))
    return created_files


def _copy_template_tree(
    template_root: Path, target_root: Path, project_root: Path, orm: str
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
        mapped_rel_path = _resolve_variant_target_rel_path(
            source.relative_to(template_root),
            orm,
        )
        if mapped_rel_path is None:
            continue
        target = target_root / mapped_rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        created_files.append(str(target.relative_to(project_root)))
    return created_files
