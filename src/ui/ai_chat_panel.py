"""AI聊天输入框模块 - 固定在桌宠下方的简单输入框"""

from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.pet_core import DesktopPet


class AIChatPanel:
    """AI聊天输入框类 - 浮动在桌宠下方"""

    def __init__(self, app: DesktopPet):
        self.app = app
        self.window: tk.Toplevel | None = None
        self._input_entry: tk.Entry | None = None
        self._position_after_id: str | None = None
        self._last_pet_pos: tuple[int, int] = (0, 0)

    def show(self) -> None:
        """显示输入框"""
        if self.window and self.window.winfo_exists():
            self.window.deiconify()
            self.window.lift()
            self._start_follow()
            if self._input_entry:
                self._input_entry.focus_set()
            # 通知UI管理器更新布局
            if hasattr(self.app, 'ui_manager'):
                self.app.ui_manager.update_pet_info(self.app.x, self.app.y, self.app.w, self.app.h)
                self.app.ui_manager.set_component_visibility('ai_chat_panel', True)
            return

        self._create_window()
        self._start_follow()
        # 通知UI管理器更新布局
        if hasattr(self.app, 'ui_manager'):
            self.app.ui_manager.update_pet_info(self.app.x, self.app.y, self.app.w, self.app.h)
            self.app.ui_manager.set_component_visibility('ai_chat_panel', True)
            # 立即更新布局
            self.app.ui_manager.update_layout()

    def hide(self) -> None:
        """隐藏输入框"""
        self._stop_follow()
        if self.window and self.window.winfo_exists():
            self.window.withdraw()
        
        # 通知UI管理器更新布局
        if hasattr(self.app, 'ui_manager'):
            self.app.ui_manager.set_component_visibility('ai_chat_panel', False)

    def close(self) -> None:
        """关闭并销毁输入框"""
        self._stop_follow()
        if self.window and self.window.winfo_exists():
            self.window.destroy()
        self.window = None
        self._input_entry = None

    def is_visible(self) -> bool:
        """检查输入框是否可见"""
        return (
            self.window is not None
            and self.window.winfo_exists()
            and self.window.winfo_viewable()
        )

    def _create_window(self) -> None:
        """创建输入框窗口"""
        self.window = tk.Toplevel(self.app.root)
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)

        # 设置窗口背景（粉色系，与气泡一致）
        bg_color = "#FFD1E8"
        border_color = "#FFB6DB"

        self.window.config(bg=bg_color)

        # 创建圆角效果的主框架
        main_frame = tk.Frame(self.window, bg=bg_color, padx=8, pady=6)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 输入框框架（带圆角效果）
        input_frame = tk.Frame(
            main_frame,
            bg="white",
            highlightbackground=border_color,
            highlightthickness=2,
            bd=0,
        )
        input_frame.pack(fill=tk.X, expand=True)

        # 输入框
        self._input_entry = tk.Entry(
            input_frame,
            font=("Microsoft YaHei", 10),
            bg="white",
            fg="#5C3B4A",
            relief=tk.FLAT,
            borderwidth=4,
            width=25,
        )
        self._input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._input_entry.focus_set()

        # 绑定回车发送
        self._input_entry.bind("<Return>", lambda e: self._send_message())

        # 发送按钮
        send_btn = tk.Label(
            input_frame,
            text="➤",
            bg="white",
            fg="#FF69B4",
            font=("Microsoft YaHei", 12, "bold"),
            cursor="hand2",
            padx=8,
        )
        send_btn.pack(side=tk.RIGHT)
        send_btn.bind("<Button-1>", lambda e: self._send_message())

        # 关闭按钮（小x）
        close_btn = tk.Label(
            main_frame,
            text="✕",
            bg=bg_color,
            fg="#5C3B4A",
            font=("Microsoft YaHei", 9),
            cursor="hand2",
            padx=2,
        )
        close_btn.place(relx=1.0, x=-5, y=2, anchor="ne")
        close_btn.bind("<Button-1>", lambda e: self.app.toggle_ai_chat_panel())

        # 设置窗口大小（紧凑）
        self.window.geometry("260x45")
        
        # 设置初始位置为桌宠右侧
        initial_x = getattr(self.app, "x", 200) + getattr(self.app, "w", 100) + 10
        initial_y = getattr(self.app, "y", 200)
        self.window.geometry(f"260x45+{initial_x}+{initial_y}")
        
        # 设置初始位置为桌宠右侧
        initial_x = getattr(self.app, "x", 200) + getattr(self.app, "w", 100) + 10
        initial_y = getattr(self.app, "y", 200)
        self.window.geometry(f"260x45+{initial_x}+{initial_y}")

    def _send_message(self) -> None:
        """发送消息"""
        if not self._input_entry or not self.app.ai_chat:
            return

        # 检查AI是否已配置
        if not self.app.ai_chat.is_configured():
            self.app.speech_bubble.show("AI功能未配置，请先设置API密钥哦~", duration=4000)
            self.app.show_ai_config_dialog()
            return

        message = self._input_entry.get().strip()
        if not message:
            return

        # 清空输入框
        self._input_entry.delete(0, tk.END)

        # 在气泡中显示用户消息
        self.app.speech_bubble.show(
            f"你: {message}", duration=2000, allow_during_music=True
        )

        # 显示思考中
        self.app.speech_bubble.show_thinking()

        # 发送给AI
        stream_response = ""  # 用于累积流式回复
        
        def on_stream_token(token: str):
            """收到流式token"""
            nonlocal stream_response
            stream_response += token
            # 实时更新气泡显示
            self.app.speech_bubble.show(f"AI: {stream_response}", duration=None)
        
        def on_response(response: str):
            # 在气泡中显示完整AI回复
            self.app.speech_bubble.show(f"AI: {response}", duration=5000)
        
        def on_error(error_msg: str):
            # 在气泡中显示错误
            self.app.speech_bubble.show(f"AI: {error_msg}", duration=4000)
        
        # 检查是否支持流式回复
        import inspect
        sig = inspect.signature(self.app.ai_chat.send_message)
        if 'on_stream_token' in sig.parameters:
            # 支持流式回复
            self.app.ai_chat.send_message(message, on_response, on_error, on_stream_token)
        else:
            # 不支持流式回复，使用普通模式
            self.app.ai_chat.send_message(message, on_response, on_error)

    def _update_position(self) -> None:
        """更新输入框位置到桌宠下方"""
        # 现在使用UI管理器来处理位置，这里不需要做任何事情
        # UI管理器会自动计算和设置位置
        pass

    def _start_follow(self) -> None:
        """开始跟随桌宠移动"""
        if self._position_after_id:
            return  # 已经在跟随了
        # 通知UI管理器更新布局
        if hasattr(self.app, 'ui_manager'):
            self.app.ui_manager.update_layout()
        self._follow_loop()

    def _follow_loop(self) -> None:
        """跟随循环"""
        if not self.is_visible():
            return

        # 检查桌宠位置是否变化
        current_pos = (getattr(self.app, "x", 200), getattr(self.app, "y", 200))
        if current_pos != self._last_pet_pos:
            # 通知UI管理器更新布局
            if hasattr(self.app, 'ui_manager'):
                self.app.ui_manager.update_pet_info(self.app.x, self.app.y, self.app.w, self.app.h)
                self.app.ui_manager.update_layout()
            self._last_pet_pos = current_pos

        # 继续循环
        self._position_after_id = self.app.root.after(16, self._follow_loop)  # ~60fps

    def _stop_follow(self) -> None:
        """停止跟随"""
        if self._position_after_id:
            try:
                self.app.root.after_cancel(self._position_after_id)
            except tk.TclError:
                pass
            self._position_after_id = None