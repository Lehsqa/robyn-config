from __future__ import annotations

import asyncio
from logging.config import fileConfig
from typing import Mapping

from alembic import context
from app.config import settings
from app.models.table import Base
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
ADMIN_TABLE_PREFIX = "robyn_admin_"


def _configure_section() -> Mapping[str, str]:
    section = config.get_section(config.config_ini_section) or {}
    section["sqlalchemy.url"] = settings.database.url
    return section


def _include_object(
    object_: object,
    name: str | None,
    type_: str,
    reflected: bool,
    compare_to: object | None,
) -> bool:
    if (
        type_ == "table"
        and reflected
        and compare_to is None
        and name is not None
        and name.startswith(ADMIN_TABLE_PREFIX)
    ):
        return False
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database.url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        include_object=_include_object,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        _configure_section(),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async def _run_async_migrations() -> None:
        async with connectable.connect() as connection:
            await connection.run_sync(_do_run_migrations)
        await connectable.dispose()

    def _do_run_migrations(connection):
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            include_object=_include_object,
        )
        with context.begin_transaction():
            context.run_migrations()

    asyncio.run(_run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
