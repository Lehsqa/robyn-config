from typing import Type, Optional, Dict, List, Union
from types import ModuleType
from tortoise import Model, Tortoise
from robyn import Robyn, Request, Response, jsonify
from robyn.templating import JinjaTemplate
from pathlib import Path
import os
import json
from datetime import datetime, timedelta
import traceback
from urllib.parse import parse_qs, unquote
import secrets
import hashlib
import base64
import importlib
import atexit

from ..auth_admin import AdminUserAdmin, RoleAdmin, UserRoleAdmin
from ..auth_models import AdminUser, Role, UserRole
from .admin import ModelAdmin
from .menu import MenuManager, MenuItem
from ..models import AdminUser
from ..i18n.translations import get_text
from typing import Callable
import qc_robyn_admin.models
import qc_robyn_admin.auth_models

class AdminSite:
    """Admin站点主类"""
    def __init__(
        self, 
        app: Robyn,
        title: str = 'QC Robyn Admin',  # 后台名称
        prefix: str = 'admin',       # 路由前缀
        copyright: str = "QC Robyn Admin",       # 版权信息，如果为None则不显示
        db_url: Optional[str] = None,
        modules: Optional[Dict[str, List[Union[str, ModuleType]]]] = None,
        generate_schemas: bool = True,
        default_language: str = 'en_US',
        startup_function: Optional[Callable] = None
    ):
        """
        初始化Admin站点
        
        :param app: Robyn应用实例
        :param title: 后台系统名称
        :param prefix: 后台路由前缀
        :param db_url: 数据库连接URL,如果为None则尝试复用已有配置
        :param modules: 模型模块配置,如果为None则尝试复用已有配置
        :param generate_schemas: 是否自动生成数据库表结构
        :param default_language: 默认语言 zh_CN, en_US
        """
        self.app = app
        self.title = title          # 后台名称
        self.prefix = prefix        # 路由前缀
        self.models: Dict[str, ModelAdmin] = {}
        self.model_registry = {}
        self.default_language = default_language
        self.menu_manager = MenuManager()
        self.copyright = copyright   # 添加版权属性
        self.startup_function = startup_function
        # 设置模板
        self._setup_templates()
        
        # 初始化数据库
        self.db_url = db_url
        self.modules = modules
        self.generate_schemas = generate_schemas
        # 确保数据库文件路径存在
        if db_url and db_url.startswith('sqlite'):
            db_path = db_url.replace('sqlite://', '')
            if db_path != ':memory:':
                os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        
        # 注册程序退出时的清理函数
        atexit.register(self._cleanup_db)
        
        # 初始化数据库
        self._init_admin_db()
        
        # 设置路由
        self._setup_routes()

        self.session_secret = secrets.token_hex(32)  # 生成随机密钥
        self.session_expire = 24 * 60 * 60  # 会话过期时间（秒）

    def get_text(self, key: str, lang: str = None) -> str:
        """使用站点默认语言的文本获取函数"""
        from ..i18n.translations import get_text, TRANSLATIONS
        current_lang = lang or self.default_language
        return TRANSLATIONS.get(current_lang, TRANSLATIONS[self.default_language]).get(key, key)

    def init_register_auth_models(self):
        # 注册系统管理模型
        self.register_model(AdminUser, AdminUserAdmin)
        self.register_model(Role, RoleAdmin)
        self.register_model(UserRole, UserRoleAdmin)

    def _setup_templates(self):
        """设置模板目录"""
        current_dir = Path(__file__).parent.parent
        template_dir = os.path.join(current_dir, 'templates')
        self.template_dir = template_dir
        # 创建 Jinja2 环境并添加全局函数
        self.jinja_template = JinjaTemplate(template_dir)
        self.jinja_template.env.globals.update({
            'get_text': self.get_text
        })

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
                        raise Exception("数据库未初始化,配置数据库或提供db_url参数")
                    # 复用现有配置
                    current_config = Tortoise.get_connection("default").config
                    self.db_url = current_config.get("credentials", {}).get("dsn")
                
                # 如果是相对路径的sqlite数据库，转换为绝对路径
                if self.db_url and self.db_url.startswith('sqlite://') and not self.db_url.startswith('sqlite://:memory:'):
                    db_path = self.db_url.replace('sqlite://', '')
                    if not os.path.isabs(db_path):
                        abs_path = os.path.abspath(db_path)
                        self.db_url = f'sqlite://{abs_path}'
                
                # 处理模块配置
                if self.modules is None:
                    # 动态导入内部模型模块
                    try:
                        models_module = importlib.import_module("qc_robyn_admin.models")
                        auth_models_module = importlib.import_module("qc_robyn_admin.auth_models")
                        
                        self.modules = {
                            "models": [
                                models_module,  # 直接使用模块对象而不是字符串
                                auth_models_module
                            ]
                        }
                    except ImportError as e:
                        print(f"Error importing internal modules: {e}")
                        raise
                        
                elif not self.modules:
                    # 如果是字典，获取现有配置
                    if not Tortoise._inited:
                        raise Exception("数据库未初始化,请先配置数据库或提供modules参数")
                    self.modules = dict(Tortoise.apps)
                    # 确保内部模型被加载
                    try:
                        models_module = importlib.import_module("qc_robyn_admin.models")
                        auth_models_module = importlib.import_module("qc_robyn_admin.auth_models")
                        
                        if "models" in self.modules and isinstance(self.modules["models"], list):
                            self.modules["models"].extend([models_module, auth_models_module])
                        else:
                            self.modules["models"] = [models_module, auth_models_module]
                    except ImportError as e:
                        print(f"Error importing internal modules: {e}")
                        raise
                        
                else:
                    # 如果提供了配置，确保内部模型被加载
                    try:
                        models_module = importlib.import_module("qc_robyn_admin.models")
                        auth_models_module = importlib.import_module("qc_robyn_admin.auth_models")
                        
                        if "models" in self.modules:
                            if isinstance(self.modules["models"], list):
                                self.modules["models"].extend([models_module, auth_models_module])
                            else:
                                self.modules["models"] = [
                                    models_module,
                                    auth_models_module,
                                    self.modules["models"]
                                ]
                        else:
                            self.modules["models"] = [models_module, auth_models_module]
                    except ImportError as e:
                        print(f"Error importing internal modules: {e}")
                        raise

                # 初始化数据库连接
                if not Tortoise._inited:
                    print(f"Initializing database with URL: {self.db_url}")
                    await Tortoise.init(
                        db_url=self.db_url,
                        modules=self.modules
                    )
                    print("Database initialized successfully")

                # 注册内部模型
                self.init_register_auth_models()

                # 生成表结构
                if self.generate_schemas:
                    print("Generating database schemas...")
                    await Tortoise.generate_schemas()
                    print("Database schemas generated successfully")

                # 触发信号来创建管理员账号
                try:
                    # 检查是否已存在管理员账号
                    existing_admin = await AdminUser.filter(username="admin").first()
                    if not existing_admin:
                        print("Creating default admin user...")
                        await AdminUser.create(
                            username="admin",
                            password=AdminUser.hash_password("admin"),
                            email="admin@example.com",
                            is_superuser=True
                        )
                        print("Default admin user created successfully")
                except Exception as e:
                    print(f"Error creating admin user: {str(e)}")
                    traceback.print_exc()

                if self.startup_function:
                    await self.startup_function()

            except Exception as e:
                print(f"Error in database initialization: {str(e)}")
                traceback.print_exc()
                raise

    def _setup_routes(self):
        """设置路由"""
        @self.app.get(f"/{self.prefix}")
        async def admin_index(request: Request):
            user = await self._get_current_user(request)
            if not user:
                return Response(status_code=307, description="Location login page" ,headers={"Location": f"/{self.prefix}/login"})
            
            language = await self._get_language(request)
            
            # 过滤用有权限访问的模型
            filtered_models = {}
            for route_id, model_admin in self.models.items():
                if await self.check_permission(request, route_id, 'view'):
                    filtered_models[route_id] = model_admin
            
            context = {
                "site_title": self.title,
                "models": filtered_models,
                "menus": self.menu_manager.get_menu_tree(),
                "user": user,
                "language": language,
                "copyright": self.copyright
            }
            return self.jinja_template.render_template("admin/index.html", **context)
            
        @self.app.get(f"/{self.prefix}/login")
        async def admin_login(request: Request):
            user = await self._get_current_user(request)
            if user:
                return Response(status_code=307, description="Location to admin page", headers={"Location": f"/{self.prefix}"})
            
            language = await self._get_language(request)  # 获取语言设置
            context = {
                "user": None,
                "language": language,
                "site_title": self.title,
                "copyright": self.copyright  # 传递版权信息到模板
            }
            return self.jinja_template.render_template("admin/login.html", **context)
            
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
                    print(f"Generated token for user {user.username}: {token}")  # 调试日志
                    
                    # 修改 cookie 设置
                    cookie_attrs = [
                        f"session_token={token}",
                        "HttpOnly",
                        "Path=/",
                        f"Max-Age={self.session_expire}"
                    ]
                    
                    # 在开发环境中暂时移除这些限制
                    # "SameSite=Lax",
                    # "Secure",
                    
                    # 更新用户最后登录时间
                    user.last_login = datetime.now()
                    await user.save()
                    
                    # 构造响应
                    response = Response(
                        status_code=303,
                        description="Login successful",
                        headers={
                            "Location": f"/{self.prefix}",
                            "Set-Cookie": "; ".join(cookie_attrs),
                            "Cache-Control": "no-cache, no-store, must-revalidate"
                        }
                    )
                    
                    print("Response headers:", response.headers)  # 调试日志
                    return response
                else:
                    print(f"Authentication failed for username: {username}")  # 调试日志
                    context = {
                        "error": "用户名或密码错误",
                        "user": None,
                        "site_title": self.title,
                        "copyright": self.copyright
                    }
                    return self.jinja_template.render_template("admin/login.html", **context)
                
            except Exception as e:
                print(f"Login error: {str(e)}")
                traceback.print_exc()  # 打印完整的错误堆栈
                return Response(
                    status_code=500,
                    description=f"登录失败: {str(e)}"
                )

        @self.app.get(f"/{self.prefix}/logout")
        async def admin_logout(request: Request):
            # 清cookie
            cookie_attrs = [
                "session_token=",
                "HttpOnly",
                "SameSite=Lax",
                "Secure",
                "Path=/",
                "Max-Age=0"  # 立即过期
            ]
            
            return Response(
                status_code=303, 
                description="", 
                headers={
                    "Location": f"/{self.prefix}/login",
                    "Set-Cookie": "; ".join(cookie_attrs)
                }
            )
        
        @self.app.get(f"/{self.prefix}/:route_id/search")
        async def model_search(request: Request):
            """模型页面中，搜索功能相关接口，进行匹配查询结果"""
            route_id: str = request.path_params.get("route_id")
            user = await self._get_current_user(request)
            if not user:
                return Response(
                    status_code=401, 
                    description="未登录",
                    headers={"Content-Type": "application/json"}
                )
            
            model_admin = self.models.get(route_id)
            if not model_admin:
                return Response(
                    status_code=404, 
                    description="模型不存在",
                    headers={"Content-Type": "application/json"}
                )
            
            # 获取索参数， 同时还要进url解码
            search_values = {
                field.name: unquote(request.query_params.get(f"search_{field.name}"))
                for field in model_admin.search_fields
                if request.query_params.get(f"search_{field.name}")
            }
            # 执行搜索查询
            queryset = await model_admin.get_queryset(request, search_values)
            objects = await queryset.limit(model_admin.per_page)
            
            # 序列化结果
            result = {
                "data": [
                    {
                        'display': model_admin.serialize_object(obj, for_display=True),
                        'data': model_admin.serialize_object(obj, for_display=False)
                    }
                    for obj in objects
                ]
            }
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
                        description="Not logged in"
                    )
                
                language = await self._get_language(request)

                if not await self.check_permission(request, route_id, 'view'):
                    return Response(
                        status_code=403, 
                        headers={"Content-Type": "text/html"},
                        description="没有权限访问此页面"
                    )
                
                model_admin = self.get_model_admin(route_id)
                if not model_admin:
                    return Response(
                        status_code=404, 
                        headers={"Content-Type": "text/html"},
                        description="model not found"
                    )
                
                frontend_config = await model_admin.get_frontend_config()
                
                # 确保语言设置确传递
                frontend_config["language"] = language
                frontend_config["default_language"] = self.default_language
                
                # 过滤用户有权限访问的模型
                filtered_models = {}
                for rid, madmin in self.models.items():
                    if await self.check_permission(request, rid, 'view'):
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
                    "copyright": self.copyright
                }  
                return self.jinja_template.render_template("admin/model_list.html", **context)
                
            except Exception as e:
                print(f"Error in model_list: {str(e)}")
                traceback.print_exc()
                return Response(
                    status_code=500,
                    headers={"Content-Type": "text/html"},
                    description=f"获取列表页失败: {str(e)}"
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
                        description="模型不存在",
                        headers={"Content-Type": "text/html"}
                    )
                    
                # 检查权限
                if not await self.check_permission(request, route_id, 'add'):
                    return Response(status_code=403, description="没有添加权限", headers={"Content-Type": "text/html"})
                # 解析表单数据
                data = request.body
                params = parse_qs(data)
                form_data = {}
                for key, value in params.items():
                    try:
                        form_data[key] = json.loads(value[0])
                    except Exception as e:
                        form_data[key] = value[0]
                success, message = await model_admin.handle_add(request, form_data)
                
                if success:
                    return Response(
                        status_code=200,
                        description=message,
                        headers={"Content-Type": "text/html"}
                    )
                else:
                    return Response(
                        status_code=400,
                        description=message,
                        headers={"Content-Type": "text/html"}
                    )
                    
            except Exception as e:
                print(f"Add error: {str(e)}")
                traceback.print_exc()
                return Response(
                    status_code=500,
                    description=f"添加失败: {str(e)}",
                    headers={"Content-Type": "text/html"}
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
                        description="模型不存在",
                        headers={"Content-Type": "text/html"}
                    )
                if not model_admin.enable_edit:
                    return Response(
                        status_code=403, 
                        description="model not allow edit", 
                        headers={"Content-Type": "text/html"}
                    )
                if not await self.check_permission(request, route_id, 'edit'):
                    return Response(status_code=403, description="do not have edit permission")
            
                # 解析表单数据
                data = request.body
                params = parse_qs(data)
                form_data = {}
                for key, value in params.items(): 
                    try:
                        form_data[key] = json.loads(value[0])
                    except Exception as e:
                        form_data[key] = value[0]
                
                # 调用模型管理类的处理方法
                success, message = await model_admin.handle_edit(request, object_id, form_data)
                
                if success:
                    return Response(
                        status_code=200,
                        description=message,
                        headers={"Content-Type": "text/html"}
                    )
                else:
                    return Response(
                        status_code=400,
                        description=message,
                        headers={"Content-Type": "text/html"}
                    )
                    
            except Exception as e:
                print(f"Edit error: {str(e)}")
                return Response(
                    status_code=500,
                    description=f"编辑失败: {str(e)}",
                    headers={"Content-Type": "text/html"}
                )

        @self.app.post(f"/{self.prefix}/:route_id/:id/delete")
        async def model_delete(request: Request):
            """处理删除记录"""
            try:
                route_id: str = request.path_params.get("route_id")
                object_id: str = request.path_params.get("id")
                user = await self._get_current_user(request)
                if not user:
                    return Response(status_code=401, description="未登录", headers={"Location": f"/{self.prefix}/login"})
                
                model_admin = self.get_model_admin(route_id)
                if not model_admin:
                    return Response(status_code=404, description="模型不存在", headers={"Content-Type": "text/html"})
                    
                # 检查权限
                if not await self.check_permission(request, route_id, 'delete'):
                    return Response(status_code=403, description="没有删除权限", headers={"Content-Type": "text/html"})
                    
                # 调用模型管理类的处理方法
                success, message = await model_admin.handle_delete(request, object_id)
                
                if success:
                    return Response(
                        status_code=200,
                        description=message,
                        headers={"Location": f"/{self.prefix}/{route_id}"}
                    )
                else:
                    return Response(
                        status_code=400,
                        description=message,
                        headers={"Content-Type": "text/html"}
                    )
                    
            except Exception as e:
                print(f"Delete error: {str(e)}")
                return Response(
                    status_code=500,
                    description=f"删除失败: {str(e)}",
                    headers={"Content-Type": "text/html"}
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
                    'limit': int(params.get('limit', ['10'])[0]),
                    'offset': int(params.get('offset', ['0'])[0]),
                    'search': params.get('search', [''])[0],
                    'sort': params.get('sort', [''])[0],
                    'order': params.get('order', ['asc'])[0],
                }
                
                # 添加其他过滤参数
                for key, value in params.items():
                    if key not in ['limit', 'offset', 'search', 'sort', 'order', '_']:
                        query_params[key] = value[0]
                        
                # 调用模型管理类的处理方法
                queryset, total = await model_admin.handle_query(request, query_params)
                
                # 序列化数据
                data = []
                async for obj in queryset:
                    try:
                        serialized = await model_admin.serialize_object(obj)
                        data.append({
                            'data': serialized,
                            'display': serialized
                        })
                    except Exception as e:
                        print(f"Error serializing object: {str(e)}")
                        continue
                
                return jsonify({
                    "total": total,
                    "data": data
                })
                
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
                    return Response(status_code=401, description="未登录", headers={"Location": f"/{self.prefix}/login"})
                
                model_admin = self.get_model_admin(route_id)
                if not model_admin:
                    return Response(status_code=404, description="模型不存在", headers={"Content-Type": "text/html"})
                
                # 解析请求数据
                data = request.body
                params = parse_qs(data)
                ids = params.get('ids[]', [])  # 获取要删除的ID列表
                
                if not ids:
                    return Response(
                        status_code=400,
                        description="未选择要删除的记录",
                        headers={"Content-Type": "text/html"}
                    )
                
                # 调用模型管理类的处理方法
                success, message, deleted_count = await model_admin.handle_batch_delete(request, ids)
                
                return jsonify({
                    "code": 200 if success else 500,
                    "message": message,
                    "success": success,
                    "data": {"deleted_count": deleted_count}
                })
                
            except Exception as e:
                print(f"Batch delete error: {str(e)}")
                return jsonify({
                    "code": 500,
                    "message": f"批量删除失败: {str(e)}",
                    "success": False
                })
        
        @self.app.post(f"/{self.prefix}/upload")
        async def file_upload(request: Request):
            """处理文件传"""
            try:
                # 验证用户登录
                user = await self._get_current_user(request)
                if not user:
                    return jsonify({
                        "code": 401,
                        "message": "未登录",
                        "success": False
                    })

                # 获取上传的文件
                files = request.files
                if not files:
                    return jsonify({
                        "code": 400,
                        "message": "没上传文件",
                        "success": False
                    })
                # 获取上传路数
                upload_path = request.form_data.get('upload_path', 'static/uploads')
                # 处理上传的文件
                uploaded_files = []
                for file_name, file_bytes in files.items():
                    # 证文件类型
                    if not file_name.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.sql', '.xlsx', '.csv', '.xls')):
                        return jsonify({
                            "code": 400,
                            "message": "不支持文件类型",
                            "success": False
                        })

                    # 生成安全的文件名
                    import uuid
                    safe_filename = f"{uuid.uuid4().hex}{os.path.splitext(file_name)[1]}"
                    
                    # 确保上传目录存在
                    os.makedirs(upload_path, exist_ok=True)
                    
                    # 保存文件
                    file_path = os.path.join(upload_path, safe_filename)
                    with open(file_path, 'wb') as f:
                        f.write(file_bytes)
                    
                    # 生成访问URL（使用绝对路径）
                    file_url = f"/{file_path.replace(os.sep, '/')}"
                    uploaded_files.append({
                        "original_name": file_name,
                        "saved_name": safe_filename,
                        "url": file_url
                    })
                
                # 返回成功响应
                return jsonify({
                    "code": 200,
                    "message": "上传成功",
                    "success": True,
                    "data": uploaded_files[0] if uploaded_files else None  # 返回一个文件的信息
                })
                
            except Exception as e:
                print(f"文件上传失败: {str(e)}")
                traceback.print_exc()
                return jsonify({
                    "code": 500,
                    "message": f"文件上传失败: {str(e)}",
                    "success": False
                })
        
        @self.app.post(f"/{self.prefix}/set_language")
        async def set_language(request: Request):
            """设置语言"""
            try:
                data = request.body
                params = parse_qs(data)
                language = params.get('language', [self.default_language])[0]
                
                # 获取当前session
                session_data = request.headers.get('Cookie')
                session_dict = {}
                if session_data:
                    for item in session_data.split(";"):
                        if "=" in item:
                            key, value = item.split("=")
                            session_dict[key.strip()] = value.strip()
                        
                # 更新session中的语言设置
                session = session_dict.get("session", "{}")
                data = json.loads(session)
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
                    headers={"Set-Cookie": "; ".join(cookie_attrs)}
                )
            except Exception as e:
                print(f"Set language failed: {str(e)}")
                return Response(status_code=500, description="Set language failed")
        
        @self.app.get(f"/{self.prefix}/:route_id/inline_data")
        async def get_inline_data(request: Request):
            try:
                route_id = request.path_params['route_id']
                model_admin = self.get_model_admin(route_id)
                if not model_admin:
                    return jsonify({"error": "Model not found"}, status_code=404)
                
                params: dict = request.query_params.to_dict()
                parent_id = params.get('parent_id', [''])[0]
                inline_model = params.get('inline_model', [''])[0]
                
                # 获取排序参数
                sort_field = params.get('sort', [''])[0]
                sort_order = params.get('order', ['asc'])[0]
                                
                if not parent_id or not inline_model:
                    return jsonify({"error": "Missing parameters"})
                
                # 找到对应的内联实例
                inline = next((i for i in model_admin._inline_instances if i.model.__name__ == inline_model), None)
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
                    sortable_field = next((field for field in inline.table_fields 
                                          if field.name == sort_field and field.sortable), None)
                    if sortable_field:
                        order_by = f"{'-' if sort_order == 'desc' else ''}{sort_field}"
                        queryset = queryset.order_by(order_by)
                
                # 获取数据
                data = []
                async for obj in queryset:
                    try:
                        serialized = await inline.serialize_object(obj)
                        data.append({
                            'data': serialized,
                            'display': serialized
                        })
                    except Exception as e:
                        print(f"Error serializing object: {str(e)}")
                        continue
                
                # 添加字段配置信息
                fields_config = [
                    {
                        'name': field.name,
                        'label': field.label,
                        'display_type': field.display_type.value if field.display_type else 'text',
                        'sortable': field.sortable,
                        'width': field.width,
                        'is_link': field.is_link  # 确保is_link也被传递到前端
                    }
                    for field in inline.table_fields
                ]
                return Response(
                    status_code=200,
                    headers={"Content-Type": "application/json; charset=utf-8"},
                    description=json.dumps({
                        "success": True,
                        "data": data,
                        "total": len(data),
                        "fields": fields_config
                    }),
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
                    return jsonify({
                        "success": False,
                        "message": "不支持导入功能"
                    })
                
                # 获取上传的文件
                files = request.files
                filename = list(files.keys())[0]
                if not files:
                    return jsonify({
                        "success": False,
                        "message": "未上传文件"
                    })
                    
                file_data = next(iter(files.values()))
                
                # 检查文件类型
                if not any(filename.endswith(ext) for ext in ['.xlsx', '.xls', '.csv']):
                    return jsonify({
                        "success": False,
                        "message": "仅支持 Excel 或 CSV 文件"
                    })
                    
                # 处理文件数据
                import pandas as pd
                import io
                
                df = None
                if filename.endswith('.csv'):
                    df = pd.read_csv(io.BytesIO(file_data))
                else:
                    df = pd.read_excel(io.BytesIO(file_data))
                    
                # 验证字段
                missing_fields = [f for f in model_admin.import_fields if f not in df.columns]
                if missing_fields:
                    return jsonify({
                        "success": False,
                        "message": f"缺少必需字段: {', '.join(missing_fields)}"
                    })
                    
                # 导入数据
                success_count = 0
                error_count = 0
                errors = []
                
                for _, row in df.iterrows():
                    try:
                        data = {field: row[field] for field in model_admin.import_fields}
                        await model_admin.model.create(**data)
                        success_count += 1
                    except Exception as e:
                        error_count += 1
                        errors.append(str(e))
                        
                return jsonify({
                    "success": True,
                    "message": f"导入完成: 成功 {success_count} 条, 失败 {error_count} 条",
                    "errors": errors if errors else None
                })
                
            except Exception as e:
                print(f"Import error: {str(e)}")
                return jsonify({
                    "success": False,
                    "message": f"导入失败: {str(e)}"
                })
        
    def register_model(self, model: Type[Model], admin_class: Optional[Type[ModelAdmin]] = None):
        """注册模型admin站点"""
        if admin_class is None:
            admin_class = ModelAdmin
            
        # 创建管理类实例
        instance = admin_class(model)
        
        # 生成唯一的路由标识符
        route_id = admin_class.__name__
        
        # 如果路由标识符已存在，添加数字后缀
        base_route_id = route_id
        counter = 1
        while route_id in self.models:
            route_id = f"{base_route_id}{counter}"
            counter += 1
            
        # 存储路由标识符到实例中，用于后续路由生成
        instance.route_id = route_id
        
        print(f"\n=== Registering Model ===")
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
            cookie_header = request.headers.get('Cookie')
            print(f"Cookie header: {cookie_header}")  # 调试日志
            
            if not cookie_header:
                print("No cookie header found")  # 调试日志
                return None
            
            # 解析cookie
            cookies = {}
            for item in cookie_header.split(";"):
                if "=" in item:
                    key, value = item.split("=", 1)
                    cookies[key.strip()] = value.strip()
            
            token = cookies.get("session_token")
            print(f"Found session token: {token}")  # 调试日志
            
            if not token:
                print("No session token in cookies")  # 调试日志
                return None
            
            # 验证会话令牌
            valid, user_id = self._verify_session_token(token)
            print(f"Token validation: valid={valid}, user_id={user_id}")  # 调试日志
            
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
            session_data = request.headers.get('Cookie')
            if not session_data:
                return self.default_language
                
            session_dict = {}
            for item in session_data.split(";"):
                if "=" in item:  # 确保有等号
                    key, value = item.split("=", 1)  # 只分一个等号
                    session_dict[key.strip()] = value.strip()
                
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
        self.menu_manager.register_menu(menu_item)  # 使用 menu_manager 注册菜单

    def get_model_admin(self, route_id: str) -> Optional[ModelAdmin]:
        """根据路由ID获取模型管理器"""
        return self.models.get(route_id)

    async def check_permission(self, request: Request, model_name: str, action: str) -> bool:
        """检查权限"""
        try:
            user = await self._get_current_user(request)
            if not user:
                print("No user found")
                return False
            
            print(f"\n=== Checking Permissions ===")
            print(f"User: {user.username}")
            print(f"Model: {model_name}")
            print(f"Action: {action}")
            
            # 超级用户拥有所有权限
            if user.is_superuser:
                print("User is superuser, granting access")
                return True
            user_roles = await UserRole.filter(user=user).prefetch_related('role')
            roles = [ur.role for ur in user_roles]
            # 获取用户的所有角色
            # roles = await user.roles.all()
            print(roles)
            print(f"User roles: {[role.name for role in roles]}")
            
            # 检查每个角色的权限
            for role in roles:
                print(f"\nChecking role: {role.name}")
                print(f"Role accessible models: {role.accessible_models}")
                
                if role.accessible_models == ['*']:
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