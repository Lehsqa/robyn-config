from .core.fields import TableField, DisplayType, FormField
from typing import Dict
from .core.admin import  ModelAdmin
from .auth_models import Role, UserRole
from .models import AdminUser

class AdminUserAdmin(ModelAdmin):
    """用户管理"""
    verbose_name = "用户管理"
    menu_group = "系统管理"
    menu_icon = "bi bi-people"
    menu_order = 1
    
    table_fields = [
        TableField("id", label="ID", hidden=True),
        TableField("username", label="用户名", sortable=True),
        TableField("email", label="邮箱", sortable=True),
        TableField("is_active", label="是否激活", display_type=DisplayType.BOOLEAN),
        TableField("is_superuser", label="是否超级用户", display_type=DisplayType.BOOLEAN),
        TableField("last_login", label="最后登录", display_type=DisplayType.DATETIME),
    ]
    add_form_fields = [
        FormField("username", label="用户名", required=True),
        FormField("email", label="邮箱"),
        FormField("password", label="密码",
                field_type=DisplayType.PASSWORD,
                processor=lambda x: AdminUser.hash_password(x)),
        FormField("is_active", label="是否启用", field_type=DisplayType.BOOLEAN),
        FormField("is_superuser", label="是否为超级用户", field_type=DisplayType.BOOLEAN),
    ]

    form_fields = [
        FormField("username", label="用户名", required=True),
        FormField("email", label="邮箱"),
        FormField("password", label="密码",
                field_type=DisplayType.PASSWORD,
                processor=lambda x: AdminUser.hash_password(x)),
        FormField("is_active", label="是否启用", field_type=DisplayType.BOOLEAN),
        FormField("is_superuser", label="是否为超级用户", field_type=DisplayType.BOOLEAN),
    ]

class RoleAdmin(ModelAdmin):
    """角色管理"""
    verbose_name = "角色管理"
    menu_group = "系统管理"
    menu_icon = "bi bi-person-badge"
    menu_order = 2
    
    table_fields = [
        TableField("id", label="ID", hidden=True),
        TableField("name", label="角色名称", sortable=True),
        TableField("description", label="描述"),
        TableField("accessible_models", label="角色权限", display_type=DisplayType.JSON),
    ]
    
    add_form_fields = [
        FormField("name", label="角色名称", required=True),
        FormField("description", label="描述"),
        FormField(
            "accessible_models", 
            label="权限配置",
            field_type=DisplayType.JSON,
        ),
    ]

    form_fields = [
        FormField("name", label="角色名称", required=True),
        FormField("description", label="描述"),
        FormField(
            "accessible_models", 
            label="权限配置",
            field_type=DisplayType.JSON,
        ),
    ]

class UserRoleAdmin(ModelAdmin):
    """用户角色关联管理"""
    verbose_name = "用户角色管理"
    menu_group = "系统管理"
    menu_icon = "bi bi-people-fill"
    menu_order = 3
    

    async def get_form_fields(self):
        """动态获取表单字段配置"""
        # 获取所有用户和角色选项
        users = await AdminUser.all()
        roles = await Role.all()
        
        user_choices = {str(user.id): user.username for user in users}
        role_choices = {str(role.id): role.name for role in roles}
        return [
            FormField(
                "user_id",
                label="用户",
                field_type=DisplayType.SELECT,
                required=True,
                choices=user_choices
            ),
            FormField(
                "role_id",
                label="角色",
                field_type=DisplayType.SELECT,
                required=True,
                choices=role_choices
            )
        ]
    
    async def get_add_form_fields(self):
        """获取添加表单字段配置"""
        return await self.get_form_fields()
    
    table_fields = [
        TableField("id", label="ID", hidden=True),
        TableField(
            "AdminUser_username",  # 使用 "模型类_字段名" 格式
            label="用户名",
            related_model=AdminUser,
            related_key="user_id",
            sortable=True
        ),
        TableField(
            "Role_name",  # 使用 "模型类_字段名" 格式
            label="角色名称",
            related_model=Role,
            related_key="role_id",
            sortable=True
        ),
        TableField(
            "created_at", 
            label="创建时间", 
            display_type=DisplayType.DATETIME,
            sortable=True,
            formatter=lambda x: x.strftime('%Y-%m-%d %H:%M:%S') if x else ''
        ),
    ]
    

    