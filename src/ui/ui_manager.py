"""UI组件自动管理器

负责管理桌面上所有UI组件的位置，避免重叠和冲突。
主程序只需要向管理器传递各组件的显示信息，管理器会自动计算和设置位置。
"""

from __future__ import annotations
from typing import Dict, List, Optional, Tuple, Any
import tkinter as tk


class UIComponent:
    """UI组件信息类"""
    
    def __init__(self, name: str, obj: Any, width: int, height: int, 
                 preferred_position: str = "auto", priority: int = 0):
        self.name = name
        self.obj = obj  # UI组件对象
        self.width = width
        self.height = height
        self.preferred_position = preferred_position  # 首选位置：top, bottom, left, right, auto
        self.priority = priority  # 优先级，数字越大优先级越高
        self.x = 0  # 当前x坐标
        self.y = 0  # 当前y坐标
        self.visible = False  # 是否可见
        
    def get_position(self) -> Tuple[int, int]:
        """获取当前位置"""
        return (self.x, self.y)
        
    def set_position(self, x: int, y: int) -> None:
        """设置位置"""
        self.x = x
        self.y = y
        if hasattr(self.obj, 'window') and self.obj.window and self.obj.window.winfo_exists():
            # 确保窗口已更新
            self.obj.window.update_idletasks()
            
            # 获取窗口的实际尺寸
            actual_width = self.obj.window.winfo_width()
            actual_height = self.obj.window.winfo_height()
            
            # 如果获取不到实际尺寸，使用注册时的尺寸
            if actual_width <= 1:
                actual_width = self.width
            if actual_height <= 1:
                actual_height = self.height
                
            # 设置窗口位置
            self.obj.window.geometry(f"{actual_width}x{actual_height}+{x}+{y}")
            
            # 确保窗口已更新
            self.obj.window.update_idletasks()
            
    def is_visible(self) -> bool:
        """检查是否可见"""
        if not self.visible:
            return False
        if hasattr(self.obj, 'window') and self.obj.window and self.obj.window.winfo_exists():
            return self.obj.window.state() != "withdrawn"
        return False


