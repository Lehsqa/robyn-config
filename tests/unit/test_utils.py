import pytest
from itertools import product
from pathlib import Path
from unittest.mock import patch

import src.create as create_module
import src.create.utils as create_utils
from src.create.utils import _config as create_config
from src.create.utils import _filesystem as create_filesystem
from src.add import utils as add_utils
from src.add.utils import _injection as add_injection
from src.add.utils import _paths as add_paths

# --- Tests for src/create/utils.py ---


def test_collect_common_items(tmp_path):
    """Test that finding common items correctly filters based on ORM."""
    common_dir = tmp_path / "common"
    common_dir.mkdir()
    (common_dir / "Makefile").touch()
    (common_dir / "README.md.jinja2").touch()
    (common_dir / "alembic.ini.jinja2").touch()
    (common_dir / "compose").mkdir()
    (common_dir / ".DS_Store").touch()

    with patch("src.create.utils._filesystem.COMMON_DIR", common_dir):
        # SQLAlchemy should include everything (alembic.ini is kept)
        items_sql = create_filesystem._collect_common_items("sqlalchemy", "uv")
        assert Path("Makefile") in items_sql
        assert Path("README.md") in items_sql
        assert Path("alembic.ini") in items_sql
        assert Path("uv.lock") in items_sql
        assert Path("poetry.lock") not in items_sql
        assert Path("compose") not in items_sql
        assert Path(".DS_Store") not in items_sql

        # Tortoise should exclude alembic.ini
        items_tortoise = create_filesystem._collect_common_items(
            "tortoise", "poetry"
        )
        assert Path("Makefile") in items_tortoise
        assert Path("README.md") in items_tortoise
        assert Path("alembic.ini") not in items_tortoise
        assert Path("poetry.lock") in items_tortoise
        assert Path("uv.lock") not in items_tortoise


def test_get_template_config():
    """Test that template config is retrieved correctly."""
    config = create_config._get_template_config(
        "ddd", "sqlalchemy", "mypro", "uv", "none"
    )
    assert config["design"] == "ddd"
    assert config["orm"] == "sqlalchemy"
    assert config["name"] == "mypro"
    assert config["package_manager"] == "uv"
    assert config["uid"] == "none"

    with pytest.raises(SystemExit):
        create_config._get_template_config(
            "invalid", "orm", "proj", "uv", "none"
        )


def test_uid_choices_constant():
    """Test that UID choices include the supported options in fallback order."""
    assert "none" in create_config.UID_CHOICES
    assert "sparkid" in create_config.UID_CHOICES
    assert create_config.UID_CHOICES[0] == "none"


def test_broker_choices_include_none_and_canonical_values():
    """Broker choices should mirror UID defaults without alias normalization."""
    assert create_config.BROKER_CHOICES == (
        "none",
        "redis",
        "rabbitmq",
        "kafka",
    )
    assert "rabytmq" not in create_config.BROKER_CHOICES


def test_worker_choices_include_none_and_supported_values():
    """Worker choices should expose the canonical worker implementations."""
    expected = ("none", "celery", "rq", "dramatiq", "huey")

    assert create_config.WORKER_CHOICES == expected
    assert create_config.INTERACTIVE_WORKER_CHOICES == expected


def test_worker_config_exports_are_available_from_create_modules():
    """Create module exports should expose worker config utilities."""
    assert create_utils.WORKER_CHOICES is create_config.WORKER_CHOICES
    assert (
        create_utils.INTERACTIVE_WORKER_CHOICES
        is create_config.INTERACTIVE_WORKER_CHOICES
    )
    assert create_module.WORKER_CHOICES is create_config.WORKER_CHOICES
    assert (
        create_module.INTERACTIVE_WORKER_CHOICES
        is create_config.INTERACTIVE_WORKER_CHOICES
    )


def _expected_worker_config(
    worker,
    worker_exp_mode=False,
    scheduler=False,
    **overrides,
):
    return {
        "worker": worker,
        "worker_exp_mode": worker_exp_mode,
        "scheduler": scheduler,
        "worker_queue": None,
        "worker_backend": None,
        "worker_redis_service": None,
        "worker_redis_db": None,
        "worker_result_redis_service": None,
        "worker_result_redis_db": None,
        "worker_scheduler": None,
        **overrides,
    }


