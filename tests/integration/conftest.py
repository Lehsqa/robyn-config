"""Shared test fixtures and helpers for integration tests."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMBINATIONS = (
    ("ddd", "sqlalchemy"),
    ("ddd", "tortoise"),
    ("mvc", "sqlalchemy"),
    ("mvc", "tortoise"),
)

ACTIVATION_PATTERN = re.compile(r"http://[^/]+/activate/([0-9a-fA-F-]+)")
APP_BASE_URL = "http://127.0.0.1:8000"
MAILHOG_API = "http://127.0.0.1:8025/api/v2/messages"

APP_COMBINATIONS = (
    ("ddd", "sqlalchemy", "none"),
    ("ddd", "sqlalchemy", "sparkid"),
    ("ddd", "tortoise", "none"),
    ("ddd", "tortoise", "sparkid"),
    ("mvc", "sqlalchemy", "none"),
    ("mvc", "tortoise", "none"),
)
ADMIN_USER_ROUTE = "UsersTableAdmin"
ROLE_ROUTE = "RoleAdmin"
USER_ROLE_ROUTE = "UserRoleAdmin"
PRODUCT_ROUTE = "ProductTableAdmin"


def _write_fake_manager(bin_dir: Path, name: str, lock_name: str) -> None:
    script = bin_dir / name
    script.write_text(
        "#!/usr/bin/env bash\n"
        'cmd="$1"\n'
        'if [ -n "$cmd" ]; then\n'
        "  shift\n"
        "fi\n"
        'if [ "$cmd" = "lock" ]; then\n'
        f'  touch "$PWD/{lock_name}"\n'
        "  exit 0\n"
        "fi\n"
        f'echo "{name} stub: unsupported command $cmd" >&2\n'
        "exit 1\n"
    )
    script.chmod(0o755)


def create_fake_package_managers(tmp_path: Path) -> Path:
    """Create lightweight stubs for uv and poetry to avoid network calls."""
    bin_dir = tmp_path / "fake_bin"
    bin_dir.mkdir(exist_ok=True)
    _write_fake_manager(bin_dir, "uv", "uv.lock")
    _write_fake_manager(bin_dir, "poetry", "poetry.lock")
    return bin_dir


def run_cli_create(
    destination: Path,
    design: str,
    orm: str,
    app_name: str = "test-app",
    bin_dir: Path | None = None,
    uid: str | None = None,
) -> None:
    """Scaffold a project via the CLI create command."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    if bin_dir:
        env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    cmd = [
        sys.executable,
        "-m",
        "cli",
        "create",
        app_name,
        "--orm",
        orm,
        "--design",
        design,
    ]
    if uid is not None:
        cmd.extend(["--uid", uid])
    cmd.append(str(destination))

    subprocess.run(
        cmd,
        check=True,
        env=env,
    )
