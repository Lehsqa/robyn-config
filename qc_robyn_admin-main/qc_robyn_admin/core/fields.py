from enum import Enum
from typing import Any, Optional, Union, Callable, List, Dict, Type
from dataclasses import dataclass
from tortoise import Model
import asyncio
from .filters import FilterType
from tortoise.expressions import Q
from functools import reduce
import operator

class DisplayType(Enum):
    """显示类型枚举"""
    TEXT = 'text'
    DATE = 'date'
    DATETIME = 'datetime'
    IMAGE = 'image'
    FILE_UPLOAD = 'file_upload'
    STATUS = 'status'
    BOOLEAN = 'boolean'
    LINK = 'link'
    HTML = 'html'
    CUSTOM = 'custom'
    PASSWORD = 'password'
    EMAIL = 'email'
    SELECT = 'select'
    SWITCH = 'switch'
    JSON = 'json'
    
@dataclass
class TableAction:
    """表格操作按钮配置"""
    name: str                # 按钮名称
    label: str              # 显示文本
    icon: str = ""          # 图标类名
    btn_class: str = "btn-primary"  # 按钮样式
    inline_model: Optional[str] = None  # 关联的内联模型名称

@dataclass
class TableField:
    """表格字段配置"""
    name: str                    
    label: Optional[str] = None  
    display_type: Optional[DisplayType] = None
    sortable: bool = False
    searchable: bool = False
    filterable: bool = False
    editable: bool = True
    readonly: bool = False
    visible: bool = True
    is_link: bool = False
    width: Optional[Union[int, str]] = None
    formatter: Optional[Callable] = None
    hidden: bool = False
    choices: Optional[Dict[Any, Any]] = None  # 实际值映射
    labels: Optional[Dict[Any, str]] = None   # 显示文本映射
    
    # 关联字段配置
    related_model: Optional[Type[Model]] = None  # 关联的模型
    related_key: Optional[str] = None           # 关联的外键字段
    
    actions: List[TableAction] = None  # 添加自定义操作按钮配置
    
    def __post_init__(self):
        if self.label is None:
            self.label = self.name.replace('_', ' ').title()
            
        # 如果display_type是LINK，自动设置is_link为True
        if self.display_type == DisplayType.LINK:
            self.is_link = True
            
        # 处理关联字段名称
        if self.related_model and self.related_key:
            # 从字段名中解析要显示的关联字段
            parts = self.name.split('_')
            if len(parts) > 1:
                self.related_field = parts[-1]  # 使用最后一部分作为关联字段名
                self.display_name = self.name   # 保持原始名称作为显示名
            else:
                self.related_field = 'id'  # 默认使用 id
                self.display_name = self.name
        else:
            self.display_name = self.name
            
        if self.actions is None:
            self.actions = []
            
    async def format_value(self, value: Any, instance: Optional[Model] = None) -> str:
        """格式化值用于显示"""
        if value is None:
            return ''
            
        # 如果是关联字段
        if self.related_model and self.related_key and instance:
            try:
                # 获取外键值
                fk_value = getattr(instance, self.related_key)
                if not fk_value:
                    return ''
                    
                # 查询关联对象
                related_obj = await self.related_model.get(id=fk_value)
                if related_obj:
                    # 获取关联字段的值
                    related_value = getattr(related_obj, self.related_field)
                    return str(related_value) if related_value is not None else ''
                return ''
            except Exception as e:
                print(f"Error getting related value: {str(e)}")
                return ''
                
        # 使用自定义格式化函数
        if self.formatter:
            try:
                if asyncio.iscoroutinefunction(self.formatter):
                    return await self.formatter(value)
                return self.formatter(value)
            except Exception as e:
                print(f"Error formatting value: {str(e)}")
                return str(value)
                
        return str(value)
    
    def to_dict(self) -> dict:
        """转换为字典，用于JSON序列化"""
        data = {
            'name': self.display_name,
            'label': self.label,
            'display_type': self.display_type.value if self.display_type else 'text',
            'sortable': self.sortable,
            'searchable': self.searchable,
            'filterable': self.filterable,
            'editable': self.editable,
            'readonly': self.readonly,
            'visible': self.visible,
            'is_link': self.is_link,
            'width': self.width,
            'hidden': self.hidden,
            'has_formatter': bool(self.formatter),
            'choices': self.choices,
            'labels': self.labels  # 添加显示文本映射
        }
        
        if self.related_model and self.related_key:
            data.update({
                'related_model': self.related_model.__name__,
                'related_key': self.related_key,
                'related_field': self.related_field
            })
            
        return data
    
