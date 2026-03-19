from __future__ import annotations

from typing import Any, Callable, Optional, Type

from robyn import Robyn

from ...admin import ModelAdmin
from ..base import SiteRuntimeConfig
from ..db import ensure_default_admin, get_session_dialect, setup_admin_db
from .base import BaseAdminSite


class AdminSite(BaseAdminSite):
    """SQLAlchemy-backed admin site."""

    def __init__(
        self,
        app: Robyn,
        title: str = "QC Robyn Admin",
        prefix: str = "admin",
        copyright: str = "QC Robyn Admin",
        transaction: Optional[Callable] = None,
        generate_schemas: bool = False,
        default_language: str = "en_US",
        default_admin_username: str = "admin",
        default_admin_password: str = "admin",
        startup_function: Optional[Callable] = None,
        orm: str = "sqlalchemy",
        **_: Any,
    ) -> None:
        if transaction is None:
            raise ValueError("transaction is required for SQLAlchemy admin")

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
                "orm": orm,
            }
        )

        super().__init__(app, runtime_config)
        self.transaction = transaction
        self._post_init()

    def _init_admin_db(self) -> None:
        setup_admin_db(self)

    async def _ensure_default_admin(self) -> None:
        await ensure_default_admin(self)

    @staticmethod
    def _get_session_dialect(session: Any) -> tuple[str, str]:
        return get_session_dialect(session)

    def register_model(
        self,
        model: Type[Any],
        admin_class: Optional[Type[ModelAdmin]] = None,
    ) -> None:
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
