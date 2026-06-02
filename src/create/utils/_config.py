"""Template configuration constants for the 'create' command."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Mapping, Sequence

ORM_CHOICES: Sequence[str] = ("sqlalchemy", "tortoise")
DESIGN_CHOICES: Sequence[str] = ("ddd", "mvc")
PACKAGE_MANAGER_CHOICES: Sequence[str] = ("uv", "poetry")
BROKER_CHOICES: Sequence[str] = (
    "none",
    "redis",
    "rabbitmq",
    "kafka",
)
INTERACTIVE_BROKER_CHOICES: Sequence[str] = BROKER_CHOICES
WORKER_CHOICES: Sequence[str] = ("none", "celery", "rq", "dramatiq", "huey")
INTERACTIVE_WORKER_CHOICES: Sequence[str] = WORKER_CHOICES
NOSQL_PROVIDERS: Sequence[str] = ("mongodb", "neo4j")
NOSQL_CHOICES: Sequence[str] = ("none", *NOSQL_PROVIDERS)
INTERACTIVE_NOSQL_CHOICES: Sequence[str] = NOSQL_PROVIDERS
UID_CHOICES: Sequence[str] = (
    "none",
    "uuidv4",
    "uuidv7",
    "nanoid",
    "ulid",
    "sparkid",
)

LOCK_FILE_BY_MANAGER: Mapping[str, str] = {
    "uv": "uv.lock",
    "poetry": "poetry.lock",
}

PACKAGE_MANAGER_DOWNLOAD_URLS: Mapping[str, str] = {
    "uv": "https://docs.astral.sh/uv/getting-started/installation/",
    "poetry": "https://python-poetry.org/docs/#installation",
}

TEMPLATE_CONFIGS: Mapping[str, dict[str, str]] = {
    "ddd:sqlalchemy": {
        "design": "ddd",
        "orm": "sqlalchemy",
        "alembic_script_location": "src/app/infrastructure/database/migrations",
    },
    "ddd:tortoise": {
        "design": "ddd",
        "orm": "tortoise",
        "tortoise_orm_path": "src.app.infrastructure.database.services.engine.TORTOISE_ORM",
        "tortoise_migrations_location": "./src/app/infrastructure/database/migrations",
    },
    "mvc:sqlalchemy": {
        "design": "mvc",
        "orm": "sqlalchemy",
        "alembic_script_location": "src/app/models/migrations",
    },
    "mvc:tortoise": {
        "design": "mvc",
        "orm": "tortoise",
        "tortoise_orm_path": "app.models.database.TORTOISE_ORM",
        "tortoise_migrations_location": "./src/app/models/migrations",
    },
}

_WORKER_REDIS_ALLOCATIONS: Mapping[str, tuple[str, int]] = {
    "none": ("valkey", 1),
    "redis": ("redis-broker", 2),
    "rabbitmq": ("valkey", 1),
    "kafka": ("valkey", 1),
}

_CELERY_BACKENDS: Mapping[str, tuple[str, str | None, int | None]] = {
    "none": ("redis", "valkey", 1),
    "redis": ("redis", "redis-broker", 2),
    "rabbitmq": ("rabbitmq", None, None),
    "kafka": ("redis", "valkey", 1),
}


def _worker_config(
    worker: str,
    worker_exp_mode: bool,
    scheduler: bool,
) -> dict[str, object]:
    """Return a predictable base context for worker templates."""
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
    }


def _resolve_worker(
    worker: str,
    broker: str,
    worker_exp_mode: bool = False,
    scheduler: bool = False,
) -> dict[str, object]:
    """Resolve worker template values for the selected broker."""
    if worker not in WORKER_CHOICES:
        raise ValueError(
            f"Unsupported worker '{worker}'. "
            f"Valid options: {', '.join(WORKER_CHOICES)}."
        )
    if broker not in BROKER_CHOICES:
        raise ValueError(
            f"Unsupported broker '{broker}'. "
            f"Valid options: {', '.join(BROKER_CHOICES)}."
        )
    if scheduler and worker == "none":
        raise ValueError("--scheduler requires --worker.")
    if worker_exp_mode and worker in ("rq", "dramatiq") and not scheduler:
        raise ValueError(
            f"Worker '{worker}' experimental mode requires --scheduler."
        )
    if worker_exp_mode and worker not in ("rq", "dramatiq"):
        if not (worker == "celery" and broker == "kafka"):
            raise ValueError(
                f"Worker '{worker}' with broker '{broker}' does not support "
                "experimental mode."
            )
    if scheduler and worker == "dramatiq" and not worker_exp_mode:
        raise ValueError(
            "Worker 'dramatiq' scheduler requires --worker-exp-mode."
        )
    config = _worker_config(worker, worker_exp_mode, scheduler)
    if worker == "none":
        return config

    config["worker_queue"] = "app.workers"
    if worker == "celery":
        backend, redis_service, redis_db = _CELERY_BACKENDS[broker]
        if broker == "kafka" and worker_exp_mode:
            backend, redis_service, redis_db = ("kafka", None, None)
        config.update(
            worker_backend=backend,
            worker_redis_service=redis_service,
            worker_redis_db=redis_db,
            worker_result_redis_service=(
                "redis-broker" if broker == "redis" else "valkey"
            ),
            worker_result_redis_db=3,
            worker_scheduler="celery-beat" if scheduler else None,
        )
        return config

    if worker == "dramatiq" and broker == "rabbitmq":
        config.update(
            worker_backend="rabbitmq",
            worker_scheduler=(
                "apscheduler" if scheduler and worker_exp_mode else None
            ),
        )
        return config

    redis_service, redis_db = _WORKER_REDIS_ALLOCATIONS[broker]
    schedulers = {
        "rq": (
            "rq-cron"
            if scheduler and worker_exp_mode
            else "rq-with-scheduler" if scheduler else None
        ),
        "dramatiq": "apscheduler" if scheduler and worker_exp_mode else None,
        "huey": "huey-consumer" if scheduler else None,
    }
    config.update(
        worker_backend="redis",
        worker_redis_service=redis_service,
        worker_redis_db=redis_db,
        worker_scheduler=schedulers[worker],
    )
    return config


def _normalize_nosql(
    values: str | Iterable[str] | None,
) -> tuple[str, ...]:
    """Normalize NoSQL input into an ordered provider tuple."""
    if values is None:
        return ()

    raw_values = (values,) if isinstance(values, str) else values
    selected = {
        provider.strip().lower()
        for value in raw_values
        for provider in value.split(",")
        if provider.strip()
    }

    if "none" in selected:
        if len(selected) > 1:
            raise ValueError(
                "NoSQL provider 'none' cannot be combined with other providers."
            )
        return ()

    for provider in selected:
        if provider not in NOSQL_PROVIDERS:
            raise ValueError(
                f"Unsupported NoSQL provider '{provider}'. "
                f"Valid options: {', '.join(NOSQL_CHOICES)}."
            )

    return tuple(
        provider for provider in NOSQL_PROVIDERS if provider in selected
    )


def _get_template_config(
    design: str,
    orm_type: str,
    project_name: str,
    package_manager: str,
    uid: str = "none",
    broker: str | None = None,
    nosql: str | Iterable[str] | None = None,
    worker: str = "none",
    worker_exp_mode: bool = False,
    scheduler: bool = False,
) -> dict[str, object]:
    """Get the template configuration for the given design and ORM type."""
    key = f"{design}:{orm_type}"
    config = TEMPLATE_CONFIGS.get(key)
    if config is None:
        print(
            f"Unsupported configuration '{key}'. "
            f"Valid options: {', '.join(TEMPLATE_CONFIGS.keys())}."
        )
        raise SystemExit(1)
    return {
        **config,
        "name": project_name,
        "package_manager": package_manager,
        "uid": uid,
        "broker": broker or "none",
        "nosql": _normalize_nosql(nosql),
        **_resolve_worker(
            worker, broker or "none", worker_exp_mode, scheduler
        ),
    }
