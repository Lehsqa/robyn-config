from tortoise import fields, models
from typing import List
from .models import AdminUser

class Role(models.Model):
    """角色模型"""
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=150, unique=True)
    description = fields.CharField(max_length=200, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    
    # 角色可访问的模型路径列表
    accessible_models = fields.JSONField(default=list)  # ['US_Trademark', 'US_DocumentRecord']
    
    async def has_model_access(self, model_path: str) -> bool:
        """检查是否有权限访问指定模型"""
        return model_path in self.accessible_models
    
    class Meta:
        table = "robyn_admin_roles"

class UserRole(models.Model):
    """用户-角色关联表"""
    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField('models.AdminUser', related_name='user_roles')
    role = fields.ForeignKeyField('models.Role', related_name='role_users')
    created_at = fields.DatetimeField(auto_now_add=True)
    
    class Meta:
        table = "robyn_admin_user_roles" 