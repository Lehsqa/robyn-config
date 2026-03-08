import os
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


def _write_fake_manager(bin_dir: Path, name: str, lock_name: str) -> None:
    script = bin_dir / name
    script.write_text(
        "#!/usr/bin/env bash\n"
        'cmd=\"$1\"\n'
        'if [ -n \"$cmd\" ]; then\n'
        "  shift\n"
        "fi\n"
        'if [ \"$cmd\" = \"lock\" ]; then\n'
        f"  touch \"$PWD/{lock_name}\"\n"
        "  exit 0\n"
        "fi\n"
        f"echo \"{name} stub: unsupported command $cmd\" >&2\n"
        "exit 1\n"
    )
    script.chmod(0o755)


def create_fake_package_managers(tmp_path: Path) -> Path:
    """Create lightweight stubs for uv and poetry to avoid network calls."""
    bin_dir = tmp_path / "fake_bin"
    bin_dir.mkdir()
    _write_fake_manager(bin_dir, "uv", "uv.lock")
    _write_fake_manager(bin_dir, "poetry", "poetry.lock")
    return bin_dir


def run_create_command(
    destination: Path,
    design: str,
    orm: str,
    package_manager: str = "uv",
    bin_dir: Path | None = None,
) -> subprocess.CompletedProcess:
    """Run the create command via subprocess."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    if bin_dir:
        env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
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
            "--package-manager",
            package_manager,
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
    fake_bin = create_fake_package_managers(tmp_path)
    result = run_create_command(project_dir, design, orm, bin_dir=fake_bin)
    
    # Check CLI execution success
    assert result.returncode == 0, f"CLI create failed: {result.stderr}"

    # 1. Verify Common Files
    assert (project_dir / "pyproject.toml").exists()
    assert (project_dir / "README.md").exists()
    assert (project_dir / "Makefile").exists()
    assert (project_dir / "compose" / "app" / "Dockerfile").exists()
    assert (project_dir / "compose" / "app" / "dev.sh").exists()
    assert (project_dir / "uv.lock").exists()
    
    # 2. Verify ORM-specific files
    if orm == "sqlalchemy":
        assert (project_dir / "alembic.ini").exists()
    else:
        assert not (project_dir / "alembic.ini").exists()

    # 3. Verify Design-specific Structure
    app_dir = project_dir / "src" / "app"
    assert app_dir.exists()
    logging_content = (app_dir / "config" / "logging.py").read_text()
    server_content = (app_dir / "server.py").read_text()
    assert "logger.remove()" in server_content
    assert "logger.add(" in server_content
    assert "sys.stderr" in server_content
    assert "if settings.logging.file:" in server_content
    assert "file: str | None = \"app\"" in logging_content

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


def test_create_with_poetry_package_manager(tmp_path):
    """Ensure the CLI can scaffold a project using poetry for dependency management."""
    project_dir = tmp_path / "poetry_project"
    fake_bin = create_fake_package_managers(tmp_path)
    result = run_create_command(
        project_dir,
        design="ddd",
        orm="sqlalchemy",
        package_manager="poetry",
        bin_dir=fake_bin,
    )

    assert result.returncode == 0, f"CLI create failed: {result.stderr}"
    assert (project_dir / "poetry.lock").exists()

    pyproject_content = (project_dir / "pyproject.toml").read_text()
    assert "[tool.poetry]" in pyproject_content
    assert "[project]" not in pyproject_content

    makefile_content = (project_dir / "Makefile").read_text()
    assert "poetry run" in makefile_content

    dockerfile_content = (
        project_dir / "compose" / "app" / "Dockerfile"
    ).read_text()
    assert "poetry.lock" in dockerfile_content
    assert "RUN mkdir -p /opt/project/logs" in dockerfile_content


def test_create_generates_reliable_compose_and_env_defaults(tmp_path):
    """Scaffold should work without manual compose/logs/env edits."""
    project_dir = tmp_path / "reliable_defaults_project"
    fake_bin = create_fake_package_managers(tmp_path)
    result = run_create_command(project_dir, "ddd", "sqlalchemy", bin_dir=fake_bin)

    assert result.returncode == 0, f"CLI create failed: {result.stderr}"

    compose_content = (project_dir / "docker-compose.yml").read_text()
    env_example_content = (project_dir / ".env.example").read_text()

    assert ".env.example" not in compose_content
    assert "      - .env" in compose_content
    assert "      - app-logs:/app/logs" in compose_content
    assert "\n  app-logs:\n" in compose_content
    assert "SETTINGS__DATABASE__HOST: postgres" in compose_content
    assert "SETTINGS__CACHE__HOST: valkey" in compose_content
    assert "SETTINGS__MAILING__HOST: mailhog" in compose_content

    assert "SETTINGS__DATABASE__HOST=localhost" in env_example_content
    assert "SETTINGS__CACHE__HOST=localhost" in env_example_content
    assert "SETTINGS__MAILING__HOST=localhost" in env_example_content


def test_create_generates_rooted_env_loading_and_nonroot_log_dir_setup(tmp_path):
    """Generated config and Dockerfile should support cwd-independent env loading."""
    project_dir = tmp_path / "rooted_env_project"
    fake_bin = create_fake_package_managers(tmp_path)
    result = run_create_command(project_dir, "mvc", "sqlalchemy", bin_dir=fake_bin)

    assert result.returncode == 0, f"CLI create failed: {result.stderr}"

    config_content = (project_dir / "src" / "app" / "config" / "__init__.py").read_text()
    dockerfile_content = (
        project_dir / "compose" / "app" / "Dockerfile"
    ).read_text()

    assert '_env_file=core.ROOT_PATH / ".env"' in config_content
    assert "RUN mkdir -p /opt/project/logs" in dockerfile_content
    assert (
        "COPY --chown=65532:65532 --from=builder /opt/project /app"
        in dockerfile_content
    )
