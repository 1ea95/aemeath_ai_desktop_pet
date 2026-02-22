"""系统托盘模块"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pystray
from PIL import Image

from src.constants import (
    BEHAVIOR_MODE_ACTIVE,
    BEHAVIOR_MODE_CLINGY,
    BEHAVIOR_MODE_QUIET,
    SCALE_OPTIONS,
    TRANSPARENCY_OPTIONS,
)
from src.utils import resource_path

if TYPE_CHECKING:
    from src.core.pet_core import DesktopPet


class TrayController:
    """系统托盘控制器"""

    def __init__(self, app: DesktopPet):
        self.app = app
        self.icon: pystray.Icon | None = None

    def _create_icon_image(self) -> Image.Image:
        """创建托盘图标"""
        try:
            icon_gif = Image.open(resource_path("assets/gifs/Aemeath.gif"))
            icon_gif.seek(0)
            icon_image = icon_gif.convert("RGBA")
            return icon_image.resize((64, 64), Image.Resampling.LANCZOS)
        except Exception as e:
            print(f"加载托盘图标失败，使用默认图标: {e}")
            return Image.new("RGB", (64, 64), color="pink")

    def _toggle_startup(self, icon: pystray.Icon):
        """切换开机自启"""
        self.app.auto_startup = not self.app.auto_startup
        self.app.set_auto_startup_flag(self.app.auto_startup)
        self.app.update_config(auto_startup=self.app.auto_startup)
        icon.menu = self.build_menu()

    def _toggle_visible(self, icon: pystray.Icon):
        """切换隐藏/显示"""
        if self.app.root.state() == "withdrawn":
            self.app.root.deiconify()
        else:
            self.app.root.withdraw()
        icon.menu = self.build_menu()

    def _toggle_click_through(self, icon: pystray.Icon):
        """切换鼠标穿透"""
        self.app.toggle_click_through()
        icon.menu = self.build_menu()

    def _set_behavior_mode(self, icon: pystray.Icon, mode: str):
        """设置行为模式"""
        self.app.set_behavior_mode(mode)
        icon.menu = self.build_menu()

    def _toggle_pomodoro(self, icon: pystray.Icon):
        """开始/停止番茄钟"""
        self.app.toggle_pomodoro()
        icon.menu = self.build_menu()

    def _reset_pomodoro(self, icon: pystray.Icon):
        """重置番茄钟"""
        self.app.reset_pomodoro()
        icon.menu = self.build_menu()

    def _quit(self, icon: pystray.Icon):
        """退出程序"""
        self.app.request_quit()

    def _on_set_scale(self, icon: pystray.Icon, index: int):
        """设置缩放"""
        self.app.set_scale(index)
        icon.menu = self.build_menu()

    def _on_set_transparency(self, icon: pystray.Icon, index: int):
        """设置透明度"""
        self.app.set_transparency(index)
        icon.menu = self.build_menu()

    def _create_scale_menu(self) -> pystray.Menu:
        """创建设置缩放子菜单"""
        items = []
        for i, scale in enumerate(SCALE_OPTIONS):

            def make_handler(idx):
                def handler(icon, item):
                    self._on_set_scale(icon, idx)

                return handler

            def make_checker(idx):
                def checker(item):
                    return self.app.scale_index == idx

                return checker

            items.append(
                pystray.MenuItem(
                    f"{scale}x",
                    make_handler(i),
                    checked=make_checker(i),
                    radio=True,
                )
            )
        return pystray.Menu(*items)

    def _create_transparency_menu(self) -> pystray.Menu:
        """创建透明度子菜单"""
        items = []
        for i, alpha in enumerate(TRANSPARENCY_OPTIONS):

            def make_handler(idx):
                def handler(icon, item):
                    self._on_set_transparency(icon, idx)

                return handler

            def make_checker(idx):
                def checker(item):
                    return self.app.transparency_index == idx

                return checker

            items.append(
                pystray.MenuItem(
                    f"{int(alpha * 100)}%",
                    make_handler(i),
                    checked=make_checker(i),
                    radio=True,
                )
            )
        return pystray.Menu(*items)

    def _create_behavior_mode_menu(self) -> pystray.Menu:
        """创建行为模式子菜单"""
        return pystray.Menu(
            pystray.MenuItem(
                "安静模式",
                lambda icon, item: self._set_behavior_mode(icon, BEHAVIOR_MODE_QUIET),
                checked=lambda item: self.app.behavior_mode == BEHAVIOR_MODE_QUIET,
                radio=True,
            ),
            pystray.MenuItem(
                "活泼模式",
                lambda icon, item: self._set_behavior_mode(icon, BEHAVIOR_MODE_ACTIVE),
                checked=lambda item: self.app.behavior_mode == BEHAVIOR_MODE_ACTIVE,
                radio=True,
            ),
            pystray.MenuItem(
                "粘人模式",
                lambda icon, item: self._set_behavior_mode(icon, BEHAVIOR_MODE_CLINGY),
                checked=lambda item: self.app.behavior_mode == BEHAVIOR_MODE_CLINGY,
                radio=True,
            ),
        )

    def _create_pomodoro_menu(self) -> pystray.Menu:
        """创建番茄钟子菜单"""
        return pystray.Menu(
            pystray.MenuItem(
                "开始" if not self.app._pomodoro_enabled else "停止",
                self._toggle_pomodoro,
            ),
            pystray.MenuItem(
                "重置",
                self._reset_pomodoro,
                enabled=lambda item: self.app._pomodoro_enabled,
            ),
        )

    def _create_ai_menu(self) -> pystray.Menu:
        """创建AI助手子菜单"""
        # 快捷提问
        quick_questions = [
            ("讲个笑话", "讲个笑话"),
            ("今天星期几", "今天星期几？"),
            ("给我建议", "给我点建议"),
            ("我累了", "我累了"),
        ]

        quick_items = []
        for label, question in quick_questions:

            def make_handler(q):
                def handler(icon, item):
                    self.app.quick_ai_chat(q)

                return handler

            quick_items.append(pystray.MenuItem(label, make_handler(question)))

        return pystray.Menu(
            pystray.MenuItem(
                "开始对话",
                lambda icon, item: self.app.open_ai_chat_dialog(),
            ),
            pystray.MenuItem(
                "快捷提问",
                pystray.Menu(*quick_items),
            ),
            pystray.MenuItem(
                "随机话题",
                lambda icon, item: self.app.quick_ai_chat(),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "清空对话历史",
                lambda icon, item: self.app.clear_ai_history(),
            ),
        )
    
    def _create_config_menu(self) -> pystray.Menu:
        """创建配置子菜单"""
        return pystray.Menu(
            pystray.MenuItem(
                "配置AI",
                lambda icon, item: self.app.show_ai_config_dialog(),
            ),
        )
    
    def _create_volume_menu(self) -> pystray.Menu:
        """创建音量控制子菜单"""
        from src.config import load_config
        
        config = load_config()
        music_volume = config.get("music_volume", 0.7)
        voice_volume = config.get("voice_volume", 0.8)
        
        return pystray.Menu(
            pystray.MenuItem(
                f"音乐音量: {int(music_volume * 100)}%",
                lambda icon, item: self._show_volume_config_dialog("music"),
            ),
            pystray.MenuItem(
                f"语音音量: {int(voice_volume * 100)}%",
                lambda icon, item: self._show_volume_config_dialog("voice"),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "音量设置",
                lambda icon, item: self._show_volume_config_dialog(),
            ),
        )
    
    def _show_volume_config_dialog(self, volume_type=None):
        """显示音量配置对话框"""
        import tkinter as tk
        from tkinter import ttk
        from src.config import load_config, update_config
        
        # 创建对话框窗口
        dialog = tk.Toplevel()
        dialog.title("音量设置")
        dialog.geometry("400x300")
        dialog.resizable(False, False)
        
        # 设置窗口居中
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        # 加载当前配置
        config = load_config()
        music_volume = tk.DoubleVar(value=config.get("music_volume", 0.7))
        voice_volume = tk.DoubleVar(value=config.get("voice_volume", 0.8))
        
        # 创建主框架
        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 音乐音量控制
        music_frame = ttk.LabelFrame(main_frame, text="音乐音量", padding="10")
        music_frame.pack(fill=tk.X, pady=(0, 15))
        
        music_label = ttk.Label(music_frame, text=f"当前音量: {int(music_volume.get() * 100)}%")
        music_label.pack(anchor=tk.W)
        
        music_scale = ttk.Scale(
            music_frame,
            from_=0.0,
            to=1.0,
            variable=music_volume,
            orient=tk.HORIZONTAL,
            command=lambda value: music_label.config(text=f"当前音量: {int(float(value) * 100)}%")
        )
        music_scale.pack(fill=tk.X, pady=(5, 0))
        
        # 语音音量控制
        voice_frame = ttk.LabelFrame(main_frame, text="语音音量", padding="10")
        voice_frame.pack(fill=tk.X, pady=(0, 15))
        
        voice_label = ttk.Label(voice_frame, text=f"当前音量: {int(voice_volume.get() * 100)}%")
        voice_label.pack(anchor=tk.W)
        
        voice_scale = ttk.Scale(
            voice_frame,
            from_=0.0,
            to=1.0,
            variable=voice_volume,
            orient=tk.HORIZONTAL,
            command=lambda value: voice_label.config(text=f"当前音量: {int(float(value) * 100)}%")
        )
        voice_scale.pack(fill=tk.X, pady=(5, 0))
        
        # 按钮框架
        print(f"🔧 调试: 创建按钮框架")
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(15, 0))
        print(f"🔧 调试: 按钮框架已创建并打包")
        
        # 保存按钮
        def save_volume_config():
            # 保存配置
            update_config(
                music_volume=music_volume.get(),
                voice_volume=voice_volume.get()
            )
            
            # 应用音乐音量
            if hasattr(self.app, 'music_controller') and self.app.music_controller:
                self.app.music_controller.set_volume(music_volume.get())
            
            # 应用语音音量
            if hasattr(self.app, 'voice_assistant') and self.app.voice_assistant:
                self.app.voice_assistant.set_voice_volume(voice_volume.get())
            
            # 更新托盘菜单
            if self.icon:
                self.icon.menu = self.build_menu()
            
            # 显示保存成功提示
            from tkinter import messagebox
            messagebox.showinfo("音量设置", "音量配置已保存并应用！")
            
            # 关闭对话框
            dialog.destroy()
        
        save_button = ttk.Button(button_frame, text="保存", command=save_volume_config)
        save_button.pack(side=tk.RIGHT)
        
        # 取消按钮
        print(f"🔧 调试: 创建取消按钮")
        cancel_button = ttk.Button(button_frame, text="取消", command=dialog.destroy)
        cancel_button.pack(side=tk.RIGHT, padx=(0, 10))
        print(f"🔧 调试: 取消按钮已创建并打包")
        
        # 如果指定了音量类型，则直接跳转到相应设置
        if volume_type == "music":
            music_scale.focus_set()
        elif volume_type == "voice":
            voice_scale.focus_set()
        
        # 设置窗口模态
        dialog.transient(dialog.master)
        dialog.grab_set()
        dialog.wait_window()

    def _create_voice_menu(self) -> pystray.Menu:
        """创建语音助手子菜单"""
        from src.config import load_config, update_config

        config = load_config()
        voice_enabled = config.get("voice_enabled", False)
        voice_wakeup_enabled = config.get("voice_wakeup_enabled", False)
        voice_asr_enabled = config.get("voice_asr_enabled", False)
        voice_tts_enabled = config.get("voice_tts_enabled", False)
        
        return pystray.Menu(
            pystray.MenuItem(
                "启用语音功能",
                self._toggle_voice,
                checked=lambda item: voice_enabled,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "语音唤醒",
                self._toggle_voice_wakeup,
                checked=lambda item: voice_wakeup_enabled,
                enabled=lambda item: voice_enabled,
            ),
            pystray.MenuItem(
                "语音识别",
                self._toggle_voice_asr,
                checked=lambda item: voice_asr_enabled,
                enabled=lambda item: voice_enabled,
            ),
            pystray.MenuItem(
                "语音合成",
                self._toggle_voice_tts,
                checked=lambda item: voice_tts_enabled,
                enabled=lambda item: voice_enabled,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "开始语音识别",
                lambda icon, item: self.app.start_voice_recognition(),
                enabled=lambda item: voice_enabled and voice_asr_enabled and self.app.is_voice_assistant_available(),
            ),
            pystray.MenuItem(
                "停止语音识别",
                lambda icon, item: self.app.stop_voice_recognition(),
                enabled=lambda item: voice_enabled and voice_asr_enabled and self.app.is_voice_assistant_running(),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "使用说明",
                self._show_voice_help,
            ),
        )
    
    def _toggle_voice(self, icon: pystray.Icon) -> None:
        """切换语音功能"""
        from src.config import load_config, update_config

        config = load_config()
        current = config.get("voice_enabled", False)
        update_config(voice_enabled=not current)
        
        # 如果启用了语音功能，尝试启动语音助手
        if not current and hasattr(self.app, 'voice_assistant'):
            self.app.voice_assistant.start()
        # 如果禁用了语音功能，停止语音助手
        elif current and hasattr(self.app, 'voice_assistant'):
            self.app.voice_assistant.stop()
            
        icon.menu = self.build_menu()
    
    def _toggle_voice_wakeup(self, icon: pystray.Icon) -> None:
        """切换语音唤醒功能"""
        from src.config import load_config, update_config

        config = load_config()
        current = config.get("voice_wakeup_enabled", False)
        update_config(voice_wakeup_enabled=not current)
        icon.menu = self.build_menu()
    
    def _toggle_voice_asr(self, icon: pystray.Icon) -> None:
        """切换语音识别功能"""
        from src.config import load_config, update_config

        config = load_config()
        current = config.get("voice_asr_enabled", False)
        update_config(voice_asr_enabled=not current)
        icon.menu = self.build_menu()
    
    def _toggle_voice_tts(self, icon: pystray.Icon) -> None:
        """切换语音合成功能"""
        from src.config import load_config, update_config

        config = load_config()
        current = config.get("voice_tts_enabled", False)
        update_config(voice_tts_enabled=not current)
        icon.menu = self.build_menu()
    
    def _show_voice_help(self) -> None:
        """显示语音助手使用说明"""
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo(
            "语音助手使用说明",
            "语音唤醒：\n"
            "1. 启用语音唤醒功能\n"
            "2. 说出唤醒词（如'爱弥斯'）\n"
            "3. 宠物会响应并开始语音识别\n\n"
            "语音识别：\n"
            "1. 启用语音识别功能\n"
            "2. 可以手动开始语音识别\n"
            "3. 说话后宠物会通过AI回复\n\n"
            "语音合成：\n"
            "1. 启用语音合成功能\n"
            "2. AI回复会以语音形式播放\n\n"
            "注意：需要先配置相关API密钥和模型文件",
        )
        root.destroy()
    
    def _show_volume_control_dialog(self) -> None:
        """显示统一的音量控制对话框"""
        import tkinter as tk
        from tkinter import ttk, messagebox
        from src.config import load_config, update_config
        
        # 创建对话框窗口
        dialog = tk.Toplevel()
        dialog.title("音量控制")
        dialog.geometry("350x330")  # 增加宽度和高度以容纳两个音量控制
        dialog.resizable(False, False)
        
        # 设置窗口居中
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        # 加载当前配置
        config = load_config()
        current_tts_volume = config.get("tts_volume", 50)
        current_music_volume = config.get("music_volume", 70)
        
        tts_volume_var = tk.IntVar(value=current_tts_volume)
        music_volume_var = tk.IntVar(value=current_music_volume)
        
        # 创建主框架
        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 标题
        title_label = ttk.Label(
            main_frame,
            text="音量控制",
            font=("Microsoft YaHei UI", 12, "bold")
        )
        title_label.pack(pady=(0, 15))
        
        # TTS音量控制框架
        tts_frame = ttk.LabelFrame(main_frame, text="TTS音量", padding="10")
        tts_frame.pack(fill=tk.X, pady=(0, 10))
        
        # TTS音量标签
        tts_label = ttk.Label(tts_frame, text="音量:")
        tts_label.pack(side=tk.LEFT, padx=(0, 10))
        
        # TTS音量滑块
        tts_slider = ttk.Scale(
            tts_frame,
            from_=0,
            to=100,
            orient=tk.HORIZONTAL,
            variable=tts_volume_var,
            length=150
        )
        tts_slider.pack(side=tk.LEFT, padx=(0, 10))
        
        # TTS音量值显示
        tts_value_label = ttk.Label(tts_frame, textvariable=tts_volume_var)
        tts_value_label.pack(side=tk.LEFT)
        
        # 音乐音量控制框架
        music_frame = ttk.LabelFrame(main_frame, text="音乐音量", padding="10")
        music_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 音乐音量标签
        music_label = ttk.Label(music_frame, text="音量:")
        music_label.pack(side=tk.LEFT, padx=(0, 10))
        
        # 音乐音量滑块
        music_slider = ttk.Scale(
            music_frame,
            from_=0,
            to=100,
            orient=tk.HORIZONTAL,
            variable=music_volume_var,
            length=150
        )
        music_slider.pack(side=tk.LEFT, padx=(0, 10))
        
        # 音乐音量值显示
        music_value_label = ttk.Label(music_frame, textvariable=music_volume_var)
        music_value_label.pack(side=tk.LEFT)
        
        # 按钮框架
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(15, 0))
        
        # 保存按钮
        def save_volumes():
            new_tts_volume = tts_volume_var.get()
            new_music_volume = music_volume_var.get()
            
            print(f"🔧 调试: 保存TTS音量为 {new_tts_volume}, 音乐音量为 {new_music_volume}")
            
            # 保存配置
            update_config(tts_volume=new_tts_volume, music_volume=new_music_volume)
            print(f"🔧 调试: 音量配置已保存到配置文件")
            
            # 应用到语音助手
            if hasattr(self.app, 'voice_assistant') and self.app.voice_assistant:
                print(f"🔧 调试: 应用TTS音量到语音助手")
                self.app.voice_assistant.set_tts_volume(new_tts_volume)
            
            # 应用到音乐控制器
            if hasattr(self.app, 'music') and self.app.music:
                print(f"🔧 调试: 应用音乐音量到音乐控制器")
                self.app.music.set_volume(new_music_volume)
            
            # 显示保存成功提示
            messagebox.showinfo("音量控制", f"TTS音量: {new_tts_volume}\n音乐音量: {new_music_volume}")
            
            # 关闭对话框
            dialog.destroy()
        
        save_button = ttk.Button(button_frame, text="保存", command=save_volumes)
        save_button.pack(side=tk.RIGHT)
        
        # 取消按钮
        cancel_button = ttk.Button(button_frame, text="取消", command=dialog.destroy)
        cancel_button.pack(side=tk.RIGHT, padx=(0, 10))
        
        # 显示对话框
        print(f"🔧 调试: 显示音量控制对话框")
        try:
            dialog.transient(self.app.root)
            dialog.grab_set()
            dialog.wait_window()
            print(f"🔧 调试: 音量控制对话框已关闭")
        except Exception as e:
            print(f"🔧 调试: 显示音量控制对话框时出错: {e}")
            dialog.wait_window()
    

    
    def _create_translate_menu(self) -> pystray.Menu:
        """创建翻译助手子菜单"""
        from src.config import load_config, update_config

        config = load_config()
        translate_enabled = config.get("translate_enabled", False)

        return pystray.Menu(
            pystray.MenuItem(
                "开启/关闭翻译",
                self._toggle_translate,
                checked=lambda item: translate_enabled,
            ),
            pystray.MenuItem(
                "手动翻译",
                lambda icon, item: self.app.translate_window.show(),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "使用说明",
                lambda icon, item: self._show_translate_help(),
            ),
        )

    def _toggle_translate(self, icon: pystray.Icon) -> None:
        """切换翻译功能"""
        from src.config import load_config, update_config

        config = load_config()
        current = config.get("translate_enabled", False)
        update_config(translate_enabled=not current)
        icon.menu = self.build_menu()

    def _show_translate_help(self) -> None:
        """显示翻译使用说明"""
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo(
            "翻译助手使用说明",
            "1. 选中需要翻译的文字\n"
            "2. 按住 Ctrl 键超过1秒\n"
            "3. 即可弹出翻译窗口\n\n"
            "注意：需要先在AI配置中启用AI功能",
        )
        root.destroy()

    def _create_quick_launch_menu(self) -> pystray.Menu:
        """创建快速启动子菜单"""
        from src.config import load_config, update_config

        config = load_config()
        quick_enabled = config.get("quick_launch_enabled", False)
        exe_path = config.get("quick_launch_exe_path", "")

        # 显示路径（截取文件名）
        if exe_path:
            display_path = os.path.basename(exe_path)
        else:
            display_path = "未设置"

        return pystray.Menu(
            pystray.MenuItem(
                "开启/关闭",
                self._toggle_quick_launch,
                checked=lambda item: quick_enabled,
            ),
            pystray.MenuItem(
                f"程序: {display_path}",
                self._set_quick_launch_path,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "使用说明",
                self._show_quick_launch_help,
            ),
        )

    def _toggle_quick_launch(self, icon: pystray.Icon) -> None:
        """切换快速启动功能"""
        from src.config import load_config, update_config

        config = load_config()
        current = config.get("quick_launch_enabled", False)
        update_config(quick_launch_enabled=not current)
        icon.menu = self.build_menu()

    def _set_quick_launch_path(self, icon: pystray.Icon, item) -> None:
        """设置快速启动的程序路径"""
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        file_path = filedialog.askopenfilename(
            title="选择要启动的程序",
            filetypes=[("可执行文件", "*.exe"), ("所有文件", "*.*")],
        )

        root.destroy()

        if file_path:
            from src.config import update_config

            update_config(quick_launch_exe_path=file_path)
            icon.menu = self.build_menu()

    def _show_quick_launch_help(self) -> None:
        """显示快速启动使用说明"""
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo(
            "快速启动使用说明",
            "快速启动程序：\n"
            "1. 先在托盘菜单中设置要启动的程序\n"
            "2. 关闭鼠标穿透功能\n"
            "3. 在宠物上快速点击5次（2秒内）\n"
            "4. 即可启动设定的程序\n\n"
            "提示：点击太快可能导致触发失败",
        )
        root.destroy()

    def build_menu(self) -> pystray.Menu:
        """构建托盘菜单"""
        return pystray.Menu(
            pystray.MenuItem(
                "隐藏" if self.app.root.state() == "normal" else "显示",
                self._toggle_visible,
            ),
            pystray.MenuItem(
                "鼠标穿透",
                self._toggle_click_through,
                checked=lambda item: self.app.click_through,
            ),
            pystray.MenuItem(
                "开机自启",
                self._toggle_startup,
                checked=lambda item: self.app.auto_startup,
            ),
            pystray.MenuItem("快速启动", self._create_quick_launch_menu()),
            pystray.MenuItem("AI助手", self._create_ai_menu()),
            pystray.MenuItem("语音助手", self._create_voice_menu()),
            pystray.MenuItem("翻译助手", self._create_translate_menu()),
            pystray.MenuItem("AI配置", lambda icon, item: self.app.show_ai_config_dialog()),
            pystray.MenuItem("音量控制", self._show_volume_control_dialog),
            pystray.MenuItem("行为模式", self._create_behavior_mode_menu()),
            pystray.MenuItem("番茄钟", self._create_pomodoro_menu()),
            pystray.MenuItem("缩放", self._create_scale_menu()),
            pystray.MenuItem("透明度", self._create_transparency_menu()),
            pystray.MenuItem("退出", self._quit),
        )

    def run(self) -> None:
        """启动托盘图标"""
        icon_image = self._create_icon_image()
        self.icon = pystray.Icon("desktop_pet", icon_image, "远航星", self.build_menu())
        self.icon.run_detached()

    def stop(self) -> None:
        """停止托盘图标"""
        if self.icon:
            self.icon.stop()