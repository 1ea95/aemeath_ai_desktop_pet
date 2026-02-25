"""LLM配置对话框模块"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.pet_core import DesktopPet

from src.config import load_config, update_config
from src.constants import (
    AI_DEFAULT_BASE_URLS,
    AI_DEFAULT_MODELS,
    AI_MODELS,
    AI_PROVIDER_CUSTOM,
    AI_PROVIDER_DEEPSEEK,
    AI_PROVIDER_DOUBAO,
    AI_PROVIDER_GLM,
    AI_PROVIDER_KIMI,
    AI_PROVIDER_OPENAI,
    AI_PROVIDER_QWEN,
    AI_PROVIDERS,
    AI_PROVIDER_NAMES,
)


class AIConfigDialog:
    """LLM配置对话框"""

    def __init__(self, app: DesktopPet):
        self.app = app
        self.dialog: tk.Toplevel | None = None
        self.notebook: ttk.Notebook | None = None
        self.config_vars: dict = {}
        
        # 语音配置变量
        self.voice_enabled_var = tk.BooleanVar()
        self.voice_wakeup_enabled_var = tk.BooleanVar()
        self.voice_asr_enabled_var = tk.BooleanVar()
        self.voice_tts_enabled_var = tk.BooleanVar()
        self.voice_wakeup_threshold_var = tk.DoubleVar()
        self.voice_wakeup_score_var = tk.DoubleVar()
        
        # ASR配置变量
        self.asr_appkey_var = tk.StringVar()
        self.asr_token_var = tk.StringVar()
        self.asr_host_url_var = tk.StringVar()
        
        # 阿里云访问凭证变量
        self.aliyun_access_key_id_var = tk.StringVar()
        self.aliyun_access_key_secret_var = tk.StringVar()
        self.aliyun_region_var = tk.StringVar()
        self.auto_token_refresh_var = tk.BooleanVar()
        
        # 音量控制变量
        self.music_volume_var = tk.DoubleVar()
        self.voice_volume_var = tk.DoubleVar()
        
        # TTS配置变量
        self.tts_api_key_var = tk.StringVar()
        self.tts_model_var = tk.StringVar()
        self.tts_voice_var = tk.StringVar()
        self.tts_url_var = tk.StringVar()
        
        # 声音模型下拉框
        self.model_combo = None
        self.tts_model_combo = None
        
        # AI回复长度限制 - 在初始化时读取配置文件
        from src.config import load_config
        config = load_config()
        current_limit = config.get("ai_response_length_limit", 0)
        
        # 根据配置值设置默认选项
        if current_limit == 0:
            default_length = "无限制"
        elif current_limit == 20:
            default_length = "20字"
        elif current_limit == 50:
            default_length = "50字"
        elif current_limit == 100:
            default_length = "100字"
        elif current_limit == 200:
            default_length = "200字"
        else:
            # 自定义值
            default_length = "自定义"
            self.custom_length_var = tk.StringVar(value=str(current_limit))
        
        self.length_limit_var = tk.StringVar(value=default_length)
        
        # LLM配置变量
        self.enabled_var = tk.BooleanVar()
        self.provider_var = tk.StringVar()
        self.api_key_var = tk.StringVar()
        self.model_var = tk.StringVar()
        self.base_url_var = tk.StringVar()
        self.personality_var = tk.StringVar()
        self.custom_length_var = tk.StringVar()
        self.length_limit_var = tk.StringVar(value="无限制")

    def show(self) -> None:
        """显示配置对话框"""
        if self.dialog and self.dialog.winfo_exists():
            self.dialog.lift()
            return

        self._create_dialog()

    def _create_dialog(self) -> None:
        """创建对话框"""
        self.dialog = tk.Toplevel(self.app.root)
        self.dialog.title("LLM配置")
        self.dialog.geometry("520x1000")
        self.dialog.resizable(False, False)
        self.dialog.transient(self.app.root)
        self.dialog.grab_set()

        # 窗口置顶（短暂显示后取消，让其他窗口可以覆盖）
        self.dialog.attributes("-topmost", True)
        self.dialog.after(2000, lambda: self.dialog.attributes("-topmost", False))

        # 居中显示
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() - 520) // 2
        y = (self.dialog.winfo_screenheight() - 1000) // 2
        self.dialog.geometry(f"+{x}+{y}")

        # 设置主题样式
        self._setup_style()

        # 加载当前配置
        config = load_config()

        # 创建界面
        self._create_widgets(config)

    def _setup_style(self) -> None:
        """设置主题样式"""
        style = ttk.Style()
        style.theme_use("clam")

        # 配置主颜色
        primary_color = "#FF69B4"
        bg_color = "#FFF5F8"
        entry_bg = "#FFFFFF"

        style.configure(".", background=bg_color)
        style.configure("TFrame", background=bg_color)
        style.configure("TLabel", background=bg_color, foreground="#5C3B4A")
        style.configure("TCheckbutton", background=bg_color, foreground="#5C3B4A")

        # 配置按钮样式
        style.configure(
            "Primary.TButton",
            background=primary_color,
            foreground="white",
            borderwidth=0,
            focuscolor="none",
        )
        style.map(
            "Primary.TButton",
            background=[("active", "#FF85C1"), ("pressed", "#E85A9C")],
        )

        style.configure(
            "Secondary.TButton",
            background="#F0F0F0",
            foreground="#5C3B4A",
            borderwidth=1,
            focuscolor="none",
        )
        style.map(
            "Secondary.TButton",
            background=[("active", "#E0E0E0")],
        )

    def _create_widgets(self, config: dict) -> None:
        """创建界面组件"""
        # 主容器
        main_container = ttk.Frame(self.dialog, padding=0)
        main_container.pack(fill=tk.BOTH, expand=True)

        # 标题栏
        title_frame = tk.Frame(main_container, bg="#FF69B4", height=50)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)

        title_label = tk.Label(
            title_frame,
            text="🤖 LLM与语音配置",
            bg="#FF69B4",
            fg="white",
            font=("Microsoft YaHei", 14, "bold"),
        )
        title_label.pack(side=tk.LEFT, padx=20, pady=10)

        # 上方可滚动区域
        scroll_container = ttk.Frame(main_container)
        scroll_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=15)

        # Canvas和滚动条
        canvas = tk.Canvas(
            scroll_container,
            highlightthickness=0,
            bg="#FFF5F8",
            height=500,
        )
        scrollbar = ttk.Scrollbar(
            scroll_container, orient="vertical", command=canvas.yview
        )
        content_frame = ttk.Frame(canvas, padding="0")
        content_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=content_frame, anchor="nw", width=460)
        canvas.configure(yscrollcommand=scrollbar.set)

        # 绑定鼠标滚轮
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind("<MouseWheel>", _on_mousewheel)
        content_frame.bind("<MouseWheel>", _on_mousewheel)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 创建选项卡
        self.notebook = ttk.Notebook(content_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # LLM配置选项卡
        ai_frame = ttk.Frame(self.notebook)
        self.notebook.add(ai_frame, text="LLM配置")
        
        # ASR配置选项卡
        asr_frame = ttk.Frame(self.notebook)
        self.notebook.add(asr_frame, text="ASR配置")
        
        # TTS配置选项卡
        tts_frame = ttk.Frame(self.notebook)
        self.notebook.add(tts_frame, text="TTS配置")
        
        # 创建LLM配置内容
        self._create_ai_config_content(ai_frame, config)
        
        # 创建ASR配置内容
        self._create_asr_config_content(asr_frame, config)
        
        # 创建TTS配置内容
        self._create_tts_config_content(tts_frame, config)

        # 下方固定按钮区域
        button_frame = tk.Frame(main_container, bg="#FFF5F8", height=60)
        button_frame.pack(fill=tk.X, side=tk.BOTTOM)
        button_frame.pack_propagate(False)

        # 分隔线
        sep = ttk.Separator(main_container, orient=tk.HORIZONTAL)
        sep.pack(fill=tk.X, side=tk.BOTTOM)

        # 按钮
        btn_test = tk.Button(
            button_frame,
            text="🔗 测试连接",
            bg="#4ECDC4",
            fg="white",
            font=("Microsoft YaHei", 10),
            borderwidth=0,
            padx=20,
            pady=8,
            cursor="hand2",
            command=self._test_connection,
        )
        btn_test.pack(side=tk.LEFT, padx=(15, 10), pady=12)

        btn_save = tk.Button(
            button_frame,
            text="✓ 确定",
            bg="#FF69B4",
            fg="white",
            font=("Microsoft YaHei", 10, "bold"),
            borderwidth=0,
            padx=25,
            pady=8,
            cursor="hand2",
            command=self._save_config,
        )
        btn_save.pack(side=tk.RIGHT, padx=(0, 15), pady=12)

        btn_cancel = tk.Button(
            button_frame,
            text="✕ 取消",
            bg="#CCCCCC",
            fg="#5C3B4A",
            font=("Microsoft YaHei", 10),
            borderwidth=0,
            padx=20,
            pady=8,
            cursor="hand2",
            command=self.dialog.destroy,
        )
        btn_cancel.pack(side=tk.RIGHT, padx=(0, 10), pady=12)

        # 初始化服务商状态
        self._on_provider_change()
    
    def _show_custom_length_dialog(self):
        """显示自定义字数限制对话框"""
        # 创建对话框
        dialog = tk.Toplevel(self.dialog)
        dialog.title("自定义字数限制")
        dialog.geometry("400x250")
        dialog.resizable(False, False)
        dialog.transient(self.dialog)
        dialog.grab_set()
        dialog.configure(bg="#FFF5F8")
        
        # 标题
        title_frame = tk.Frame(dialog, bg="#FF69B4", height=45)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)
        
        tk.Label(
            title_frame,
            text="自定义字数限制",
            bg="#FF69B4",
            fg="white",
            font=("Microsoft YaHei", 12, "bold"),
        ).pack(side=tk.LEFT, padx=15, pady=10)
        
        # 内容区域
        content_frame = tk.Frame(dialog, bg="#FFF5F8")
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # 输入框
        tk.Label(
            content_frame,
            text="请输入字数限制（0表示无限制）：",
            bg="#FFF5F8",
            fg="#5C3B4A",
            font=("Microsoft YaHei", 10),
            anchor="w"
        ).pack(fill=tk.X, pady=(0, 5))
        
        self.custom_length_var = tk.StringVar()
        # 获取当前自定义值
        from src.config import load_config
        config = load_config()
        current_limit = config.get("ai_response_length_limit", 0)
        if current_limit > 200:  # 如果当前值大于200，显示当前值
            self.custom_length_var.set(str(current_limit))
        
        length_entry = ttk.Entry(
            content_frame,
            textvariable=self.custom_length_var,
            width=20
        )
        length_entry.pack(fill=tk.X, pady=(0, 10))
        
        # 按钮区域
        button_frame = tk.Frame(content_frame, bg="#FFF5F8")
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        def apply_custom_length():
            try:
                value = self.custom_length_var.get().strip()
                if value == "":
                    limit = 0
                else:
                    limit = int(value)
                    if limit < 0:
                        limit = 0
                
                # 更新下拉框显示
                self.length_limit_var.set(f"{limit}字")
                # 更新映射
                self.length_limit_mapping[f"{limit}字"] = limit
                dialog.destroy()
            except ValueError:
                from tkinter import messagebox
                messagebox.showerror(
                    "错误",
                    "请输入有效的数字",
                    parent=dialog
                )
        
        def cancel_dialog():
            dialog.destroy()
        
        # 按钮
        tk.Button(
            button_frame,
            text="确定",
            bg="#FF69B4",
            fg="white",
            font=("Microsoft YaHei", 10),
            borderwidth=0,
            padx=20,
            pady=5,
            cursor="hand2",
            command=apply_custom_length
        ).pack(side=tk.RIGHT, padx=(0, 5))
        
        tk.Button(
            button_frame,
            text="取消",
            bg="#CCCCCC",
            fg="#5C3B4A",
            font=("Microsoft YaHei", 10),
            borderwidth=0,
            padx=20,
            pady=5,
            cursor="hand2",
            command=cancel_dialog
        ).pack(side=tk.RIGHT)
        
        # 居中显示
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (400 // 2)
        y = (dialog.winfo_screenheight() // 2) - (250 // 2)
        dialog.geometry(f"+{x}+{y}")

    def _create_ai_config_content(self, parent, config: dict) -> None:
        """创建LLM配置选项卡内容"""
        # 启用LLM功能
        enabled_frame = ttk.Frame(parent)
        enabled_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.enabled_var.set(config.get("ai_enabled", False))
        enabled_check = ttk.Checkbutton(
            enabled_frame,
            text="启用LLM对话功能",
            variable=self.enabled_var
        )
        enabled_check.pack(anchor=tk.W)
        
        # 服务商选择
        provider_frame = ttk.Frame(parent)
        provider_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(provider_frame, text="服务商:").pack(anchor=tk.W)
        
        # 创建服务商单选按钮
        self.provider_var.set(config.get("ai_provider", "glm"))
        
        for provider in ["glm", "deepseek", "openai", "qwen", "kimi", "doubao"]:
            rb = ttk.Radiobutton(
                provider_frame,
                text=provider.upper(),
                value=provider,
                variable=self.provider_var,
                command=self._on_provider_change
            )
            rb.pack(anchor=tk.W, padx=(20, 0))
        
        # API密钥
        api_key_frame = ttk.Frame(parent)
        api_key_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(api_key_frame, text="API密钥:").pack(anchor=tk.W)
        self.api_key_var.set(config.get("ai_api_key", ""))
        api_key_entry = ttk.Entry(api_key_frame, textvariable=self.api_key_var, show="*")
        api_key_entry.pack(fill=tk.X, pady=(5, 0))
        
        # 模型选择
        model_frame = ttk.Frame(parent)
        model_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(model_frame, text="模型:").pack(anchor=tk.W)
        self.model_var.set(config.get("ai_model", "glm-4-flash"))
        
        # 创建模型下拉框
        self.model_combo = ttk.Combobox(
            model_frame,
            textvariable=self.model_var,
            values=AI_MODELS.get(AI_PROVIDER_GLM, []),
            state="readonly"
        )
        self.model_combo.pack(fill=tk.X, pady=(5, 0))
        
        # 基础URL
        base_url_frame = ttk.Frame(parent)
        base_url_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(base_url_frame, text="Base URL:").pack(anchor=tk.W)
        self.base_url_var.set(config.get("ai_base_url", "https://open.bigmodel.cn/api/paas/v4"))
        base_url_entry = ttk.Entry(base_url_frame, textvariable=self.base_url_var)
        base_url_entry.pack(fill=tk.X, pady=(5, 0))
        
        # 人设选择
        personality_frame = ttk.Frame(parent)
        personality_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(personality_frame, text="人设选择:").pack(anchor=tk.W)
        
        # 人设下拉框
        personality_combo_frame = ttk.Frame(personality_frame)
        personality_combo_frame.pack(fill=tk.X, pady=(5, 0))
        
        # 人设选项列表
        personality_options = [
            ("aemeath", "爱弥斯（标准版）"),
            ("aemeath_enhanced", "爱弥斯（加强版）")
        ]
        
        # 创建下拉框
        self.personality_var = tk.StringVar()
        self.personality_var.set(config.get("ai_personality", "aemeath"))
        
        self.personality_combo = ttk.Combobox(
            personality_combo_frame,
            textvariable=self.personality_var,
            values=[option[1] for option in personality_options],
            state="readonly",
            width=20
        )
        self.personality_combo.pack(fill=tk.X)
        
        # 设置当前选中项
        current_personality = self.personality_var.get()
        for value, display in personality_options:
            if value == current_personality:
                self.personality_combo.set(display)
                break
        
        # 人设说明
        personality_desc_frame = ttk.Frame(parent)
        personality_desc_frame.pack(fill=tk.X, padx=10, pady=5)
        
        personality_desc_label = ttk.Label(
            personality_desc_frame,
            text="标准版：可爱活泼的桌面宠物\n加强版：更丰富的情感表达和互动体验",
            justify=tk.LEFT,
            foreground="gray"
        )
        personality_desc_label.pack(anchor=tk.W)
        
        # 存储人设选项映射，用于保存配置时获取实际值
        self.personality_mapping = {display: value for value, display in personality_options}
        
        # AI回复长度限制
        length_limit_frame = ttk.Frame(parent)
        length_limit_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(length_limit_frame, text="AI回复长度限制:").pack(anchor=tk.W)
        
        length_control_frame = ttk.Frame(length_limit_frame)
        length_control_frame.pack(fill=tk.X, pady=(5, 0))
        
        # 长度限制选项
        length_options = [
            "无限制",
            "20字",
            "50字",
            "100字",
            "200字",
            "自定义"
        ]
        
        # 长度限制映射
        self.length_limit_mapping = {
            "无限制": 0,
            "20字": 20,
            "50字": 50,
            "100字": 100,
            "200字": 200
        }
        
        # 获取当前配置
        current_limit = config.get("ai_response_length_limit", 0)
        
        # 设置当前选中项
        current_display = "无限制"
        is_custom = False
        
        # 检查是否是预定义的值
        for display, value in self.length_limit_mapping.items():
            if value == current_limit:
                current_display = display
                break
        else:
            # 不是预定义值，检查是否是自定义值
            if current_limit > 0:
                current_display = "自定义"
                is_custom = True
                # 添加自定义值到映射
                self.length_limit_mapping[f"{current_limit}字"] = current_limit
                # 设置自定义长度变量
                self.custom_length_var = tk.StringVar(value=str(current_limit))
        
        # 创建下拉框
        self.length_limit_var = tk.StringVar()
        self.length_limit_var.set(current_display)
        
        self.length_limit_combo = ttk.Combobox(
            length_control_frame,
            textvariable=self.length_limit_var,
            values=length_options,
            state="readonly",
            width=15
        )
        self.length_limit_combo.pack(side=tk.LEFT)
        
        # 绑定选择事件
        def on_length_select(event=None):
            selected = self.length_limit_var.get()
            if selected == "自定义":
                self._show_custom_length_dialog()
        
        self.length_limit_combo.bind("<<ComboboxSelected>>", on_length_select)
        
        # 说明
        length_desc_label = ttk.Label(
            length_control_frame,
            text="（仅对加强版人设有效）",
            foreground="gray",
            font=("Microsoft YaHei", 8),
        )
        length_desc_label.pack(side=tk.LEFT, padx=(10, 0))
        
        # 初始化服务商配置
        self._on_provider_change()
    
    def _create_asr_config_content(self, parent, config: dict) -> None:
        """创建ASR配置选项卡内容"""
        # 语音功能总开关
        voice_enabled_frame = ttk.Frame(parent)
        voice_enabled_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.voice_enabled_var.set(config.get("voice_enabled", False))
        voice_enabled_check = ttk.Checkbutton(
            voice_enabled_frame,
            text="启用语音功能",
            variable=self.voice_enabled_var
        )
        voice_enabled_check.pack(anchor=tk.W)
        
        # 语音唤醒
        wakeup_frame = ttk.Frame(parent)
        wakeup_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.voice_wakeup_enabled_var.set(config.get("voice_wakeup_enabled", False))
        wakeup_check = ttk.Checkbutton(
            wakeup_frame,
            text="启用语音唤醒",
            variable=self.voice_wakeup_enabled_var
        )
        wakeup_check.pack(anchor=tk.W)
        
        # 语音识别
        asr_frame = ttk.Frame(parent)
        asr_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.voice_asr_enabled_var.set(config.get("voice_asr_enabled", False))
        asr_check = ttk.Checkbutton(
            asr_frame,
            text="启用语音识别",
            variable=self.voice_asr_enabled_var
        )
        asr_check.pack(anchor=tk.W)
        
        # ASR配置
        asr_config_frame = ttk.Frame(parent)
        asr_config_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(asr_config_frame, text="ASR AppKey:").pack(anchor=tk.W)
        self.asr_appkey_var.set(config.get("asr_appkey", ""))
        asr_appkey_entry = ttk.Entry(asr_config_frame, textvariable=self.asr_appkey_var)
        asr_appkey_entry.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Label(asr_config_frame, text="ASR Token:").pack(anchor=tk.W, pady=(10, 0))
        token_input_frame = ttk.Frame(asr_config_frame)
        token_input_frame.pack(fill=tk.X, pady=(5, 0))
        
        asr_token_entry = ttk.Entry(token_input_frame, textvariable=self.asr_token_var)
        asr_token_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # 自动获取Token按钮
        auto_token_btn = ttk.Button(
            token_input_frame,
            text="自动获取",
            command=self._auto_get_token,
            width=10
        )
        auto_token_btn.pack(side=tk.RIGHT, padx=(5, 0))
        
        # Token状态显示
        self.token_status_label = ttk.Label(asr_config_frame, text="", foreground="gray")
        self.token_status_label.pack(anchor=tk.W, pady=(2, 0))
        
        # 阿里云访问凭证配置
        aliyun_frame = ttk.LabelFrame(parent, text="阿里云访问凭证")
        aliyun_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # 自动刷新Token选项
        auto_refresh_frame = ttk.Frame(aliyun_frame)
        auto_refresh_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.auto_token_refresh_var.set(config.get("auto_token_refresh", True))
        auto_refresh_check = ttk.Checkbutton(
            auto_refresh_frame,
            text="自动刷新Token（推荐）",
            variable=self.auto_token_refresh_var
        )
        auto_refresh_check.pack(anchor=tk.W)
        
        # AccessKey ID
        access_key_frame = ttk.Frame(aliyun_frame)
        access_key_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(access_key_frame, text="AccessKey ID:").pack(anchor=tk.W)
        self.aliyun_access_key_id_var.set(config.get("aliyun_access_key_id", ""))
        access_key_entry = ttk.Entry(access_key_frame, textvariable=self.aliyun_access_key_id_var)
        access_key_entry.pack(fill=tk.X, pady=(5, 0))
        
        # AccessKey Secret
        secret_key_frame = ttk.Frame(aliyun_frame)
        secret_key_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(secret_key_frame, text="AccessKey Secret:").pack(anchor=tk.W)
        self.aliyun_access_key_secret_var.set(config.get("aliyun_access_key_secret", ""))
        secret_key_entry = ttk.Entry(secret_key_frame, textvariable=self.aliyun_access_key_secret_var, show="*")
        secret_key_entry.pack(fill=tk.X, pady=(5, 0))
        
        # 区域
        region_frame = ttk.Frame(aliyun_frame)
        region_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(region_frame, text="区域:").pack(anchor=tk.W)
        self.aliyun_region_var.set(config.get("aliyun_region", "cn-shanghai"))
        region_combo = ttk.Combobox(
            region_frame,
            textvariable=self.aliyun_region_var,
            values=["cn-shanghai", "cn-beijing", "cn-hangzhou", "cn-shenzhen"],
            state="readonly"
        )
        region_combo.pack(fill=tk.X, pady=(5, 0))
        
        # 凭证说明
        credential_desc = tk.Label(
            aliyun_frame,
            text="说明：请在阿里云控制台获取AccessKey ID和Secret，\n并确保已开通智能语音交互服务",
            justify=tk.LEFT,
            fg="gray"
        )
        credential_desc.pack(anchor=tk.W, padx=10, pady=(5, 0))
        

    
    def _on_provider_change(self, event=None) -> None:
        """服务商改变时更新默认模型和Base URL"""
        # 只在实际更改服务商时才更新模型，避免覆盖用户已保存的配置
        if event is None:  # 如果是初始化调用，不更新模型
            return
            
        provider = self.provider_var.get()
        print(f"\n🔄 服务商变更: {provider}")
        
        # 服务商配置映射
        provider_configs = {
            "glm": {
                "models": ["glm-4-flash", "glm-4-air", "glm-4", "glm-4.7", "glm-3-turbo"],
                "default_model": "glm-4-flash",
                "default_url": "https://open.bigmodel.cn/api/paas/v4"
            },
            "deepseek": {
                "models": ["deepseek-chat", "deepseek-coder"],
                "default_model": "deepseek-chat",
                "default_url": "https://api.deepseek.com/v1"
            },
            "openai": {
                "models": ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo"],
                "default_model": "gpt-3.5-turbo",
                "default_url": "https://api.openai.com/v1"
            },
            "qwen": {
                "models": ["qwen-turbo", "qwen-plus", "qwen-max"],
                "default_model": "qwen-turbo",
                "default_url": "https://dashscope.aliyuncs.com/compatible-mode/v1"
            },
            "kimi": {
                "models": ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
                "default_model": "moonshot-v1-8k",
                "default_url": "https://api.moonshot.ai/v1"
            },
            "doubao": {
                "models": ["doubao-lite-4k", "doubao-pro-4k", "doubao-pro-32k"],
                "default_model": "doubao-lite-4k",
                "default_url": "https://ark.cn-beijing.volces.com/api/v3"
            }
        }
        
        # 获取当前服务商的配置
        config = provider_configs.get(provider, provider_configs["glm"])
        
        # 更新模型列表
        if hasattr(self, 'model_combo'):
            self.model_combo["values"] = config["models"]
            self.model_var.set(config["default_model"])
            self.model_combo.set(config["default_model"])
            print(f"📝 默认模型: {config['default_model']}")
        
        # 更新Base URL
        current_url = self.base_url_var.get()
        if not current_url or current_url == "https://open.bigmodel.cn/api/paas/v4":  # 只有在默认URL时才自动更新
            self.base_url_var.set(config["default_url"])
            print(f"🔗 自动设置默认URL: {config['default_url']}")
        else:
            print(f"🔗 保留当前URL: {current_url}")
        
        print(f"✅ 服务商配置更新完成\n")

    def _on_model_change(self, event=None) -> None:
        """模型改变时的回调"""
        pass

    def _add_custom_model(self) -> None:
        """手动添加自定义模型"""
        # 创建输入对话框
        input_dialog = tk.Toplevel(self.dialog)
        input_dialog.title("添加自定义模型")
        input_dialog.geometry("350x150")
        input_dialog.resizable(False, False)
        input_dialog.transient(self.dialog)
        input_dialog.grab_set()
        input_dialog.configure(bg="#FFF5F8")

        # 标题
        title_frame = tk.Frame(input_dialog, bg="#FF69B4", height=30)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)

        tk.Label(
            title_frame,
            text="➕ 添加自定义模型",
            bg="#FF69B4",
            fg="white",
            font=("Microsoft YaHei", 11, "bold"),
        ).pack(side=tk.LEFT, padx=15, pady=5)

        # 内容
        content_frame = tk.Frame(input_dialog, bg="#FFF5F8")
        content_frame.pack(expand=True, fill=tk.BOTH, padx=20, pady=15)

        tk.Label(
            content_frame,
            text="请输入模型名称:",
            bg="#FFF5F8",
            fg="#5C3B4A",
            font=("Microsoft YaHei", 10),
            anchor="w",
        ).pack(fill=tk.X)

        model_entry = ttk.Entry(content_frame, font=("Microsoft YaHei", 10))
        model_entry.pack(fill=tk.X, pady=(5, 10))
        model_entry.focus()

        # 按钮
        btn_frame = tk.Frame(content_frame, bg="#FFF5F8")
        btn_frame.pack(fill=tk.X)

        def confirm():
            model_name = model_entry.get().strip()
            if not model_name:
                messagebox.showwarning("提示", "请输入模型名称", parent=input_dialog)
                return

            # 添加到当前模型列表
            current_values = list(self.model_combo["values"])
            if model_name not in current_values:
                current_values.append(model_name)
                self.model_combo["values"] = current_values

            # 选中新添加的模型
            self.config_vars["model"].set(model_name)
            self.model_combo.set(model_name)

            input_dialog.destroy()

        tk.Button(
            btn_frame,
            text="✓ 添加",
            bg="#FF69B4",
            fg="white",
            font=("Microsoft YaHei", 10),
            borderwidth=0,
            padx=20,
            pady=5,
            cursor="hand2",
            command=confirm,
        ).pack(side=tk.LEFT, padx=(0, 10))

        tk.Button(
            btn_frame,
            text="✕ 取消",
            bg="#CCCCCC",
            fg="#5C3B4A",
            font=("Microsoft YaHei", 10),
            borderwidth=0,
            padx=20,
            pady=5,
            cursor="hand2",
            command=input_dialog.destroy,
        ).pack(side=tk.LEFT)

        # 回车确认
        input_dialog.bind("<Return>", lambda e: confirm())

    def _save_config(self) -> None:
        """保存配置"""
        try:
            # 获取LLM配置
            ai_enabled = self.enabled_var.get()
            ai_provider = self.provider_var.get()
            ai_api_key = self.api_key_var.get().strip()
            ai_model = self.model_var.get().strip()
            ai_base_url = self.base_url_var.get().strip()
            
            # 清理base_url，移除可能的反引号
            if ai_base_url.startswith('`') and ai_base_url.endswith('`'):
                ai_base_url = ai_base_url[1:-1].strip()
                print(f"🔧 清理base_url: {ai_base_url}")
            
            print(f"\n🔧 准备保存LLM配置:")
            print(f"  ai_enabled: {ai_enabled}")
            print(f"  ai_provider: {ai_provider}")
            print(f"  ai_api_key: {'已配置' if ai_api_key else '未配置'}")
            print(f"  ai_model: {ai_model}")
            print(f"  ai_base_url: {ai_base_url}")
            
            # 构建配置更新字典
            config_updates = {
                # LLM配置
                "ai_enabled": ai_enabled,
                "ai_provider": ai_provider,
                "ai_api_key": ai_api_key,
                "ai_model": ai_model,
                "ai_base_url": ai_base_url,
                "ai_personality": self.personality_mapping.get(self.personality_var.get(), "aemeath"),
                "ai_response_length_limit": self._get_length_limit_value(),
                "ai_response_length_limit": self.length_limit_mapping.get(self.length_limit_var.get(), 0),
                
                # 语音配置
                "voice_enabled": self.voice_enabled_var.get(),
                "voice_wakeup_enabled": self.voice_wakeup_enabled_var.get(),
                "voice_asr_enabled": self.voice_asr_enabled_var.get(),
                "voice_tts_enabled": self.voice_tts_enabled_var.get(),
                
                # ASR配置
                "asr_appkey": self.asr_appkey_var.get().strip(),
                "asr_token": self.asr_token_var.get().strip(),
                
                # 阿里云访问凭证配置
                "aliyun_access_key_id": self.aliyun_access_key_id_var.get().strip(),
                "aliyun_access_key_secret": self.aliyun_access_key_secret_var.get().strip(),
                "aliyun_region": self.aliyun_region_var.get().strip(),
                "auto_token_refresh": self.auto_token_refresh_var.get(),
                
                # TTS配置
                "tts_api_key": self.tts_api_key_var.get().strip(),
                "tts_model": self.tts_model_var.get().strip(),
                "tts_voice": self.tts_voice_var.get().strip(),
                "tts_url": self.tts_url_var.get().strip(),
                
                # 音量配置
                "music_volume": self.music_volume_var.get(),
                "voice_volume": self.voice_volume_var.get(),
            }
            
            # 保存配置前打印调试信息
            print(f"\n🔧 准备保存配置:")
            for key, value in config_updates.items():
                if 'api_key' in key:
                    print(f"  {key}: {'已配置' if value else '未配置'}")
                else:
                    print(f"  {key}: {value}")
            
            # 保存配置
            update_config(**config_updates)
            print("\n✅ 配置保存成功")
            
            # 强制刷新配置缓存
            from src.config import load_config
            load_config(force_refresh=True)
            
            # 验证配置是否真的被保存
            from src.config import load_config
            saved_config = load_config()
            print(f"\n🔍 验证保存的配置:")
            print(f"  ai_provider: {saved_config.get('ai_provider', '未找到')}")
            print(f"  ai_enabled: {saved_config.get('ai_enabled', '未找到')}")
            print(f"  ai_api_key: {'已配置' if saved_config.get('ai_api_key', '') else '未配置'}")
            print(f"  ai_model: {saved_config.get('ai_model', '未找到')}")
            print(f"  ai_base_url: {saved_config.get('ai_base_url', '未找到')}")
            print(f"  ai_personality: {saved_config.get('ai_personality', '未找到')}")
            print(f"\n📁 配置文件位置: {saved_config}")

            # 重新加载AI引擎配置
            if hasattr(self.app, "ai_chat") and self.app.ai_chat:
                self.app.ai_chat.reload_config()
            
            # 重新加载语音助手配置
            if hasattr(self.app, "voice_assistant") and self.app.voice_assistant:
                self.app.voice_assistant._load_config()
                # 如果语音功能启用，重新启动语音助手
                if self.voice_enabled_var.get():
                    self.app.voice_assistant.stop()
                    self.app.voice_assistant.start()
                else:
                    self.app.voice_assistant.stop()

            messagebox.showinfo("成功", "配置已保存并应用！", parent=self.dialog)
            self.dialog.destroy()

        except Exception as e:
            import traceback
            error_msg = f"保存配置失败: {e}"
            print(f"❌ {error_msg}")
            print("详细错误信息:")
            traceback.print_exc()
            messagebox.showerror("错误", error_msg, parent=self.dialog)
    
    def _get_length_limit_value(self) -> int:
        """获取字数限制值"""
        selected = self.length_limit_var.get()
        
        # 如果是自定义选项，从输入框获取值
        if selected == "自定义":
            try:
                value = self.custom_length_var.get().strip()
                if value == "":
                    return 0
                else:
                    limit = int(value)
                    return max(0, limit)  # 确保不小于0
            except (ValueError, AttributeError):
                return 0
        
        # 否则从映射中获取
        return self.length_limit_mapping.get(selected, 0)

    def _test_connection(self) -> None:
        """测试API连接"""
        import threading

        api_key = self.api_key_var.get().strip()
        provider = self.provider_var.get()
        model = self.model_var.get().strip()
        base_url = self.base_url_var.get().strip()

        if not api_key:
            messagebox.showwarning("提示", "请先输入API密钥", parent=self.dialog)
            return

        if provider == AI_PROVIDER_CUSTOM and not base_url:
            messagebox.showwarning(
                "提示", "自定义API模式下请填写Base URL", parent=self.dialog
            )
            return

        # 设置默认base_url
        if not base_url:
            base_url = AI_DEFAULT_BASE_URLS.get(provider, "")

        def _test():
            try:
                import requests

                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                }

                # Kimi需要特殊处理
                if provider == AI_PROVIDER_KIMI:
                    headers["Authorization"] = f"Bearer {api_key}"
                # 千问需要特殊处理
                elif provider == AI_PROVIDER_QWEN:
                    headers["Authorization"] = f"Bearer {api_key}"

                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": "你好"}],
                    "max_tokens": 10,
                }

                response = requests.post(
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=15,
                )

                if response.status_code == 200:
                    self.dialog.after(
                        0,
                        lambda: messagebox.showinfo(
                            "成功",
                            "连接测试成功！AI功能可以正常使用~",
                            parent=self.dialog,
                        ),
                    )
                elif response.status_code == 401:
                    self.dialog.after(
                        0,
                        lambda: messagebox.showerror(
                            "错误",
                            "API密钥无效，请检查密钥是否正确",
                            parent=self.dialog,
                        ),
                    )
                else:
                    error_text = response.text[:200]
                    self.dialog.after(
                        0,
                        lambda: messagebox.showerror(
                            "错误",
                            f"连接失败 (状态码: {response.status_code}):\n{error_text}",
                            parent=self.dialog,
                        ),
                    )

            except Exception as e:
                self.dialog.after(
                    0,
                    lambda: messagebox.showerror(
                        "错误", f"测试连接时出错: {str(e)}", parent=self.dialog
                    ),
                )

        # 显示测试中的提示
        test_window = tk.Toplevel(self.dialog)
        test_window.title("测试连接")
        test_window.geometry("280x120")
        test_window.transient(self.dialog)
        test_window.grab_set()
        test_window.resizable(False, False)
        test_window.configure(bg="#FFF5F8")

        # 标题栏风格
        title_frame = tk.Frame(test_window, bg="#FF69B4", height=30)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)

        tk.Label(
            title_frame,
            text="🔗 测试连接",
            bg="#FF69B4",
            fg="white",
            font=("Microsoft YaHei", 11, "bold"),
        ).pack(side=tk.LEFT, padx=15, pady=5)

        # 内容
        content_frame = tk.Frame(test_window, bg="#FFF5F8")
        content_frame.pack(expand=True, fill=tk.BOTH, padx=20, pady=15)

        # 加载动画标签
        loading_label = tk.Label(
            content_frame,
            text="⏳ 正在连接AI服务...",
            bg="#FFF5F8",
            fg="#5C3B4A",
            font=("Microsoft YaHei", 10),
        )
        loading_label.pack()

        # 取消按钮
        btn_cancel = tk.Button(
            content_frame,
            text="✕ 取消",
            bg="#CCCCCC",
            fg="#5C3B4A",
            font=("Microsoft YaHei", 9),
            borderwidth=0,
            padx=15,
            pady=4,
            cursor="hand2",
            command=test_window.destroy,
        )
        btn_cancel.pack(pady=(10, 0))

        def run_test_and_close():
            _test()
            test_window.destroy()

        threading.Thread(target=run_test_and_close, daemon=True).start()
    
    def _auto_get_token(self) -> None:
        """自动获取ASR Token"""
        access_key_id = self.aliyun_access_key_id_var.get().strip()
        access_key_secret = self.aliyun_access_key_secret_var.get().strip()
        region = self.aliyun_region_var.get().strip()
        
        if not access_key_id or not access_key_secret:
            messagebox.showerror("错误", "请先填写阿里云访问凭证")
            return
        
        # 显示获取中状态
        self.token_status_label.config(text="正在获取Token...", foreground="blue")
        self.dialog.update()
        
        try:
            # 导入token管理器
            from src.voice.token_manager import get_asr_token, setup_aliyun_credentials
            
            # 设置阿里云凭证
            setup_aliyun_credentials(access_key_id, access_key_secret, region)
            
            # 获取token
            token = get_asr_token(force_refresh=True)
            
            if token:
                # 更新token输入框
                self.asr_token_var.set(token)
                
                # 显示成功状态
                self.token_status_label.config(text="✅ Token获取成功", foreground="green")
                messagebox.showinfo("成功", "ASR Token获取成功！")
            else:
                # 显示失败状态
                self.token_status_label.config(text="❌ Token获取失败", foreground="red")
                messagebox.showerror("错误", "无法获取ASR Token，请检查访问凭证是否正确")
        except ImportError:
            self.token_status_label.config(text="❌ 缺少依赖库", foreground="red")
            messagebox.showerror("错误", "请安装阿里云SDK: pip install aliyun-python-sdk-core==2.15.1")
        except Exception as e:
            self.token_status_label.config(text=f"❌ 获取失败: {str(e)}", foreground="red")
            messagebox.showerror("错误", f"获取Token时发生错误: {str(e)}")
    
    def _check_token_status(self) -> None:
        """检查当前Token状态"""
        current_token = self.asr_token_var.get().strip()
        
        if not current_token:
            self.token_status_label.config(text="未配置Token", foreground="gray")
            return
        
        try:
            from src.voice.token_manager import get_token_manager
            token_manager = get_token_manager()
            token_info = token_manager.get_token_info()
            
            if token_info['is_valid']:
                if token_info['expire_time']:
                    self.token_status_label.config(
                        text=f"✅ Token有效 (过期时间: {token_info['expire_time'][:10]})", 
                        foreground="green"
                    )
                else:
                    self.token_status_label.config(text="✅ Token有效", foreground="green")
            else:
                self.token_status_label.config(text="⚠️ Token已过期或无效", foreground="orange")
        except Exception:
            self.token_status_label.config(text="❌ 无法检查Token状态", foreground="red")
    
    def _create_tts_config_content(self, parent, config: dict) -> None:
        """创建TTS配置选项卡内容"""
        # 语音合成
        tts_frame = ttk.Frame(parent)
        tts_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.voice_tts_enabled_var.set(config.get("voice_tts_enabled", False))
        tts_check = ttk.Checkbutton(
            tts_frame,
            text="启用语音合成",
            variable=self.voice_tts_enabled_var
        )
        tts_check.pack(anchor=tk.W)
        
        # TTS配置
        tts_config_frame = ttk.Frame(parent)
        tts_config_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(tts_config_frame, text="TTS API密钥:").pack(anchor=tk.W)
        self.tts_api_key_var.set(config.get("tts_api_key", ""))
        tts_api_key_entry = ttk.Entry(tts_config_frame, textvariable=self.tts_api_key_var)
        tts_api_key_entry.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Label(tts_config_frame, text="TTS URL:").pack(anchor=tk.W, pady=(10, 0))
        self.tts_url_var.set(config.get("tts_url", "wss://nls-gateway-cn-shanghai.aliyuncs.com/ws/v1"))
        tts_url_entry = ttk.Entry(tts_config_frame, textvariable=self.tts_url_var)
        tts_url_entry.pack(fill=tk.X, pady=(5, 0))
        
        # 声音模型
        voice_model_frame = ttk.Frame(tts_config_frame)
        voice_model_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Label(voice_model_frame, text="声音模型:").pack(anchor=tk.W)
        
        # 创建声音模型下拉框
        self.tts_model_var.set(config.get("tts_model", "cosyvoice-v3-flash"))
        
        model_frame = ttk.Frame(voice_model_frame)
        model_frame.pack(fill=tk.X, pady=(5, 0))
        
        # 声音模型选项
        model_options = [
            "cosyvoice-v2",
            "cosyvoice-v3-flash",
            "cosyvoice-v3-plus"
        ]
        
        self.tts_model_combo = ttk.Combobox(
            model_frame,
            textvariable=self.tts_model_var,
            values=model_options,
            state="readonly"
        )
        self.tts_model_combo.pack(fill=tk.X, pady=(5, 0))
        
        # 音色ID
        voice_id_frame = ttk.Frame(tts_config_frame)
        voice_id_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Label(voice_id_frame, text="音色ID:").pack(anchor=tk.W)
        self.tts_voice_var.set(config.get("tts_voice", "cosyvoice-v3-flash-anbao1-69f1b1345bb9496b9eab08e6d5462bb2"))
        voice_id_entry = ttk.Entry(voice_id_frame, textvariable=self.tts_voice_var)
        voice_id_entry.pack(fill=tk.X, pady=(5, 0))
        
        # 音色ID说明
        voice_id_desc = tk.Label(
            voice_id_frame,
            text="音色ID格式示例: cosyvoice-v3-plus-myvoice-xxxxxxxx",
            bg="#FFF5F8",
            fg="#888888",
            font=("Microsoft YaHei", 8),
            anchor="w",
        )
        voice_id_desc.pack(anchor=tk.W, pady=(5, 0))