@pytest.mark.parametrize(
    ("worker", "broker", "worker_exp_mode", "scheduler", "expected"),
    [
        *[
            ("none", broker, False, False, _expected_worker_config("none"))
            for broker in ("none", "redis", "rabbitmq", "kafka")
        ],
        (
            "celery",
            "none",
            False,
            False,
            _expected_worker_config(
                "celery",
                worker_queue="app.workers",
                worker_backend="redis",
                worker_redis_service="valkey",
                worker_redis_db=1,
                worker_result_redis_service="valkey",
                worker_result_redis_db=3,
            ),
        ),
        (
            "celery",
            "redis",
            False,
            False,
            _expected_worker_config(
                "celery",
                worker_queue="app.workers",
                worker_backend="redis",
                worker_redis_service="redis-broker",
                worker_redis_db=2,
                worker_result_redis_service="redis-broker",
                worker_result_redis_db=3,
            ),
        ),
        (
            "celery",
            "rabbitmq",
            False,
            False,
            _expected_worker_config(
                "celery",
                worker_queue="app.workers",
                worker_backend="rabbitmq",
                worker_result_redis_service="valkey",
                worker_result_redis_db=3,
            ),
        ),
        (
            "celery",
            "kafka",
            False,
            False,
            _expected_worker_config(
                "celery",
                worker_queue="app.workers",
                worker_backend="redis",
                worker_redis_service="valkey",
                worker_redis_db=1,
                worker_result_redis_service="valkey",
                worker_result_redis_db=3,
            ),
        ),
        (
            "celery",
            "kafka",
            True,
            False,
            _expected_worker_config(
                "celery",
                worker_exp_mode=True,
                worker_queue="app.workers",
                worker_backend="kafka",
                worker_result_redis_service="valkey",
                worker_result_redis_db=3,
            ),
        ),
        *[
            (
                "rq",
                broker,
                worker_exp_mode,
                worker_exp_mode,
                _expected_worker_config(
                    "rq",
                    worker_exp_mode=worker_exp_mode,
                    scheduler=worker_exp_mode,
                    worker_queue="app.workers",
                    worker_backend="redis",
                    worker_redis_service=(
                        "redis-broker" if broker == "redis" else "valkey"
                    ),
                    worker_redis_db=2 if broker == "redis" else 1,
                    worker_scheduler="rq-cron" if worker_exp_mode else None,
                ),
            )
            for broker in ("none", "redis", "rabbitmq", "kafka")
            for worker_exp_mode in (False, True)
        ],
        *[
            (
                "dramatiq",
                broker,
                worker_exp_mode,
                worker_exp_mode,
                _expected_worker_config(
                    "dramatiq",
                    worker_exp_mode=worker_exp_mode,
                    scheduler=worker_exp_mode,
                    worker_queue="app.workers",
                    worker_backend=(
                        "rabbitmq" if broker == "rabbitmq" else "redis"
                    ),
                    worker_redis_service=(
                        None
                        if broker == "rabbitmq"
                        else "redis-broker" if broker == "redis" else "valkey"
                    ),
                    worker_redis_db=(
                        None
                        if broker == "rabbitmq"
                        else 2 if broker == "redis" else 1
                    ),
                    worker_scheduler=(
                        "apscheduler" if worker_exp_mode else None
                    ),
                ),
            )
            for broker in ("none", "redis", "rabbitmq", "kafka")
            for worker_exp_mode in (False, True)
        ],
        *[
            (
                "huey",
                broker,
                False,
                False,
                _expected_worker_config(
                    "huey",
                    worker_queue="app.workers",
                    worker_backend="redis",
                    worker_redis_service=(
                        "redis-broker" if broker == "redis" else "valkey"
                    ),
                    worker_redis_db=2 if broker == "redis" else 1,
                ),
            )
            for broker in ("none", "redis", "rabbitmq", "kafka")
        ],
    ],
)
def test_resolve_worker_matrix(
    worker, broker, worker_exp_mode, scheduler, expected
):
    """Worker resolution should follow the approved allocation matrix."""
    assert (
        create_config._resolve_worker(
            worker,
            broker,
            worker_exp_mode,
            scheduler,
        )
        == expected
    )


