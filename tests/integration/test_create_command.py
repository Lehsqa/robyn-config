import json
import os
import py_compile
import shutil
import subprocess
import sys
import time
import tomllib
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
    worker: str | None = None,
    worker_exp_mode: bool = False,
    scheduler: bool = False,
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
    if worker is not None:
        cmd.extend(["--worker", worker])
    if worker_exp_mode:
        cmd.append("--worker-exp-mode")
    if scheduler:
        cmd.append("--scheduler")
    cmd.append(str(destination))
    return subprocess.run(
        cmd,
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )


def load_compose_services(project_dir: Path) -> dict[str, dict[str, object]]:
    """Return the normalized Docker Compose services for a scaffold."""
    if shutil.which("docker") is None:
        pytest.skip("docker CLI is not available")
    compose_version = subprocess.run(
        ["docker", "compose", "version"],
        capture_output=True,
        text=True,
    )
    if compose_version.returncode != 0:
        pytest.skip("docker compose is not available")

    shutil.copy2(project_dir / ".env.example", project_dir / ".env")
    config_result = subprocess.run(
        ["docker", "compose", "config", "--format", "json"],
        cwd=project_dir,
        capture_output=True,
        text=True,
    )
    assert config_result.returncode == 0, config_result.stderr
    return json.loads(config_result.stdout)["services"]


