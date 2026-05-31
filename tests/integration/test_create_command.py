import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.integration.conftest import (
    ROOT,
    COMBINATIONS,
    create_fake_package_managers,
)


def run_create_command(
    destination: Path,
    design: str,
    orm: str,
    package_manager: str = "uv",
    bin_dir: Path | None = None,
    uid: str | None = None,
    broker: str | None = None,
    nosql: str | None = None,
) -> subprocess.CompletedProcess:
    """Run the create command via subprocess."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    if bin_dir:
        env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    cmd = [
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
    ]
    if uid is not None:
        cmd.extend(["--uid", uid])
    if broker is not None:
        cmd.extend(["--broker", broker])
    if nosql is not None:
        cmd.extend(["--nosql", nosql])
    cmd.append(str(destination))
    return subprocess.run(
        cmd,
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
    assert 'file: str | None = "app"' in logging_content

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
    result = run_create_command(
        project_dir, "ddd", "sqlalchemy", bin_dir=fake_bin
    )

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


def test_create_generates_rooted_env_loading_and_nonroot_log_dir_setup(
    tmp_path,
):
    """Generated config and Dockerfile should support cwd-independent env loading."""
    project_dir = tmp_path / "rooted_env_project"
    fake_bin = create_fake_package_managers(tmp_path)
    result = run_create_command(
        project_dir, "mvc", "sqlalchemy", bin_dir=fake_bin
    )

    assert result.returncode == 0, f"CLI create failed: {result.stderr}"

    config_content = (
        project_dir / "src" / "app" / "config" / "__init__.py"
    ).read_text()
    dockerfile_content = (
        project_dir / "compose" / "app" / "Dockerfile"
    ).read_text()

    assert '_env_file=core.ROOT_PATH / ".env"' in config_content
    assert "RUN mkdir -p /opt/project/logs" in dockerfile_content
    assert (
        "COPY --chown=65532:65532 --from=builder /opt/project /app"
        in dockerfile_content
    )


@pytest.mark.parametrize(
    ("uid", "expected_primary_key_type"),
    [
        ("none", "int"),
        ("sparkid", "str"),
    ],
)
@pytest.mark.parametrize("design,orm", COMBINATIONS)
def test_create_user_templates_adapt_to_uid_type(
    tmp_path: Path,
    design: str,
    orm: str,
    uid: str,
    expected_primary_key_type: str,
) -> None:
    project_dir = tmp_path / f"{design}-{orm}-{uid}-user-types"
    fake_bin = create_fake_package_managers(tmp_path)
    result = run_create_command(
        project_dir,
        design,
        orm,
        bin_dir=fake_bin,
        uid=uid,
    )

    assert result.returncode == 0, f"CLI create failed: {result.stderr}"

    if design == "ddd":
        base_entities_content = (
            project_dir
            / "src"
            / "app"
            / "infrastructure"
            / "application"
            / "entities"
            / "base.py"
        ).read_text()
        entities_content = (
            project_dir / "src" / "app" / "domain" / "users" / "entities.py"
        ).read_text()
        contracts_content = (
            project_dir
            / "src"
            / "app"
            / "presentation"
            / "users"
            / "contracts.py"
        ).read_text()
        auth_content = (
            project_dir / "src" / "app" / "operational" / "authentication.py"
        ).read_text()
    else:
        base_entities_content = (
            project_dir / "src" / "app" / "schemas.py"
        ).read_text()
        entities_content = base_entities_content
        contracts_content = (
            project_dir / "src" / "app" / "views" / "contracts.py"
        ).read_text()
        auth_content = (
            project_dir / "src" / "app" / "views" / "authentication.py"
        ).read_text()

    assert f"PrimaryKey = {expected_primary_key_type}" in base_entities_content
    assert "id: PrimaryKey" in entities_content
    assert "user_id: PrimaryKey" in entities_content
    assert (
        'id: Annotated[PrimaryKey, Field(description="User id")]'
        in contracts_content
    )
    assert "return parse_primary_key(str(sub))" in auth_content


@pytest.mark.parametrize("design", ("ddd", "mvc"))
@pytest.mark.parametrize("broker", ("redis", "rabbitmq", "kafka"))
def test_create_generates_selected_broker_template(
    tmp_path: Path,
    design: str,
    broker: str,
) -> None:
    project_dir = tmp_path / f"{design}-{broker}-broker"
    fake_bin = create_fake_package_managers(tmp_path)
    result = run_create_command(
        project_dir,
        design,
        "sqlalchemy",
        bin_dir=fake_bin,
        broker=broker,
    )

    assert result.returncode == 0, f"CLI create failed: {result.stderr}"

    app_dir = project_dir / "src" / "app"
    pyproject_content = (project_dir / "pyproject.toml").read_text()
    compose_content = (project_dir / "docker-compose.yml").read_text()
    env_example_content = (project_dir / ".env.example").read_text()
    settings_content = (app_dir / "config" / "__init__.py").read_text()

    assert f'broker = "{broker}"' in pyproject_content
    assert "from . import broker as _broker" in settings_content
    assert "broker: _broker.Settings = _broker.Settings()" in settings_content
    assert (app_dir / "config" / "broker.py").exists()

    if design == "ddd":
        assert (app_dir / "infrastructure" / "broker" / "__init__.py").exists()
        assert (app_dir / "infrastructure" / "broker" / "services.py").exists()
        assert not (app_dir / "broker.py").exists()
    else:
        assert (app_dir / "broker.py").exists()
        assert not (app_dir / "infrastructure").exists()

    if broker == "redis":
        assert "redis-broker:" in compose_content
        assert "SETTINGS__BROKER__HOST: redis-broker" in compose_content
        assert "SETTINGS__BROKER__HOST=localhost" in env_example_content
        assert "SETTINGS__BROKER__PORT=6380" in env_example_content
        assert "SETTINGS__BROKER__DB=1" in env_example_content
        assert "db: int = 1" in (app_dir / "config" / "broker.py").read_text()
    elif broker == "rabbitmq":
        assert "aio-pika>=" in pyproject_content
        assert "rabbitmq:" in compose_content
        assert "SETTINGS__BROKER__HOST: rabbitmq" in compose_content
        assert "SETTINGS__BROKER__PORT=5672" in env_example_content
    else:
        assert "aiokafka>=" in pyproject_content
        assert "kafka:" in compose_content
        assert "image: apache/kafka:4.3.0" in compose_content
        assert "KAFKA_PROCESS_ROLES: broker,controller" in compose_content
        assert "KAFKA_CFG_PROCESS_ROLES" not in compose_content
        assert (
            "SETTINGS__BROKER__BOOTSTRAP_SERVERS: kafka:9092"
            in compose_content
        )
        assert (
            "SETTINGS__BROKER__BOOTSTRAP_SERVERS=localhost:29092"
            in env_example_content
        )


@pytest.mark.parametrize("design", ("ddd", "mvc"))
@pytest.mark.parametrize("nosql", ("mongodb", "neo4j"))
def test_create_generates_selected_nosql_template(
    tmp_path: Path,
    design: str,
    nosql: str,
) -> None:
    project_dir = tmp_path / f"{design}-{nosql}-nosql"
    fake_bin = create_fake_package_managers(tmp_path)
    result = run_create_command(
        project_dir,
        design,
        "sqlalchemy",
        bin_dir=fake_bin,
        nosql=nosql,
    )

    assert result.returncode == 0, f"CLI create failed: {result.stderr}"

    app_dir = project_dir / "src" / "app"
    pyproject_content = (project_dir / "pyproject.toml").read_text()
    compose_content = (project_dir / "docker-compose.yml").read_text()
    env_example_content = (project_dir / ".env.example").read_text()
    settings_content = (app_dir / "config" / "__init__.py").read_text()
    nosql_settings_dir = app_dir / "config" / "nosql"
    nosql_settings_content = (nosql_settings_dir / f"{nosql}.py").read_text()
    nosql_init_content = (nosql_settings_dir / "__init__.py").read_text()

    assert "from . import nosql as _nosql" in settings_content
    assert "nosql: _nosql.Settings = _nosql.Settings()" in settings_content
    assert f'nosql = ["{nosql}"]' in pyproject_content
    assert f"{nosql}: _{nosql}.Settings = _{nosql}.Settings()" in (
        nosql_init_content
    )

    if design == "ddd":
        nosql_dir = app_dir / "infrastructure" / "nosql"
        provider_dir = nosql_dir / nosql
        service_path = provider_dir / "services" / "engine.py"
        assert (nosql_dir / "__init__.py").exists()
        assert (provider_dir / "__init__.py").exists()
        assert (provider_dir / "services" / "__init__.py").exists()
    else:
        nosql_dir = app_dir / "nosql"
        provider_dir = nosql_dir / nosql
        service_path = provider_dir / "services.py"
        assert not (app_dir / "infrastructure").exists()
        assert (nosql_dir / "__init__.py").exists()
        assert (provider_dir / "__init__.py").exists()

    service_content = service_path.read_text()
    if design == "ddd":
        assert "from .....config import settings" in service_content
    else:
        assert "from ...config import settings" in service_content

    if nosql == "mongodb":
        assert "from pymongo import AsyncMongoClient" in service_content
        assert 'await self.client.admin.command("ping")' in service_content
        assert "await self.client.close()" in service_content
        assert "settings.nosql.mongodb.dsn" in service_content
        assert 'host: str = "mongodb"' in nosql_settings_content
        assert "def dsn(self) -> str:" in nosql_settings_content
        assert "pymongo>=4.11.0" in pyproject_content
        assert "mongodb:" in compose_content
        assert "SETTINGS__NOSQL__MONGODB__HOST: mongodb" in compose_content
        assert "SETTINGS__NOSQL__MONGODB__HOST=localhost" in (
            env_example_content
        )
    else:
        assert (
            "from neo4j import AsyncDriver, AsyncGraphDatabase"
            in service_content
        )
        assert "await self.driver.verify_connectivity()" in service_content
        assert "await self.driver.close()" in service_content
        assert "settings.nosql.neo4j.uri" in service_content
        assert 'uri: str = "neo4j://neo4j:7687"' in nosql_settings_content
        assert "neo4j>=6.2.0" in pyproject_content
        assert "neo4j:" in compose_content
        assert (
            "SETTINGS__NOSQL__NEO4J__URI: neo4j://neo4j:7687"
            in compose_content
        )
        assert "SETTINGS__NOSQL__NEO4J__URI=neo4j://localhost:7687" in (
            env_example_content
        )


@pytest.mark.parametrize("design", ("ddd", "mvc"))
def test_create_generates_multiple_nosql_templates(
    tmp_path: Path,
    design: str,
) -> None:
    project_dir = tmp_path / f"{design}-multi-nosql"
    fake_bin = create_fake_package_managers(tmp_path)
    result = run_create_command(
        project_dir,
        design,
        "sqlalchemy",
        bin_dir=fake_bin,
        nosql="mongodb,neo4j",
    )

    assert result.returncode == 0, f"CLI create failed: {result.stderr}"

    app_dir = project_dir / "src" / "app"
    pyproject_content = (project_dir / "pyproject.toml").read_text()
    compose_content = (project_dir / "docker-compose.yml").read_text()
    nosql_settings = app_dir / "config" / "nosql"
    nosql_init_content = (nosql_settings / "__init__.py").read_text()

    assert (nosql_settings / "mongodb.py").exists()
    assert (nosql_settings / "neo4j.py").exists()
    assert 'nosql = ["mongodb", "neo4j"]' in pyproject_content
    assert "pymongo>=4.11.0" in pyproject_content
    assert "neo4j>=6.2.0" in pyproject_content
    assert "mongodb:" in compose_content
    assert "neo4j:" in compose_content
    assert "SETTINGS__NOSQL__MONGODB__HOST: mongodb" in compose_content
    assert "SETTINGS__NOSQL__NEO4J__URI: neo4j://neo4j:7687" in (
        compose_content
    )
    assert "mongodb: _mongodb.Settings = _mongodb.Settings()" in (
        nosql_init_content
    )
    assert "neo4j: _neo4j.Settings = _neo4j.Settings()" in nosql_init_content

    if design == "ddd":
        nosql_dir = app_dir / "infrastructure" / "nosql"
        assert (nosql_dir / "mongodb" / "services" / "engine.py").exists()
        assert (nosql_dir / "neo4j" / "services" / "engine.py").exists()
    else:
        nosql_dir = app_dir / "nosql"
        assert (nosql_dir / "mongodb" / "services.py").exists()
        assert (nosql_dir / "neo4j" / "services.py").exists()


def test_create_composes_broker_and_multiple_nosql_templates(
    tmp_path: Path,
) -> None:
    project_dir = tmp_path / "broker-and-multi-nosql"
    fake_bin = create_fake_package_managers(tmp_path)
    result = run_create_command(
        project_dir,
        "ddd",
        "sqlalchemy",
        bin_dir=fake_bin,
        broker="kafka",
        nosql="mongodb,neo4j",
    )

    assert result.returncode == 0, f"CLI create failed: {result.stderr}"

    app_dir = project_dir / "src" / "app"
    compose_content = (project_dir / "docker-compose.yml").read_text()

    assert (app_dir / "infrastructure" / "broker" / "services.py").exists()
    assert (
        app_dir / "infrastructure" / "nosql" / "mongodb" / "services"
    ).exists()
    assert (
        app_dir / "infrastructure" / "nosql" / "neo4j" / "services"
    ).exists()
    assert "kafka:" in compose_content
    assert "mongodb:" in compose_content
    assert "neo4j:" in compose_content
