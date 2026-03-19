"""Utility functions for the 'create' command."""

from __future__ import annotations

from ._config import (
    DESIGN_CHOICES,
    LOCK_FILE_BY_MANAGER,
    ORM_CHOICES,
    PACKAGE_MANAGER_CHOICES,
    PACKAGE_MANAGER_DOWNLOAD_URLS,
    TEMPLATE_CONFIGS,
)
from ._filesystem import (
    collect_existing_items,
    copy_template,
    get_generated_items,
    prepare_destination,
)
from ._interactive import InteractiveCreateConfig, run_create_interactive
from ._package_manager import (
    apply_package_manager,
    ensure_package_manager_available,
)

__all__ = [
    "DESIGN_CHOICES",
    "LOCK_FILE_BY_MANAGER",
    "ORM_CHOICES",
    "PACKAGE_MANAGER_CHOICES",
    "PACKAGE_MANAGER_DOWNLOAD_URLS",
    "TEMPLATE_CONFIGS",
    "apply_package_manager",
    "collect_existing_items",
    "copy_template",
    "ensure_package_manager_available",
    "get_generated_items",
    "prepare_destination",
    "InteractiveCreateConfig",
    "run_create_interactive",
]