@pytest.mark.parametrize(
    ("worker", "broker", "worker_exp_mode"),
    [
        *[
            ("none", broker, True)
            for broker in ("none", "redis", "rabbitmq", "kafka")
        ],
        ("celery", "none", True),
        ("celery", "redis", True),
        ("celery", "rabbitmq", True),
        *[
            ("huey", broker, True)
            for broker in ("none", "redis", "rabbitmq", "kafka")
        ],
    ],
)
def test_resolve_worker_rejects_invalid_experimental_combinations(
    worker, broker, worker_exp_mode
):
    """Experimental mode should only be enabled for supported combinations."""
    with pytest.raises(ValueError, match="experimental mode"):
        create_config._resolve_worker(worker, broker, worker_exp_mode)


@pytest.mark.parametrize(
    ("worker", "broker", "message"),
    [
        ("sidekiq", "none", "Unsupported worker 'sidekiq'"),
        ("none", "nats", "Unsupported broker 'nats'"),
    ],
)
def test_resolve_worker_rejects_unknown_choices(worker, broker, message):
    """Unknown worker resolver choices should fail before template copying."""
    with pytest.raises(ValueError, match=message):
        create_config._resolve_worker(worker, broker)


@pytest.mark.parametrize(
    ("worker", "broker", "worker_exp_mode"),
    [
        ("celery", "none", False),
        ("rq", "redis", False),
        ("dramatiq", "rabbitmq", False),
        ("huey", "none", False),
        ("celery", "kafka", True),
    ],
)
def test_resolve_worker_without_scheduler_disables_scheduler_logic(
    worker, broker, worker_exp_mode
):
    """Workers should not configure periodic processing without opt-in."""
    config = create_config._resolve_worker(
        worker,
        broker,
        worker_exp_mode,
        scheduler=False,
    )

    assert config["scheduler"] is False
    assert config["worker_scheduler"] is None


@pytest.mark.parametrize(
    ("worker", "broker", "worker_exp_mode", "worker_scheduler"),
    [
        ("celery", "none", False, "celery-beat"),
        ("rq", "redis", False, "rq-with-scheduler"),
        ("rq", "none", True, "rq-cron"),
        ("dramatiq", "rabbitmq", True, "apscheduler"),
        ("huey", "none", False, "huey-consumer"),
    ],
)
def test_resolve_worker_with_scheduler_enables_selected_scheduler_logic(
    worker, broker, worker_exp_mode, worker_scheduler
):
    """Scheduler opt-in should select the worker-specific periodic runtime."""
    config = create_config._resolve_worker(
        worker,
        broker,
        worker_exp_mode,
        scheduler=True,
    )

    assert config["scheduler"] is True
    assert config["worker_scheduler"] == worker_scheduler


@pytest.mark.parametrize("worker", ("rq", "dramatiq"))
def test_resolve_worker_rejects_scheduler_experimental_mode_without_scheduler(
    worker,
):
    """Scheduler-only experimental modes should require scheduler opt-in."""
    with pytest.raises(ValueError, match="requires --scheduler"):
        create_config._resolve_worker(
            worker,
            "none",
            worker_exp_mode=True,
            scheduler=False,
        )


def test_resolve_worker_rejects_scheduler_without_worker():
    """Scheduler opt-in should not be accepted without a worker."""
    with pytest.raises(ValueError, match="requires --worker"):
        create_config._resolve_worker("none", "none", scheduler=True)


def test_resolve_worker_rejects_dramatiq_scheduler_without_experimental_mode():
    """Dramatiq scheduler support should stay explicitly experimental."""
    with pytest.raises(ValueError, match="requires --worker-exp-mode"):
        create_config._resolve_worker("dramatiq", "none", scheduler=True)


