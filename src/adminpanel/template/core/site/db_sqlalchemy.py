from __future__ import annotations

from typing import Any

from sqlalchemy import or_, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError

from ...models import AdminUser
from .auth_common import ADVISORY_LOCK_ID


async def ensure_default_admin(site: Any) -> None:
    if site._default_admin_initialized:
        return

    async with site._default_admin_init_lock:
        if site._default_admin_initialized:
            return

        advisory_lock_acquired = False
        async with site.transaction() as session:
            try:
                dialect_name, driver_name = get_session_dialect(session)
                is_postgresql = dialect_name == "postgresql" or (
                    "postgres" in driver_name
                )

                if is_postgresql:
                    await session.execute(
                        text("SELECT pg_advisory_lock(:lock_id)"),
                        {"lock_id": ADVISORY_LOCK_ID},
                    )
                    advisory_lock_acquired = True

                result = await session.execute(
                    select(AdminUser).where(
                        or_(
                            AdminUser.username == site.default_admin_username,
                            AdminUser.email == "admin@example.com",
                        )
                    )
                )
                admin_user = result.scalar_one_or_none()
                if admin_user is None:
                    if is_postgresql:
                        await session.execute(
                            pg_insert(AdminUser)
                            .values(
                                username=site.default_admin_username,
                                password=AdminUser.hash_password(
                                    site.default_admin_password
                                ),
                                email="admin@example.com",
                                is_superuser=True,
                                is_active=True,
                            )
                            .on_conflict_do_nothing()
                        )
                    else:
                        try:
                            async with session.begin_nested():
                                session.add(
                                    AdminUser(
                                        username=site.default_admin_username,
                                        password=AdminUser.hash_password(
                                            site.default_admin_password
                                        ),
                                        email="admin@example.com",
                                        is_superuser=True,
                                        is_active=True,
                                    )
                                )
                        except IntegrityError:
                            pass  # Admin already exists from a concurrent process
            finally:
                if advisory_lock_acquired:
                    try:
                        await session.execute(
                            text("SELECT pg_advisory_unlock(:lock_id)"),
                            {"lock_id": ADVISORY_LOCK_ID},
                        )
                    except Exception:
                        pass

        site._default_admin_initialized = True


def get_session_dialect(session: Any) -> tuple[str, str]:
    bind = session.get_bind()
    if bind is None:
        bind = session.bind
    if bind is None:
        return "", ""

    sync_bind = getattr(bind, "sync_engine", bind)
    dialect = getattr(sync_bind, "dialect", None)
    url = getattr(sync_bind, "url", None)

    dialect_name = str(getattr(dialect, "name", "") or "").lower()
    driver_name = str(getattr(url, "drivername", "") or "").lower()
    return dialect_name, driver_name


def setup_admin_db(site: Any) -> None:
    @site.app.startup_handler
    async def init_admin() -> None:
        try:
            await ensure_default_admin(site)
            if site.startup_function:
                await site.startup_function()
        except Exception:
            raise
