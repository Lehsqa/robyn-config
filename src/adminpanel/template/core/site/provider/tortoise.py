from __future__ import annotations

import atexit
from types import ModuleType
from typing import Any, Callable, Type

from robyn import Robyn
from tortoise import Model

from ...admin import ModelAdmin
from ..base import SiteRuntimeConfig
from ..db import (
    cleanup_db,
    ensure_default_admin,
    ensure_sqlite_directory,
    setup_admin_db,
)
from .base import BaseAdminSite


class AdminSite(BaseAdminSite):
    """Tortoise-backed admin site."""

    def __init__(
        self,
        app: Robyn,
        title: str = "QC Robyn Admin",
        prefix: str = "admin",
        copyright: str = "QC Robyn Admin",
        db_url: str | None = None,
        modules: dict[str, list[str | ModuleType]] | None = None,
        transaction: Callable | None = None,
        generate_schemas: bool = True,
        default_language: str = "en_US",
        default_admin_username: str = "admin",
        default_admin_password: str = "admin",
        startup_function: Callable | None = None,
        **_: Any,
    ):
        runtime_config = SiteRuntimeConfig.model_validate(
            {
                "title": title,
                "prefix": prefix,
                "copyright": copyright,
                "default_language": default_language,
                "default_admin_username": default_admin_username,
                "default_admin_password": default_admin_password,
                "startup_function": startup_function,
                "generate_schemas": generate_schemas,
                "orm": "tortoise",
            }
        )

        super().__init__(app, runtime_config)
        self.db_url = ensure_sqlite_directory(db_url)
        self.modules = modules
        self.transaction = transaction

        atexit.register(self._cleanup_db)
        self._post_init()

    def _cleanup_db(self):
        cleanup_db()

    def _init_admin_db(self) -> None:
        setup_admin_db(self)

    async def _ensure_default_admin(self) -> None:
        await ensure_default_admin(self)

    def register_model(
        self,
        model: Type[Model],
        admin_class: Type[ModelAdmin] | None = None,
    ):
        if admin_class is None:
            admin_class = ModelAdmin

        instance = admin_class(model, transaction=self.transaction)
        instance.site = self

        route_id = (
            f"{model.__name__}Admin"
            if admin_class is ModelAdmin
            else admin_class.__name__
        )
        base_route_id = route_id
        counter = 1
        while route_id in self.models:
            route_id = f"{base_route_id}{counter}"
            counter += 1

        instance.route_id = route_id
        self.models[route_id] = instance
        self.model_registry.setdefault(model.__name__, []).append(instance)
