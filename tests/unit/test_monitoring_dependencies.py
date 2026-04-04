"""Unit tests for monitoring._dependencies — pyproject.toml injection."""

from __future__ import annotations

from pathlib import Path

import pytest

from monitoring.utils._dependencies import (
    _ensure_dependency,
    _ensure_poetry_dependency,
    _ensure_project_dependency,
)

# ---------------------------------------------------------------------------
# Fixtures — real pyproject.toml content from the template
# ---------------------------------------------------------------------------

UV_PYPROJECT = """\
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "my-app"
version = "0.1.0"
requires-python = ">=3.11,<4.0"
dependencies = [
  "robyn[pydantic]>=0.81.0",
  "asyncpg>=0.29.0",
  "pydantic[email]>=2.6.4",
  "loguru>=0.7.2",
]

[tool.robyn-config]
design = "ddd"
orm = "sqlalchemy"
package_manager = "uv"
"""

POETRY_PYPROJECT = """\
[build-system]
requires = ["poetry-core>=1.9.0"]
build-backend = "poetry.core.masonry.api"

[tool.poetry]
name = "my-app"
version = "0.1.0"

[tool.poetry.dependencies]
python = ">=3.11,<4.0"
robyn = { version = ">=0.81.0", extras = ["pydantic"] }
asyncpg = ">=0.29.0"
pydantic = { version = ">=2.6.4", extras = ["email"] }
loguru = ">=0.7.2"

[tool.poetry.group.dev.dependencies]
pytest = ">=7.4.0"

[tool.robyn-config]
design = "ddd"
orm = "sqlalchemy"
package_manager = "poetry"
"""


# ---------------------------------------------------------------------------
# uv / PEP-621 format
# ---------------------------------------------------------------------------

class TestEnsureProjectDependency:
    def test_appends_at_end_of_dependencies_list(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(UV_PYPROJECT)

        _ensure_project_dependency(pyproject, "prometheus-client", ">=0.20.0")

        lines = pyproject.read_text().splitlines()
        bracket_idx = next(i for i, l in enumerate(lines) if l.strip() == "]")
        inserted_idx = bracket_idx - 1
        assert lines[inserted_idx].strip() == '"prometheus-client>=0.20.0",'

    def test_dependency_appears_in_list(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(UV_PYPROJECT)

        _ensure_project_dependency(pyproject, "prometheus-client", ">=0.20.0")

        assert '"prometheus-client>=0.20.0",' in pyproject.read_text()

    def test_idempotent_when_already_present(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(UV_PYPROJECT)

        _ensure_project_dependency(pyproject, "prometheus-client", ">=0.20.0")
        _ensure_project_dependency(pyproject, "prometheus-client", ">=0.20.0")

        assert pyproject.read_text().count("prometheus-client") == 1

    def test_normalises_package_name(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(UV_PYPROJECT)

        _ensure_project_dependency(pyproject, "prometheus-client", ">=0.20.0")
        # Same package with underscore variant should not be duplicated
        _ensure_project_dependency(pyproject, "prometheus_client", ">=0.20.0")

        assert pyproject.read_text().count("prometheus") == 1

    def test_existing_dependencies_unchanged(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(UV_PYPROJECT)

        _ensure_project_dependency(pyproject, "prometheus-client", ">=0.20.0")
        content = pyproject.read_text()

        assert '"robyn[pydantic]>=0.81.0",' in content
        assert '"loguru>=0.7.2",' in content


# ---------------------------------------------------------------------------
# poetry format
# ---------------------------------------------------------------------------

class TestEnsurePoetryDependency:
    def test_appends_inside_poetry_dependencies_section(
        self, tmp_path: Path
    ) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(POETRY_PYPROJECT)

        _ensure_poetry_dependency(pyproject, "prometheus-client", ">=0.20.0")
        content = pyproject.read_text()

        assert 'prometheus-client = ">=0.20.0"' in content

    def test_does_not_bleed_into_dev_section(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(POETRY_PYPROJECT)

        _ensure_poetry_dependency(pyproject, "prometheus-client", ">=0.20.0")
        lines = pyproject.read_text().splitlines()

        dep_idx = next(
            i for i, l in enumerate(lines) if "prometheus-client" in l
        )
        dev_idx = next(
            i for i, l in enumerate(lines)
            if "[tool.poetry.group.dev.dependencies]" in l
        )
        assert dep_idx < dev_idx

    def test_idempotent_when_already_present(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(POETRY_PYPROJECT)

        _ensure_poetry_dependency(pyproject, "prometheus-client", ">=0.20.0")
        _ensure_poetry_dependency(pyproject, "prometheus-client", ">=0.20.0")

        assert pyproject.read_text().count("prometheus-client") == 1

    def test_existing_dependencies_unchanged(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(POETRY_PYPROJECT)

        _ensure_poetry_dependency(pyproject, "prometheus-client", ">=0.20.0")
        content = pyproject.read_text()

        assert 'robyn = { version = ">=0.81.0"' in content
        assert 'loguru = ">=0.7.2"' in content


# ---------------------------------------------------------------------------
# _ensure_dependency dispatcher
# ---------------------------------------------------------------------------

class TestEnsureDependency:
    def test_dispatches_to_project_for_uv(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(UV_PYPROJECT)

        _ensure_dependency(pyproject, "uv", "prometheus-client", ">=0.20.0")

        assert '"prometheus-client>=0.20.0",' in pyproject.read_text()

    def test_dispatches_to_poetry(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(POETRY_PYPROJECT)

        _ensure_dependency(pyproject, "poetry", "prometheus-client", ">=0.20.0")

        assert 'prometheus-client = ">=0.20.0"' in pyproject.read_text()

    def test_no_op_when_file_missing(self, tmp_path: Path) -> None:
        missing = tmp_path / "pyproject.toml"
        # should not raise
        _ensure_dependency(missing, "uv", "prometheus-client", ">=0.20.0")
