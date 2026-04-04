"""Constants for the 'monitoring' command."""

from __future__ import annotations

from pathlib import Path

MONITORING_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_ROOT = MONITORING_ROOT / "template"

MONITORING_DEPENDENCIES: tuple[tuple[str, str], ...] = (
    ("prometheus-client", ">=0.20.0"),
)
