from __future__ import annotations

from .auth_models import Role
from .core.admin import ModelAdmin
from .core.fields import DisplayType, FormField, TableField
from .models import AdminUser


class AdminUserAdmin(ModelAdmin):
    verbose_name = "User Management"
    menu_group = "System Management"
    menu_icon = "bi bi-people"
    menu_order = 1

    table_fields = [
        TableField("id", label="ID", hidden=True),
        TableField("username", label="Username", sortable=True),
        TableField("email", label="Email", sortable=True),
        TableField("is_active", label="Active", display_type=DisplayType.BOOLEAN),
        TableField(
            "is_superuser",
            label="Superuser",
            display_type=DisplayType.BOOLEAN,
        ),
        TableField(
            "last_login",
            label="Last Login",
            display_type=DisplayType.DATETIME,
        ),
    ]

    add_form_fields = [
        FormField("username", label="Username", required=True),
        FormField("email", label="Email"),
        FormField(
            "password",
            label="Password",
            field_type=DisplayType.PASSWORD,
            processor=lambda value: AdminUser.hash_password(value),
        ),
        FormField("is_active", label="Active", field_type=DisplayType.BOOLEAN),
        FormField(
            "is_superuser",
            label="Superuser",
            field_type=DisplayType.BOOLEAN,
        ),
    ]

    form_fields = add_form_fields


class RoleAdmin(ModelAdmin):
    verbose_name = "Role Management"
    menu_group = "System Management"
    menu_icon = "bi bi-person-badge"
    menu_order = 2

    table_fields = [
        TableField("id", label="ID", hidden=True),
        TableField("name", label="Role Name", sortable=True),
        TableField("description", label="Description"),
        TableField(
            "accessible_models",
            label="Permissions",
            display_type=DisplayType.JSON,
        ),
    ]

    add_form_fields = [
        FormField("name", label="Role Name", required=True),
        FormField("description", label="Description"),
        FormField(
            "accessible_models",
            label="Permissions",
            field_type=DisplayType.JSON,
        ),
    ]

    form_fields = add_form_fields


class UserRoleAdmin(ModelAdmin):
    verbose_name = "User Role Management"
    menu_group = "System Management"
    menu_icon = "bi bi-people-fill"
    menu_order = 3

    async def get_form_fields(self):
        users = await AdminUser.all()
        roles = await Role.all()
        user_choices = {str(user.id): user.username for user in users}
        role_choices = {str(role.id): role.name for role in roles}
        return [
            FormField(
                "user_id",
                label="User",
                field_type=DisplayType.SELECT,
                required=True,
                choices=user_choices,
            ),
            FormField(
                "role_id",
                label="Role",
                field_type=DisplayType.SELECT,
                required=True,
                choices=role_choices,
            ),
        ]

    async def get_add_form_fields(self):
        return await self.get_form_fields()

    table_fields = [
        TableField("id", label="ID", hidden=True),
        TableField(
            "AdminUser_username",
            label="Username",
            related_model=AdminUser,
            related_key="user_id",
            sortable=True,
        ),
        TableField(
            "Role_name",
            label="Role Name",
            related_model=Role,
            related_key="role_id",
            sortable=True,
        ),
        TableField(
            "created_at",
            label="Created At",
            display_type=DisplayType.DATETIME,
            sortable=True,
            formatter=lambda value: value.strftime("%Y-%m-%d %H:%M:%S") if value else "",
        ),
    ]