@pytest.mark.parametrize(
    ("worker", "broker", "scheduler", "worker_exp_mode"),
    product(
        create_config.WORKER_CHOICES,
        create_config.BROKER_CHOICES,
        (False, True),
        (False, True),
    ),
)
def test_resolve_worker_accepts_only_supported_option_combinations(
    worker, broker, scheduler, worker_exp_mode
):
    """Every worker option combination should be explicitly accepted or rejected."""
    valid = {
        "none": not scheduler and not worker_exp_mode,
        "celery": not worker_exp_mode or broker == "kafka",
        "rq": scheduler or not worker_exp_mode,
        "dramatiq": scheduler == worker_exp_mode,
        "huey": not worker_exp_mode,
    }[worker]

    if valid:
        config = create_config._resolve_worker(
            worker,
            broker,
            worker_exp_mode,
            scheduler,
        )
        assert config["worker"] == worker
        assert config["scheduler"] is scheduler
    else:
        with pytest.raises(ValueError):
            create_config._resolve_worker(
                worker,
                broker,
                worker_exp_mode,
                scheduler,
            )


def test_get_template_config_includes_resolved_worker_mapping():
    """Template config should merge the resolved worker context."""
    config = create_config._get_template_config(
        "ddd",
        "sqlalchemy",
        "myproj",
        "uv",
        worker="celery",
    )

    assert {
        key: config[key] for key in _expected_worker_config("celery")
    } == _expected_worker_config(
        "celery",
        worker_queue="app.workers",
        worker_backend="redis",
        worker_redis_service="valkey",
        worker_redis_db=1,
        worker_result_redis_service="valkey",
        worker_result_redis_db=3,
    )


def test_get_template_config_worker_defaults_to_none():
    """Template config should preserve existing callers with no worker."""
    config = create_config._get_template_config(
        "ddd", "sqlalchemy", "myproj", "uv"
    )

    assert {
        key: config[key] for key in _expected_worker_config("none")
    } == _expected_worker_config("none")


def test_nosql_choices_include_none_and_supported_values():
    """NoSQL choices should mirror UID and broker fallback behavior."""
    assert create_config.NOSQL_CHOICES == ("none", "mongodb", "neo4j")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, ()),
        ("none", ()),
        ("mongodb", ("mongodb",)),
        ("mongodb,neo4j", ("mongodb", "neo4j")),
        (("neo4j", "mongodb", "neo4j"), ("mongodb", "neo4j")),
        ((" MONGODB ", " neo4j "), ("mongodb", "neo4j")),
    ],
)
def test_normalize_nosql(value, expected):
    """NoSQL input should become one ordered, de-duplicated provider tuple."""
    assert create_config._normalize_nosql(value) == expected


@pytest.mark.parametrize("value", ("mongodb,none", ("none", "neo4j")))
def test_normalize_nosql_rejects_none_combined_with_provider(value):
    """The no-provider sentinel should only be accepted by itself."""
    with pytest.raises(ValueError, match="'none' cannot be combined"):
        create_config._normalize_nosql(value)


def test_normalize_nosql_rejects_unknown_provider():
    """Unknown providers should fail before template copying begins."""
    with pytest.raises(ValueError, match="Unsupported NoSQL provider 'redis'"):
        create_config._normalize_nosql("redis")


def test_get_template_config_includes_uid():
    """Test that the template context preserves the selected UID type."""
    config = create_config._get_template_config(
        "ddd", "sqlalchemy", "myproj", "uv", "sparkid"
    )
    assert config["uid"] == "sparkid"


def test_get_template_config_uid_defaults_to_none():
    """Test that explicit 'none' flows through the template context unchanged."""
    config = create_config._get_template_config(
        "ddd", "sqlalchemy", "myproj", "uv", "none"
    )
    assert config["uid"] == "none"


def test_get_template_config_includes_nosql():
    """Test that the template context preserves selected NoSQL providers."""
    config = create_config._get_template_config(
        "ddd",
        "sqlalchemy",
        "myproj",
        "uv",
        "none",
        "none",
        ("mongodb", "neo4j"),
    )
    assert config["nosql"] == ("mongodb", "neo4j")


