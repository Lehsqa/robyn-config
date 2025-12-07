import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


COMBINATIONS = [
    ("ddd", "sqlalchemy"),
    ("ddd", "tortoise"),
    ("mvc", "sqlalchemy"),
    ("mvc", "tortoise"),
]


def run_create_command(
    destination: Path, design: str, orm: str
) -> subprocess.CompletedProcess:
    """Run the create command via subprocess."""
    env = {"PYTHONPATH": str(ROOT / "src")}
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "cli",
            "create",
            "test-project",
            "--orm",
            orm,
            "--design",
            design,
            str(destination),
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize("design,orm", COMBINATIONS)
def test_create_project_structure(tmp_path, design, orm):
    """Verify that create command generates correct file structure."""
    project_dir = tmp_path / "test_project"
    result = run_create_command(project_dir, design, orm)
    
    # Check CLI execution success
    assert result.returncode == 0, f"CLI create failed: {result.stderr}"
    assert "copied to" in result.stdout

    # 1. Verify Common Files
    assert (project_dir / "pyproject.toml").exists()
    assert (project_dir / "README.md").exists()
    assert (project_dir / "Makefile").exists()
    assert (project_dir / "compose" / "app" / "Dockerfile").exists()
    assert (project_dir / "compose" / "app" / "dev.sh").exists()
    
    # 2. Verify ORM-specific files
    if orm == "sqlalchemy":
        assert (project_dir / "alembic.ini").exists()
    else:
        assert not (project_dir / "alembic.ini").exists()

    # 3. Verify Design-specific Structure
    app_dir = project_dir / "src" / "app"
    assert app_dir.exists()

    if design == "ddd":
        assert (app_dir / "domain").is_dir()
        assert (app_dir / "infrastructure").is_dir()
        assert (app_dir / "operational").is_dir()
        assert (app_dir / "presentation").is_dir()
        # Ensure MVC folders are NOT present
        assert not (app_dir / "models").exists()
        assert not (app_dir / "views").exists()
    else:  # mvc
        assert (app_dir / "models").is_dir()
        assert (app_dir / "views").is_dir()
        # Ensure DDD folders are NOT present
        assert not (app_dir / "domain").exists()
        assert not (app_dir / "infrastructure").exists()

    # 4. Content Verification (pyproject.toml context)
    pyproject_content = (project_dir / "pyproject.toml").read_text()
    assert f'design = "{design}"' in pyproject_content
    assert f'orm = "{orm}"' in pyproject_content
