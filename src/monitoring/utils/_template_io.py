"""Template I/O helpers for the 'monitoring' command."""

from __future__ import annotations

import shutil
from pathlib import Path


def _copy_template_tree(source_root: Path, target_root: Path) -> list[str]:
    """Recursively copy a template tree to a target directory."""
    created: list[str] = []
    for source in source_root.rglob("*"):
        if source.is_dir():
            continue
        rel = source.relative_to(source_root)
        target = target_root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        created.append(str(target))
    return created