def test_get_template_config_nosql_defaults_to_none():
    """Test that NoSQL defaults to no generated overlay."""
    config = create_config._get_template_config(
        "ddd", "sqlalchemy", "myproj", "uv"
    )
    assert config["nosql"] == ()


def test_copy_nosql_files_merges_selected_overlays(tmp_path, monkeypatch):
    """Selected NoSQL overlays should merge without provider collisions."""
    nosql_dir = tmp_path / "nosql"
    (nosql_dir / "common").mkdir(parents=True)
    (nosql_dir / "ddd" / "common").mkdir(parents=True)
    for provider in ("mongodb", "neo4j"):
        config_dir = nosql_dir / "ddd" / provider / "config" / "nosql"
        config_dir.mkdir(parents=True)
        (config_dir / f"{provider}.py.jinja2").write_text(
            f'PROVIDER = "{provider}"\n'
        )
    destination = tmp_path / "generated"

    monkeypatch.setattr(
        create_filesystem, "NOSQL_DIR", nosql_dir, raising=False
    )

    create_filesystem._copy_nosql_files(
        destination,
        "ddd",
        ("mongodb", "neo4j"),
        {"nosql": ("mongodb", "neo4j")},
    )

    generated = destination / "src" / "app" / "config" / "nosql"
    assert (generated / "mongodb.py").read_text() == 'PROVIDER = "mongodb"\n'
    assert (generated / "neo4j.py").read_text() == 'PROVIDER = "neo4j"\n'


def test_copy_nosql_files_none_is_noop(tmp_path):
    """The none provider should not create application files."""
    destination = tmp_path / "generated"

    create_filesystem._copy_nosql_files(destination, "ddd", (), {"nosql": ()})

    assert not destination.exists()


def test_copy_worker_files_none_is_noop(tmp_path):
    """The none worker should not create application files."""
    destination = tmp_path / "generated"

    create_filesystem._copy_worker_files(
        destination, "ddd", "none", {"worker": "none"}
    )

    assert not destination.exists()


def test_copy_worker_files_renders_selected_overlay(tmp_path, monkeypatch):
    """The selected worker overlay should be copied and rendered."""
    workers_dir = tmp_path / "workers"
    config_dir = workers_dir / "ddd" / "celery" / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "worker.py.jinja2").write_text(
        'QUEUE = "{{ worker_queue }}"\n'
    )
    destination = tmp_path / "generated"

    monkeypatch.setattr(
        create_filesystem, "WORKERS_DIR", workers_dir, raising=False
    )

    create_filesystem._copy_worker_files(
        destination,
        "ddd",
        "celery",
        {"worker": "celery", "worker_queue": "app.workers"},
    )

    generated = destination / "src" / "app" / "config" / "worker.py"
    assert generated.read_text() == 'QUEUE = "app.workers"\n'
    assert not list(destination.rglob("*.jinja2"))


@pytest.mark.parametrize(
    ("design", "backend", "selected_broker", "excluded_broker"),
    [
        ("ddd", "redis", "RedisBroker", "RabbitmqBroker"),
        ("ddd", "rabbitmq", "RabbitmqBroker", "RedisBroker"),
        ("mvc", "redis", "RedisBroker", "RabbitmqBroker"),
        ("mvc", "rabbitmq", "RabbitmqBroker", "RedisBroker"),
    ],
)
def test_copy_worker_files_renders_only_selected_dramatiq_broker(
    tmp_path, design, backend, selected_broker, excluded_broker
):
    """Dramatiq overlays should not import an unused optional backend."""
    destination = tmp_path / f"generated-{design}-{backend}"
    context = {
        "worker": "dramatiq",
        "worker_queue": "app.workers",
        "worker_backend": backend,
        "worker_redis_service": "valkey",
        "worker_redis_db": 1,
    }

    create_filesystem._copy_worker_files(
        destination,
        design,
        "dramatiq",
        context,
    )

    relative_broker = (
        Path("infrastructure/worker/broker.py")
        if design == "ddd"
        else Path("worker/broker.py")
    )
    broker_content = (
        destination / "src" / "app" / relative_broker
    ).read_text()

    assert f"import {selected_broker}" in broker_content
    assert f"broker = {selected_broker}(" in broker_content
    assert excluded_broker not in broker_content
    assert "dramatiq.set_broker(broker)" in broker_content


