"""Integration tests for the 'add' command."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
try:
    import tomllib
except ImportError:
    import tomli as tomllib

from tests.integration.test_create_command import create_fake_package_managers

ROOT = Path(__file__).resolve().parents[2]

COMBINATIONS = [
    ("ddd", "sqlalchemy"),
    ("ddd", "tortoise"),
    ("mvc", "sqlalchemy"),
    ("mvc", "tortoise"),
]


def run_cli_create(
    destination: Path, design: str, orm: str, bin_dir: Path | None = None
) -> None:
    """Create a new project using the CLI."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    if bin_dir:
        env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "cli",
            "create",
            "test-app",
            "--orm",
            orm,
            "--design",
            design,
            str(destination),
        ],
        check=True,
        env=env,
    )


def run_cli_add(project_path: Path, name: str) -> None:
    """Add business logic to an existing project using the CLI."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "cli",
            "add",
            name,
            str(project_path),
        ],
        check=True,
        env=env,
    )


def run_make_migration(project_path: Path) -> subprocess.CompletedProcess:
    """Run make makemigration in the project directory."""
    env = os.environ.copy()
    return subprocess.run(
        ["make", "makemigration", "MIGRATION_MESSAGE=add_product"],
        cwd=project_path,
        capture_output=True,
        text=True,
        env=env,
    )


def _read_add_config(project_path: Path) -> dict[str, str]:
    with open(project_path / "pyproject.toml", "rb") as f:
        data = tomllib.load(f)
    return data.get("tool", {}).get("robyn-config", {}).get("add", {}) or {}


def _ddd_paths_from_config(project_dir: Path, add_cfg: dict[str, str]) -> dict[str, Path]:
    return {
        "domain": project_dir / add_cfg.get("domain_path", "src/app/domain"),
        "operational": project_dir / add_cfg.get("operational_path", "src/app/operational"),
        "presentation": project_dir / add_cfg.get("presentation_path", "src/app/presentation"),
        "db_repo": project_dir / add_cfg.get(
            "database_repository_path", "src/app/infrastructure/database/repository"
        ),
        "db_tables": project_dir / add_cfg.get(
            "database_table_path", "src/app/infrastructure/database/tables.py"
        ),
    }


def _mvc_paths_from_config(project_dir: Path, add_cfg: dict[str, str]) -> dict[str, Path]:
    return {
        "views": project_dir / add_cfg.get("views_path", "src/app/views"),
        "db_repo": project_dir / add_cfg.get("database_repository_path", "src/app/models/repository.py"),
        "db_tables": project_dir / add_cfg.get("database_table_path", "src/app/models/models.py"),
        "urls": project_dir / add_cfg.get("urls_path", "src/app/urls.py"),
    }




@pytest.mark.integration
@pytest.mark.parametrize("design,orm", COMBINATIONS)
def test_add_command_creates_files(tmp_path: Path, design: str, orm: str) -> None:
    """Test that the add command creates all expected files."""
    project_dir = tmp_path / "test-project"
    fake_bin = create_fake_package_managers(tmp_path)
    run_cli_create(project_dir, design=design, orm=orm, bin_dir=fake_bin)
    add_cfg = _read_add_config(project_dir)

    # Add a new business logic module
    run_cli_add(project_dir, "product")

    if design == "ddd":
        paths = _ddd_paths_from_config(project_dir, add_cfg)
        # Check DDD files were created
        assert (paths["domain"] / "product" / "__init__.py").exists()
        assert (paths["domain"] / "product" / "entities.py").exists()
        assert (paths["domain"] / "product" / "repository.py").exists()
        assert (paths["db_repo"] / "product.py").exists()
        assert (paths["operational"] / "product.py").exists()
        assert (paths["presentation"] / "product" / "__init__.py").exists()
        assert (paths["presentation"] / "product" / "contracts.py").exists()
        assert (paths["presentation"] / "product" / "rest.py").exists()

        # Check table was added
        tables_content = paths["db_tables"].read_text()
        assert "ProductTable" in tables_content

        # Check domain import was updated
        domain_init = (paths["domain"] / "__init__.py").read_text()
        assert "product" in domain_init

        # Check routes were registered
        pres_init = (paths["presentation"] / "__init__.py").read_text()
        assert "product" in pres_init
        assert "product.register(app)" in pres_init

    elif design == "mvc":
        paths = _mvc_paths_from_config(project_dir, add_cfg)
        # Check MVC files were appended
        models_content = paths["db_tables"].read_text()
        assert "ProductTable" in models_content

        repo_content = paths["db_repo"].read_text()
        assert "ProductRepository" in repo_content

        assert (paths["views"] / "product.py").exists()

        # Check routes were registered in urls.py
        urls_content = paths["urls"].read_text()
        assert "product" in urls_content
        assert "product.register(app)" in urls_content


@pytest.mark.integration
@pytest.mark.parametrize("design,orm", COMBINATIONS)
def test_add_command_no_lint_errors(tmp_path: Path, design: str, orm: str) -> None:
    """Test that the generated code from add command passes ruff linting."""
    project_dir = tmp_path / "test-project-lint"
    fake_bin = create_fake_package_managers(tmp_path)
    run_cli_create(project_dir, design=design, orm=orm, bin_dir=fake_bin)
    add_cfg = _read_add_config(project_dir)
    run_cli_add(project_dir, "product")

    # Check only the files generated by add command
    if design == "ddd":
        paths = _ddd_paths_from_config(project_dir, add_cfg)
        files_to_check = [
            paths["domain"] / "product",
            paths["db_repo"] / "product.py",
            paths["operational"] / "product.py",
            paths["presentation"] / "product",
        ]
    else:  # mvc
        paths = _mvc_paths_from_config(project_dir, add_cfg)
        files_to_check = [
            paths["db_tables"],
            paths["db_repo"],
            paths["views"] / "product.py",
        ]
    
    for file_path in files_to_check:
        if file_path.exists():
            result = subprocess.run(
                ["ruff", "check", str(file_path)],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0, f"Ruff check failed for {file_path}:\n{result.stdout}\n{result.stderr}"


@pytest.mark.integration
@pytest.mark.parametrize("design,orm", COMBINATIONS)
def test_add_command_multiple_entities(tmp_path: Path, design: str, orm: str) -> None:
    """Test adding multiple business logic entities."""
    project_dir = tmp_path / "test-project-multi"
    fake_bin = create_fake_package_managers(tmp_path)
    run_cli_create(project_dir, design=design, orm=orm, bin_dir=fake_bin)
    add_cfg = _read_add_config(project_dir)

    # Add multiple entities
    run_cli_add(project_dir, "product")
    run_cli_add(project_dir, "order")
    run_cli_add(project_dir, "category")

    if design == "ddd":
        paths = _ddd_paths_from_config(project_dir, add_cfg)
        # Check all entities exist
        for entity in ["product", "order", "category"]:
            assert (paths["domain"] / entity / "__init__.py").exists()
            assert (paths["presentation"] / entity / "__init__.py").exists()

        # Check all are in domain __init__
        domain_init = (paths["domain"] / "__init__.py").read_text()
        assert "product" in domain_init
        assert "order" in domain_init
        assert "category" in domain_init

    elif design == "mvc":
        paths = _mvc_paths_from_config(project_dir, add_cfg)
        models_content = paths["db_tables"].read_text()
        repo_content = paths["db_repo"].read_text()
        
        for entity in ["product", "order", "category"]:
            name = "".join(word.capitalize() for word in entity.split("_"))
            assert f"{name}Table" in models_content
            assert f"{name}Repository" in repo_content
            assert (project_dir / "src" / "app" / "views" / f"{entity}.py").exists()


@pytest.mark.integration
def test_add_command_fails_without_robyn_config(tmp_path: Path) -> None:
    """Test that add command fails if pyproject.toml doesn't have robyn-config section."""
    project_dir = tmp_path / "non-robyn-project"
    project_dir.mkdir()
    
    # Create a minimal pyproject.toml without robyn-config
    pyproject = project_dir / "pyproject.toml"
    pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"\n')
    
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "cli",
            "add",
            "product",
            str(project_dir),
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    
    assert result.returncode != 0
    assert "robyn-config" in result.stdout.lower() or "robyn-config" in result.stderr.lower()


@pytest.mark.integration
def test_add_command_fails_without_pyproject(tmp_path: Path) -> None:
    """Test that add command fails if pyproject.toml doesn't exist."""
    project_dir = tmp_path / "empty-project"
    project_dir.mkdir()
    
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "cli",
            "add",
            "product",
            str(project_dir),
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    
    assert result.returncode != 0
    assert "pyproject.toml" in result.stdout or "pyproject.toml" in result.stderr
