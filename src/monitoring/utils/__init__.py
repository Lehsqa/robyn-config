"""Utility functions for the 'monitoring' command."""

from __future__ import annotations

from pathlib import Path

from add import read_project_config
from add.utils._paths import _extract_design_orm

from ._app import _ensure_prometheus_client, _write_metrics_route
from ._constants import TEMPLATE_ROOT
from ._template_io import _copy_template_tree

__all__ = ["add_monitoring"]


def add_monitoring(project_path: Path) -> list[str]:
    """Generate Alloy + Loki + Prometheus + Grafana monitoring for a robyn-config project."""
    config = read_project_config(project_path)
    design, _ = _extract_design_orm(config)

    if not TEMPLATE_ROOT.exists():
        raise FileNotFoundError("Monitoring template package not found.")

    created = _copy_template_tree(TEMPLATE_ROOT, project_path)
    metrics_file = _write_metrics_route(project_path, design)
    created.append(str(metrics_file))
    _ensure_prometheus_client(project_path, config)
    return created
