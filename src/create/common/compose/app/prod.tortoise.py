"""Runtime entrypoint for production images.

Runs Aerich migrations before handing off to the Robyn server (or any custom command).
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys

IGNORABLE_WARNINGS = ("App 'models' is already initialized.",)
APP_MODULE = os.environ.get("ROBYN_APP_MODULE", "app.server")


def _run(cmd: list[str], *, ignore_existing: bool = False) -> None:
    if not ignore_existing:
        subprocess.run(cmd, check=True)
        return

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode == 0:
        sys.stdout.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        return

    combined = f"{proc.stdout}{proc.stderr}"
    if any(warning in combined for warning in IGNORABLE_WARNINGS):
        sys.stdout.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        return

    raise subprocess.CalledProcessError(
        proc.returncode, cmd, output=proc.stdout, stderr=proc.stderr
    )


def main() -> None:
    _run(["aerich", "init-db"], ignore_existing=True)
    _run(["aerich", "upgrade"])

    raw_cmd = os.environ.get("APP_CMD")
    if raw_cmd:
        _run(shlex.split(raw_cmd))
        return

    _run(
        [
            sys.executable,
            "-m",
            APP_MODULE,
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
