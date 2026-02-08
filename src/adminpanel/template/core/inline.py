from typing import Type, List, Optional
from tortoise import Model
from .fields import TableField, FormField
import asyncio
from dataclasses import dataclass

class InlineModelAdmin:
    """内联管理类基类"""
    model: Type[Model] = None  # 关联的模型
    fk_field: str = None       # 外键字段名
    extra: int = 1             # 额外显示的空表单数量
    max_num: Optional[int] = None  # 最大条数限制
    can_delete: bool = True    # 是否可以删除
    verbose_name: Optional[str] = None  # 显示名称
    
    # 显示和编辑字段配置
    table_fields: List[TableField] = []
    form_fields: List[FormField] = []
    
    # 默认排序字段列表
    default_ordering: List[str] = None  # 如 ['-created_at', 'name']
    
    def __init__(self, parent_model: Type[Model]):
        if not self.model:
            raise ValueError("必须指定 model")
        if not self.fk_field:
            raise ValueError("必须指定 fk_field")
            
        self.parent_model = parent_model
        if not self.verbose_name:
            if hasattr(self.model, 'Meta') and hasattr(self.model.Meta, 'description'):
                self.verbose_name = self.model.Meta.description
            else:
                self.verbose_name = self.model.__name__
                
        # 初始化排序配置
        if self.default_ordering is None:
            self.default_ordering = []
        self.is_inline = True  # 设置为内联模型

    async def get_queryset(self, parent_instance):
        """获取关联的查询集"""
        if not parent_instance:
            return self.model.none()
        
        # 构建查询条件
        filter_kwargs = {self.fk_field: parent_instance.id}
        
        # 获取基础查询集
        queryset = self.model.filter(**filter_kwargs)
        
        # 应用默认排序
        if self.default_ordering:
            queryset = queryset.order_by(*self.default_ordering)
            
        return queryset
        
    def get_formset(self):
        """获取表单集配置"""
        # 从table_fields中获取可排序字段
        ordering_fields = [
            field.name for field in self.table_fields 
            if field.sortable
        ]
        return {
            'model': self.model.__name__,
            'fk_field': self.fk_field,
            'extra': self.extra,
            'max_num': self.max_num,
            'can_delete': self.can_delete,
            'fields': [field.to_dict() for field in self.form_fields],
            'table_fields': [field.to_dict() for field in self.table_fields],
            'verbose_name': self.verbose_name,
            'title': self.verbose_name,
            # 添加排序配置
            'default_ordering': self.default_ordering,
            'ordering_fields': ordering_fields  # 使用从table_fields获取的可排序字段
        }
        
    async def serialize_object(self, obj: Model, for_display: bool = True) -> dict:
        """序列化对象"""
        result = {'id': str(getattr(obj, 'id', ''))}
        
        for field in self.table_fields:
            try:
                if field.related_model and field.related_key:
                    # 处理关联字段
                    fk_value = getattr(obj, field.related_key)
                    if fk_value:
                        try:
                            related_obj = await field.related_model.get(id=fk_value)
                            if related_obj:
                                # 获取关联字段的值
                                related_field = field.name.split('_')[-1]  # 获取最后一部分作为字段名
                                related_value = getattr(related_obj, related_field)
                                result[field.name] = str(related_value) if related_value is not None else ''
                                continue
                        except Exception as e:
                            print(f"Error getting related object: {str(e)}")
                    result[field.name] = ''
                else:
                    # 处理普通字段
                    value = getattr(obj, field.name, None)
                    if for_display and field.formatter and value is not None:
                        try:
                            if asyncio.iscoroutinefunction(field.formatter):
                                result[field.name] = await field.formatter(value)
                            else:
                                result[field.name] = field.formatter(value)
                        except Exception as e:
                            print(f"Error formatting field {field.name}: {str(e)}")
                            result[field.name] = str(value) if value is not None else ''
                    else:
                        result[field.name] = str(value) if value is not None else ''
            except Exception as e:
                print(f"Error processing field {field.name}: {str(e)}")
                result[field.name] = ''
        
        return result