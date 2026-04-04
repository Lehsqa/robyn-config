"""App-side injection helpers for the 'monitoring' command."""

from __future__ import annotations

import shutil
from pathlib import Path

from add.utils import _register_routes_ddd, _register_routes_mvc

from ._constants import MONITORING_DEPENDENCIES
from ._dependencies import _detect_package_manager, _install_dependency

METRICS_SOURCE = Path(__file__).resolve().parent.parent / "app" / "metrics.py"


def _write_metrics_route(project_path: Path, design: str) -> Path:
    """Copy metrics.py to the appropriate presentation layer and register it."""
    if design == "ddd":
        target = project_path / "src" / "app" / "presentation" / "metrics.py"
        presentation_dir = target.parent
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(METRICS_SOURCE, target)
        _register_routes_ddd(presentation_dir, "metrics")
    else:
        target = project_path / "src" / "app" / "views" / "metrics.py"
        urls_path = project_path / "src" / "app" / "urls.py"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(METRICS_SOURCE, target)
        _register_routes_mvc(urls_path, "metrics")
    return target


def _ensure_prometheus_client(project_path: Path, config: dict) -> None:
    import shutil

    pyproject_path = project_path / "pyproject.toml"
    pyproject_text = (
        pyproject_path.read_text() if pyproject_path.exists() else ""
    )
    package_manager = _detect_package_manager(config, pyproject_text)
    for dep, version in MONITORING_DEPENDENCIES:
        if shutil.which(package_manager):
            try:
                _install_dependency(
                    project_path, package_manager, dep, version
                )
                continue
            except RuntimeError:
                pass
        # Fallback: write pyproject.toml only; user must run sync manually.
        from ._dependencies import _ensure_dependency

        _ensure_dependency(pyproject_path, package_manager, dep, version)
