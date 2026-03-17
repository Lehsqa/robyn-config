"""Package manager utilities for the 'create' command."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import click

from ._config import (
    LOCK_FILE_BY_MANAGER,
    PACKAGE_MANAGER_CHOICES,
    PACKAGE_MANAGER_DOWNLOAD_URLS,
)


def ensure_package_manager_available(package_manager: str) -> None:
    """Validate the requested package manager is available on PATH."""
    if package_manager not in PACKAGE_MANAGER_CHOICES:
        raise click.ClickException(
            "Unsupported package manager "
            f"'{package_manager}'. Choose from: {', '.join(PACKAGE_MANAGER_CHOICES)}"
        )

    if shutil.which(package_manager) is None:
        download_url = PACKAGE_MANAGER_DOWNLOAD_URLS.get(package_manager)
        download_hint = (
            f" Download it from {download_url} before running the create command."
            if download_url
            else " Install it before running the create command."
        )
        raise click.ClickException(
            f"Package manager '{package_manager}' is not installed.{download_hint}"
        )


def apply_package_manager(destination: Path, package_manager: str) -> None:
    """Generate the lock file for the project using the chosen package manager."""
    ensure_package_manager_available(package_manager)

    lock_file = LOCK_FILE_BY_MANAGER.get(package_manager, "lock file")
    lock_path = destination / lock_file
    env = os.environ.copy()
    if package_manager == "uv":
        env.setdefault("UV_CACHE_DIR", str(destination / ".uv-cache"))
    else:
        env.setdefault("POETRY_CACHE_DIR", str(destination / ".poetry-cache"))
    if package_manager == "uv":
        command = ["uv", "lock"]
    else:
        command = ["poetry", "lock", "--no-interaction", "--quiet"]

    result = subprocess.run(
        command, cwd=destination, capture_output=True, text=True, env=env
    )
    if result.returncode != 0:
        message = (
            result.stderr.strip() or result.stdout.strip() or "Unknown error"
        )
        raise click.ClickException(
            f"Failed to generate {lock_file} with {package_manager}: {message}"
        )
    if lock_file and not lock_path.exists():
        output = result.stdout.strip() or result.stderr.strip()
        detail = f" ({output})" if output else ""
        raise click.ClickException(
            f"{package_manager} finished without creating {lock_file}{detail}"
        )
