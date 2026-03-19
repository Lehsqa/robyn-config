from __future__ import annotations

import asyncio
import os
from typing import Any

from tortoise import Tortoise
from tortoise.exceptions import IntegrityError as TortoiseIntegrityError

from ...auth_models import AdminUser
from .auth_common import ADVISORY_LOCK_ID


def ensure_sqlite_directory(db_url: str | None) -> str | None:
    if not db_url or not db_url.startswith("sqlite://"):
        return db_url

    db_path = db_url.replace("sqlite://", "")
    if db_path == ":memory:":
        return db_url

    if not os.path.isabs(db_path):
        db_path = os.path.abspath(db_path)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    return f"sqlite://{db_path}"


def cleanup_db() -> None:
    if not Tortoise._inited:
        return

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    loop.run_until_complete(Tortoise.close_connections())


async def ensure_default_admin(site: Any) -> None:
    if site._default_admin_initialized:
        return

    async with site._default_admin_init_lock:
        if site._default_admin_initialized:
            return

        db_url = str(site.db_url or "").strip().lower()
        using_postgres = db_url.startswith("postgres")
        advisory_lock_acquired = False

        async with site.transaction() as connection:
            try:
                if using_postgres:
                    await connection.execute_query(
                        f"SELECT pg_advisory_lock({ADVISORY_LOCK_ID})"
                    )
                    advisory_lock_acquired = True

                existing_admin = (
                    await AdminUser.filter(
                        username=site.default_admin_username
                    )
                    .using_db(connection)
                    .first()
                )
                if not existing_admin:
                    existing_admin = (
                        await AdminUser.filter(email="admin@example.com")
                        .using_db(connection)
                        .first()
                    )

                if not existing_admin:
                    try:
                        await AdminUser.create(
                            username=site.default_admin_username,
                            password=AdminUser.hash_password(
                                site.default_admin_password
                            ),
                            email="admin@example.com",
                            is_superuser=True,
                            is_active=True,
                            using_db=connection,
                        )
                    except TortoiseIntegrityError:
                        pass
            finally:
                if advisory_lock_acquired:
                    try:
                        await connection.execute_query(
                            f"SELECT pg_advisory_unlock({ADVISORY_LOCK_ID})"
                        )
                    except Exception:
                        pass

        site._default_admin_initialized = True


def setup_admin_db(site: Any) -> None:
    @site.app.startup_handler
    async def init_admin() -> None:
        if not site.db_url:
            if not Tortoise._inited:
                raise RuntimeError(
                    "Database is not initialized. Configure database or provide db_url."
                )
            current_config = Tortoise.get_connection("default").config
            site.db_url = current_config.get("credentials", {}).get("dsn")

        site.db_url = ensure_sqlite_directory(site.db_url)

        if site.modules is None or not site.modules:
            if not Tortoise._inited:
                raise RuntimeError(
                    "Model modules are required when database is not initialized."
                )
            site.modules = dict(Tortoise.apps)

        if not Tortoise._inited:
            await Tortoise.init(db_url=site.db_url, modules=site.modules)

        if site.generate_schemas:
            await Tortoise.generate_schemas()

        await ensure_default_admin(site)
        if site.startup_function:
            await site.startup_function()
