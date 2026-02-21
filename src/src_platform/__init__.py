"""平台集成包（Windows 系统托盘/快捷键/系统 API 等）"""

from src.src_platform.hotkey import GlobalHotkey, hotkey_manager
from src.src_platform.system import (
    enable_dpi_awareness,
    get_window_handle,
    set_click_through,
    set_window_topmost,
)
from src.src_platform.tray import TrayController

__all__ = [
    "GlobalHotkey",
    "TrayController",
    "enable_dpi_awareness",
    "get_window_handle",
    "hotkey_manager",
    "set_click_through",
    "set_window_topmost",
]
