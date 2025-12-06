"""Runtime entrypoint for production images.

Runs Alembic migrations before handing off to the Robyn server (or any custom command).
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def main() -> None:
    _run(["alembic", "upgrade", "head"])

    raw_cmd = os.environ.get("APP_CMD")
    if raw_cmd:
        _run(shlex.split(raw_cmd))
        return

    _run(
        [
            sys.executable,
            "-m",
            "app.server",
            "--fast",
            "--processes",
            "4",
            "--workers",
            "3",
            "--log-level",
            "WARNING",
        ]
    )


if __name__ == "__main__":
    main()