def test_copy_worker_files_raises_for_missing_overlay(tmp_path, monkeypatch):
    """A selected worker without templates should fail with a clear error."""
    workers_dir = tmp_path / "workers"
    destination = tmp_path / "generated"

    monkeypatch.setattr(
        create_filesystem, "WORKERS_DIR", workers_dir, raising=False
    )

    with pytest.raises(FileNotFoundError) as exc_info:
        create_filesystem._copy_worker_files(
            destination, "ddd", "celery", {"worker": "celery"}
        )

    assert str(exc_info.value) == (
        "Could not find worker template for 'ddd/celery'."
    )


@pytest.mark.parametrize("design", ("ddd", "mvc"))
def test_copy_template_renders_selected_worker_settings(
    tmp_path, monkeypatch, design
):
    """Worker arguments should reach overlays and root settings templates."""
    workers_dir = tmp_path / "workers"
    config_dir = workers_dir / design / "rq" / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "worker.py.jinja2").write_text(
        'WORKER = "{{ worker }}"\nEXPERIMENTAL = {{ worker_exp_mode }}\n'
    )
    destination = tmp_path / f"generated-{design}"

    monkeypatch.setattr(
        create_filesystem, "WORKERS_DIR", workers_dir, raising=False
    )

    create_filesystem.copy_template(
        destination,
        "sqlalchemy",
        design,
        "worker-project",
        "uv",
        "none",
        "none",
        "none",
        "rq",
        True,
        True,
    )

    config_content = (
        destination / "src" / "app" / "config" / "__init__.py"
    ).read_text()
    worker_content = (
        destination / "src" / "app" / "config" / "worker.py"
    ).read_text()

    assert "from . import worker as _worker" in config_content
    assert "worker: _worker.Settings = _worker.Settings()" in config_content
    assert worker_content == 'WORKER = "rq"\nEXPERIMENTAL = True\n'


def test_render_jinja2_in_tree(tmp_path):
    """_render_jinja2_in_tree renders .jinja2 files and deletes them."""
    sub_dir = tmp_path / "sub"
    sub_dir.mkdir()
    jinja_file = sub_dir / "base.py.jinja2"
    jinja_file.write_text("id = {{ uid }}")

    create_filesystem._render_jinja2_in_tree(tmp_path, {"uid": "sparkid"})

    rendered = sub_dir / "base.py"
    assert rendered.exists()
    assert rendered.read_text() == "id = sparkid"
    assert not jinja_file.exists()


def test_render_jinja2_in_tree_noop_when_no_templates(tmp_path):
    """_render_jinja2_in_tree is a no-op when no .jinja2 files exist."""
    regular_file = tmp_path / "file.py"
    regular_file.write_text("class Foo: pass")

    create_filesystem._render_jinja2_in_tree(tmp_path, {"uid": "none"})

    assert regular_file.exists()
    assert regular_file.read_text() == "class Foo: pass"


def _generated_base_path(destination: Path, design: str) -> Path:
    if design == "ddd":
        return (
            destination
            / "src"
            / "app"
            / "infrastructure"
            / "database"
            / "tables"
            / "base.py"
        )
    return destination / "src" / "app" / "models" / "tables" / "base.py"


