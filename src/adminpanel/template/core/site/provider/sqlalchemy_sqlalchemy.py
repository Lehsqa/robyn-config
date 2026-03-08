from __future__ import annotations

import asyncio
import json
import secrets
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional, Type

from robyn import Request, Robyn
from robyn.templating import JinjaTemplate

from ....i18n.translations import TRANSLATIONS
from ...admin import ModelAdmin
from ...menu import MenuItem, MenuManager
from ..auth import (
    check_permission,
    generate_session_token,
    get_current_user,
    get_language,
    verify_session_token,
)
from ..base import (
    ModelAdminMetadata,
    SiteRuntimeConfig,
    merge_admin_settings,
    pluralize_word,
)
from ..db import ensure_default_admin, get_session_dialect, setup_admin_db
from ..helpers import decode_cookie_payload, encode_cookie_payload, parse_cookie_header
from ..routes import setup_routes


class AdminSite:
    """SQLAlchemy-backed admin site."""

    def __init__(
        self,
        app: Robyn,
        title: str = "QC Robyn Admin",
        prefix: str = "admin",
        copyright: str = "QC Robyn Admin",
        session_factory: Optional[Callable[[], Any]] = None,
        generate_schemas: bool = False,
        default_language: str = "en_US",
        default_admin_username: str = "admin",
        default_admin_password: str = "admin",
        startup_function: Optional[Callable] = None,
        orm: str = "sqlalchemy",
        **_: Any,
    ) -> None:
        if session_factory is None:
            raise ValueError("session_factory is required for SQLAlchemy admin")

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

        self.app = app
        self.title = runtime_config.title
        self.prefix = runtime_config.prefix
        self.models: dict[str, ModelAdmin] = {}
        self.model_registry: dict[str, list[ModelAdmin]] = {}
        self.default_language = runtime_config.default_language
        self.default_admin_username = runtime_config.default_admin_username
        self.default_admin_password = runtime_config.default_admin_password
        self.menu_manager = MenuManager()
        self.copyright = runtime_config.copyright
        self.startup_function = runtime_config.startup_function
        self.session_factory = session_factory
        self.generate_schemas = runtime_config.generate_schemas
        self.orm = runtime_config.orm
        self._default_admin_initialized = False
        self._default_admin_init_lock = asyncio.Lock()

        self._setup_templates()
        self._init_admin_db()
        self._setup_routes()

        self.session_secret = secrets.token_hex(32)
        self.session_expire = 24 * 60 * 60
        self.max_recent_actions = runtime_config.max_recent_actions
        self.recent_actions: list[dict[str, str]] = []
        self.default_settings: dict[str, Any] = (
            runtime_config.default_settings.model_dump()
        )

    async def _get_visible_models(self, request: Request) -> dict[str, ModelAdmin]:
        visible: dict[str, ModelAdmin] = {}
        for route_id, model_admin in self.models.items():
            if await self.check_permission(request, route_id, "view"):
                visible[route_id] = model_admin
        return visible

    def _get_model_table_name(self, model_admin: ModelAdmin) -> str:
        return ModelAdminMetadata.from_model_admin(model_admin).table_name

    def _get_model_source_filename(self, model_admin: ModelAdmin) -> str:
        metadata = ModelAdminMetadata.from_model_admin(model_admin)
        module_name = metadata.module_name
        if not isinstance(module_name, str) or not module_name:
            return "Models"

        module_parts = module_name.split(".")
        file_name = module_parts[-1]
        if file_name == "__init__" and len(module_parts) > 1:
            file_name = module_parts[-2]
        return self._format_label(file_name or "models", pluralize=True)

    @staticmethod
    def _pluralize_word(word: str) -> str:
        return pluralize_word(word)

    def _format_label(self, raw_value: str, pluralize: bool) -> str:
        normalized = raw_value.strip().replace("-", "_").replace(" ", "_")
        parts = [part for part in normalized.split("_") if part]
        if not parts:
            return "Models" if pluralize else "Model"
        if pluralize:
            parts[-1] = self._pluralize_word(parts[-1])
        return " ".join(part.capitalize() for part in parts)

    def _get_model_display_name(self, model_admin: ModelAdmin) -> str:
        metadata = ModelAdminMetadata.from_model_admin(model_admin)
        table_name = metadata.table_name
        if table_name:
            return self._format_label(table_name, pluralize=False)
        return self._format_label(metadata.verbose_name, pluralize=False)

    def _build_model_categories(
        self, visible_models: dict[str, ModelAdmin]
    ) -> list[dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for route_id, model_admin in visible_models.items():
            category_name = self._get_model_source_filename(model_admin)
            grouped.setdefault(category_name, []).append(
                {
                    "route_id": route_id,
                    "model_admin": model_admin,
                    "display_name": self._get_model_display_name(model_admin),
                }
            )

        categories: list[dict[str, Any]] = []
        for category_name in sorted(grouped.keys()):
            models_in_category = sorted(
                grouped[category_name],
                key=lambda item: str(item["display_name"]).lower(),
            )
            categories.append({"name": category_name, "models": models_in_category})
        return categories

    def _record_action(
        self,
        username: str,
        action: str,
        target: str = "",
        details: str = "",
    ) -> None:
        self.recent_actions.append(
            {
                "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
                "username": username or "system",
                "action": action,
                "target": target,
                "details": details,
            }
        )
        if len(self.recent_actions) > self.max_recent_actions:
            self.recent_actions = self.recent_actions[-self.max_recent_actions :]

    def _get_admin_settings(self, request: Request) -> dict[str, Any]:
        return merge_admin_settings(
            cookie_header=request.headers.get("Cookie"),
            default_settings=self.default_settings,
            parse_cookie_header=parse_cookie_header,
            decode_cookie_payload=decode_cookie_payload,
        )

    def _build_settings_cookie(self, settings: dict[str, Any]) -> str:
        payload = json.dumps(settings, separators=(",", ":"))
        encoded = encode_cookie_payload(payload)
        attrs = [
            f"admin_settings={encoded}",
            "Path=/",
            "Max-Age=2592000",
            "SameSite=Lax",
        ]
        return "; ".join(attrs)

    def _read_log_lines(self, log_file_path: str, max_lines: int) -> tuple[list[str], str]:
        max_lines = max(20, min(int(max_lines), 2000))
        candidate = Path(log_file_path)
        if not candidate.is_absolute():
            candidate = Path.cwd() / candidate

        resolved_path = str(candidate)
        if not candidate.exists():
            return [f"Log file does not exist: {resolved_path}"], resolved_path

        try:
            with candidate.open("r", encoding="utf-8", errors="replace") as handle:
                lines = [line.rstrip("\n") for line in deque(handle, maxlen=max_lines)]
            if not lines:
                return ["Log file is empty."], resolved_path
            return lines, resolved_path
        except Exception as exc:
            return [f"Failed to read log file: {exc}"], resolved_path

    def get_text(self, key: str, lang: str | None = None) -> str:
        current_lang = lang or self.default_language
        return TRANSLATIONS.get(
            current_lang,
            TRANSLATIONS[self.default_language],
        ).get(key, key)

    def _setup_templates(self) -> None:
        # provider/sqlalchemy.py -> site -> core -> adminpanel
        current_dir = Path(__file__).resolve().parents[3]
        template_dir = str(current_dir / "templates")
        self.template_dir = template_dir
        self.jinja_template = JinjaTemplate(template_dir)
        self.jinja_template.env.globals.update({"get_text": self.get_text})

    def _init_admin_db(self) -> None:
        setup_admin_db(self)

    async def _ensure_default_admin(self) -> None:
        await ensure_default_admin(self)

    def _setup_routes(self) -> None:
        setup_routes(self)

    def init_register_auth_models(self) -> None:
        return None

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

        instance = admin_class(model, session_factory=self.session_factory)
        instance.site = self

        route_id = f"{model.__name__}Admin" if admin_class is ModelAdmin else admin_class.__name__
        base_route_id = route_id
        counter = 1
        while route_id in self.models:
            route_id = f"{base_route_id}{counter}"
            counter += 1

        instance.route_id = route_id
        self.models[route_id] = instance
        self.model_registry.setdefault(model.__name__, []).append(instance)

    def _generate_session_token(self, user_id: int) -> str:
        return generate_session_token(self, user_id)

    def _verify_session_token(self, token: str) -> tuple[bool, Optional[int]]:
        return verify_session_token(self, token)

    async def _get_current_user(self, request: Request):
        return await get_current_user(self, request)

    async def _get_language(self, request: Request) -> str:
        return await get_language(self, request)

    async def check_permission(
        self, request: Request, model_name: str, action: str
    ) -> bool:
        return await check_permission(self, request, model_name, action)

    def register_menu(self, menu_item: MenuItem):
        self.menu_manager.register_menu(menu_item)

    def get_model_admin(self, route_id: str) -> Optional[ModelAdmin]:
        return self.models.get(route_id)
