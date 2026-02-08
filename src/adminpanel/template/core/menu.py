from dataclasses import dataclass
from typing import Optional, Dict, List

@dataclass
class MenuItem:
    """菜单项配置"""
    name: str                    # 菜单名称
    icon: str = ""              # 图标类名 (Bootstrap Icons)
    parent: Optional[str] = None # 父菜单名称
    order: int = 0              # 排序值

class MenuManager:
    """菜单管理器"""
    def __init__(self):
        self.menus: Dict[str, MenuItem] = {}
        
    def register_menu(self, menu_item: MenuItem):
        """注册菜单项"""
        self.menus[menu_item.name] = menu_item
        
    def get_menu_tree(self) -> Dict[str, MenuItem]:
        """获取菜单树结构"""
        return self.menus 