@pytest.mark.parametrize(
    ("design", "orm", "uid", "expected_snippets"),
    [
        (
            "ddd",
            "sqlalchemy",
            "none",
            ["id: Mapped[int] = mapped_column(primary_key=True)"],
        ),
        (
            "ddd",
            "sqlalchemy",
            "uuidv4",
            ["from sqlalchemy import Uuid", "default=uuid.uuid4"],
        ),
        (
            "ddd",
            "sqlalchemy",
            "uuidv7",
            ["from sqlalchemy import Uuid", "default=uuid.uuid7"],
        ),
        (
            "ddd",
            "sqlalchemy",
            "nanoid",
            ["from nanoid import generate", "String(21)"],
        ),
        ("ddd", "sqlalchemy", "ulid", ["from ulid import ULID", "String(26)"]),
        (
            "ddd",
            "sqlalchemy",
            "sparkid",
            ["from sparkid import generate_id", "default=generate_id"],
        ),
        ("ddd", "tortoise", "none", ["id = fields.IntField(pk=True)"]),
        ("ddd", "tortoise", "uuidv4", ["id = fields.UUIDField(pk=True)"]),
        ("ddd", "tortoise", "uuidv7", ["import uuid", "default=uuid.uuid7"]),
        (
            "ddd",
            "tortoise",
            "nanoid",
            ["from nanoid import generate", "max_length=21"],
        ),
        (
            "ddd",
            "tortoise",
            "ulid",
            ["from ulid import ULID", "max_length=26"],
        ),
        (
            "ddd",
            "tortoise",
            "sparkid",
            ["from sparkid import generate_id", "default=generate_id"],
        ),
        (
            "mvc",
            "sqlalchemy",
            "sparkid",
            ["from sparkid import generate_id", "default=generate_id"],
        ),
        (
            "mvc",
            "tortoise",
            "nanoid",
            ["from nanoid import generate", "max_length=21"],
        ),
    ],
)
def test_copy_template_renders_uid_base_templates(
    tmp_path, design, orm, uid, expected_snippets
):
    destination = tmp_path / f"{design}-{orm}-{uid}"

    create_filesystem.copy_template(
        destination,
        orm,
        design,
        "uid-project",
        "uv",
        uid,
    )

    base_file = _generated_base_path(destination, design)
    content = base_file.read_text()

    assert base_file.exists()
    for snippet in expected_snippets:
        assert snippet in content
    assert not list(destination.rglob("*.jinja2"))


@pytest.mark.parametrize(
    ("package_manager", "uid", "expected_dependency"),
    [
        ("uv", "nanoid", "python-nanoid>=2.0.0"),
        ("uv", "ulid", "python-ulid>=3.0.0"),
        ("uv", "sparkid", "sparkid>=1.0.0"),
        ("poetry", "nanoid", 'python-nanoid = ">=2.0.0"'),
        ("poetry", "ulid", 'python-ulid = ">=3.0.0"'),
        ("poetry", "sparkid", 'sparkid = ">=1.0.0"'),
    ],
)
def test_copy_template_adds_uid_metadata_and_dependencies(
    tmp_path, package_manager, uid, expected_dependency
):
    destination = tmp_path / f"{package_manager}-{uid}"

    create_filesystem.copy_template(
        destination,
        "sqlalchemy",
        "ddd",
        "uid-project",
        package_manager,
        uid,
    )

    pyproject_content = (destination / "pyproject.toml").read_text()

    assert f'uid = "{uid}"' in pyproject_content
    assert expected_dependency in pyproject_content


@pytest.mark.parametrize(
    ("package_manager", "expected_python_floor"),
    [
        ("uv", 'requires-python = ">=3.13,<4.0"'),
        ("poetry", 'python = ">=3.13,<4.0"'),
    ],
)
def test_copy_template_raises_python_floor_for_uuidv7(
    tmp_path, package_manager, expected_python_floor
):
    destination = tmp_path / f"{package_manager}-uuidv7"

    create_filesystem.copy_template(
        destination,
        "sqlalchemy",
        "ddd",
        "uid-project",
        package_manager,
        "uuidv7",
    )

    pyproject_content = (destination / "pyproject.toml").read_text()

    assert 'uid = "uuidv7"' in pyproject_content
    assert expected_python_floor in pyproject_content


# --- Tests for src/add/utils.py ---


