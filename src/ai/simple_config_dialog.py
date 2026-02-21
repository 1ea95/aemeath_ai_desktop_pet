"""简单的LLM配置对话框模块"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Any

from src.config import load_config, update_config
from src.constants import (
    AI_DEFAULT_BASE_URLS,
    AI_DEFAULT_MODELS,
)


class SimpleConfigDialog:
    """简单的LLM配置对话框"""

    def __init__(self, app):
        self.app = app
        self.dialog = None
        self.config_vars = {}

    def show(self) -> None:
        """显示配置对话框"""
        self._create_dialog()
        self._create_widgets()
        self.dialog.wait_window()

    def _create_dialog(self) -> None:
        """创建对话框"""
        self.dialog = tk.Toplevel(self.app.root)
        self.dialog.title("LLM配置")
        self.dialog.geometry("500x600")
        self.dialog.resizable(False, False)
        self.dialog.transient(self.app.root)
        self.dialog.grab_set()

        # 居中显示
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() - 500) // 2
        y = (self.dialog.winfo_screenheight() - 600) // 2
        self.dialog.geometry(f"+{x}+{y}")

    def _create_widgets(self) -> None:
        """创建界面组件"""
        # 加载当前配置
        config = load_config()
        
        # 主容器
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 标题
        title_label = ttk.Label(
            main_frame,
            text="LLM配置",
            font=("Microsoft YaHei", 14, "bold")
        )
        title_label.pack(pady=(0, 20))
        
        # 启用LLM
        self.config_vars["ai_enabled"] = tk.BooleanVar(
            value=config.get("ai_enabled", False)
        )
        enabled_check = ttk.Checkbutton(
            main_frame,
            text="启用LLM对话功能",
            variable=self.config_vars["ai_enabled"]
        )
        enabled_check.pack(anchor=tk.W, pady=(0, 15))
        
        # 服务商选择
        provider_frame = ttk.LabelFrame(main_frame, text="服务商", padding=10)
        provider_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.config_vars["ai_provider"] = tk.StringVar(
            value=config.get("ai_provider", "glm")
        )
        
        providers = [
            ("GLM", "glm"),
            ("DeepSeek", "deepseek"),
            ("OpenAI", "openai"),
            ("千问", "qwen"),
            ("Kimi", "kimi"),
            ("豆包", "doubao")
        ]
        
        for display_name, value in providers:
            rb = ttk.Radiobutton(
                provider_frame,
                text=display_name,
                value=value,
                variable=self.config_vars["ai_provider"],
                command=self._on_provider_change
            )
            rb.pack(anchor=tk.W)
        
        # API配置
        api_frame = ttk.LabelFrame(main_frame, text="API配置", padding=10)
        api_frame.pack(fill=tk.X, pady=(0, 15))
        
        # API密钥
        ttk.Label(api_frame, text="API密钥:").pack(anchor=tk.W)
        self.config_vars["ai_api_key"] = tk.StringVar(
            value=config.get("ai_api_key", "")
        )
        api_key_entry = ttk.Entry(
            api_frame,
            textvariable=self.config_vars["ai_api_key"],
            show="*"
        )
        api_key_entry.pack(fill=tk.X, pady=(5, 10))
        
        # 模型选择
        ttk.Label(api_frame, text="模型:").pack(anchor=tk.W)
        self.config_vars["ai_model"] = tk.StringVar(
            value=config.get("ai_model", "glm-4-flash")
        )
        self.model_combo = ttk.Combobox(
            api_frame,
            textvariable=self.config_vars["ai_model"],
            values=["glm-4-flash", "glm-4-air", "glm-4"],
            state="readonly"
        )
        self.model_combo.pack(fill=tk.X, pady=(5, 10))
        
        # Base URL
        ttk.Label(api_frame, text="Base URL:").pack(anchor=tk.W)
        self.config_vars["ai_base_url"] = tk.StringVar(
            value=config.get("ai_base_url", "https://open.bigmodel.cn/api/paas/v4")
        )
        base_url_entry = ttk.Entry(
            api_frame,
            textvariable=self.config_vars["ai_base_url"]
        )
        base_url_entry.pack(fill=tk.X, pady=(5, 0))
        
        # 按钮区域
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))
        
        save_btn = ttk.Button(
            button_frame,
            text="保存",
            command=self._save_config
        )
        save_btn.pack(side=tk.RIGHT, padx=(10, 0))
        
        cancel_btn = ttk.Button(
            button_frame,
            text="取消",
            command=self._cancel
        )
        cancel_btn.pack(side=tk.RIGHT)
        
        # 初始化服务商配置
        self._on_provider_change()
    
    def _on_provider_change(self) -> None:
        """服务商改变时更新默认模型和Base URL"""
        provider = self.config_vars["ai_provider"].get()
        
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
            self.config_vars["ai_model"].set(config["default_model"])
            self.model_combo.set(config["default_model"])
        
        # 更新Base URL
        current_url = self.config_vars["ai_base_url"].get()
        if not current_url or current_url == "https://open.bigmodel.cn/api/paas/v4":
            self.config_vars["ai_base_url"].set(config["default_url"])
    
    def _save_config(self) -> None:
        """保存配置"""
        try:
            # 获取配置
            ai_enabled = self.config_vars["ai_enabled"].get()
            ai_provider = self.config_vars["ai_provider"].get()
            ai_api_key = self.config_vars["ai_api_key"].get().strip()
            ai_model = self.config_vars["ai_model"].get().strip()
            ai_base_url = self.config_vars["ai_base_url"].get().strip()
            
            print(f"\n🔧 准备保存LLM配置:")
            print(f"  ai_enabled: {ai_enabled}")
            print(f"  ai_provider: {ai_provider}")
            print(f"  ai_api_key: {'已配置' if ai_api_key else '未配置'}")
            print(f"  ai_model: {ai_model}")
            print(f"  ai_base_url: {ai_base_url}")
            
            # 保存配置
            update_config(
                ai_enabled=ai_enabled,
                ai_provider=ai_provider,
                ai_api_key=ai_api_key,
                ai_model=ai_model,
                ai_base_url=ai_base_url,
                ai_personality="aemeath"
            )
            
            print("\n✅ LLM配置保存成功")
            
            # 重新加载AI引擎配置
            if hasattr(self.app, "ai_chat") and self.app.ai_chat:
                self.app.ai_chat.reload_config()
                print("✅ AI引擎配置已重新加载")
            
            messagebox.showinfo("成功", "配置已保存")
            
            # 关闭对话框
            if self.dialog:
                self.dialog.destroy()
                self.dialog = None
                
        except Exception as e:
            import traceback
            error_msg = f"保存配置失败: {e}"
            print(f"\n❌ {error_msg}")
            print("详细错误信息:")
            traceback.print_exc()
            messagebox.showerror("错误", error_msg)
    
    def _cancel(self) -> None:
        """取消配置"""
        if self.dialog:
            self.dialog.destroy()
            self.dialog = None