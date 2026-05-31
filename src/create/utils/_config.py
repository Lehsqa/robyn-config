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
    }