@dataclass
class FormField:
    """表单字段配置"""
    name: str
    label: Optional[str] = None
    field_type: Optional[DisplayType] = None
    required: bool = False
    readonly: bool = False
    help_text: Optional[str] = None
    placeholder: Optional[str] = None
    validators: List[Callable] = None
    choices: Optional[Dict[Any, str]] = None
    default: Any = None
    processor: Optional[Callable] = None  # 添加数据处理函数
    upload_path: Optional[str] = None  # 静态资源存储路径
    accept: Optional[str] = None  # 接受的文件类型
    max_size: Optional[int] = None  # 最大文件大小（字节）
    multiple: bool = False  # 是否支持多文件上传
    preview: bool = True  # 是否显示预览
    drag_text: Optional[str] = None  # 拖拽区域提示文本
    
    def __post_init__(self):
        if self.label is None:
            self.label = self.name.replace('_', ' ').title()
        self.validators = self.validators or []
    
    def process_value(self, value: Any) -> Any:
        """处理字值"""
        if self.processor:
            return self.processor(value)
        return value
    
    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'label': self.label,
            'field_type': self.field_type.value if self.field_type else None,
            'required': self.required,
            'readonly': self.readonly,
            'help_text': self.help_text,
            'placeholder': self.placeholder,
            'choices': self.choices,
            'default': self.default,
            'upload_path': self.upload_path,
            'accept': self.accept,
            'max_size': self.max_size,
            'multiple': self.multiple,
            'preview': self.preview,
            'drag_text': self.drag_text
        }
    
@dataclass
class SearchField:
    """search field config
    
    name: str  if not related_model, name format is "field" else "RelatedModel_field"

    label: str


    """
    name: str                    #
    label: Optional[str] = None
    placeholder: str = ""
    operator: str = 'icontains'
    
    # relate modal
    related_model: Optional[Type[Model]] = None  # relate modal
    related_key: Optional[str] = None           # relate key  
    
    def __post_init__(self):
        if self.label is None:
            self.label = self.name.replace('_', ' ').title()
        if not self.placeholder:
            self.placeholder = f"{self.label}"
            
    def to_dict(self) -> dict:
        data = {
            'name': self.name,
            'label': self.label,
            'placeholder': self.placeholder,
            'operator': self.operator
        }
        if self.related_model:
            data.update({
                'related_model': self.related_model.__name__,
            })
        return data

    async def build_search_query(self, search_value: str) -> dict:
        if not search_value:
            return {}
        if self.related_model and self.related_key:
            # 从字段名中解析要搜索的关联字段
            model_name = self.related_model.__name__
            if self.name.startswith(model_name + '_'):
                # 获取实际要搜索的字段名
                related_field = self.name[len(model_name + '_'):]
                try:
                    # 先查询关联模型
                    related_objects = await self.related_model.filter(
                        **{f"{related_field}__icontains": search_value}
                    )
                    if not related_objects:
                        return {"id": None}   
                    # 构建 OR 条件列表
                    conditions = [
                        Q(**{f"{self.related_key}": str(obj.id)})
                        for obj in related_objects
                    ] 
                    if conditions:
                        # 返回组合的Q对象
                        combined_q = reduce(operator.or_, conditions)
                        return {"_q_object": combined_q}
                    return {"id": None}
                except Exception as e:
                    print(f"Error in related search: {str(e)}")
                    return {"id": None}
        else:
            # 直接搜索当前字段，使用精确匹配而不是模糊匹配
            return {f"{self.name}": search_value}
