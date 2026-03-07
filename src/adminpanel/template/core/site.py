from typing import Any, Type, Optional, Dict, List, Union
from types import ModuleType
import asyncio
from tortoise import Model, Tortoise, connections
from tortoise.exceptions import IntegrityError as TortoiseIntegrityError
from robyn import Robyn, Request, Response, jsonify
from robyn.templating import JinjaTemplate
from pathlib import Path
import os
import json
from collections import deque
from datetime import datetime
import traceback
from urllib.parse import parse_qs, unquote
import secrets
import hashlib
import base64
import atexit

from ..auth_models import AdminUser, UserRole
from .admin import ModelAdmin
from .menu import MenuManager, MenuItem
from typing import Callable


class AdminSite:
    """Admin站点主类"""

    def __init__(
        self,
        app: Robyn,
        title: str = "QC Robyn Admin",  # 后台名称
        prefix: str = "admin",  # 路由前缀
        copyright: str = "QC Robyn Admin",  # 版权信息，如果为None则不显示
        db_url: Optional[str] = None,
        modules: Optional[Dict[str, List[Union[str, ModuleType]]]] = None,
        generate_schemas: bool = True,
        default_language: str = "en_US",
        default_admin_username: str = "admin",
        default_admin_password: str = "admin",
        startup_function: Optional[Callable] = None,
    ):
        """
        初始化Admin站点

        :param app: Robyn应用实例
        :param title: 后台系统名称
        :param prefix: 后台路由前缀
        :param db_url: 数据库连接URL,如果为None则尝试复用已有配置
        :param modules: 模型模块配置,如果为None则尝试复用已有配置
        :param generate_schemas: 是否自动生成数据库表结构
        :param default_language: default language code
        """
        self.app = app
        self.title = title  # 后台名称
        self.prefix = prefix  # 路由前缀
        self.models: Dict[str, ModelAdmin] = {}
        self.model_registry = {}
        self.default_language = default_language
        self.default_admin_username = default_admin_username
        self.default_admin_password = default_admin_password
        self._default_admin_initialized = False
        self._default_admin_init_lock = asyncio.Lock()
        self.menu_manager = MenuManager()
        self.copyright = copyright  # 添加版权属性
        self.startup_function = startup_function
        # 设置模板
        self._setup_templates()

        # 初始化数据库
        self.db_url = db_url
        self.modules = modules
        self.generate_schemas = generate_schemas
        # 确保数据库文件路径存在
        if db_url and db_url.startswith("sqlite"):
            db_path = db_url.replace("sqlite://", "")
            if db_path != ":memory:":
                os.makedirs(
                    os.path.dirname(os.path.abspath(db_path)), exist_ok=True
                )

        # 注册程序退出时的清理函数
        atexit.register(self._cleanup_db)

        # 初始化数据库
        self._init_admin_db()

        # 设置路由
        self._setup_routes()

        self.session_secret = secrets.token_hex(32)  # 生成随机密钥
        self.session_expire = 24 * 60 * 60  # 会话过期时间（秒）
        self.max_recent_actions = 100
        self.recent_actions: list[dict[str, str]] = []
        self.default_settings = {
            "log_file_path": "logs/app.log",
            "log_tail_lines": 200,
            "theme": "dark",
        }

    async def _get_visible_models(
        self, request: Request
    ) -> Dict[str, ModelAdmin]:
        visible: Dict[str, ModelAdmin] = {}
        for route_id, model_admin in self.models.items():
            if await self.check_permission(request, route_id, "view"):
                visible[route_id] = model_admin
        return visible

    def _get_model_table_name(self, model_admin: ModelAdmin) -> str:
        model = getattr(model_admin, "model", None)
        table_name = getattr(model, "__tablename__", None)
        if isinstance(table_name, str) and table_name:
            return table_name

        meta = getattr(model, "_meta", None)
        db_table = getattr(meta, "db_table", None)
        if isinstance(db_table, str) and db_table:
            return db_table
        return ""

    def _get_model_source_filename(self, model_admin: ModelAdmin) -> str:
        model = getattr(model_admin, "model", None)
        module_name = getattr(model, "__module__", "")
        if not isinstance(module_name, str) or not module_name:
            return "Models"

        module_parts = module_name.split(".")
        file_name = module_parts[-1]
        if file_name == "__init__" and len(module_parts) > 1:
            file_name = module_parts[-2]
        return self._format_label(file_name or "models", pluralize=True)

    @staticmethod
    def _pluralize_word(word: str) -> str:
        lower_word = word.lower()
        if lower_word.endswith("s"):
            return word
        if lower_word.endswith(("x", "z", "ch", "sh")):
            return f"{word}es"
        if (
            lower_word.endswith("y")
            and len(lower_word) > 1
            and lower_word[-2] not in {"a", "e", "i", "o", "u"}
        ):
            return f"{word[:-1]}ies"
        return f"{word}s"

    def _format_label(self, raw_value: str, pluralize: bool) -> str:
        normalized = raw_value.strip().replace("-", "_").replace(" ", "_")
        parts = [part for part in normalized.split("_") if part]
        if not parts:
            return "Models" if pluralize else "Model"

        if pluralize:
            parts[-1] = self._pluralize_word(parts[-1])

        return " ".join(part.capitalize() for part in parts)

    def _get_model_display_name(self, model_admin: ModelAdmin) -> str:
        table_name = self._get_model_table_name(model_admin)
        if table_name:
            return self._format_label(table_name, pluralize=False)
        return self._format_label(
            str(model_admin.verbose_name), pluralize=False
        )

    def _build_model_categories(
        self, visible_models: Dict[str, ModelAdmin]
    ) -> List[Dict[str, object]]:
        grouped: Dict[str, List[Dict[str, object]]] = {}
        for route_id, model_admin in visible_models.items():
            category_name = self._get_model_source_filename(model_admin)
            grouped.setdefault(category_name, []).append(
                {
                    "route_id": route_id,
                    "model_admin": model_admin,
                    "display_name": self._get_model_display_name(model_admin),
                }
            )

        categories: List[Dict[str, object]] = []
        for category_name in sorted(grouped.keys()):
            models_in_category = sorted(
                grouped[category_name],
                key=lambda item: str(item["display_name"]).lower(),
            )
            categories.append(
                {"name": category_name, "models": models_in_category}
            )
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
                "timestamp": datetime.utcnow().strftime(
                    "%Y-%m-%d %H:%M:%S UTC"
                ),
                "username": username or "system",
                "action": action,
                "target": target,
                "details": details,
            }
        )
        if len(self.recent_actions) > self.max_recent_actions:
            self.recent_actions = self.recent_actions[
                -self.max_recent_actions :
            ]

    def _get_admin_settings(self, request: Request) -> Dict[str, object]:
        settings = dict(self.default_settings)
        cookie_header = request.headers.get("Cookie")
        if not cookie_header:
            return settings

        cookies = _parse_cookie_header(cookie_header)
        raw = cookies.get("admin_settings")
        if not raw:
            return settings

        try:
            payload = _decode_cookie_payload(raw)
            decoded = json.loads(payload)
            if isinstance(decoded, dict):
                log_path = decoded.get("log_file_path")
                if isinstance(log_path, str) and log_path.strip():
                    settings["log_file_path"] = log_path.strip()

                log_tail = decoded.get("log_tail_lines")
                if isinstance(log_tail, int):
                    settings["log_tail_lines"] = max(20, min(log_tail, 2000))

                theme = decoded.get("theme")
                if theme in {"dark", "light"}:
                    settings["theme"] = theme
        except Exception:
            return settings
        return settings

    def _build_settings_cookie(self, settings: Dict[str, object]) -> str:
        payload = json.dumps(settings, separators=(",", ":"))
        encoded = _encode_cookie_payload(payload)
        attrs = [
            f"admin_settings={encoded}",
            "Path=/",
            "Max-Age=2592000",
            "SameSite=Lax",
        ]
        return "; ".join(attrs)

    def _read_log_lines(
        self, log_file_path: str, max_lines: int
    ) -> tuple[List[str], str]:
        max_lines = max(20, min(int(max_lines), 2000))
        candidate = Path(log_file_path)
        if not candidate.is_absolute():
            candidate = Path.cwd() / candidate

        resolved_path = str(candidate)
        if not candidate.exists():
            return [f"Log file does not exist: {resolved_path}"], resolved_path

        try:
            with candidate.open(
                "r", encoding="utf-8", errors="replace"
            ) as handle:
                lines = [
                    line.rstrip("\n")
                    for line in deque(handle, maxlen=max_lines)
                ]
            if not lines:
                return ["Log file is empty."], resolved_path
            return lines, resolved_path
        except Exception as exc:
            return [f"Failed to read log file: {exc}"], resolved_path

    def get_text(self, key: str, lang: str = None) -> str:
        """使用站点默认语言的文本获取函数"""
        from ..i18n.translations import TRANSLATIONS

        current_lang = lang or self.default_language
        return TRANSLATIONS.get(
            current_lang, TRANSLATIONS[self.default_language]
        ).get(key, key)

    def init_register_auth_models(self):
        # Kept for backward compatibility with older templates.
        return None

    def _setup_templates(self):
        """设置模板目录"""
        current_dir = Path(__file__).parent.parent
        template_dir = os.path.join(current_dir, "templates")
        self.template_dir = template_dir
        # 创建 Jinja2 环境并添加全局函数
        self.jinja_template = JinjaTemplate(template_dir)
        self.jinja_template.env.globals.update({"get_text": self.get_text})

    def _cleanup_db(self):
        """清理数据库连接"""
        if Tortoise._inited:
            import asyncio

            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            loop.run_until_complete(Tortoise.close_connections())

    def _init_admin_db(self):
        """初始化admin数据"""
        from tortoise import Tortoise

        @self.app.startup_handler
        async def init_admin():
            try:
                # 如果没有提供配置,试获取已有配置
                if not self.db_url:
                    if not Tortoise._inited:
                        raise Exception(
                            "Database is not initialized. Configure database or provide db_url."
                        )
                    # 复用现有配置
                    current_config = Tortoise.get_connection("default").config
                    self.db_url = current_config.get("credentials", {}).get(
                        "dsn"
                    )

                # 如果是相对路径的sqlite数据库，转换为绝对路径
                if (
                    self.db_url
                    and self.db_url.startswith("sqlite://")
                    and not self.db_url.startswith("sqlite://:memory:")
                ):
                    db_path = self.db_url.replace("sqlite://", "")
                    if not os.path.isabs(db_path):
                        abs_path = os.path.abspath(db_path)
                        self.db_url = f"sqlite://{abs_path}"

                if self.modules is None or not self.modules:
                    if not Tortoise._inited:
                        raise Exception(
                            "Model modules are required. "
                            "Provide modules explicitly when database is not initialized."
                        )
                    self.modules = dict(Tortoise.apps)

                # 初始化数据库连接
                if not Tortoise._inited:
                    print(f"Initializing database with URL: {self.db_url}")
                    await Tortoise.init(
                        db_url=self.db_url, modules=self.modules
                    )
                    print("Database initialized successfully")

                # 生成表结构
                if self.generate_schemas:
                    print("Generating database schemas...")
                    await Tortoise.generate_schemas()
                    print("Database schemas generated successfully")

                await self._ensure_default_admin()

                if self.startup_function:
                    await self.startup_function()

            except Exception as e:
                print(f"Error in database initialization: {str(e)}")
                traceback.print_exc()
                raise

    async def _ensure_default_admin(self):
        if self._default_admin_initialized:
            return

        async with self._default_admin_init_lock:
            if self._default_admin_initialized:
                return

            advisory_lock_acquired = False
            advisory_lock_id = 193384911
            db_url = str(self.db_url or "").strip().lower()
            using_postgres = db_url.startswith("postgres")
            try:
                if using_postgres:
                    connection = connections.get("default")
                    await connection.execute_query(
                        f"SELECT pg_advisory_lock({advisory_lock_id})"
                    )
                    advisory_lock_acquired = True

                existing_admin = await AdminUser.filter(
                    username=self.default_admin_username
                ).first()
                if not existing_admin:
                    existing_admin = await AdminUser.filter(
                        email="admin@example.com"
                    ).first()
                if not existing_admin:
                    print("Creating default admin user...")
                    try:
                        await AdminUser.create(
                            username=self.default_admin_username,
                            password=AdminUser.hash_password(
                                self.default_admin_password
                            ),
                            email="admin@example.com",
                            is_superuser=True,
                            is_active=True,
                        )
                        print("Default admin user created successfully")
                    except TortoiseIntegrityError:
                        # Another process created the same default admin
                        # concurrently. Treat as success.
                        pass
                self._default_admin_initialized = True
            except Exception as e:
                print(f"Error creating admin user: {str(e)}")
                traceback.print_exc()
                raise
            finally:
                if advisory_lock_acquired:
                    try:
                        connection = connections.get("default")
                        await connection.execute_query(
                            f"SELECT pg_advisory_unlock({advisory_lock_id})"
                        )
                    except Exception:
                        pass

    def _setup_routes(self):
        """设置路由"""

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
            settings = self._get_admin_settings(request)
            filtered_models = await self._get_visible_models(request)
            model_categories = self._build_model_categories(filtered_models)
            recent_actions = list(reversed(self.recent_actions[-20:]))
            log_lines, resolved_log_path = self._read_log_lines(
                str(settings["log_file_path"]),
                int(settings["log_tail_lines"]),
            )

            context = {
                "site_title": self.title,
                "models": filtered_models,
                "model_categories": model_categories,
                "user": user,
                "language": language,
                "copyright": self.copyright,
                "active_tab": "dashboard",
                "recent_actions": recent_actions,
                "log_lines": log_lines,
                "resolved_log_path": resolved_log_path,
                "admin_settings": settings,
            }
            return self.jinja_template.render_template(
                "admin/index.html", **context
            )

        @self.app.get(f"/{self.prefix}/models")
        async def models_index(request: Request):
            user = await self._get_current_user(request)
            if not user:
                return Response(
                    status_code=307,
                    description="Location login page",
                    headers={"Location": f"/{self.prefix}/login"},
                )

            language = await self._get_language(request)
            settings = self._get_admin_settings(request)
            filtered_models = await self._get_visible_models(request)
            model_categories = self._build_model_categories(filtered_models)
            context = {
                "site_title": self.title,
                "models": filtered_models,
                "model_categories": model_categories,
                "user": user,
                "language": language,
                "copyright": self.copyright,
                "active_tab": "models",
                "admin_settings": settings,
            }
            return self.jinja_template.render_template(
                "admin/models.html", **context
            )

        @self.app.get(f"/{self.prefix}/users")
        async def users_alias(request: Request):
            user = await self._get_current_user(request)
            if not user:
                return Response(
                    status_code=307,
                    description="Location login page",
                    headers={"Location": f"/{self.prefix}/login"},
                )
            return Response(
                status_code=303,
                description="Users tab moved to models",
                headers={"Location": f"/{self.prefix}/models"},
            )

        @self.app.get(f"/{self.prefix}/settings")
        async def settings_page(request: Request):
            user = await self._get_current_user(request)
            if not user:
                return Response(
                    status_code=307,
                    description="Location login page",
                    headers={"Location": f"/{self.prefix}/login"},
                )

            language = await self._get_language(request)
            settings = self._get_admin_settings(request)
            filtered_models = await self._get_visible_models(request)
            model_categories = self._build_model_categories(filtered_models)
            context = {
                "site_title": self.title,
                "models": filtered_models,
                "model_categories": model_categories,
                "user": user,
                "language": language,
                "copyright": self.copyright,
                "active_tab": "settings",
                "admin_settings": settings,
            }
            return self.jinja_template.render_template(
                "admin/settings.html", **context
            )

        @self.app.post(f"/{self.prefix}/settings")
        async def settings_save(request: Request):
            user = await self._get_current_user(request)
            if not user:
                return Response(
                    status_code=307,
                    description="Location login page",
                    headers={"Location": f"/{self.prefix}/login"},
                )

            current_settings = self._get_admin_settings(request)
            data = request.body
            if isinstance(data, bytes):
                data = data.decode("utf-8")
            params = parse_qs(str(data or ""))

            log_file_path = params.get(
                "log_file_path", [str(current_settings["log_file_path"])]
            )[0]
            if not isinstance(log_file_path, str) or not log_file_path.strip():
                log_file_path = str(current_settings["log_file_path"])

            raw_log_tail = params.get(
                "log_tail_lines", [str(current_settings["log_tail_lines"])]
            )[0]
            try:
                log_tail_lines = int(raw_log_tail)
            except Exception:
                log_tail_lines = int(current_settings["log_tail_lines"])
            log_tail_lines = max(20, min(log_tail_lines, 2000))

            theme = params.get("theme", [str(current_settings["theme"])])[0]
            if theme not in {"dark", "light"}:
                theme = str(current_settings["theme"])

            updated_settings = {
                "log_file_path": str(log_file_path).strip(),
                "log_tail_lines": log_tail_lines,
                "theme": theme,
            }
            self._record_action(
                username=user.username,
                action="settings_updated",
                target="admin",
                details=f"log_file_path={updated_settings['log_file_path']}",
            )
            return Response(
                status_code=303,
                description="Settings saved",
                headers={
                    "Location": f"/{self.prefix}/settings",
                    "Set-Cookie": self._build_settings_cookie(
                        updated_settings
                    ),
                },
            )

        @self.app.get(f"/{self.prefix}/login")
        async def admin_login(request: Request):
            user = await self._get_current_user(request)
            if user:
                return Response(
                    status_code=307,
                    description="Location to admin page",
                    headers={"Location": f"/{self.prefix}"},
                )

            language = await self._get_language(request)  # 获取语言设置
            settings = self._get_admin_settings(request)
            context = {
                "user": None,
                "language": language,
                "site_title": self.title,
                "copyright": self.copyright,  # 传递版权信息到模板
                "active_tab": "",
                "admin_settings": settings,
            }
            return self.jinja_template.render_template(
                "admin/login.html", **context
            )

        @self.app.post(f"/{self.prefix}/login")
        async def admin_login_post(request: Request):
            try:
                data = request.body
                params = parse_qs(data)
                params_dict = {key: value[0] for key, value in params.items()}
                username = params_dict.get("username")
                password = params_dict.get("password")

                print(f"Login attempt - username: {username}")  # 调试日志

                user = await AdminUser.authenticate(username, password)
                if user:
                    # 生成安全的会话令牌
                    token = self._generate_session_token(user.id)
                    print(
                        f"Generated token for user {user.username}: {token}"
                    )  # 调试日志

                    # 修改 cookie 设置
                    cookie_attrs = [
                        f"session_token={token}",
                        "HttpOnly",
                        "Path=/",
                        f"Max-Age={self.session_expire}",
                    ]

                    # 在开发环境中暂时移除这些限制
                    # "SameSite=Lax",
                    # "Secure",

                    # 更新用户最后登录时间
                    user.last_login = datetime.now()
                    await user.save()
                    self._record_action(
                        username=user.username,
                        action="login",
                        target="admin",
                    )

                    # 构造响应
                    response = Response(
                        status_code=303,
                        description="Login successful",
                        headers={
                            "Location": f"/{self.prefix}",
                            "Set-Cookie": "; ".join(cookie_attrs),
                            "Cache-Control": "no-cache, no-store, must-revalidate",
                        },
                    )

                    print("Response headers:", response.headers)  # 调试日志
                    return response
                else:
                    print(
                        f"Authentication failed for username: {username}"
                    )  # 调试日志
                    language = await self._get_language(request)
                    settings = self._get_admin_settings(request)
                    context = {
                        "error": "Invalid username or password",
                        "user": None,
                        "language": language,
                        "site_title": self.title,
                        "copyright": self.copyright,
                        "active_tab": "",
                        "admin_settings": settings,
                    }
                    return self.jinja_template.render_template(
                        "admin/login.html", **context
                    )

            except Exception as e:
                print(f"Login error: {str(e)}")
                traceback.print_exc()  # 打印完整的错误堆栈
                return Response(
                    status_code=500, description=f"Login failed: {str(e)}"
                )

        @self.app.get(f"/{self.prefix}/logout")
        async def admin_logout(request: Request):
            user = await self._get_current_user(request)
            if user:
                self._record_action(
                    username=user.username,
                    action="logout",
                    target="admin",
                )
            # 清cookie
            cookie_attrs = [
                "session_token=",
                "HttpOnly",
                "SameSite=Lax",
                "Secure",
                "Path=/",
                "Max-Age=0",  # 立即过期
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
            """模型页面中，搜索功能相关接口，进行匹配查询结果"""
            route_id: str = request.path_params.get("route_id")
            user = await self._get_current_user(request)
            if not user:
                return Response(
                    status_code=401,
                    description="Not logged in",
                    headers={"Content-Type": "application/json"},
                )

            model_admin = self.models.get(route_id)
            if not model_admin:
                return Response(
                    status_code=404,
                    description="Model not found",
                    headers={"Content-Type": "application/json"},
                )

            # 获取索参数， 同时还要进url解码
            search_values = {
                field.name: unquote(
                    request.query_params.get(f"search_{field.name}")
                )
                for field in model_admin.search_fields
                if request.query_params.get(f"search_{field.name}")
            }
            # 执行搜索查询
            queryset = await model_admin.get_queryset(request, search_values)
            objects = await queryset.limit(model_admin.per_page)

            # 序列化结果
            serialized_data = []
            for obj in objects:
                serialized_data.append(
                    {
                        "display": await model_admin.serialize_object(
                            obj, for_display=True
                        ),
                        "data": await model_admin.serialize_object(
                            obj, for_display=False
                        ),
                    }
                )
            result = {"data": serialized_data}
            return jsonify(result)

        @self.app.get(f"/{self.prefix}/:route_id")
        async def model_list(request: Request):
            try:
                route_id: str = request.path_params.get("route_id")
                user = await self._get_current_user(request)
                if not user:
                    return Response(
                        status_code=303,
                        headers={"Location": f"/{self.prefix}/login"},
                        description="Not logged in",
                    )

                if route_id == "users":
                    return Response(
                        status_code=303,
                        headers={"Location": f"/{self.prefix}/models"},
                        description="Users tab moved to models",
                    )

                language = await self._get_language(request)

                if not await self.check_permission(request, route_id, "view"):
                    return Response(
                        status_code=403,
                        headers={"Content-Type": "text/html"},
                        description="Permission denied",
                    )

                model_admin = self.get_model_admin(route_id)
                if not model_admin:
                    return Response(
                        status_code=404,
                        headers={"Content-Type": "text/html"},
                        description="model not found",
                    )

                frontend_config = await model_admin.get_frontend_config()

                # 确保语言设置确传递
                frontend_config["language"] = language
                frontend_config["default_language"] = self.default_language

                settings = self._get_admin_settings(request)
                filtered_models = await self._get_visible_models(request)
                model_categories = self._build_model_categories(
                    filtered_models
                )
                display_name = self._get_model_display_name(model_admin)

                context = {
                    "site_title": self.title,
                    "models": filtered_models,
                    "model_categories": model_categories,
                    "user": user,
                    "language": language,
                    "current_model": route_id,
                    "verbose_name": display_name,
                    "frontend_config": frontend_config,
                    "copyright": self.copyright,
                    "active_tab": "models",
                    "admin_settings": settings,
                }
                return self.jinja_template.render_template(
                    "admin/model_list.html", **context
                )

            except Exception as e:
                print(f"Error in model_list: {str(e)}")
                traceback.print_exc()
                return Response(
                    status_code=500,
                    headers={"Content-Type": "text/html"},
                    description=f"Failed to load list page: {str(e)}",
                )

        @self.app.get(f"/{self.prefix}/:route_id/add")
        async def model_add(request: Request):
            try:
                route_id: str = request.path_params.get("route_id")
                user = await self._get_current_user(request)
                if not user:
                    return Response(
                        status_code=303,
                        headers={"Location": f"/{self.prefix}/login"},
                        description="Not logged in",
                    )

                model_admin = self.get_model_admin(route_id)
                if not model_admin:
                    return Response(
                        status_code=404,
                        headers={"Content-Type": "text/html"},
                        description="model not found",
                    )

                if not await self.check_permission(request, route_id, "add"):
                    return Response(
                        status_code=403,
                        headers={"Content-Type": "text/html"},
                        description="No create permission",
                    )

                language = await self._get_language(request)
                form_fields = [
                    field.to_dict()
                    for field in await model_admin.get_form_fields()
                ]
                can_add = (
                    model_admin.allow_add
                    and await self.check_permission(request, route_id, "add")
                )

                settings = self._get_admin_settings(request)
                filtered_models = await self._get_visible_models(request)
                model_categories = self._build_model_categories(
                    filtered_models
                )
                display_name = self._get_model_display_name(model_admin)
                context = {
                    "site_title": self.title,
                    "models": filtered_models,
                    "model_categories": model_categories,
                    "user": user,
                    "language": language,
                    "current_model": route_id,
                    "verbose_name": display_name,
                    "route_id": route_id,
                    "object_id": "",
                    "form_fields": form_fields,
                    "form_data": {},
                    "can_edit": can_add,
                    "can_delete": False,
                    "is_add_mode": True,
                    "copyright": self.copyright,
                    "active_tab": "models",
                    "admin_settings": settings,
                }
                return self.jinja_template.render_template(
                    "admin/model_change.html", **context
                )
            except Exception as e:
                print(f"Error in model_add: {str(e)}")
                traceback.print_exc()
                return Response(
                    status_code=500,
                    headers={"Content-Type": "text/html"},
                    description=f"Failed to load add page: {str(e)}",
                )

        @self.app.get(f"/{self.prefix}/:route_id/:id/change")
        async def model_change(request: Request):
            try:
                route_id: str = request.path_params.get("route_id")
                object_id: str = unquote(
                    str(request.path_params.get("id", ""))
                )
                user = await self._get_current_user(request)
                if not user:
                    return Response(
                        status_code=303,
                        headers={"Location": f"/{self.prefix}/login"},
                        description="Not logged in",
                    )

                if not await self.check_permission(request, route_id, "view"):
                    return Response(
                        status_code=403,
                        headers={"Content-Type": "text/html"},
                        description="Permission denied",
                    )

                model_admin = self.get_model_admin(route_id)
                if not model_admin:
                    return Response(
                        status_code=404,
                        headers={"Content-Type": "text/html"},
                        description="model not found",
                    )

                obj = await model_admin.get_object(object_id)
                if not obj:
                    return Response(
                        status_code=404,
                        headers={"Content-Type": "text/html"},
                        description="Record not found",
                    )

                language = await self._get_language(request)
                form_fields = [
                    field.to_dict()
                    for field in await model_admin.get_form_fields()
                ]
                form_data = await model_admin.serialize_object(
                    obj, for_display=False
                )

                settings = self._get_admin_settings(request)
                filtered_models = await self._get_visible_models(request)
                model_categories = self._build_model_categories(
                    filtered_models
                )
                display_name = self._get_model_display_name(model_admin)
                can_edit = (
                    model_admin.enable_edit
                    and await self.check_permission(request, route_id, "edit")
                )
                can_delete = (
                    model_admin.allow_delete
                    and await self.check_permission(
                        request, route_id, "delete"
                    )
                )

                context = {
                    "site_title": self.title,
                    "models": filtered_models,
                    "model_categories": model_categories,
                    "user": user,
                    "language": language,
                    "current_model": route_id,
                    "verbose_name": display_name,
                    "route_id": route_id,
                    "object_id": object_id,
                    "form_fields": form_fields,
                    "form_data": form_data,
                    "can_edit": can_edit,
                    "can_delete": can_delete,
                    "is_add_mode": False,
                    "copyright": self.copyright,
                    "active_tab": "models",
                    "admin_settings": settings,
                }
                return self.jinja_template.render_template(
                    "admin/model_change.html", **context
                )
            except Exception as e:
                print(f"Error in model_change: {str(e)}")
                traceback.print_exc()
                return Response(
                    status_code=500,
                    headers={"Content-Type": "text/html"},
                    description=f"Failed to load change page: {str(e)}",
                )

        @self.app.post(f"/{self.prefix}/:route_id/add")
        async def model_add_post(request: Request):
            """处理添加记录"""
            try:
                route_id: str = request.path_params.get("route_id")
                model_admin = self.get_model_admin(route_id)
                if not model_admin:
                    return Response(
                        status_code=404,
                        description="Model not found",
                        headers={"Content-Type": "text/html"},
                    )

                # 检查权限
                if not await self.check_permission(request, route_id, "add"):
                    return Response(
                        status_code=403,
                        description="No create permission",
                        headers={"Content-Type": "text/html"},
                    )
                # 解析表单数据
                data = request.body
                params = parse_qs(data)
                form_data = {}
                for key, value in params.items():
                    try:
                        form_data[key] = json.loads(value[0])
                    except Exception:
                        form_data[key] = value[0]
                success, message = await model_admin.handle_add(
                    request, form_data
                )

                if success:
                    user = await self._get_current_user(request)
                    if user:
                        self._record_action(
                            username=user.username,
                            action="create",
                            target=route_id,
                        )
                    return Response(
                        status_code=200,
                        description=message,
                        headers={"Content-Type": "text/html"},
                    )
                else:
                    return Response(
                        status_code=400,
                        description=message,
                        headers={"Content-Type": "text/html"},
                    )

            except Exception as e:
                print(f"Add error: {str(e)}")
                traceback.print_exc()
                return Response(
                    status_code=500,
                    description=f"Create failed: {str(e)}",
                    headers={"Content-Type": "text/html"},
                )

        @self.app.post(f"/{self.prefix}/:route_id/:id/edit")
        async def model_edit_post(request: Request):
            """处理编辑记录"""
            try:
                route_id: str = request.path_params.get("route_id")
                object_id: str = request.path_params.get("id")

                model_admin = self.get_model_admin(route_id)
                if not model_admin:
                    return Response(
                        status_code=404,
                        description="Model not found",
                        headers={"Content-Type": "text/html"},
                    )
                if not model_admin.enable_edit:
                    return Response(
                        status_code=403,
                        description="model not allow edit",
                        headers={"Content-Type": "text/html"},
                    )
                if not await self.check_permission(request, route_id, "edit"):
                    return Response(
                        status_code=403,
                        description="do not have edit permission",
                    )

                # 解析表单数据
                data = request.body
                params = parse_qs(data)
                form_data = {}
                for key, value in params.items():
                    try:
                        form_data[key] = json.loads(value[0])
                    except Exception:
                        form_data[key] = value[0]

                # 调用模型管理类的处理方法
                success, message = await model_admin.handle_edit(
                    request, object_id, form_data
                )

                if success:
                    user = await self._get_current_user(request)
                    if user:
                        self._record_action(
                            username=user.username,
                            action="update",
                            target=f"{route_id}:{object_id}",
                        )
                    return Response(
                        status_code=200,
                        description=message,
                        headers={"Content-Type": "text/html"},
                    )
                else:
                    return Response(
                        status_code=400,
                        description=message,
                        headers={"Content-Type": "text/html"},
                    )

            except Exception as e:
                print(f"Edit error: {str(e)}")
                return Response(
                    status_code=500,
                    description=f"Edit failed: {str(e)}",
                    headers={"Content-Type": "text/html"},
                )

        @self.app.post(f"/{self.prefix}/:route_id/:id/delete")
        async def model_delete(request: Request):
            """处理删除记录"""
            try:
                route_id: str = request.path_params.get("route_id")
                object_id: str = request.path_params.get("id")
                user = await self._get_current_user(request)
                if not user:
                    return Response(
                        status_code=401,
                        description="Not logged in",
                        headers={"Location": f"/{self.prefix}/login"},
                    )

                model_admin = self.get_model_admin(route_id)
                if not model_admin:
                    return Response(
                        status_code=404,
                        description="Model not found",
                        headers={"Content-Type": "text/html"},
                    )

                # 检查权限
                if not await self.check_permission(
                    request, route_id, "delete"
                ):
                    return Response(
                        status_code=403,
                        description="No delete permission",
                        headers={"Content-Type": "text/html"},
                    )

                # 调用模型管理类的处理方法
                success, message = await model_admin.handle_delete(
                    request, object_id
                )

                if success:
                    if user:
                        self._record_action(
                            username=user.username,
                            action="delete",
                            target=f"{route_id}:{object_id}",
                        )
                    return Response(
                        status_code=200,
                        description=message,
                        headers={"Location": f"/{self.prefix}/{route_id}"},
                    )
                else:
                    return Response(
                        status_code=400,
                        description=message,
                        headers={"Content-Type": "text/html"},
                    )

            except Exception as e:
                print(f"Delete error: {str(e)}")
                return Response(
                    status_code=500,
                    description=f"Delete failed: {str(e)}",
                    headers={"Content-Type": "text/html"},
                )

        @self.app.get(f"/{self.prefix}/:route_id/data")
        async def model_data(request: Request):
            """获取模型数据"""
            try:
                route_id: str = request.path_params.get("route_id")
                model_admin = self.get_model_admin(route_id)
                if not model_admin:
                    return jsonify({"error": "Model not found"})

                # 解析查询参数
                params: dict = request.query_params.to_dict()
                query_params = {
                    "limit": max(
                        1, _to_int(_first_value(params.get("limit"), 10), 10)
                    ),
                    "offset": max(
                        0, _to_int(_first_value(params.get("offset"), 0), 0)
                    ),
                    "search": _first_value(params.get("search"), ""),
                    "sort": _first_value(params.get("sort"), ""),
                    "order": _first_value(params.get("order"), "asc"),
                }

                # 添加其他过滤参数
                for key, value in params.items():
                    if key not in [
                        "limit",
                        "offset",
                        "search",
                        "sort",
                        "order",
                        "_",
                    ]:
                        query_params[key] = _first_value(value)

                # 调用模型管理类的处理方法
                queryset, total = await model_admin.handle_query(
                    request, query_params
                )

                # 序列化数据
                data = []
                async for obj in queryset:
                    try:
                        serialized = await model_admin.serialize_object(obj)
                        data.append(
                            {"data": serialized, "display": serialized}
                        )
                    except Exception as e:
                        print(f"Error serializing object: {str(e)}")
                        continue

                return jsonify({"total": total, "data": data})

            except Exception as e:
                print(f"Error in model_data: {str(e)}")
                return jsonify({"error": str(e)})

        @self.app.post(f"/{self.prefix}/:route_id/batch_delete")
        async def model_batch_delete(request: Request):
            """批量删除记录"""
            try:
                route_id: str = request.path_params.get("route_id")
                user = await self._get_current_user(request)
                if not user:
                    return Response(
                        status_code=401,
                        description="Not logged in",
                        headers={"Location": f"/{self.prefix}/login"},
                    )

                model_admin = self.get_model_admin(route_id)
                if not model_admin:
                    return Response(
                        status_code=404,
                        description="Model not found",
                        headers={"Content-Type": "text/html"},
                    )

                # 解析请求数据
                data = request.body
                params = parse_qs(data)
                ids = params.get("ids[]", [])  # 获取要删除的ID列表

                if not ids:
                    return Response(
                        status_code=400,
                        description="No records selected",
                        headers={"Content-Type": "text/html"},
                    )

                # 调用模型管理类的处理方法
                success, message, deleted_count = (
                    await model_admin.handle_batch_delete(request, ids)
                )
                if success and user:
                    self._record_action(
                        username=user.username,
                        action="batch_delete",
                        target=route_id,
                        details=f"deleted_count={deleted_count}",
                    )

                return jsonify(
                    {
                        "code": 200 if success else 500,
                        "message": message,
                        "success": success,
                        "data": {"deleted_count": deleted_count},
                    }
                )

            except Exception as e:
                print(f"Batch delete error: {str(e)}")
                return jsonify(
                    {
                        "code": 500,
                        "message": f"Batch delete failed: {str(e)}",
                        "success": False,
                    }
                )

        @self.app.post(f"/{self.prefix}/upload")
        async def file_upload(request: Request):
            """处理文件传"""
            try:
                # 验证用户登录
                user = await self._get_current_user(request)
                if not user:
                    return jsonify(
                        {
                            "code": 401,
                            "message": "Not logged in",
                            "success": False,
                        }
                    )

                # 获取上传的文件
                files = request.files
                if not files:
                    return jsonify(
                        {
                            "code": 400,
                            "message": "No file uploaded",
                            "success": False,
                        }
                    )
                # 获取上传路数
                upload_path = request.form_data.get(
                    "upload_path", "static/uploads"
                )
                # 处理上传的文件
                uploaded_files = []
                for file_name, file_bytes in files.items():
                    # 证文件类型
                    if not file_name.lower().endswith(
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

                    # 生成安全的文件名
                    import uuid

                    safe_filename = (
                        f"{uuid.uuid4().hex}{os.path.splitext(file_name)[1]}"
                    )

                    # 确保上传目录存在
                    os.makedirs(upload_path, exist_ok=True)

                    # 保存文件
                    file_path = os.path.join(upload_path, safe_filename)
                    with open(file_path, "wb") as f:
                        f.write(file_bytes)

                    # 生成访问URL（使用绝对路径）
                    file_url = f"/{file_path.replace(os.sep, '/')}"
                    uploaded_files.append(
                        {
                            "original_name": file_name,
                            "saved_name": safe_filename,
                            "url": file_url,
                        }
                    )

                # 返回成功响应
                return jsonify(
                    {
                        "code": 200,
                        "message": "Upload successful",
                        "success": True,
                        "data": (
                            uploaded_files[0] if uploaded_files else None
                        ),  # 返回一个文件的信息
                    }
                )

            except Exception as e:
                print(f"Upload failed: {str(e)}")
                traceback.print_exc()
                return jsonify(
                    {
                        "code": 500,
                        "message": f"Upload failed: {str(e)}",
                        "success": False,
                    }
                )

        @self.app.post(f"/{self.prefix}/set_language")
        async def set_language(request: Request):
            """设置语言"""
            try:
                data = request.body
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                params = parse_qs(str(data or ""))
                language = params.get("language", [self.default_language])[0]

                # 获取当前session
                session_data = request.headers.get("Cookie")
                session_dict = {}
                if session_data:
                    for item in session_data.split(";"):
                        if "=" in item:
                            key, value = item.split("=", 1)
                            session_dict[key.strip()] = value.strip()

                # 更新session中的语言设置
                session = session_dict.get("session", "{}")
                try:
                    data = json.loads(session)
                except json.JSONDecodeError:
                    data = {}
                data["language"] = language

                # 构建cookie
                cookie_value = json.dumps(data)
                cookie_attrs = [
                    f"session={cookie_value}",
                    "HttpOnly",
                    "SameSite=Lax",
                    "Path=/",
                ]

                return Response(
                    status_code=200,
                    description="Language set successfully",
                    headers={"Set-Cookie": "; ".join(cookie_attrs)},
                )
            except Exception as e:
                print(f"Set language failed: {str(e)}")
                return Response(
                    status_code=500,
                    description="Set language failed",
                    headers={"Content-Type": "text/plain; charset=utf-8"},
                )

        @self.app.get(f"/{self.prefix}/:route_id/inline_data")
        async def get_inline_data(request: Request):
            try:
                route_id = request.path_params["route_id"]
                model_admin = self.get_model_admin(route_id)
                if not model_admin:
                    return jsonify(
                        {"error": "Model not found"}, status_code=404
                    )

                params: dict = request.query_params.to_dict()
                parent_id = _first_value(params.get("parent_id"), "")
                inline_model = _first_value(params.get("inline_model"), "")

                # 获取排序参数
                sort_field = _first_value(params.get("sort"), "")
                sort_order = _first_value(params.get("order"), "asc")

                if not parent_id or not inline_model:
                    return jsonify({"error": "Missing parameters"})

                # 找到对应的内联实例
                inline = next(
                    (
                        i
                        for i in model_admin._inline_instances
                        if i.model.__name__ == inline_model
                    ),
                    None,
                )
                if not inline:
                    return jsonify({"error": "Inline model not found"})

                # 获取父实例
                parent_instance = await model_admin.get_object(parent_id)
                if not parent_instance:
                    return jsonify({"error": "Parent object not found"})

                # 获取查询集
                queryset = await inline.get_queryset(parent_instance)

                # 应用排序
                if sort_field:
                    # 检查字段是否可排序
                    sortable_field = next(
                        (
                            field
                            for field in inline.table_fields
                            if field.name == sort_field and field.sortable
                        ),
                        None,
                    )
                    if sortable_field:
                        order_by = f"{'-' if sort_order == 'desc' else ''}{sort_field}"
                        queryset = queryset.order_by(order_by)

                # 获取数据
                data = []
                async for obj in queryset:
                    try:
                        serialized = await inline.serialize_object(obj)
                        data.append(
                            {"data": serialized, "display": serialized}
                        )
                    except Exception as e:
                        print(f"Error serializing object: {str(e)}")
                        continue

                # 添加字段配置信息
                fields_config = [
                    {
                        "name": field.name,
                        "label": field.label,
                        "display_type": (
                            field.display_type.value
                            if field.display_type
                            else "text"
                        ),
                        "sortable": field.sortable,
                        "width": field.width,
                        "is_link": field.is_link,  # 确保is_link也被传递到前端
                    }
                    for field in inline.table_fields
                ]
                return Response(
                    status_code=200,
                    headers={
                        "Content-Type": "application/json; charset=utf-8"
                    },
                    description=json.dumps(
                        {
                            "success": True,
                            "data": data,
                            "total": len(data),
                            "fields": fields_config,
                        }
                    ),
                )

            except Exception as e:
                print(f"Error in get_inline_data: {str(e)}")
                traceback.print_exc()
                return jsonify(
                    {"error": str(e)},
                    # headers={"Content-Type": "application/json; charset=utf-8"}
                )

        @self.app.post(f"/{self.prefix}/:route_id/import")
        async def handle_import(request: Request):
            """处理数据导入"""
            try:
                route_id = request.path_params.get("route_id")
                model_admin = self.get_model_admin(route_id)

                if not model_admin or not model_admin.allow_import:
                    return jsonify(
                        {
                            "success": False,
                            "message": "Import is not supported",
                        }
                    )

                # 获取上传的文件
                files = request.files
                filename = list(files.keys())[0]
                if not files:
                    return jsonify(
                        {"success": False, "message": "No file uploaded"}
                    )

                file_data = next(iter(files.values()))

                # 检查文件类型
                if not any(
                    filename.endswith(ext) for ext in [".xlsx", ".xls", ".csv"]
                ):
                    return jsonify(
                        {
                            "success": False,
                            "message": "Only Excel or CSV files are supported",
                        }
                    )

                # 处理文件数据
                import pandas as pd
                import io

                df = None
                if filename.endswith(".csv"):
                    df = pd.read_csv(io.BytesIO(file_data))
                else:
                    df = pd.read_excel(io.BytesIO(file_data))

                # 验证字段
                missing_fields = [
                    f for f in model_admin.import_fields if f not in df.columns
                ]
                if missing_fields:
                    return jsonify(
                        {
                            "success": False,
                            "message": f"Missing required fields: {', '.join(missing_fields)}",
                        }
                    )

                # 导入数据
                success_count = 0
                error_count = 0
                errors = []

                for _, row in df.iterrows():
                    try:
                        data = {
                            field: row[field]
                            for field in model_admin.import_fields
                        }
                        await model_admin.model.create(**data)
                        success_count += 1
                    except Exception as e:
                        error_count += 1
                        errors.append(str(e))

                user = await self._get_current_user(request)
                if user:
                    self._record_action(
                        username=user.username,
                        action="import",
                        target=route_id,
                        details=f"success={success_count},failed={error_count}",
                    )
                return jsonify(
                    {
                        "success": True,
                        "message": f"Import completed: {success_count} succeeded, {error_count} failed",
                        "errors": errors if errors else None,
                    }
                )

            except Exception as e:
                print(f"Import error: {str(e)}")
                return jsonify(
                    {"success": False, "message": f"Import failed: {str(e)}"}
                )

    def register_model(
        self,
        model: Type[Model],
        admin_class: Optional[Type[ModelAdmin]] = None,
    ):
        """注册模型admin站点"""
        if admin_class is None:
            admin_class = ModelAdmin

        # 创建管理类实例
        instance = admin_class(model)

        # 生成唯一的路由标识符
        if admin_class is ModelAdmin:
            route_id = f"{model.__name__}Admin"
        else:
            route_id = admin_class.__name__

        # 如果路由标识符已存在，添加数字后缀
        base_route_id = route_id
        counter = 1
        while route_id in self.models:
            route_id = f"{base_route_id}{counter}"
            counter += 1

        # 存储路由标识符到实例中，用于后续路由生成
        instance.route_id = route_id

        print("\n=== Registering Model ===")
        print(f"Model: {model.__name__}")
        print(f"Admin Class: {admin_class.__name__}")
        print(f"Route ID: {route_id}")
        print("========================\n")

        # 使用路由标识符作为键存储管理类实例
        self.models[route_id] = instance

        # 更新模型到管理类的映射
        if model.__name__ not in self.model_registry:
            self.model_registry[model.__name__] = []
        self.model_registry[model.__name__].append(instance)

    def _generate_session_token(self, user_id: int) -> str:
        """生成安全的会话令牌"""
        timestamp = int(datetime.now().timestamp())
        # 组合用户ID、时间戳和随机值
        raw_token = f"{user_id}:{timestamp}:{secrets.token_hex(16)}"
        # 使用密钥进行签名
        signature = hashlib.sha256(
            f"{raw_token}:{self.session_secret}".encode()
        ).hexdigest()
        # 组合并编码
        token = base64.urlsafe_b64encode(
            f"{raw_token}:{signature}".encode()
        ).decode()
        return token

    def _verify_session_token(self, token: str) -> tuple[bool, Optional[int]]:
        """验证会话令牌"""
        try:
            # 解码令牌
            decoded = base64.urlsafe_b64decode(token.encode()).decode()
            raw_token, signature = decoded.rsplit(":", 1)

            # 验证签名
            expected_signature = hashlib.sha256(
                f"{raw_token}:{self.session_secret}".encode()
            ).hexdigest()

            if not secrets.compare_digest(signature, expected_signature):
                return False, None

            # 解析令牌内容
            user_id, timestamp, _ = raw_token.split(":", 2)
            timestamp = int(timestamp)

            # 检查是否过期
            if datetime.now().timestamp() - timestamp > self.session_expire:
                return False, None

            return True, int(user_id)
        except Exception as e:
            print(f"Session verification error: {str(e)}")
            return False, None

    async def _get_current_user(self, request: Request) -> Optional[AdminUser]:
        """获取当前登录用户"""
        try:
            # 从cookie中获取session
            cookie_header = request.headers.get("Cookie")
            print(f"Cookie header: {cookie_header}")  # 调试日志

            if not cookie_header:
                print("No cookie header found")  # 调试日志
                return None

            # 解析cookie
            cookies = _parse_cookie_header(cookie_header)

            token = cookies.get("session_token")
            print(f"Found session token: {token}")  # 调试日志

            if not token:
                print("No session token in cookies")  # 调试日志
                return None

            # 验证会话令牌
            valid, user_id = self._verify_session_token(token)
            print(
                f"Token validation: valid={valid}, user_id={user_id}"
            )  # 调试日志

            if not valid:
                print("Invalid session token")  # 调试日志
                return None

            try:
                user = await AdminUser.get(id=user_id)
                if user:
                    print(f"Found user: {user.username}")  # 调试日志
                else:
                    print(f"No user found for id: {user_id}")  # 调试日志
                return user

            except Exception as e:
                print(f"Error loading user: {str(e)}")
                traceback.print_exc()
                return None

        except Exception as e:
            print(f"Error in _get_current_user: {str(e)}")
            traceback.print_exc()
            return None

    async def _get_language(self, request: Request) -> str:
        """获取当前语言"""
        try:
            session_data = request.headers.get("Cookie")
            if not session_data:
                return self.default_language

            session_dict = _parse_cookie_header(session_data)

            session = session_dict.get("session")
            if not session:
                return self.default_language

            try:
                data = json.loads(session)
                return data.get("language", self.default_language)
            except json.JSONDecodeError:
                return self.default_language

        except Exception as e:
            print(f"Error getting language: {str(e)}")
            return self.default_language

    def register_menu(self, menu_item: MenuItem):
        """注册菜项"""
        self.menu_manager.register_menu(
            menu_item
        )  # 使用 menu_manager 注册菜单

    def get_model_admin(self, route_id: str) -> Optional[ModelAdmin]:
        """根据路由ID获取模型管理器"""
        return self.models.get(route_id)

    async def check_permission(
        self, request: Request, model_name: str, action: str
    ) -> bool:
        """检查权限"""
        try:
            user = await self._get_current_user(request)
            if not user:
                print("No user found")
                return False

            print("\n=== Checking Permissions ===")
            print(f"User: {user.username}")
            print(f"Model: {model_name}")
            print(f"Action: {action}")

            # 超级用户拥有所有权限
            if user.is_superuser:
                print("User is superuser, granting access")
                return True
            user_roles = await UserRole.filter(user=user).prefetch_related(
                "role"
            )
            roles = [ur.role for ur in user_roles]
            # 获取用户的所有角色
            # roles = await user.roles.all()
            print(roles)
            print(f"User roles: {[role.name for role in roles]}")

            # 检查每个角色的权限
            for role in roles:
                print(f"\nChecking role: {role.name}")
                print(f"Role accessible models: {role.accessible_models}")

                if role.accessible_models == ["*"]:
                    print("Role has full access")
                    return True
                elif model_name in role.accessible_models:
                    print(f"Role has access to {model_name}")
                    return True
                else:
                    print(f"Role does not have access to {model_name}")

            print("No role has required access")
            return False

        except Exception as e:
            print(f"Error in permission check: {str(e)}")
            traceback.print_exc()
            return False


def _parse_cookie_header(header: str) -> Dict[str, str]:
    cookies: Dict[str, str] = {}
    for item in header.split(";"):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        cookies[key.strip()] = value.strip()
    return cookies


def _encode_cookie_payload(payload: str) -> str:
    return base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")


def _decode_cookie_payload(encoded: str) -> str:
    padding = "=" * (-len(encoded) % 4)
    return base64.urlsafe_b64decode(f"{encoded}{padding}".encode()).decode()


def _first_value(value: Any, default: Any = None) -> Any:
    if isinstance(value, list):
        return value[0] if value else default
    if value is None:
        return default
    return value


def _to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
