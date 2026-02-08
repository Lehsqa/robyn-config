from enum import Enum
from typing import Optional, Dict, Any, Type
from dataclasses import dataclass
from tortoise import Model
from tortoise.expressions import Q
import operator
from functools import reduce

class FilterType(Enum):
    """过滤器类型"""
    INPUT = 'input'
    SELECT = 'select'
    DATE_RANGE = 'date_range'
    NUMBER_RANGE = 'number_range'
    BOOLEAN = 'boolean'

@dataclass
class FilterField:
    """过滤字段基类"""
    name: str                    # 字段名称，格式应该是 "模型类_字段名"
    label: Optional[str] = None
    filter_type: FilterType = FilterType.INPUT
    choices: Optional[Dict[Any, str]] = None
    multiple: bool = False
    placeholder: Optional[str] = None
    operator: str = 'icontains'
    
    # 添加关联字段支持，与 SearchField 保持一致
    related_model: Optional[Type[Model]] = None  # 关联的模型
    related_key: Optional[str] = None           # 外键字段名
    
    def __post_init__(self):
        if self.label is None:
            self.label = self.name.replace('_', ' ').title()
            
    def to_dict(self) -> dict:
        """转换为字典，用于JSON序列化"""
        data = {
            'name': self.name,
            'label': self.label,
            'type': self.filter_type.value,
            'choices': self.choices,
            'placeholder': self.placeholder,
            'multiple': self.multiple,
            'operator': self.operator
        }
        
        if self.related_model:
            data.update({
                'related_model': self.related_model.__name__
            })
            
        return data

    async def build_filter_query(self, filter_value: str) -> dict:
        """构建过滤查询条件"""
        if not filter_value:
            return {}
            
        if self.related_model and self.related_key:
            # 从字段名中解析要过滤的关联字段
            model_name = self.related_model.__name__
            if self.name.startswith(model_name + '_'):
                # 获取实际要过滤的字段名
                related_field = self.name[len(model_name + '_'):]
                try:
                    # 先查询关联模型
                    related_objects = await self.related_model.filter(
                        **{f"{related_field}__icontains": filter_value}
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
                    print(f"Error in related filter: {str(e)}")
                    return {"id": None}
        else:
            # 直接过滤当前字段
            return {f"{self.name}__{self.operator}": filter_value}

class InputFilter(FilterField):
    """输入框过滤器"""
    def __init__(self, name: str, label: Optional[str] = None, placeholder: Optional[str] = None,
                 operator: str = 'icontains', related_model: Optional[Type[Model]] = None,
                 related_key: Optional[str] = None):
        super().__init__(
            name=name,
            label=label,
            filter_type=FilterType.INPUT,
            placeholder=placeholder,
            operator=operator,
            related_model=related_model,
            related_key=related_key
        )

class SelectFilter(FilterField):
    """下拉框过滤器"""
    def __init__(self, name: str, choices: Dict[Any, str], label: Optional[str] = None,
                 multiple: bool = False, related_model: Optional[Type[Model]] = None,
                 related_key: Optional[str] = None):
        super().__init__(
            name=name,
            label=label,
            filter_type=FilterType.SELECT,
            choices=choices,
            multiple=multiple,
            related_model=related_model,
            related_key=related_key
        )

class DateRangeFilter(FilterField):
    """日期范围过滤器"""
    def __init__(self, name: str, label: Optional[str] = None):
        super().__init__(
            name=name,
            label=label,
            filter_type=FilterType.DATE_RANGE
        )

class NumberRangeFilter(FilterField):
    """数字范围过滤器"""
    def __init__(self, name: str, label: Optional[str] = None):
        super().__init__(
            name=name,
            label=label,
            filter_type=FilterType.NUMBER_RANGE
        )

class BooleanFilter(FilterField):
    """布尔过滤器"""
    def __init__(self, name: str, label: Optional[str] = None):
        super().__init__(
            name=name,
            label=label,
            filter_type=FilterType.BOOLEAN,
            choices={True: '是', False: '否'}
        )