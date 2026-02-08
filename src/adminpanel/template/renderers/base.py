from abc import ABC, abstractmethod
from typing import Any, Dict
from ..core.fields import DisplayType, Field

class BaseRenderer(ABC):
    """渲染器基类"""
    
    @abstractmethod
    def render(self, value: Any, context: Dict[str, Any] = None) -> str:
        """渲染值"""
        pass

class TableRenderer(BaseRenderer):
    """表格渲染器"""
    def render(self, value: Any, context: Dict[str, Any] = None) -> str:
        field = context.get('field')
        if not field:
            return str(value)
        return field.format_value(value)

class FormRenderer(BaseRenderer):
    """表单渲染器"""
    def render(self, value: Any, context: Dict[str, Any] = None) -> str:
        field = context.get('field')
        if not field:
            return f'<input type="text" value="{value}">'
        return self._render_widget(value, field)

    def _render_widget(self, value: Any, field: Field) -> str:
        if field.display_type == DisplayType.SELECT:
            return self._render_select(value, field)
        elif field.display_type == DisplayType.RADIO:
            return self._render_radio(value, field)
        # ... 其他类型的渲染
        
    def _render_select(self, value: Any, field: Field) -> str:
        """渲染下拉选择框"""
        options = []
        for choice_value, choice_label in field.choices.items():
            selected = 'selected' if str(value) == str(choice_value) else ''
            options.append(f'<option value="{choice_value}" {selected}>{choice_label}</option>')
        
        return f'<select name="{field.name}">\n{"".join(options)}\n</select>'
        
    def _render_radio(self, value: Any, field: Field) -> str:
        """渲染单选框组"""
        radios = []
        for choice_value, choice_label in field.choices.items():
            checked = 'checked' if str(value) == str(choice_value) else ''
            radio_id = f"{field.name}_{choice_value}"
            radios.append(
                f'<div class="form-check">\n'
                f'  <input type="radio" id="{radio_id}" value="{choice_value}" {checked} '
                f'class="form-check-input" name="{field.name}">\n'
                f'  <label class="form-check-label" for="{radio_id}">{choice_label}</label>\n'
                f'</div>'
            )
        return '\n'.join(radios)