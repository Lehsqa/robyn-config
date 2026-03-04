from __future__ import annotations

from typing import Dict

from sqlalchemy import select

from .auth_models_sqlalchemy import Role
from .core.fields import DisplayType, FormField, TableField
from .core.sqlalchemy_admin import ModelAdmin
from .models_sqlalchemy import AdminUser


class AdminUserAdmin(ModelAdmin):
    verbose_name = "User Management"
    menu_group = "System Management"
    menu_icon = "bi bi-people"
    menu_order = 1

    table_fields = [
        TableField("id", label="ID", hidden=True),
        TableField("username", label="Username", sortable=True),
        TableField("email", label="Email", sortable=True),
        TableField(
            "is_active", label="Active", display_type=DisplayType.BOOLEAN
        ),
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

    table_fields = [
        TableField("id", label="ID", hidden=True),
        TableField("user_id", label="User ID", sortable=True),
        TableField("role_id", label="Role ID", sortable=True),
        TableField(
            "created_at",
            label="Created At",
            display_type=DisplayType.DATETIME,
            sortable=True,
            formatter=lambda value: (
                value.strftime("%Y-%m-%d %H:%M:%S") if value else ""
            ),
        ),
    ]

    async def get_form_fields(self):
        if not hasattr(self, "site") or self.site is None:
            return [
                FormField("user_id", label="User ID", required=True),
                FormField("role_id", label="Role ID", required=True),
            ]

        session = self.site.session_factory()
        try:
            users_result = await session.execute(select(AdminUser))
            roles_result = await session.execute(select(Role))
            users = users_result.scalars().all()
            roles = roles_result.scalars().all()
            user_choices: Dict[str, str] = {
                str(user.id): user.username for user in users
            }
            role_choices: Dict[str, str] = {
                str(role.id): role.name for role in roles
            }
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
        finally:
            await session.close()

    async def get_add_form_fields(self):
        return await self.get_form_fields()