def assert_generated_worker_modules_import(
    project_dir: Path,
    design: str,
    worker: str,
) -> None:
    """Import generated worker modules with lightweight external dependency stubs."""
    worker_package = (
        "app.infrastructure.worker" if design == "ddd" else "app.worker"
    )
    module = {
        "celery": f"{worker_package}.tasks",
        "rq": f"{worker_package}.cron",
        "dramatiq": f"{worker_package}.scheduler",
        "huey": f"{worker_package}.tasks",
    }[worker]
    script = f"""
import importlib
import sys
import types

sys.path.insert(0, {str(project_dir / "src")!r})

def stub(name, package=False):
    module = types.ModuleType(name)
    if package:
        module.__path__ = []
    sys.modules[name] = module
    return module

app = stub("app", package=True)
app.__path__ = [{str(project_dir / "src" / "app")!r}]
if {design!r} == "ddd":
    infrastructure = stub("app.infrastructure", package=True)
    infrastructure.__path__ = [{str(project_dir / "src" / "app" / "infrastructure")!r}]

config = stub("app.config")
config.settings = types.SimpleNamespace(
    worker=types.SimpleNamespace(
        queue="app.workers",
        broker_url="redis://valkey:6379/1",
        result_backend="redis://valkey:6379/3",
        redis_url="redis://valkey:6379/1",
        rabbitmq_url=None,
    ),
)

class CeleryConfig:
    def update(self, **kwargs):
        self.settings = kwargs

class Celery:
    def __init__(self, *args, **kwargs):
        self.conf = CeleryConfig()

    def task(self, function):
        return function

celery = stub("celery")
celery.Celery = Celery

class Redis:
    @classmethod
    def from_url(cls, url):
        return cls()

redis = stub("redis")
redis.Redis = Redis

class Queue:
    def __init__(self, *args, **kwargs):
        pass

class Repeat:
    def __init__(self, *args, **kwargs):
        pass

rq = stub("rq", package=True)
rq.Queue = Queue
rq.Repeat = Repeat
rq_cron = stub("rq.cron")
rq_cron.register = lambda *args, **kwargs: None

def actor(*args, **kwargs):
    def decorate(function):
        function.send = lambda *args, **kwargs: None
        return function
    return decorate

dramatiq = stub("dramatiq", package=True)
dramatiq.actor = actor
dramatiq.set_broker = lambda broker: None
stub("dramatiq.brokers", package=True)

class Broker:
    def __init__(self, *args, **kwargs):
        pass

dramatiq_redis = stub("dramatiq.brokers.redis")
dramatiq_redis.RedisBroker = Broker
dramatiq_rabbitmq = stub("dramatiq.brokers.rabbitmq")
dramatiq_rabbitmq.RabbitmqBroker = Broker

stub("apscheduler", package=True)
stub("apscheduler.schedulers", package=True)
apscheduler_blocking = stub("apscheduler.schedulers.blocking")

class BlockingScheduler:
    def add_job(self, *args, **kwargs):
        pass

apscheduler_blocking.BlockingScheduler = BlockingScheduler
stub("apscheduler.triggers", package=True)
apscheduler_cron = stub("apscheduler.triggers.cron")

class CronTrigger:
    @classmethod
    def from_crontab(cls, expression):
        return cls()

apscheduler_cron.CronTrigger = CronTrigger

def decorator(*args, **kwargs):
    return lambda function: function

class RedisHuey:
    def __init__(self, *args, **kwargs):
        pass

    task = decorator
    periodic_task = decorator

huey = stub("huey")
huey.RedisHuey = RedisHuey
huey.crontab = lambda **kwargs: kwargs

importlib.import_module({module!r})
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=project_dir,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


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
        assert "RABBITMQ_DEFAULT_USER=app" in env_example_content
        assert "RABBITMQ_DEFAULT_PASS=app" in env_example_content
        assert "SETTINGS__BROKER__PORT=5672" in env_example_content
        assert "SETTINGS__BROKER__USER=app" in env_example_content
        assert "SETTINGS__BROKER__PASSWORD=app" in env_example_content
        broker_settings = (app_dir / "config" / "broker.py").read_text()
        assert 'user: str = "app"' in broker_settings
        assert 'password: str = "app"' in broker_settings
        services = load_compose_services(project_dir)
        rabbitmq_environment = services["rabbitmq"]["environment"]
        assert rabbitmq_environment["RABBITMQ_DEFAULT_USER"] == "app"
        assert rabbitmq_environment["RABBITMQ_DEFAULT_PASS"] == "app"
        app_environment = services["app"]["environment"]
        assert app_environment["SETTINGS__BROKER__USER"] == "app"
        assert app_environment["SETTINGS__BROKER__PASSWORD"] == "app"
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


@pytest.mark.parametrize("design", ("ddd", "mvc"))
@pytest.mark.parametrize(
    ("worker", "modules", "periodic_marker", "settings_markers"),
    [
        (
            "celery",
            ("app.py", "tasks.py"),
            "beat_schedule",
            (
                'broker_url: str = "redis://valkey:6379/1"',
                'result_backend: str = "redis://valkey:6379/3"',
            ),
        ),
        (
            "rq",
            ("queue.py", "tasks.py", "cron.py"),
            "register(",
            ('redis_url: str = "redis://valkey:6379/1"',),
        ),
        (
            "dramatiq",
            ("broker.py", "tasks.py", "scheduler.py"),
            "add_job(",
            (
                'backend: str = "redis"',
                'redis_url: str | None = "redis://valkey:6379/1"',
            ),
        ),
        (
            "huey",
            ("app.py", "tasks.py"),
            "@huey.periodic_task",
            ('redis_url: str = "redis://valkey:6379/1"',),
        ),
    ],
)
def test_create_generates_selected_worker_template(
    tmp_path: Path,
    design: str,
    worker: str,
    modules: tuple[str, ...],
    periodic_marker: str,
    settings_markers: tuple[str, ...],
) -> None:
    project_dir = tmp_path / f"{design}-{worker}-worker"
    fake_bin = create_fake_package_managers(tmp_path)
    result = run_create_command(
        project_dir,
        design,
        "sqlalchemy",
        bin_dir=fake_bin,
        worker=worker,
        worker_exp_mode=worker == "dramatiq",
        scheduler=True,
    )

    assert result.returncode == 0, f"CLI create failed: {result.stderr}"

    app_dir = project_dir / "src" / "app"
    settings_content = (app_dir / "config" / "__init__.py").read_text()
    worker_settings = app_dir / "config" / "worker.py"
    runtime_dir = (
        app_dir / "infrastructure" / "worker"
        if design == "ddd"
        else app_dir / "worker"
    )

    assert "from . import worker as _worker" in settings_content
    assert "worker: _worker.Settings = _worker.Settings()" in settings_content
    assert worker_settings.exists()
    worker_settings_content = worker_settings.read_text()
    assert 'queue: str = "app.workers"' in worker_settings_content
    for settings_marker in settings_markers:
        assert settings_marker in worker_settings_content
    assert (runtime_dir / "__init__.py").exists()

    for module in modules:
        assert (runtime_dir / module).exists()

    periodic_content = "\n".join(
        (runtime_dir / module).read_text() for module in modules
    )
    assert "example_task" in periodic_content
    assert "periodic_job" in periodic_content
    assert periodic_marker in periodic_content
    if worker == "celery":
        assert "broker_transport_options" not in periodic_content

    for source in (worker_settings, *runtime_dir.glob("*.py")):
        py_compile.compile(str(source), doraise=True)
    assert_generated_worker_modules_import(project_dir, design, worker)


@pytest.mark.parametrize("design", ("ddd", "mvc"))
@pytest.mark.parametrize(
    ("worker", "runtime_file", "active_marker"),
    [
        ("celery", "app.py", "beat_schedule"),
        ("huey", "tasks.py", "@huey.periodic_task"),
    ],
)
def test_create_without_scheduler_omits_active_periodic_registration(
    tmp_path: Path,
    design: str,
    worker: str,
    runtime_file: str,
    active_marker: str,
) -> None:
    """Workers should not register periodic jobs without scheduler opt-in."""
    project_dir = tmp_path / f"{design}-{worker}-without-scheduler"
    fake_bin = create_fake_package_managers(tmp_path)
    result = run_create_command(
        project_dir,
        design,
        "sqlalchemy",
        bin_dir=fake_bin,
        worker=worker,
    )

    assert result.returncode == 0, f"CLI create failed: {result.stderr}"

    app_dir = project_dir / "src" / "app"
    runtime_dir = (
        app_dir / "infrastructure" / "worker"
        if design == "ddd"
        else app_dir / "worker"
    )
    assert active_marker not in (runtime_dir / runtime_file).read_text()
    py_compile.compile(str(runtime_dir / runtime_file), doraise=True)
    assert (
        "\n  worker-scheduler:\n"
        not in (project_dir / "docker-compose.yml").read_text()
    )


@pytest.mark.parametrize(
    ("worker", "command_marker"),
    [
        ("celery", "celery -A app.worker.app beat"),
        ("rq", "--with-scheduler"),
        ("dramatiq", "python -m app.worker.scheduler"),
    ],
)
def test_create_without_scheduler_omits_scheduler_commands_from_readme(
    tmp_path: Path,
    worker: str,
    command_marker: str,
) -> None:
    """README commands should not advertise scheduler behavior without opt-in."""
    project_dir = tmp_path / f"{worker}-without-scheduler-readme"
    fake_bin = create_fake_package_managers(tmp_path)
    result = run_create_command(
        project_dir,
        "mvc",
        "sqlalchemy",
        bin_dir=fake_bin,
        worker=worker,
    )

    assert result.returncode == 0, f"CLI create failed: {result.stderr}"
    assert command_marker not in (project_dir / "README.md").read_text()


@pytest.mark.parametrize("design", ("ddd", "mvc"))
def test_create_generates_celery_kafka_transport_options(
    tmp_path: Path,
    design: str,
) -> None:
    project_dir = tmp_path / f"{design}-celery-kafka-worker"
    fake_bin = create_fake_package_managers(tmp_path)
    result = run_create_command(
        project_dir,
        design,
        "sqlalchemy",
        bin_dir=fake_bin,
        broker="kafka",
        worker="celery",
        worker_exp_mode=True,
    )

    assert result.returncode == 0, f"CLI create failed: {result.stderr}"

    app_dir = project_dir / "src" / "app"
    worker_settings = (app_dir / "config" / "worker.py").read_text()
    runtime_dir = (
        app_dir / "infrastructure" / "worker"
        if design == "ddd"
        else app_dir / "worker"
    )
    worker_app = (runtime_dir / "app.py").read_text()

    assert 'broker_url: str = "confluentkafka://kafka:9092"' in (
        worker_settings
    )
    assert 'result_backend: str = "redis://valkey:6379/3"' in worker_settings
    assert 'broker_transport_options={"allow_create_topics": True}' in (
        worker_app
    )


@pytest.mark.parametrize("design", ("ddd", "mvc"))
def test_create_generates_dramatiq_rabbitmq_settings(
    tmp_path: Path,
    design: str,
) -> None:
    project_dir = tmp_path / f"{design}-dramatiq-rabbitmq-worker"
    fake_bin = create_fake_package_managers(tmp_path)
    result = run_create_command(
        project_dir,
        design,
        "sqlalchemy",
        bin_dir=fake_bin,
        broker="rabbitmq",
        worker="dramatiq",
    )

    assert result.returncode == 0, f"CLI create failed: {result.stderr}"

    worker_settings = (
        project_dir / "src" / "app" / "config" / "worker.py"
    ).read_text()
    assert 'backend: str = "rabbitmq"' in worker_settings
    assert "redis_url: str | None = None" in worker_settings
    assert (
        'rabbitmq_url: str | None = "amqp://app:app@rabbitmq:5672//"'
        in worker_settings
    )


@pytest.mark.parametrize("package_manager", ("uv", "poetry"))
@pytest.mark.parametrize(
    ("worker", "broker", "worker_exp_mode", "scheduler", "dependency_markers"),
    [
        ("celery", None, False, False, ("celery[redis]",)),
        ("celery", "rabbitmq", False, True, ("celery[redis]",)),
        (
            "celery",
            "kafka",
            True,
            False,
            ("celery[redis]", "confluent-kafka"),
        ),
        ("rq", None, False, False, ("rq",)),
        ("dramatiq", None, False, False, ("dramatiq[redis]",)),
        ("dramatiq", "rabbitmq", False, False, ("dramatiq[rabbitmq]",)),
        ("dramatiq", None, True, True, ("dramatiq[redis]", "apscheduler")),
        ("huey", None, False, True, ("huey",)),
    ],
)
def test_create_generates_worker_dependencies_and_metadata(
    tmp_path: Path,
    package_manager: str,
    worker: str,
    broker: str | None,
    worker_exp_mode: bool,
    scheduler: bool,
    dependency_markers: tuple[str, ...],
) -> None:
    project_dir = tmp_path / (
        f"{package_manager}-{worker}-{broker or 'none'}-{worker_exp_mode}"
    )
    fake_bin = create_fake_package_managers(tmp_path)
    result = run_create_command(
        project_dir,
        "ddd",
        "sqlalchemy",
        package_manager=package_manager,
        bin_dir=fake_bin,
        broker=broker,
        worker=worker,
        worker_exp_mode=worker_exp_mode,
        scheduler=scheduler,
    )

    assert result.returncode == 0, f"CLI create failed: {result.stderr}"

    pyproject_content = (project_dir / "pyproject.toml").read_text()
    parsed_pyproject = tomllib.loads(pyproject_content)
    metadata = parsed_pyproject["tool"]["robyn-config"]
    assert metadata["worker"] == worker
    assert metadata["worker_exp_mode"] is worker_exp_mode
    assert metadata["scheduler"] is scheduler
    if package_manager == "uv":
        for dependency_marker in dependency_markers:
            assert dependency_marker in pyproject_content
    else:
        dependencies = parsed_pyproject["tool"]["poetry"]["dependencies"]
        for dependency_marker in dependency_markers:
            if "[" in dependency_marker:
                dependency, extras = dependency_marker.rstrip("]").split("[")
                assert extras in dependencies[dependency]["extras"]
            else:
                assert dependency_marker in dependencies


@pytest.mark.parametrize(
    (
        "design",
        "worker",
        "worker_exp_mode",
        "scheduler",
        "worker_command",
        "scheduler_command",
    ),
    [
        (
            "ddd",
            "celery",
            False,
            True,
            (
                "celery",
                "-A",
                "app.infrastructure.worker.app",
                "worker",
                "--queues",
                "app.workers",
            ),
            ("celery", "-A", "app.infrastructure.worker.app", "beat"),
        ),
        (
            "mvc",
            "rq",
            False,
            False,
            (
                "rq",
                "worker",
                "app.workers",
                "--url",
                "redis://valkey:6379/1",
            ),
            None,
        ),
        (
            "mvc",
            "rq",
            False,
            True,
            (
                "rq",
                "worker",
                "app.workers",
                "--url",
                "redis://valkey:6379/1",
                "--with-scheduler",
            ),
            None,
        ),
        (
            "ddd",
            "rq",
            True,
            True,
            (
                "rq",
                "worker",
                "app.workers",
                "--url",
                "redis://valkey:6379/1",
            ),
            (
                "rq",
                "cron",
                "app.infrastructure.worker.cron",
                "--url",
                "redis://valkey:6379/1",
            ),
        ),
        (
            "mvc",
            "dramatiq",
            False,
            False,
            ("dramatiq", "app.worker.tasks", "--queues", "app.workers"),
            None,
        ),
        (
            "ddd",
            "dramatiq",
            True,
            True,
            (
                "dramatiq",
                "app.infrastructure.worker.tasks",
                "--queues",
                "app.workers",
            ),
            ("python", "-m", "app.infrastructure.worker.scheduler"),
        ),
        (
            "mvc",
            "huey",
            False,
            False,
            ("huey_consumer.py", "app.worker.tasks.huey"),
            None,
        ),
    ],
)
def test_create_generates_worker_compose_services(
    tmp_path: Path,
    design: str,
    worker: str,
    worker_exp_mode: bool,
    scheduler: bool,
    worker_command: tuple[str, ...],
    scheduler_command: tuple[str, ...] | None,
) -> None:
    project_dir = tmp_path / f"{design}-{worker}-{worker_exp_mode}-compose"
    fake_bin = create_fake_package_managers(tmp_path)
    result = run_create_command(
        project_dir,
        design,
        "sqlalchemy",
        bin_dir=fake_bin,
        worker=worker,
        worker_exp_mode=worker_exp_mode,
        scheduler=scheduler,
    )

    assert result.returncode == 0, f"CLI create failed: {result.stderr}"

    compose_content = (project_dir / "docker-compose.yml").read_text()
    assert "\n  worker:\n" in compose_content
    services = load_compose_services(project_dir)
    worker_service = services["worker"]
    assert worker_service["entrypoint"] == []
    assert worker_service["command"] == list(worker_command)
    assert "      - ./src/app:/app/src/app" in compose_content
    assert "SETTINGS__WORKER__QUEUE: app.workers" in compose_content
    assert (
        "SETTINGS__WORKER__REDIS_URL: redis://valkey:6379/1"
        in (compose_content)
        or worker == "celery"
    )
    assert (
        "      valkey:\n        condition: service_healthy" in compose_content
    )
    if scheduler_command is None:
        assert "\n  worker-scheduler:\n" not in compose_content
    else:
        assert "\n  worker-scheduler:\n" in compose_content
        scheduler_service = services["worker-scheduler"]
        assert scheduler_service["entrypoint"] == []
        assert scheduler_service["command"] == list(scheduler_command)


@pytest.mark.parametrize(
    (
        "worker",
        "broker",
        "worker_exp_mode",
        "scheduler",
        "env_markers",
        "compose_markers",
        "queue_dependency",
        "celery_result_dependency",
    ),
    [
        (
            "rq",
            None,
            False,
            False,
            ("SETTINGS__WORKER__REDIS_URL=redis://localhost:6379/1",),
            ("SETTINGS__WORKER__REDIS_URL: redis://valkey:6379/1",),
            "valkey",
            None,
        ),
        (
            "rq",
            "redis",
            False,
            False,
            ("SETTINGS__WORKER__REDIS_URL=redis://localhost:6380/2",),
            ("SETTINGS__WORKER__REDIS_URL: redis://redis-broker:6379/2",),
            "redis-broker",
            None,
        ),
        (
            "celery",
            "rabbitmq",
            False,
            True,
            (
                "SETTINGS__WORKER__BROKER_URL=amqp://app:app@localhost:5672//",
                "SETTINGS__WORKER__RESULT_BACKEND=redis://localhost:6379/3",
            ),
            (
                "SETTINGS__WORKER__BROKER_URL: amqp://${RABBITMQ_DEFAULT_USER:-app}:${RABBITMQ_DEFAULT_PASS:-app}@rabbitmq:5672//",
                "SETTINGS__WORKER__RESULT_BACKEND: redis://valkey:6379/3",
            ),
            "rabbitmq",
            "valkey",
        ),
        (
            "celery",
            "kafka",
            True,
            True,
            (
                "SETTINGS__WORKER__BROKER_URL=confluentkafka://localhost:29092",
                "SETTINGS__WORKER__RESULT_BACKEND=redis://localhost:6379/3",
            ),
            (
                "SETTINGS__WORKER__BROKER_URL: confluentkafka://kafka:9092",
                "SETTINGS__WORKER__RESULT_BACKEND: redis://valkey:6379/3",
            ),
            "kafka",
            "valkey",
        ),
        (
            "dramatiq",
            "rabbitmq",
            False,
            False,
            (
                "SETTINGS__WORKER__BACKEND=rabbitmq",
                "SETTINGS__WORKER__RABBITMQ_URL=amqp://app:app@localhost:5672//",
            ),
            (
                "SETTINGS__WORKER__BACKEND: rabbitmq",
                "SETTINGS__WORKER__RABBITMQ_URL: amqp://${RABBITMQ_DEFAULT_USER:-app}:${RABBITMQ_DEFAULT_PASS:-app}@rabbitmq:5672//",
            ),
            "rabbitmq",
            None,
        ),
    ],
)
def test_create_generates_worker_env_and_compose_queue_resolution(
    tmp_path: Path,
    worker: str,
    broker: str | None,
    worker_exp_mode: bool,
    scheduler: bool,
    env_markers: tuple[str, ...],
    compose_markers: tuple[str, ...],
    queue_dependency: str,
    celery_result_dependency: str | None,
) -> None:
    project_dir = tmp_path / (
        f"{worker}-{broker or 'none'}-{worker_exp_mode}-resolution"
    )
    fake_bin = create_fake_package_managers(tmp_path)
    result = run_create_command(
        project_dir,
        "ddd",
        "sqlalchemy",
        bin_dir=fake_bin,
        broker=broker,
        worker=worker,
        worker_exp_mode=worker_exp_mode,
        scheduler=scheduler,
    )

    assert result.returncode == 0, f"CLI create failed: {result.stderr}"

    env_example_content = (project_dir / ".env.example").read_text()
    compose_content = (project_dir / "docker-compose.yml").read_text()
    assert "SETTINGS__WORKER__QUEUE=app.workers" in env_example_content
    assert "SETTINGS__WORKER__QUEUE: app.workers" in compose_content
    for marker in env_markers:
        assert marker in env_example_content
    for marker in compose_markers:
        assert compose_content.count(marker) >= 2
    worker_section = compose_content.split("\n  worker:\n", maxsplit=1)[1]
    worker_section = worker_section.split(
        "\n  worker-scheduler:\n", maxsplit=1
    )[0]
    assert (
        f"      {queue_dependency}:\n" "        condition: service_healthy"
    ) in worker_section or queue_dependency == "kafka"
    if queue_dependency == "kafka":
        assert "      kafka:\n        condition: service_started" in (
            worker_section
        )
    if celery_result_dependency is not None:
        result_dependency = (
            f"      {celery_result_dependency}:\n"
            "        condition: service_healthy"
        )
        assert result_dependency in worker_section
        scheduler_section = compose_content.split(
            "\n  worker-scheduler:\n", maxsplit=1
        )[1]
        assert result_dependency in scheduler_section


@pytest.mark.parametrize(
    (
        "worker",
        "worker_exp_mode",
        "scheduler",
        "command_marker",
        "warning_marker",
    ),
    [
        ("celery", False, True, "celery -A app.worker.app beat", None),
        (
            "celery",
            True,
            False,
            "celery -A app.worker.app worker --queues app.workers",
            "Kafka transport is experimental and supports only one Celery worker.",
        ),
        (
            "rq",
            True,
            True,
            "rq cron app.worker.cron --url redis://localhost:6379/1",
            "RQ cron is beta.",
        ),
        (
            "dramatiq",
            True,
            True,
            "python -m app.worker.scheduler",
            "APScheduler integration is experimental.",
        ),
        (
            "huey",
            False,
            True,
            "huey_consumer.py app.worker.tasks.huey",
            None,
        ),
    ],
)
def test_create_documents_selected_worker_commands_and_warnings(
    tmp_path: Path,
    worker: str,
    worker_exp_mode: bool,
    scheduler: bool,
    command_marker: str,
    warning_marker: str | None,
) -> None:
    project_dir = tmp_path / f"{worker}-{worker_exp_mode}-readme"
    fake_bin = create_fake_package_managers(tmp_path)
    broker = "kafka" if worker == "celery" and worker_exp_mode else None
    result = run_create_command(
        project_dir,
        "mvc",
        "sqlalchemy",
        bin_dir=fake_bin,
        broker=broker,
        worker=worker,
        worker_exp_mode=worker_exp_mode,
        scheduler=scheduler,
    )

    assert result.returncode == 0, f"CLI create failed: {result.stderr}"

    readme_content = (project_dir / "README.md").read_text()
    assert command_marker in readme_content
    assert "`app.workers`" in readme_content
    assert "`worker`" in readme_content
    if warning_marker is not None:
        assert warning_marker in readme_content


def test_create_renders_compose_config_for_worker_services(
    tmp_path: Path,
) -> None:
    project_dir = tmp_path / "worker-compose-config"
    fake_bin = create_fake_package_managers(tmp_path)
    result = run_create_command(
        project_dir,
        "ddd",
        "sqlalchemy",
        bin_dir=fake_bin,
        broker="rabbitmq",
        worker="celery",
        scheduler=True,
    )
    assert result.returncode == 0, f"CLI create failed: {result.stderr}"

    services = load_compose_services(project_dir)
    assert services["worker"]["entrypoint"] == []
    assert services["worker"]["command"] == [
        "celery",
        "-A",
        "app.infrastructure.worker.app",
        "worker",
        "--queues",
        "app.workers",
    ]
    assert services["worker-scheduler"]["entrypoint"] == []
    assert services["worker-scheduler"]["command"] == [
        "celery",
        "-A",
        "app.infrastructure.worker.app",
        "beat",
    ]
    assert set(services["worker"]["depends_on"]) == {"rabbitmq", "valkey"}
    assert set(services["worker-scheduler"]["depends_on"]) == {
        "rabbitmq",
        "valkey",
    }


@pytest.mark.skipif(
    os.environ.get("RUN_DOCKER_SERVICE_TESTS") != "1",
    reason="set RUN_DOCKER_SERVICE_TESTS=1 to run Docker service smoke tests",
)
def test_create_starts_rabbitmq_with_worker_credentials(
    tmp_path: Path,
) -> None:
    """RabbitMQ should create credentials usable by separate worker containers."""
    if shutil.which("docker") is None:
        pytest.skip("docker CLI is not available")

    project_dir = tmp_path / "rabbitmq-worker-smoke"
    fake_bin = create_fake_package_managers(tmp_path)
    result = run_create_command(
        project_dir,
        "ddd",
        "sqlalchemy",
        bin_dir=fake_bin,
        broker="rabbitmq",
        worker="celery",
    )
    assert result.returncode == 0, f"CLI create failed: {result.stderr}"

    env_content = (project_dir / ".env.example").read_text()
    env_content = env_content.replace(
        "RABBITMQ_DEFAULT_USER=app",
        "RABBITMQ_DEFAULT_USER=worker-app",
    ).replace(
        "RABBITMQ_DEFAULT_PASS=app",
        "RABBITMQ_DEFAULT_PASS=worker-pass",
    )
    (project_dir / ".env").write_text(env_content)
    try:
        config_result = subprocess.run(
            ["docker", "compose", "config", "--format", "json"],
            cwd=project_dir,
            capture_output=True,
            text=True,
        )
        assert config_result.returncode == 0, config_result.stderr
        compose_config = json.loads(config_result.stdout)
        assert (
            compose_config["services"]["worker"]["environment"][
                "SETTINGS__WORKER__BROKER_URL"
            ]
            == "amqp://worker-app:worker-pass@rabbitmq:5672//"
        )
        network = compose_config["networks"]["default"]["name"]

        up_result = subprocess.run(
            ["docker", "compose", "up", "-d", "rabbitmq"],
            cwd=project_dir,
            capture_output=True,
            text=True,
        )
        assert up_result.returncode == 0, up_result.stderr

        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            auth_result = subprocess.run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "--network",
                    network,
                    "rabbitmq:3.13-management-alpine",
                    "rabbitmqadmin",
                    "--host",
                    "rabbitmq",
                    "--username",
                    "worker-app",
                    "--password",
                    "worker-pass",
                    "list",
                    "users",
                ],
                capture_output=True,
                text=True,
            )
            if auth_result.returncode == 0:
                break
            time.sleep(2)
        else:
            pytest.fail(auth_result.stderr)
    finally:
        subprocess.run(
            ["docker", "compose", "down", "-v", "--remove-orphans"],
            cwd=project_dir,
            capture_output=True,
            text=True,
        )