class UIManager:
    """UI组件自动管理器"""
    
    def __init__(self, app):
        self.app = app
        self.components: Dict[str, UIComponent] = {}
        self.pet_width = 100
        self.pet_height = 100
        self.pet_x = 0
        self.pet_y = 0
        
    def register_component(self, name: str, obj: Any, width: int, height: int,
                          preferred_position: str = "auto", priority: int = 0) -> None:
        """注册UI组件
        
        Args:
            name: 组件名称
            obj: 组件对象
            width: 组件宽度
            height: 组件高度
            preferred_position: 首选位置 (top, bottom, left, right, auto)
            priority: 优先级，数字越大优先级越高
        """
        component = UIComponent(name, obj, width, height, preferred_position, priority)
        self.components[name] = component
        
    def update_pet_info(self, x: int, y: int, width: int, height: int) -> None:
        """更新宠物信息
        
        Args:
            x: 宠物x坐标
            y: 宠物y坐标
            width: 宠物宽度
            height: 宠物高度
        """
        self.pet_x = x
        self.pet_y = y
        self.pet_width = width
        self.pet_height = height
        
    def set_component_visibility(self, name: str, visible: bool) -> None:
        """设置组件可见性
        
        Args:
            name: 组件名称
            visible: 是否可见
        """
        if name in self.components:
            self.components[name].visible = visible
            # 确保主窗口已更新
            self.app.root.update_idletasks()
            # 延迟更新布局，确保窗口状态已更新
            self.app.root.after(10, self.update_layout)
            
    def update_layout(self) -> None:
        """更新布局，根据当前可见的组件重新计算位置"""
        # 获取所有组件，包括可能刚显示但还没有标记为可见的组件
        all_components = list(self.components.values())
        
        # 确保所有窗口都已更新
        self.app.root.update_idletasks()
        
        # 更新所有组件的实际尺寸和可见性
        for component in all_components:
            if hasattr(component.obj, 'window') and component.obj.window and component.obj.window.winfo_exists():
                # 确保组件窗口已更新
                component.obj.window.update_idletasks()
                
                actual_width = component.obj.window.winfo_width()
                actual_height = component.obj.window.winfo_height()
                
                # 如果获取到了实际尺寸，更新组件的尺寸信息
                if actual_width > 1:
                    component.width = actual_width
                if actual_height > 1:
                    component.height = actual_height
                
                # 更新可见性
                component.visible = component.obj.window.state() != "withdrawn"
        
        # 获取所有可见的组件
        visible_components = [comp for comp in all_components if comp.visible]
        
        # 按优先级排序，优先级高的先处理
        visible_components.sort(key=lambda x: x.priority, reverse=True)
        
        # 再次确保所有组件的尺寸已正确更新
        for component in visible_components:
            if hasattr(component.obj, 'window') and component.obj.window and component.obj.window.winfo_exists():
                # 确保组件窗口已更新
                component.obj.window.update_idletasks()
                
                actual_width = component.obj.window.winfo_width()
                actual_height = component.obj.window.winfo_height()
                
                # 如果获取到了实际尺寸，更新组件的尺寸信息
                if actual_width > 1:
                    component.width = actual_width
                if actual_height > 1:
                    component.height = actual_height
        
        # 计算每个组件的位置
        for component in visible_components:
            self._calculate_component_position(component, visible_components)
            
    def _calculate_component_position(self, component: UIComponent, 
                                     all_visible: List[UIComponent]) -> None:
        """计算组件位置
        
        Args:
            component: 要计算位置的组件
            all_visible: 所有可见的组件列表
        """
        # 根据组件名称和首选位置计算初始位置
        if component.preferred_position == "auto":
            x, y = self._get_auto_position(component, all_visible)
        elif component.preferred_position == "top":
            x = self.pet_x + self.pet_width // 2 - component.width // 2
            y = self.pet_y - component.height - 5
        elif component.preferred_position == "bottom":
            x = self.pet_x + self.pet_width // 2 - component.width // 2
            y = self.pet_y + self.pet_height + 5
        elif component.preferred_position == "left":
            x = self.pet_x - component.width - 5
            y = self.pet_y + self.pet_height // 2 - component.height // 2
        elif component.preferred_position == "right":
            x = self.pet_x + self.pet_width + 5
            y = self.pet_y + self.pet_height // 2 - component.height // 2
        else:
            # 默认放在上方
            x = self.pet_x + self.pet_width // 2 - component.width // 2
            y = self.pet_y - component.height - 5
            
        # 确保不超出屏幕
        screen_w = self.app.root.winfo_screenwidth()
        screen_h = self.app.root.winfo_screenheight()
        x = max(10, min(x, screen_w - component.width - 10))
        y = max(10, min(y, screen_h - component.height - 10))
        
        # 检查是否与其他组件重叠，如果重叠则调整位置
        x, y = self._avoid_overlap(component, x, y, all_visible)
        
        # 更新组件的尺寸信息
        if hasattr(component.obj, 'window') and component.obj.window and component.obj.window.winfo_exists():
            actual_width = component.obj.window.winfo_width()
            actual_height = component.obj.window.winfo_height()
            
            # 如果获取到了实际尺寸，更新组件的尺寸信息
            if actual_width > 1:
                component.width = actual_width
            if actual_height > 1:
                component.height = actual_height
                
        # 设置组件位置
        component.set_position(x, y)
        
    def _get_auto_position(self, component: UIComponent, 
                          all_visible: List[UIComponent]) -> Tuple[int, int]:
        """获取自动计算的位置
        
        Args:
            component: 要计算位置的组件
            all_visible: 所有可见的组件列表
            
        Returns:
            (x, y) 坐标
        """
        # 根据组件类型自动选择最佳位置
        if component.name == "speech_bubble":
            # 语音气泡放在宠物上方，考虑气泡的实际高度
            x = self.pet_x + self.pet_width // 2 - component.width // 2
            # 确保气泡底部在宠物上方，留出一定间隙
            y = self.pet_y - component.height - 5
        elif component.name == "music_panel":
            # 音乐面板放在宠物下方，留出适当间隙
            x = self.pet_x + self.pet_width // 2 - component.width // 2
            y = self.pet_y + self.pet_height + 5
        elif component.name == "pomodoro_indicator":
            # 番茄钟根据其他组件情况决定位置
            speech_bubble = next((c for c in all_visible if c.name == "speech_bubble"), None)
            music_panel = next((c for c in all_visible if c.name == "music_panel"), None)
            
            # 默认位置：宠物上方
            x = self.pet_x + self.pet_width // 2 - component.width // 2
            y = self.pet_y - component.height - 5
            
            if music_panel:
                # 有音乐面板，番茄钟放在歌名气泡的上方
                x = self.pet_x + self.pet_width // 2 - component.width // 2
                if speech_bubble:
                    # 有语音气泡，番茄钟放在语音气泡上方
                    y = speech_bubble.y - component.height - 5
                else:
                    # 没有找到语音气泡，放在宠物上方
                    y = self.pet_y - component.height - 5
                # 确保不超出屏幕
                screen_h = self.app.root.winfo_screenheight()
                if y < 10:
                    y = 10
            elif speech_bubble:
                # 只有语音气泡，没有音乐面板，放在宠物下方
                x = self.pet_x + self.pet_width // 2 - component.width // 2
                y = self.pet_y + self.pet_height + 5
                # 确保不与语音气泡重叠
                if self._is_overlapping(x, y, component.width, component.height,
                                       speech_bubble.x, speech_bubble.y, speech_bubble.width, speech_bubble.height):
                    # 如果与语音气泡重叠，放在语音气泡下方
                    y = speech_bubble.y + speech_bubble.height + 5
        elif component.name == "ai_chat_panel":
            # AI聊天面板放在宠物右侧
            x = self.pet_x + self.pet_width + 10
            y = self.pet_y
        else:
            # 其他组件默认放在宠物上方
            x = self.pet_x + self.pet_width // 2 - component.width // 2
            y = self.pet_y - component.height - 5
            
        return (x, y)
        
    def _avoid_overlap(self, component: UIComponent, x: int, y: int, 
                      all_visible: List[UIComponent]) -> Tuple[int, int]:
        """避免与其他组件重叠
        
        Args:
            component: 要检查的组件
            x: 初始x坐标
            y: 初始y坐标
            all_visible: 所有可见的组件列表
            
        Returns:
            调整后的(x, y)坐标
        """
        # 检查是否与其他组件重叠
        for other in all_visible:
            if other.name == component.name:
                continue  # 跳过自己
                
            # 检查是否重叠
            if self._is_overlapping(x, y, component.width, component.height,
                                   other.x, other.y, other.width, other.height):
                # 尝试向四个方向移动，找到不重叠的位置
                directions = [
                    (x, y - other.height - 5),  # 上
                    (x, y + other.height + 5),  # 下
                    (x - other.width - 5, y),  # 左
                    (x + other.width + 5, y),  # 右
                ]
                
                for new_x, new_y in directions:
                    # 确保不超出屏幕
                    screen_w = self.app.root.winfo_screenwidth()
                    screen_h = self.app.root.winfo_screenheight()
                    new_x = max(10, min(new_x, screen_w - component.width - 10))
                    new_y = max(10, min(new_y, screen_h - component.height - 10))
                    
                    # 检查新位置是否与所有组件都不重叠
                    overlap = False
                    for check_other in all_visible:
                        if check_other.name == component.name:
                            continue
                        if self._is_overlapping(new_x, new_y, component.width, component.height,
                                              check_other.x, check_other.y, check_other.width, check_other.height):
                            overlap = True
                            break
                            
                    if not overlap:
                        return (new_x, new_y)
                        
        return (x, y)
        
    def _is_overlapping(self, x1: int, y1: int, w1: int, h1: int,
                       x2: int, y2: int, w2: int, h2: int) -> bool:
        """检查两个矩形是否重叠
        
        Args:
            x1, y1, w1, h1: 第一个矩形的x, y, 宽度, 高度
            x2, y2, w2, h2: 第二个矩形的x, y, 宽度, 高度
            
        Returns:
            是否重叠
        """
        return not (
            x1 + w1 <= x2 or
            x2 + w2 <= x1 or
            y1 + h1 <= y2 or
            y2 + h2 <= y1
        )
        
    def hide_all_components(self) -> None:
        """隐藏所有组件"""
        for component in self.components.values():
            if hasattr(component.obj, 'hide'):
                component.obj.hide()
            elif hasattr(component.obj, 'window') and component.obj.window and component.obj.window.winfo_exists():
                component.obj.window.withdraw()
            component.visible = False
            
    def show_component(self, name: str) -> None:
        """显示指定组件
        
        Args:
            name: 组件名称
        """
        if name in self.components:
            component = self.components[name]
            component.visible = True
            if hasattr(component.obj, 'show'):
                component.obj.show()
            elif hasattr(component.obj, 'window') and component.obj.window and component.obj.window.winfo_exists():
                component.obj.window.deiconify()
            self.update_layout()
            
    def get_component(self, name: str) -> Optional[UIComponent]:
        """获取组件
        
        Args:
            name: 组件名称
            
        Returns:
            组件对象，如果不存在则返回None
        """
        return self.components.get(name)