@pytest.mark.parametrize(
    "input_name, expected_lower, expected_cap",
    [
        ("product", "product", "Product"),
        ("user_profile", "user_profile", "UserProfile"),
        ("My-Service", "my_service", "MyService"),
        ("api response", "api_response", "ApiResponse"),
    ],
)
def test_normalize_entity_name(input_name, expected_lower, expected_cap):
    lower, cap = add_utils._normalize_entity_name(input_name)
    assert lower == expected_lower
    assert cap == expected_cap


def test_format_comment():
    assert add_utils._format_comment("") == ""
    assert add_utils._format_comment("  comment") == " # comment"
    assert add_utils._format_comment("# existing") == " # existing"


def test_read_project_config(tmp_path):
    # Missing file
    with pytest.raises(FileNotFoundError):
        add_paths.read_project_config(tmp_path)

    # Missing section
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[tool.other]\nkey='val'")
    with pytest.raises(ValueError, match="No \\[tool.robyn-config\\]"):
        add_paths.read_project_config(tmp_path)

    # Valid config
    pyproject.write_text("[tool.robyn-config]\ndesign='ddd'\norm='sqlalchemy'")
    config = add_paths.read_project_config(tmp_path)
    assert config["design"] == "ddd"
    assert config["orm"] == "sqlalchemy"


def test_ensure_import_from(tmp_path):
    file_path = tmp_path / "test_import.py"

    # 1. New file creation
    add_injection._ensure_import_from(file_path, ".models", "User")
    assert file_path.read_text().strip() == "from .models import User"

    # 2. Append to existing import
    add_injection._ensure_import_from(file_path, ".models", "Product")
    content = file_path.read_text()
    assert "from .models import User, Product" in content

    # 3. Append with comment preservation
    file_path.write_text("from .models import User  # old comment")
    add_injection._ensure_import_from(file_path, ".models", "Product")
    content = file_path.read_text()
    assert "from .models import User, Product  # old comment" in content

    # 4. Handle multiline parenthesis import
    file_path.write_text("from .models import (\n    User,\n)")
    add_injection._ensure_import_from(file_path, ".models", "Product")
    content = file_path.read_text()
    assert "    User," in content
    assert "    Product," in content


def test_add_to_all_list(tmp_path):
    file_path = tmp_path / "test_all.py"

    # Create file with existing __all__
    file_path.write_text('__all__ = (\n    "User",\n)')

    add_injection._add_to_all_list(file_path, "Product")

    content = file_path.read_text()
    assert '"User",' in content
    assert '"Product",' in content
    assert content.count("__all__") == 1


@pytest.mark.parametrize(
    ("design", "uid_line", "expected_uid"),
    [
        ("ddd", "uid = 'sparkid'\n", "sparkid"),
        ("mvc", "", "none"),
    ],
)
def test_add_business_logic_passes_uid_to_template_helpers(
    monkeypatch, tmp_path, design, uid_line, expected_uid
):
    config_lines = [
        "[tool.robyn-config]",
        f"design = '{design}'",
        "orm = 'sqlalchemy'",
    ]
    if uid_line:
        config_lines.append(uid_line.strip())
    (tmp_path / "pyproject.toml").write_text("\n".join(config_lines) + "\n")

    fake_paths = object()
    captured: dict[str, str] = {}

    monkeypatch.setattr(
        add_utils, "_load_add_paths", lambda *_args, **_kwargs: fake_paths
    )
    monkeypatch.setattr(
        add_utils,
        "_normalize_entity_name",
        lambda _name: ("product", "Product"),
    )

    def fake_add_templates(
        _project_path,
        _paths,
        _name,
        _name_capitalized,
        _orm,
        uid,
    ):
        captured["uid"] = uid
        return ["created.py"]

    if design == "ddd":
        monkeypatch.setattr(
            add_utils, "_add_ddd_templates", fake_add_templates
        )
    else:
        monkeypatch.setattr(
            add_utils, "_add_mvc_templates", fake_add_templates
        )

    created_files = add_utils.add_business_logic(tmp_path, "product")

    assert created_files == ["created.py"]
    assert captured["uid"] == expected_uid
