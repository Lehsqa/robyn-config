from __future__ import annotations

import base64
import json
import secrets
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Type
from urllib.parse import parse_qs, unquote

from robyn import Request, Response, Robyn, jsonify
from robyn.templating import JinjaTemplate
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from ..auth_admin_sqlalchemy import AdminUserAdmin, RoleAdmin, UserRoleAdmin
from ..auth_models_sqlalchemy import Role, UserRole
from ..i18n.translations import TRANSLATIONS
from ..models_sqlalchemy import AdminUser
from .menu import MenuItem, MenuManager
from .sqlalchemy_admin import ModelAdmin


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
        startup_function: Optional[Callable] = None,
        orm: str = "sqlalchemy",
        **_: Any,
    ) -> None:
        if session_factory is None:
            raise ValueError("session_factory is required for SQLAlchemy admin")

        self.app = app
        self.title = title
        self.prefix = prefix
        self.models: Dict[str, ModelAdmin] = {}
        self.model_registry: Dict[str, list[ModelAdmin]] = {}
        self.default_language = default_language
        self.menu_manager = MenuManager()
        self.copyright = copyright
        self.startup_function = startup_function
        self.session_factory = session_factory
        self.generate_schemas = generate_schemas
        self.orm = orm

        self._setup_templates()
        self._init_admin_db()
        self._setup_routes()

        self.session_secret = secrets.token_hex(32)
        self.session_expire = 24 * 60 * 60

    def get_text(self, key: str, lang: str | None = None) -> str:
        current_lang = lang or self.default_language
        return TRANSLATIONS.get(current_lang, TRANSLATIONS[self.default_language]).get(
            key, key
        )

    def _setup_templates(self) -> None:
        current_dir = Path(__file__).parent.parent
        template_dir = str(current_dir / "templates")
        self.template_dir = template_dir
        self.jinja_template = JinjaTemplate(template_dir)
        self.jinja_template.env.globals.update({"get_text": self.get_text})

    def _init_admin_db(self) -> None:
        @self.app.startup_handler
        async def init_admin() -> None:
            try:
                self.init_register_auth_models()
                await self._ensure_default_admin()
                if self.startup_function:
                    await self.startup_function()
            except Exception:
                traceback.print_exc()
                raise

    def init_register_auth_models(self) -> None:
        self.register_model(AdminUser, AdminUserAdmin)
        self.register_model(Role, RoleAdmin)
        self.register_model(UserRole, UserRoleAdmin)

    async def _ensure_default_admin(self) -> None:
        session = self.session_factory()
        try:
            result = await session.execute(
                select(AdminUser).where(
                    or_(
                        AdminUser.username == "admin",
                        AdminUser.email == "admin@example.com",
                    )
                )
            )
            admin_user = result.scalar_one_or_none()
            if admin_user is None:
                session.add(
                    AdminUser(
                        username="admin",
                        password=AdminUser.hash_password("admin"),
                        email="admin@example.com",
                        is_superuser=True,
                        is_active=True,
                    )
                )
                try:
                    await session.commit()
                except IntegrityError:
                    # Another startup handler/process created the default admin
                    # concurrently. Treat as success.
                    await session.rollback()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    def _setup_routes(self) -> None:
        @self.app.get(f"/{self.prefix}")
        async def admin_index(request: Request):
            user = await self._get_current_user(request)
            if not user:
                return Response(
                    status_code=307,
                    description="Location login page",
                    headers={"Location": f"/{self.prefix}/login"},
                )

            language = await self._get_language(request)
            filtered_models = {}
            for route_id, model_admin in self.models.items():
                if await self.check_permission(request, route_id, "view"):
                    filtered_models[route_id] = model_admin

            context = {
                "site_title": self.title,
                "models": filtered_models,
                "menus": self.menu_manager.get_menu_tree(),
                "user": user,
                "language": language,
                "copyright": self.copyright,
            }
            return self.jinja_template.render_template("admin/index.html", **context)

        @self.app.get(f"/{self.prefix}/login")
        async def admin_login(request: Request):
            user = await self._get_current_user(request)
            if user:
                return Response(
                    status_code=307,
                    description="Location to admin page",
                    headers={"Location": f"/{self.prefix}"},
                )

            language = await self._get_language(request)
            context = {
                "user": None,
                "language": language,
                "site_title": self.title,
                "copyright": self.copyright,
            }
            return self.jinja_template.render_template("admin/login.html", **context)

        @self.app.post(f"/{self.prefix}/login")
        async def admin_login_post(request: Request):
            try:
                params = parse_qs(_body_to_text(request.body))
                username = _first_value(params.get("username"), "")
                password = _first_value(params.get("password"), "")

                session = self.session_factory()
                try:
                    user = await AdminUser.authenticate(session, username, password)
                    if not user:
                        context = {
                            "error": "Invalid username or password",
                            "user": None,
                            "site_title": self.title,
                            "copyright": self.copyright,
                        }
                        return self.jinja_template.render_template(
                            "admin/login.html", **context
                        )

                    user.last_login = datetime.utcnow()
                    await session.commit()
                finally:
                    await session.close()

                token = self._generate_session_token(user.id)
                cookie_attrs = [
                    f"session_token={token}",
                    "HttpOnly",
                    "Path=/",
                    f"Max-Age={self.session_expire}",
                ]
                return Response(
                    status_code=303,
                    description="Login successful",
                    headers={
                        "Location": f"/{self.prefix}",
                        "Set-Cookie": "; ".join(cookie_attrs),
                        "Cache-Control": "no-cache, no-store, must-revalidate",
                    },
                )
            except Exception as exc:
                traceback.print_exc()
                return Response(status_code=500, description=f"Login failed: {exc}")

        @self.app.get(f"/{self.prefix}/logout")
        async def admin_logout(request: Request):
            cookie_attrs = [
                "session_token=",
                "HttpOnly",
                "Path=/",
                "Max-Age=0",
            ]
            return Response(
                status_code=303,
                description="",
                headers={
                    "Location": f"/{self.prefix}/login",
                    "Set-Cookie": "; ".join(cookie_attrs),
                },
            )

        @self.app.get(f"/{self.prefix}/:route_id/search")
        async def model_search(request: Request):
            route_id: str = request.path_params.get("route_id")
            user = await self._get_current_user(request)
            if not user:
                return Response(status_code=401, description="Not logged in")

            model_admin = self.models.get(route_id)
            if not model_admin:
                return Response(status_code=404, description="Model not found")

            search_values = {
                field.name: unquote(_first_value(request.query_params.get(f"search_{field.name}"), ""))
                for field in model_admin.search_fields
                if request.query_params.get(f"search_{field.name}")
            }
            queryset = await model_admin.get_queryset(request, search_values)
            objects = await queryset.limit(model_admin.per_page)

            data = []
            for obj in objects:
                display = await model_admin.serialize_object(obj, for_display=True)
                raw = await model_admin.serialize_object(obj, for_display=False)
                data.append({"display": display, "data": raw})
            return jsonify({"data": data})

        @self.app.get(f"/{self.prefix}/:route_id")
        async def model_list(request: Request):
            route_id: str = request.path_params.get("route_id")
            user = await self._get_current_user(request)
            if not user:
                return Response(
                    status_code=303,
                    headers={"Location": f"/{self.prefix}/login"},
                    description="Not logged in",
                )

            language = await self._get_language(request)
            if not await self.check_permission(request, route_id, "view"):
                return Response(status_code=403, description="Permission denied")

            model_admin = self.get_model_admin(route_id)
            if not model_admin:
                return Response(status_code=404, description="model not found")

            frontend_config = await model_admin.get_frontend_config()
            frontend_config["language"] = language
            frontend_config["default_language"] = self.default_language

            filtered_models = {}
            for rid, madmin in self.models.items():
                if await self.check_permission(request, rid, "view"):
                    filtered_models[rid] = madmin

            context = {
                "site_title": self.title,
                "models": filtered_models,
                "menus": self.menu_manager.get_menu_tree(),
                "user": user,
                "language": language,
                "current_model": route_id,
                "verbose_name": model_admin.verbose_name,
                "frontend_config": frontend_config,
                "copyright": self.copyright,
            }
            return self.jinja_template.render_template("admin/model_list.html", **context)

        @self.app.post(f"/{self.prefix}/:route_id/add")
        async def model_add_post(request: Request):
            route_id: str = request.path_params.get("route_id")
            model_admin = self.get_model_admin(route_id)
            if not model_admin:
                return Response(status_code=404, description="Model not found")
            if not await self.check_permission(request, route_id, "add"):
                return Response(status_code=403, description="No create permission")

            params = parse_qs(_body_to_text(request.body))
            form_data = _parse_form_payload(params)
            success, message = await model_admin.handle_add(request, form_data)
            return Response(
                status_code=200 if success else 400,
                description=message,
                headers={"Content-Type": "text/html"},
            )

        @self.app.post(f"/{self.prefix}/:route_id/:id/edit")
        async def model_edit_post(request: Request):
            route_id: str = request.path_params.get("route_id")
            object_id: str = request.path_params.get("id")

            model_admin = self.get_model_admin(route_id)
            if not model_admin:
                return Response(status_code=404, description="Model not found")
            if not model_admin.enable_edit:
                return Response(status_code=403, description="model not allow edit")
            if not await self.check_permission(request, route_id, "edit"):
                return Response(status_code=403, description="No edit permission")

            params = parse_qs(_body_to_text(request.body))
            form_data = _parse_form_payload(params)
            success, message = await model_admin.handle_edit(request, object_id, form_data)
            return Response(
                status_code=200 if success else 400,
                description=message,
                headers={"Content-Type": "text/html"},
            )

        @self.app.post(f"/{self.prefix}/:route_id/:id/delete")
        async def model_delete(request: Request):
            route_id: str = request.path_params.get("route_id")
            object_id: str = request.path_params.get("id")
            user = await self._get_current_user(request)
            if not user:
                return Response(status_code=401, description="Not logged in")

            model_admin = self.get_model_admin(route_id)
            if not model_admin:
                return Response(status_code=404, description="Model not found")
            if not await self.check_permission(request, route_id, "delete"):
                return Response(status_code=403, description="No delete permission")

            success, message = await model_admin.handle_delete(request, object_id)
            return Response(
                status_code=200 if success else 400,
                description=message,
                headers={"Content-Type": "text/html"},
            )

        @self.app.get(f"/{self.prefix}/:route_id/data")
        async def model_data(request: Request):
            route_id: str = request.path_params.get("route_id")
            model_admin = self.get_model_admin(route_id)
            if not model_admin:
                return jsonify({"error": "Model not found"})

            params: dict = request.query_params.to_dict()
            query_params = {
                "limit": int(_first_value(params.get("limit"), 10)),
                "offset": int(_first_value(params.get("offset"), 0)),
                "search": _first_value(params.get("search"), ""),
                "sort": _first_value(params.get("sort"), ""),
                "order": _first_value(params.get("order"), "asc"),
            }
            for key, value in params.items():
                if key not in {"limit", "offset", "search", "sort", "order", "_"}:
                    query_params[key] = _first_value(value)

            queryset, total = await model_admin.handle_query(request, query_params)

            data = []
            async for obj in queryset:
                serialized = await model_admin.serialize_object(obj)
                data.append({"data": serialized, "display": serialized})

            return jsonify({"total": total, "data": data})

        @self.app.post(f"/{self.prefix}/:route_id/batch_delete")
        async def model_batch_delete(request: Request):
            route_id: str = request.path_params.get("route_id")
            user = await self._get_current_user(request)
            if not user:
                return Response(status_code=401, description="Not logged in")

            model_admin = self.get_model_admin(route_id)
            if not model_admin:
                return Response(status_code=404, description="Model not found")

            params = parse_qs(_body_to_text(request.body))
            ids = params.get("ids[]", [])
            if not ids:
                return jsonify(
                    {
                        "code": 400,
                        "message": "No records selected",
                        "success": False,
                    }
                )

            success, message, deleted_count = await model_admin.handle_batch_delete(
                request, ids
            )
            return jsonify(
                {
                    "code": 200 if success else 500,
                    "message": message,
                    "success": success,
                    "data": {"deleted_count": deleted_count},
                }
            )

        @self.app.get(f"/{self.prefix}/:route_id/inline_data")
        async def get_inline_data(request: Request):
            route_id = request.path_params.get("route_id")
            model_admin = self.get_model_admin(route_id)
            if not model_admin:
                return jsonify({"error": "Model not found"})

            params: dict = request.query_params.to_dict()
            parent_id = _first_value(params.get("parent_id"), "")
            inline_model = _first_value(params.get("inline_model"), "")
            if not parent_id or not inline_model:
                return jsonify({"error": "Missing parameters"})

            data = await model_admin.get_inline_data(parent_id, inline_model)
            return jsonify({"success": True, "data": data, "total": len(data), "fields": []})

        @self.app.post(f"/{self.prefix}/upload")
        async def file_upload(request: Request):
            try:
                user = await self._get_current_user(request)
                if not user:
                    return jsonify(
                        {"code": 401, "message": "Not logged in", "success": False}
                    )

                files = request.files
                if not files:
                    return jsonify(
                        {
                            "code": 400,
                            "message": "No file uploaded",
                            "success": False,
                        }
                    )

                upload_path = request.form_data.get("upload_path", "static/uploads")
                uploaded_files = []
                for file_name, file_bytes in files.items():
                    lower_name = file_name.lower()
                    if not lower_name.endswith(
                        (
                            ".jpg",
                            ".jpeg",
                            ".png",
                            ".gif",
                            ".sql",
                            ".xlsx",
                            ".csv",
                            ".xls",
                        )
                    ):
                        return jsonify(
                            {
                                "code": 400,
                                "message": "Unsupported file type",
                                "success": False,
                            }
                        )

                    import os
                    import uuid

                    safe_filename = (
                        f"{uuid.uuid4().hex}{os.path.splitext(file_name)[1]}"
                    )
                    os.makedirs(upload_path, exist_ok=True)
                    file_path = os.path.join(upload_path, safe_filename)
                    with open(file_path, "wb") as file_obj:
                        file_obj.write(file_bytes)

                    file_url = f"/{file_path.replace(os.sep, '/')}"
                    uploaded_files.append(
                        {
                            "original_name": file_name,
                            "saved_name": safe_filename,
                            "url": file_url,
                        }
                    )

                return jsonify(
                    {
                        "code": 200,
                        "message": "Upload successful",
                        "success": True,
                        "data": uploaded_files[0] if uploaded_files else None,
                    }
                )
            except Exception as exc:
                traceback.print_exc()
                return jsonify(
                    {
                        "code": 500,
                        "message": f"Upload failed: {exc}",
                        "success": False,
                    }
                )

        @self.app.post(f"/{self.prefix}/set_language")
        async def set_language(request: Request):
            try:
                params = parse_qs(_body_to_text(request.body))
                language = _first_value(params.get("language"), self.default_language)
                cookie_attrs = [
                    f"session={json.dumps({'language': language})}",
                    "HttpOnly",
                    "Path=/",
                ]
                return Response(
                    status_code=200,
                    description="Language set successfully",
                    headers={"Set-Cookie": "; ".join(cookie_attrs)},
                )
            except Exception:
                return Response(status_code=500, description="Set language failed")

        @self.app.post(f"/{self.prefix}/:route_id/import")
        async def handle_import(request: Request):
            try:
                route_id = request.path_params.get("route_id")
                model_admin = self.get_model_admin(route_id)
                if not model_admin or not model_admin.allow_import:
                    return jsonify(
                        {"success": False, "message": "Import is not supported"}
                    )

                files = request.files
                if not files:
                    return jsonify(
                        {"success": False, "message": "No file uploaded"}
                    )

                filename = list(files.keys())[0]
                file_data = next(iter(files.values()))
                if not any(filename.endswith(ext) for ext in [".xlsx", ".xls", ".csv"]):
                    return jsonify(
                        {"success": False, "message": "Only Excel or CSV files are supported"}
                    )

                import io
                import pandas as pd

                if filename.endswith(".csv"):
                    dataframe = pd.read_csv(io.BytesIO(file_data))
                else:
                    dataframe = pd.read_excel(io.BytesIO(file_data))

                missing_fields = [
                    field
                    for field in model_admin.import_fields
                    if field not in dataframe.columns
                ]
                if missing_fields:
                    return jsonify(
                        {
                            "success": False,
                            "message": f"Missing required fields: {', '.join(missing_fields)}",
                        }
                    )

                success_count = 0
                error_count = 0
                errors: list[str] = []
                session = self.session_factory()
                try:
                    for _, row in dataframe.iterrows():
                        try:
                            payload = {
                                field: row[field]
                                for field in model_admin.import_fields
                            }
                            session.add(model_admin.model(**payload))
                            success_count += 1
                        except Exception as exc:
                            error_count += 1
                            errors.append(str(exc))
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise
                finally:
                    await session.close()

                return jsonify(
                    {
                        "success": True,
                        "message": f"Import completed: {success_count} succeeded, {error_count} failed",
                        "errors": errors if errors else None,
                    }
                )
            except Exception as exc:
                traceback.print_exc()
                return jsonify({"success": False, "message": f"Import failed: {exc}"})

    def register_model(
        self,
        model: Type[Any],
        admin_class: Optional[Type[ModelAdmin]] = None,
    ) -> None:
        if admin_class is None:
            admin_class = ModelAdmin

        instance = admin_class(model, session_factory=self.session_factory)
        instance.site = self

        route_id = admin_class.__name__
        base_route_id = route_id
        counter = 1
        while route_id in self.models:
            route_id = f"{base_route_id}{counter}"
            counter += 1

        instance.route_id = route_id
        self.models[route_id] = instance

        self.model_registry.setdefault(model.__name__, []).append(instance)

    def _generate_session_token(self, user_id: int) -> str:
        timestamp = int(datetime.utcnow().timestamp())
        raw_token = f"{user_id}:{timestamp}:{secrets.token_hex(16)}"
        signature = _sign_token(raw_token, self.session_secret)
        return base64.urlsafe_b64encode(f"{raw_token}:{signature}".encode()).decode()

    def _verify_session_token(self, token: str) -> tuple[bool, Optional[int]]:
        try:
            decoded = base64.urlsafe_b64decode(token.encode()).decode()
            raw_token, signature = decoded.rsplit(":", 1)
            expected_signature = _sign_token(raw_token, self.session_secret)
            if not secrets.compare_digest(signature, expected_signature):
                return False, None

            user_id, timestamp, _ = raw_token.split(":", 2)
            if datetime.utcnow().timestamp() - int(timestamp) > self.session_expire:
                return False, None
            return True, int(user_id)
        except Exception:
            return False, None

    async def _get_current_user(self, request: Request) -> Optional[AdminUser]:
        cookie_header = request.headers.get("Cookie")
        if not cookie_header:
            return None

        cookies = _parse_cookie_header(cookie_header)
        token = cookies.get("session_token")
        if not token:
            return None

        valid, user_id = self._verify_session_token(token)
        if not valid or user_id is None:
            return None

        session = self.session_factory()
        try:
            return await session.get(AdminUser, user_id)
        finally:
            await session.close()

    async def _get_language(self, request: Request) -> str:
        session_data = request.headers.get("Cookie")
        if not session_data:
            return self.default_language

        session_dict = _parse_cookie_header(session_data)
        payload = session_dict.get("session")
        if not payload:
            return self.default_language

        try:
            data = json.loads(payload)
            return data.get("language", self.default_language)
        except json.JSONDecodeError:
            return self.default_language

    def register_menu(self, menu_item: MenuItem):
        self.menu_manager.register_menu(menu_item)

    def get_model_admin(self, route_id: str) -> Optional[ModelAdmin]:
        return self.models.get(route_id)

    async def check_permission(self, request: Request, model_name: str, action: str) -> bool:
        user = await self._get_current_user(request)
        if not user:
            return False

        if user.is_superuser:
            return True

        session = self.session_factory()
        try:
            stmt = (
                select(Role)
                .join(UserRole, UserRole.role_id == Role.id)
                .where(UserRole.user_id == user.id)
            )
            result = await session.execute(stmt)
            roles = result.scalars().all()
            for role in roles:
                if role.accessible_models == ["*"]:
                    return True
                if role.accessible_models and model_name in role.accessible_models:
                    return True
            return False
        finally:
            await session.close()


def _parse_cookie_header(header: str) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for item in header.split(";"):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        cookies[key.strip()] = value.strip()
    return cookies


def _sign_token(raw_token: str, secret: str) -> str:
    import hashlib

    return hashlib.sha256(f"{raw_token}:{secret}".encode()).hexdigest()


def _body_to_text(body: Any) -> str:
    if isinstance(body, bytes):
        return body.decode("utf-8")
    return str(body or "")


def _first_value(value: Any, default: Any = None) -> Any:
    if isinstance(value, list):
        return value[0] if value else default
    if value is None:
        return default
    return value


def _parse_form_payload(params: dict[str, list[str]]) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for key, value in params.items():
        raw = _first_value(value, "")
        try:
            data[key] = json.loads(raw)
        except Exception:
            data[key] = raw
    return data
