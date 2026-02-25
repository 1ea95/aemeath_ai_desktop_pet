"""系统命令处理模块

处理语音识别结果中的系统操作命令
"""

import os
import subprocess
import webbrowser
import threading
from typing import Dict, Tuple, Callable, Optional, TYPE_CHECKING

from src.config import load_config

if TYPE_CHECKING:
    from src.core.pet_core import DesktopPet


class SystemCommandProcessor:
    """
    系统命令处理器
    
    负责识别和执行语音命令中的系统操作
    """
    
    def __init__(self, app: "DesktopPet") -> None:
        """
        初始化系统命令处理器
        
        Args:
            app: 桌面宠物应用实例
        """
        self.app = app
        self._pending_dangerous_command: Optional[str] = None
        
        # 系统命令映射，包含是否为危险操作
        self.system_commands: Dict[str, Tuple[Callable, bool]] = {
            # 系统控制
            "关机": (lambda: self._execute_system_command("shutdown /s /t 5"), True),
            "重启": (lambda: self._execute_system_command("shutdown /r /t 5"), True),
            "注销": (lambda: self._execute_system_command("shutdown /l"), True),
            "锁屏": (lambda: self._execute_system_command("rundll32.exe user32.dll,LockWorkStation"), False),
            "睡眠": (lambda: self._execute_system_command("rundll32.exe powrprof.dll,SetSuspendState 0,1,0"), False),
            "休眠": (lambda: self._execute_system_command("shutdown /h"), False),
            
            # 系统音量控制
            "静音": (lambda: self._set_system_volume(0), False),
            "取消静音": (lambda: self._restore_system_volume(), False),
            "音量最大": (lambda: self._set_system_volume(100), False),
            "音量中等": (lambda: self._set_system_volume(50), False),
            "音量调高": (lambda: self._adjust_system_volume(10), False),
            "音量调低": (lambda: self._adjust_system_volume(-10), False),
            
            # 音乐音量控制
            "音乐静音": (lambda: self._set_music_volume(0), False),
            "音乐音量调高": (lambda: self._adjust_music_volume(10), False),
            "音乐音量调低": (lambda: self._adjust_music_volume(-10), False),
            "音乐音量最大": (lambda: self._set_music_volume(100), False),
            
            # 语音音量控制
            "语音静音": (lambda: self._set_voice_volume(0), False),
            "语音音量调高": (lambda: self._adjust_voice_volume(10), False),
            "语音音量调低": (lambda: self._adjust_voice_volume(-10), False),
            "语音音量最大": (lambda: self._set_voice_volume(100), False),
            
            # 应用程序启动
            "记事本": (lambda: self._launch_app("notepad.exe"), False),
            "计算器": (lambda: self._launch_app("calc.exe"), False),
            "画图": (lambda: self._launch_app("mspaint.exe"), False),
            "浏览器": (lambda: webbrowser.open("https://www.baidu.com"), False),
            "命令提示符": (lambda: self._launch_app("cmd.exe"), False),
            "任务管理器": (lambda: self._launch_app("taskmgr.exe"), False),
            "vscode": (lambda: self._launch_app("code"), False),
            "visual studio code": (lambda: self._launch_app("code"), False),
            
            # 媒体控制
            "播放": (lambda: self._media_control("play"), False),
            "暂停": (lambda: self._media_control("pause"), False),
            "停止": (lambda: self._media_control("stop"), False),
            "下一首": (lambda: self._media_control("next"), False),
            "上一首": (lambda: self._media_control("prev"), False),
            
            # 桌面操作
            "显示桌面": (lambda: self._show_desktop(), False),
            "刷新桌面": (lambda: self._refresh_desktop(), False),
            "打开文件管理器": (lambda: self._launch_app("explorer.exe"), False),
            
            # 系统设置
            "系统设置": (lambda: self._launch_app("ms-settings:"), False),
            "网络设置": (lambda: self._launch_app("ms-settings:network"), False),
            "蓝牙设置": (lambda: self._launch_app("ms-settings:bluetooth"), False),
            "显示设置": (lambda: self._launch_app("ms-settings:display"), False),
            "声音设置": (lambda: self._launch_app("ms-settings:sound"), False),
        }
    
    def process_command(self, message: str) -> bool:
        """
        处理语音消息，检查是否为系统操作命令
        
        Args:
            message: 用户语音消息
            
        Returns:
            如果是系统命令并已执行返回True，否则返回False
        """
        # 加载配置
        config = load_config()
        system_commands_enabled = config.get("system_commands_enabled", True)
        confirm_dangerous = config.get("system_commands_confirm_dangerous", True)
        
        if not system_commands_enabled:
            return False
        
        # 先检查模糊音量命令
        if self._process_fuzzy_volume_command(message):
            return True
        
        # 检查消息中是否包含系统命令
        for command, (action, is_dangerous) in self.system_commands.items():
            if command in message:
                try:
                    # 对于危险操作，需要确认
                    if is_dangerous and confirm_dangerous:
                        if hasattr(self.app, 'speech_bubble'):
                            self.app.speech_bubble.show(f"⚠️ {command}是危险操作，请再说一次确认~", duration=3000)
                        
                        # 检查是否已经确认过
                        if self._pending_dangerous_command is None:
                            self._pending_dangerous_command = command
                            return True
                        elif self._pending_dangerous_command == command:
                            # 确认执行
                            self._pending_dangerous_command = None
                        else:
                            # 不同的危险命令，重置
                            self._pending_dangerous_command = command
                            if hasattr(self.app, 'speech_bubble'):
                                self.app.speech_bubble.show(f"⚠️ {command}是危险操作，请再说一次确认~", duration=3000)
                            return True
                    
                    if hasattr(self.app, 'speech_bubble'):
                        self.app.speech_bubble.show(f"正在执行: {command}~", duration=2000)
                    
                    # 在后台线程执行系统命令
                    def execute_command():
                        try:
                            action()
                            if hasattr(self.app, 'speech_bubble'):
                                self.app.speech_bubble.show(f"{command}完成! ✅", duration=3000)
                        except Exception as e:
                            if hasattr(self.app, 'speech_bubble'):
                                self.app.speech_bubble.show(f"{command}失败: {str(e)}", duration=3000)
                    
                    threading.Thread(target=execute_command, daemon=True).start()
                    return True
                except Exception as e:
                    if hasattr(self.app, 'speech_bubble'):
                        self.app.speech_bubble.show(f"执行{command}失败: {str(e)}", duration=3000)
                    return True
        
        return False
    
    def process_exact_command(self, message: str) -> bool:
        """
        精确匹配系统命令
        
        Args:
            message: 用户语音消息
            
        Returns:
            如果是精确匹配的系统命令并已执行返回True，否则返回False
        """
        # 加载配置
        config = load_config()
        system_commands_enabled = config.get("system_commands_enabled", True)
        confirm_dangerous = config.get("system_commands_confirm_dangerous", True)
        
        if not system_commands_enabled:
            return False
        
        # 精确匹配：消息完全等于命令
        if message in self.system_commands:
            command = message
            action, is_dangerous = self.system_commands[command]
            
            try:
                # 对于危险操作，需要确认
                if is_dangerous and confirm_dangerous:
                    if hasattr(self.app, 'speech_bubble'):
                        self.app.speech_bubble.show(f"⚠️ {command}是危险操作，请再说一次确认~", duration=3000)
                    
                    # 检查是否已经确认过
                    if self._pending_dangerous_command is None:
                        self._pending_dangerous_command = command
                        return True
                    elif self._pending_dangerous_command == command:
                        # 确认执行
                        self._pending_dangerous_command = None
                    else:
                        # 不同的危险命令，重置
                        self._pending_dangerous_command = command
                        if hasattr(self.app, 'speech_bubble'):
                            self.app.speech_bubble.show(f"⚠️ {command}是危险操作，请再说一次确认~", duration=3000)
                        return True
                
                if hasattr(self.app, 'speech_bubble'):
                    self.app.speech_bubble.show(f"正在执行: {command}~", duration=2000)
                
                # 在后台线程执行系统命令
                def execute_command():
                    try:
                        action()
                        if hasattr(self.app, 'speech_bubble'):
                            self.app.speech_bubble.show(f"{command}完成! ✅", duration=3000)
                    except Exception as e:
                        if hasattr(self.app, 'speech_bubble'):
                            self.app.speech_bubble.show(f"{command}失败: {str(e)}", duration=3000)
                
                threading.Thread(target=execute_command, daemon=True).start()
                return True
            except Exception as e:
                if hasattr(self.app, 'speech_bubble'):
                    self.app.speech_bubble.show(f"执行{command}失败: {str(e)}", duration=3000)
                return True
        
        return False
    
    def find_fuzzy_command(self, message: str) -> Optional[str]:
        """
        查找模糊匹配的命令
        
        Args:
            message: 用户语音消息
            
        Returns:
            找到的命令名称，如果没有找到返回None
        """
        # 加载配置
        config = load_config()
        system_commands_enabled = config.get("system_commands_enabled", True)
        
        if not system_commands_enabled:
            return None
        
        # 获取所有命令（临时实现，使用现有的system_commands）
        all_commands = {}
        for command, (action, is_dangerous) in self.system_commands.items():
            # 确定命令类型
            command_type = "system"
            if "音量" in command:
                command_type = "volume"
            elif any(app in command for app in ["记事本", "计算器", "画图", "浏览器", "vscode"]):
                command_type = "app"
            elif any(media in command for media in ["播放", "暂停", "停止", "下一首", "上一首"]):
                command_type = "media"
            
            all_commands[command] = {
                "keywords": [command],
                "type": command_type,
                "action": "system_control" if command_type == "system" else "custom"
            }
        
        # 模糊匹配：消息包含命令关键词
        for command_name, command_info in all_commands.items():
            # 跳过精确匹配的情况（由精确匹配处理）
            if message == command_name:
                continue
                
            # 检查消息是否包含命令关键词
            for keyword in command_info["keywords"]:
                if keyword in message:
                    # 特殊处理：音量控制命令
                    if command_name in ["静音", "取消静音", "音量最大", "音量中等", "音量调高", "音量调低", 
                                      "音乐静音", "音乐音量调高", "音乐音量调低", "音乐音量最大",
                                      "语音静音", "语音音量调高", "语音音量调低", "语音音量最大"]:
                        if self._process_fuzzy_volume_command(message):
                            return "音量控制"
                    
                    # 特殊处理：应用程序启动命令
                    if command_info["type"] in ["app", "custom"] and command_info["action"] == "custom":
                        if self._process_fuzzy_app_command(message):
                            return "应用程序启动"
                    
                    # 简单模糊匹配，返回命令名称
                    return command_name
        
        return None
    
    def process_fuzzy_command(self, message: str) -> Optional[str]:
        """
        模糊匹配系统命令
        
        模糊匹配逻辑：
        1. 检查消息中是否包含预定义的命令关键词
        2. 优先处理特殊类型的命令（如音量控制）
        3. 返回匹配的命令名称，但不执行（由调用方决定是否执行）
        
        Args:
            message: 用户语音消息
            
        Returns:
            如果是模糊匹配的系统命令返回命令名称，否则返回None
        """
        # 使用新的find_fuzzy_command方法
        return self.find_fuzzy_command(message)
    
    def _process_fuzzy_app_command(self, message: str) -> bool:
        """
        处理模糊的应用程序启动命令
        
        Args:
            message: 用户语音消息
            
        Returns:
            如果是模糊的应用程序启动命令返回True，否则返回False
        """
        # 获取所有命令
        all_commands = self._get_all_commands()
        
        # 检查消息中是否包含应用程序关键词
        for command_name, command_info in all_commands.items():
            if command_info["type"] in ["app", "custom"] and command_info["action"] == "launch_app":
                for keyword in command_info["keywords"]:
                    if keyword in message:
                        # 执行应用程序启动
                        try:
                            if command_info["type"] == "app":
                                # 预设应用程序
                                subprocess.Popen(command_info["path"])
                                if hasattr(self.app, 'speech_bubble'):
                                    self.app.speech_bubble.show(f"{command_name}已启动! ✅", duration=3000)
                            elif command_info["type"] == "custom":
                                # 自定义应用程序
                                app_path = command_info["params"].get("path", "")
                                if app_path:
                                    subprocess.Popen(app_path)
                                    if hasattr(self.app, 'speech_bubble'):
                                        self.app.speech_bubble.show(f"{command_name}已启动! ✅", duration=3000)
                                else:
                                    # 路径为空，返回False
                                    print(f"🔧 调试模式: 应用程序路径为空")
                                    return False
                        except Exception as e:
                            # 启动失败，返回False
                            print(f"🔧 调试模式: 启动应用程序失败: {str(e)}")
                            return False
        
        return False
    
    def is_command(self, message: str) -> bool:
        """
        判断消息是否包含命令
        
        Args:
            message: 用户语音消息
            
        Returns:
            如果是命令返回True，否则返回False
        """
        # 加载配置
        config = load_config()
        system_commands_enabled = config.get("system_commands_enabled", True)
        
        if not system_commands_enabled:
            return False
        
        # 获取所有命令
        all_commands = self._get_all_commands()
        
        # 精确匹配：消息完全等于命令
        if message in all_commands:
            return True
        
        # 检查模糊匹配
        for command_name, command_info in all_commands.items():
            for keyword in command_info["keywords"]:
                if keyword in message:
                    return True
        
        # 检查模糊音量命令
        if self._process_fuzzy_volume_command(message):
            return True
        
        return False
    
    def _get_all_commands(self) -> dict:
        """
        获取所有命令及其关键词
        
        Returns:
            包含所有命令的字典
        """
        commands = {}
        
        # 添加系统命令
        for command, (action, is_dangerous) in self.system_commands.items():
            commands[command] = {
                "keywords": [command],
                "action": action,
                "is_dangerous": is_dangerous
            }
        
        # 添加应用程序关键词
        app_keywords = {
            "记事本": ["记事本", "笔记本", "便签", "笔记"],
            "计算器": ["计算器", "计算", "算术", "数学"],
            "浏览器": ["浏览器", "上网", "网页", "浏览"],
            "画图": ["画图", "画画", "绘图", "画板"],
            "任务管理器": ["任务管理器", "任务", "进程", "任务栏"],
            "vscode": ["vscode", "visual studio code", "代码编辑器", "编辑器", "打代码", "写代码", "编程", "开发"]
        }
        
        for app_name, keywords in app_keywords.items():
            if app_name in commands:
                commands[app_name]["keywords"].extend(keywords)
            else:
                commands[app_name] = {
                    "keywords": keywords,
                    "action": lambda name=app_name: self._launch_app_by_name(name),
                    "is_dangerous": False
                }
        
        return commands
    
    def should_use_llm_assistance(self, message: str) -> bool:
        """
        判断是否应该使用LLM辅助理解
        
        Args:
            message: 用户语音消息
            
        Returns:
            如果应该使用LLM辅助理解返回True，否则返回False
        """
        # 加载配置
        config = load_config()
        llm_assistance_enabled = config.get("llm_command_assistance_enabled", True)
        
        if not llm_assistance_enabled:
            return False
        
        # 检查消息长度，太短或太长都不适合LLM辅助
        if len(message) < 5 or len(message) > 50:
            return False
        
        # 检查是否包含命令相关关键词
        command_keywords = [
            "打开", "关闭", "启动", "运行", "执行",
            "调高", "调低", "增大", "减小", "设置",
            "播放", "暂停", "停止", "下一首", "上一首",
            "重启", "关机", "锁屏", "睡眠", "休眠",
            "代码", "编程", "开发", "vscode", "打代码", "写代码"
        ]
        
        # 如果包含命令关键词，但又不匹配精确或模糊命令，则使用LLM辅助
        for keyword in command_keywords:
            if keyword in message:
                # 检查是否已经匹配过精确或模糊命令
                if not self.is_command(message):
                    return True
                break
        
        return False
    
    def _is_exact_or_fuzzy_match(self, message: str) -> bool:
        """
        检查消息是否已经匹配精确或模糊命令
        
        Args:
            message: 用户语音消息
            
        Returns:
            如果已经匹配返回True，否则返回False
        """
        # 检查精确匹配
        if message in self.system_commands:
            return True
        
        # 检查模糊匹配
        for command in self.system_commands.keys():
            if command in message:
                return True
        
        # 检查模糊音量命令
        if self._process_fuzzy_volume_command(message):
            return True
        
        return False
    
    def _get_all_commands(self) -> Dict[str, Dict]:
        """
        获取所有命令的统一字典，包括系统命令、应用程序命令和自定义命令
        
        Returns:
            统一的命令字典
        """
        # 加载配置
        config = load_config()
        custom_commands = config.get("custom_commands", {})
        
        # 初始化统一命令字典
        all_commands = {}
        
        # 添加系统命令
        for command_name, (action, is_dangerous) in self.system_commands.items():
            all_commands[command_name] = {
                "type": "system",
                "action": "system",
                "handler": action,
                "is_dangerous": is_dangerous,
                "keywords": [command_name]
            }
        
        # 添加应用程序命令
        app_commands = {
            "记事本": {"path": "notepad", "keywords": ["记事本", "笔记本", "便签", "笔记"]},
            "计算器": {"path": "calc", "keywords": ["计算器", "计算", "算术", "数学"]},
            "浏览器": {"path": "https://www.baidu.com", "keywords": ["浏览器", "上网", "网页", "浏览"]},
            "画图": {"path": "mspaint", "keywords": ["画图", "画画", "绘图", "画板"]},
            "任务管理器": {"path": "taskmgr", "keywords": ["任务管理器", "任务", "进程", "任务栏"]},
            "vscode": {"path": "code", "keywords": ["vscode", "visual studio code", "代码编辑器", "编辑器", "打代码", "写代码", "编程", "开发"]},
            "微信": {"path": "WeChat.exe", "keywords": ["微信", "wechat"]}
        }
        
        for app_name, app_data in app_commands.items():
            # 优先使用自定义命令中的路径
            if app_name in custom_commands and custom_commands[app_name].get("action") == "launch_app":
                app_data["path"] = custom_commands[app_name].get("params", {}).get("path", app_data["path"])
            
            all_commands[app_name] = {
                "type": "app",
                "action": "launch_app",
                "path": app_data["path"],
                "is_dangerous": False,
                "keywords": app_data["keywords"]
            }
        
        # 添加自定义命令
        for command_name, command_data in custom_commands.items():
            if command_name not in all_commands:  # 避免覆盖已存在的应用程序命令
                all_commands[command_name] = {
                    "type": "custom",
                    "action": command_data.get("action", ""),
                    "params": command_data.get("params", {}),
                    "is_dangerous": command_data.get("is_dangerous", False),
                    "keywords": [command_name]
                }
        
        return all_commands
    
    def execute_command_by_name(self, command_name: str, original_command: str = None) -> bool:
        """
        根据命令名称执行命令
        
        Args:
            command_name: 命令名称
            original_command: 原始命令（如"打开微信"）
            
        Returns:
            如果命令存在并执行成功返回True，否则返回False
        """
        # 加载配置
        config = load_config()
        system_commands_enabled = config.get("system_commands_enabled", True)
        confirm_dangerous = config.get("system_commands_confirm_dangerous", True)
        
        if not system_commands_enabled:
            return False
        
        # 获取所有命令
        all_commands = self._get_all_commands()
        
        # 检查是否是"动作+目标"组合
        action_word = None
        target_app = None
        
        # 动作词映射
        action_words = ["打开", "启动", "运行", "关闭", "退出", "结束"]
        
        for word in action_words:
            if command_name.startswith(word):
                action_word = word
                target_app = command_name[len(word):].strip()
                break
        
        # 如果是"动作+目标"组合
        if action_word and target_app:
            # 处理应用程序操作
            if action_word in ["打开", "启动", "运行"]:
                # 优先使用原始命令（如果有）
                cmd_to_pass = original_command if original_command else command_name
                return self._launch_app_by_name(target_app, cmd_to_pass)
            elif action_word in ["关闭", "退出", "结束"]:
                return self._close_app_by_name(target_app)
        
        # 查找命令
        if command_name in all_commands:
            command_info = all_commands[command_name]
            
            try:
                # 对于危险操作，需要确认
                if command_info["is_dangerous"] and confirm_dangerous:
                    if hasattr(self.app, 'speech_bubble'):
                        self.app.speech_bubble.show(f"⚠️ {command_name}是危险操作，请再说一次确认~", duration=3000)
                    
                    # 检查是否已经确认过
                    if self._pending_dangerous_command is None:
                        self._pending_dangerous_command = command_name
                        return True
                    elif self._pending_dangerous_command == command_name:
                        # 确认执行
                        self._pending_dangerous_command = None
                    else:
                        # 不同的危险命令，重置
                        self._pending_dangerous_command = command_name
                        if hasattr(self.app, 'speech_bubble'):
                            self.app.speech_bubble.show(f"⚠️ {command_name}是危险操作，请再说一次确认~", duration=3000)
                        return True
                
                # 执行命令并返回结果
                try:
                    # 根据命令类型执行
                    if command_info["type"] == "system":
                        # 执行系统命令
                        command_info["handler"]()
                        if hasattr(self.app, 'speech_bubble'):
                            self.app.speech_bubble.show(f"{command_name}完成! ✅", duration=3000)
                        return True
                    elif command_info["type"] == "app" and command_info["action"] == "launch_app":
                        # 启动应用程序
                        subprocess.Popen(command_info["path"])
                        if hasattr(self.app, 'speech_bubble'):
                            self.app.speech_bubble.show(f"{command_name}已启动! ✅", duration=3000)
                        return True
                    elif command_info["type"] == "custom":
                        # 执行自定义命令
                        if command_info["action"] == "launch_app":
                            app_path = command_info["params"].get("path", "")
                            if app_path:
                                subprocess.Popen(app_path)
                                if hasattr(self.app, 'speech_bubble'):
                                    self.app.speech_bubble.show(f"{command_name}已启动! ✅", duration=3000)
                                return True
                            else:
                                if hasattr(self.app, 'speech_bubble'):
                                    self.app.speech_bubble.show(f"{command_name}失败: 未找到路径", duration=3000)
                                return False
                        else:
                            if hasattr(self.app, 'speech_bubble'):
                                self.app.speech_bubble.show(f"{command_name}失败: 不支持的操作", duration=3000)
                            return False
                    
                except Exception as e:
                    # 检查是否是应用程序启动失败
                    if "无法启动应用程序" in str(e):
                        # 尝试从错误消息中提取应用程序名称
                        app_name = self._extract_app_name_from_error(str(e))
                        if app_name:
                            # 显示自定义路径对话框
                            self._show_custom_path_dialog(app_name)
                        else:
                            if hasattr(self.app, 'speech_bubble'):
                                self.app.speech_bubble.show(f"{command_name}失败: {str(e)}", duration=3000)
                    else:
                        if hasattr(self.app, 'speech_bubble'):
                            self.app.speech_bubble.show(f"{command_name}失败: {str(e)}", duration=3000)
                    return False
            except Exception as e:
                # 检查是否是应用程序启动失败
                if "无法启动应用程序" in str(e):
                    # 尝试从错误消息中提取应用程序名称
                    app_name = self._extract_app_name_from_error(str(e))
                    if app_name:
                        # 显示自定义路径对话框
                        self._show_custom_path_dialog(app_name)
                    else:
                        if hasattr(self.app, 'speech_bubble'):
                            self.app.speech_bubble.show(f"执行{command_name}失败: {str(e)}", duration=3000)
                else:
                    if hasattr(self.app, 'speech_bubble'):
                        self.app.speech_bubble.show(f"执行{command_name}失败: {str(e)}", duration=3000)
                return False
        
        return False
    
    def _process_fuzzy_volume_command(self, message: str) -> bool:
        """
        处理模糊音量命令，如"调大音量"、"调小音量"等
        
        Args:
            message: 用户语音消息
            
        Returns:
            如果是模糊音量命令并已执行返回True，否则返回False
        """
        # 系统音量模糊命令
        system_volume_patterns = [
            ("调大音量", lambda: self._adjust_system_volume(10)),
            ("调小音量", lambda: self._adjust_system_volume(-10)),
            ("音量调大", lambda: self._adjust_system_volume(10)),
            ("音量调小", lambda: self._adjust_system_volume(-10)),
            ("声音大点", lambda: self._adjust_system_volume(10)),
            ("声音小点", lambda: self._adjust_system_volume(-10)),
        ]
        
        # 音乐音量模糊命令
        music_volume_patterns = [
            ("音乐调大", lambda: self._adjust_music_volume(10)),
            ("音乐调小", lambda: self._adjust_music_volume(-10)),
            ("音乐大声", lambda: self._adjust_music_volume(10)),
            ("音乐小声", lambda: self._adjust_music_volume(-10)),
        ]
        
        # 语音音量模糊命令
        voice_volume_patterns = [
            ("语音调大", lambda: self._adjust_voice_volume(10)),
            ("语音调小", lambda: self._adjust_voice_volume(-10)),
            ("语音大声", lambda: self._adjust_voice_volume(10)),
            ("语音小声", lambda: self._adjust_voice_volume(-10)),
        ]
        
        # 检查系统音量命令
        for pattern, action in system_volume_patterns:
            if pattern in message:
                if hasattr(self.app, 'speech_bubble'):
                    self.app.speech_bubble.show(f"正在调整系统音量~", duration=2000)
                
                threading.Thread(target=action, daemon=True).start()
                return True
        
        # 检查音乐音量命令
        for pattern, action in music_volume_patterns:
            if pattern in message:
                if hasattr(self.app, 'speech_bubble'):
                    self.app.speech_bubble.show(f"正在调整音乐音量~", duration=2000)
                
                threading.Thread(target=action, daemon=True).start()
                return True
        
        # 检查语音音量命令
        for pattern, action in voice_volume_patterns:
            if pattern in message:
                if hasattr(self.app, 'speech_bubble'):
                    self.app.speech_bubble.show(f"正在调整语音音量~", duration=2000)
                
                threading.Thread(target=action, daemon=True).start()
                return True
        
        return False
    
    def get_command_list(self) -> Dict[str, list]:
        """
        获取分类后的命令列表
        
        Returns:
            分类后的命令字典
        """
        return {
            "系统控制": [
                "关机 - 关闭计算机",
                "重启 - 重新启动计算机",
                "注销 - 注销当前用户",
                "锁屏 - 锁定计算机",
                "睡眠 - 使计算机进入睡眠状态",
                "休眠 - 使计算机进入休眠状态",
            ],
            "系统音量控制": [
                "静音 - 将系统音量设置为静音",
                "取消静音 - 取消系统静音",
                "音量最大 - 将系统音量设置为最大",
                "音量中等 - 将系统音量设置为中等",
                "音量调高 - 增加系统音量",
                "音量调低 - 减少系统音量",
            ],
            "音乐音量控制": [
                "音乐静音 - 将音乐音量设置为静音",
                "音乐音量调高 - 增加音乐音量",
                "音乐音量调低 - 减少音乐音量",
                "音乐音量最大 - 将音乐音量设置为最大",
            ],
            "语音音量控制": [
                "语音静音 - 将语音音量设置为静音",
                "语音音量调高 - 增加语音音量",
                "语音音量调低 - 减少语音音量",
                "语音音量最大 - 将语音音量设置为最大",
            ],
            "应用程序": [
                "记事本 - 打开记事本",
                "计算器 - 打开计算器",
                "画图 - 打开画图工具",
                "浏览器 - 打开默认浏览器",
                "命令提示符 - 打开命令提示符",
                "任务管理器 - 打开任务管理器",
            ],
            "媒体控制": [
                "播放 - 播放媒体",
                "暂停 - 暂停媒体",
                "停止 - 停止媒体",
                "下一首 - 播放下一首",
                "上一首 - 播放上一首",
            ],
            "桌面操作": [
                "显示桌面 - 显示桌面",
                "刷新桌面 - 刷新桌面",
                "打开文件管理器 - 打开文件资源管理器",
            ],
            "系统设置": [
                "系统设置 - 打开系统设置",
                "网络设置 - 打开网络设置",
                "蓝牙设置 - 打开蓝牙设置",
                "显示设置 - 打开显示设置",
                "声音设置 - 打开声音设置",
            ],
        }
    
    def _execute_system_command(self, command: str) -> None:
        """
        执行系统命令
        
        Args:
            command: 要执行的命令
        """
        if os.name == 'nt':  # Windows
            subprocess.run(command, shell=True)
        else:  # Linux/Mac
            subprocess.run(command, shell=True)
    
    def _launch_app(self, app_name: str) -> None:
        """
        启动应用程序
        
        Args:
            app_name: 应用程序名称或路径
        """
        # 首先尝试使用自定义路径
        custom_path = self._get_custom_app_path(app_name)
        if custom_path:
            app_path = custom_path
        else:
            app_path = app_name
            
        try:
            if os.name == 'nt':  # Windows
                subprocess.Popen(app_path)
            else:  # Linux/Mac
                subprocess.Popen(app_path.split())
        except Exception as e:
            # 如果启动失败，抛出异常
            raise Exception(f"无法启动应用程序: {str(e)}")
    
    def _get_custom_app_path(self, app_name: str) -> Optional[str]:
        """
        获取应用程序的自定义路径
        
        Args:
            app_name: 应用程序名称
            
        Returns:
            自定义路径，如果不存在则返回None
        """
        config = load_config()
        
        # 首先检查custom_app_paths
        custom_paths = config.get("custom_app_paths", {})
        if app_name in custom_paths:
            return custom_paths[app_name]
        
        # 然后检查custom_commands
        custom_commands = config.get("custom_commands", {})
        if app_name in custom_commands:
            command_data = custom_commands[app_name]
            if command_data.get("action") == "launch_app":
                return command_data.get("params", {}).get("path")
        
        return None
    
    def _show_custom_path_dialog(self, app_name: str) -> None:
        """
        显示自定义路径对话框
        
        Args:
            app_name: 应用程序名称
        """
        try:
            import tkinter as tk
            from tkinter import filedialog, messagebox
            
            # 创建对话框
            # 获取主窗口
            root = None
            if hasattr(self.app, 'root'):
                root = self.app.root
            elif hasattr(self.app, 'window'):
                root = self.app.window
            
            dialog = tk.Toplevel(root) if root else tk.Toplevel()
            dialog.title(f"添加{app_name}路径")
            dialog.geometry("500x300")
            dialog.resizable(False, False)
            if root:
                dialog.transient(root)
            dialog.grab_set()
            dialog.configure(bg="#FFF5F8")
            
            # 标题
            title_frame = tk.Frame(dialog, bg="#FF69B4", height=45)
            title_frame.pack(fill=tk.X)
            title_frame.pack_propagate(False)
            
            tk.Label(
                title_frame,
                text=f"添加{app_name}路径",
                bg="#FF69B4",
                fg="white",
                font=("Microsoft YaHei", 12, "bold"),
            ).pack(side=tk.LEFT, padx=15, pady=10)
            
            # 内容区域
            content_frame = tk.Frame(dialog, bg="#FFF5F8")
            content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
            
            # 说明
            tk.Label(
                content_frame,
                text=f"无法找到{app_name}，请点击下方按钮选择{app_name}的可执行文件：",
                bg="#FFF5F8",
                fg="#5C3B4A",
                font=("Microsoft YaHei", 10),
                anchor="w"
            ).pack(fill=tk.X, pady=(0, 10))
            
            # 路径显示
            path_frame = tk.Frame(content_frame, bg="#FFF5F8")
            path_frame.pack(fill=tk.X, pady=(0, 10))
            
            path_var = tk.StringVar()
            path_label = tk.Label(
                path_frame,
                text="尚未选择文件",
                bg="#FFF5F8",
                fg="#5C3B4A",
                font=("Microsoft YaHei", 9),
                anchor="w"
            )
            path_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
            
            def browse_file():
                """浏览文件"""
                if app_name.lower() in ["记事本", "notepad"]:
                    filetypes = [("可执行文件", "*.exe"), ("所有文件", "*.*")]
                    initial_dir = "C:\\Windows\\System32"
                elif app_name.lower() in ["计算器", "calculator"]:
                    filetypes = [("可执行文件", "*.exe"), ("所有文件", "*.*")]
                    initial_dir = "C:\\Windows\\System32"
                elif app_name.lower() in ["vscode", "code"]:
                    filetypes = [("可执行文件", "Code.exe"), ("所有文件", "*.*")]
                    initial_dir = "C:\\Program Files"
                else:
                    filetypes = [("可执行文件", "*.exe"), ("所有文件", "*.*")]
                    initial_dir = "C:\\Program Files"
                
                file_path = filedialog.askopenfilename(
                    title=f"选择{app_name}可执行文件",
                    filetypes=filetypes,
                    initialdir=initial_dir
                )
                if file_path:
                    path_var.set(file_path)
                    # 只显示文件名，而不是完整路径
                    import os
                    file_name = os.path.basename(file_path)
                    path_label.config(text=f"已选择: {file_name}")
            
            browse_btn = tk.Button(
                path_frame,
                text="选择文件...",
                bg="#FF69B4",
                fg="white",
                font=("Microsoft YaHei", 9),
                borderwidth=0,
                padx=10,
                pady=5,
                cursor="hand2",
                command=browse_file
            )
            browse_btn.pack(side=tk.RIGHT, padx=(5, 0))
            
            # 按钮区域
            button_frame = tk.Frame(content_frame, bg="#FFF5F8")
            button_frame.pack(fill=tk.X, pady=(10, 0))
            
            def save_path():
                """保存路径"""
                path = path_var.get().strip()
                if not path:
                    messagebox.showerror("错误", "请先选择一个文件", parent=dialog)
                    return
                
                if not os.path.exists(path):
                    messagebox.showerror("错误", "指定的文件不存在", parent=dialog)
                    return
                
                # 保存到配置文件
                from src.config import update_config
                config = load_config()
                custom_paths = config.get("custom_app_paths", {})
                custom_paths[app_name] = path
                update_config(custom_app_paths=custom_paths)
                
                # 尝试启动应用程序
                try:
                    if os.name == 'nt':  # Windows
                        subprocess.Popen(path)
                    else:  # Linux/Mac
                        subprocess.Popen(path.split())
                    
                    if hasattr(self.app, 'speech_bubble'):
                        self.app.speech_bubble.show(f"{app_name}已启动! ✅", duration=3000)
                    
                    dialog.destroy()
                except Exception as e:
                    messagebox.showerror("错误", f"无法启动{app_name}: {str(e)}", parent=dialog)
            
            def cancel_dialog():
                """取消对话框"""
                dialog.destroy()
            
            # 按钮
            tk.Button(
                button_frame,
                text="保存并启动",
                bg="#FF69B4",
                fg="white",
                font=("Microsoft YaHei", 10),
                borderwidth=0,
                padx=20,
                pady=5,
                cursor="hand2",
                command=save_path
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
            x = (dialog.winfo_screenwidth() // 2) - (500 // 2)
            y = (dialog.winfo_screenheight() // 2) - (300 // 2)
            dialog.geometry(f"+{x}+{y}")
            
            # 自动打开文件选择器
            dialog.after(100, browse_file)
            
        except Exception as e:
            # 如果无法创建对话框，至少记录错误
            print(f"无法显示自定义路径对话框: {str(e)}")
    
    def _set_system_volume(self, level: int) -> None:
        """
        设置系统音量
        
        Args:
            level: 音量级别 (0-100)
        """
        if os.name == 'nt':  # Windows
            # 简单实现：通过多次按音量键来调整
            if level == 0:
                # 静音
                subprocess.run("powershell -command \"(New-Object -comObject WScript.Shell).SendKeys([char]173)\"", shell=True)
            elif level == 100:
                # 最大音量
                for _ in range(50):
                    subprocess.run("powershell -command \"(New-Object -comObject WScript.Shell).SendKeys([char]175)\"", shell=True)
            else:
                # 根据百分比调整
                steps = int(level / 2)
                for _ in range(steps):
                    subprocess.run("powershell -command \"(New-Object -comObject WScript.Shell).SendKeys([char]175)\"", shell=True)
        else:  # Linux/Mac
            # 使用amixer设置音量
            subprocess.run(f"amixer set Master {level}%", shell=True)
    
    def _adjust_system_volume(self, delta: int) -> None:
        """
        调整系统音量
        
        Args:
            delta: 音量调整量，正数为增加，负数为减少
        """
        if os.name == 'nt':  # Windows
            if delta > 0:
                key = "[char]175"  # 音量增加
            else:
                key = "[char]174"  # 音量减少
            
            steps = abs(delta // 2)
            for _ in range(steps):
                subprocess.run(f"powershell -command \"(New-Object -comObject WScript.Shell).SendKeys({key})\"", shell=True)
        else:  # Linux/Mac
            if delta > 0:
                subprocess.run("amixer set Master 5%+", shell=True)
            else:
                subprocess.run("amixer set Master 5%-", shell=True)
    
    def _restore_system_volume(self) -> None:
        """取消静音/恢复系统音量"""
        if os.name == 'nt':  # Windows
            subprocess.run("powershell -command \"(New-Object -comObject WScript.Shell).SendKeys([char]173)\"", shell=True)
        else:  # Linux/Mac
            subprocess.run("amixer set Master unmute", shell=True)
    
    def _set_music_volume(self, level: int) -> None:
        """
        设置音乐音量
        
        Args:
            level: 音量级别 (0-100)
        """
        if hasattr(self.app, 'music'):
            # 确保音量在有效范围内
            level = max(0, min(100, level))
            self.app.music.set_volume(level)
            
            # 显示当前音量
            if hasattr(self.app, 'speech_bubble'):
                self.app.speech_bubble.show(f"音乐音量已设置为: {level}% 🎵", duration=2000)
    
    def _adjust_music_volume(self, delta: int) -> None:
        """
        调整音乐音量
        
        Args:
            delta: 音量调整量，正数为增加，负数为减少
        """
        if hasattr(self.app, 'music'):
            current_volume = self.app.music.get_volume()
            new_volume = max(0, min(100, current_volume + delta))
            self.app.music.set_volume(new_volume)
            
            # 显示当前音量
            if hasattr(self.app, 'speech_bubble'):
                self.app.speech_bubble.show(f"音乐音量已调整为: {new_volume}% 🎵", duration=2000)
    
    def _set_voice_volume(self, level: int) -> None:
        """
        设置语音音量
        
        Args:
            level: 音量级别 (0-100)
        """
        # 确保音量在有效范围内
        level = max(0, min(100, level))
        
        # 保存到配置
        from src.config import update_config
        update_config(tts_volume=level)
        
        # 更新当前实例的音量设置
        self.voice_volume = level / 100.0
        
        # 显示当前音量
        if hasattr(self.app, 'speech_bubble'):
            self.app.speech_bubble.show(f"语音音量已设置为: {level}% 🎤", duration=2000)
    
    def _adjust_voice_volume(self, delta: int) -> None:
        """
        调整语音音量
        
        Args:
            delta: 音量调整量，正数为增加，负数为减少
        """
        from src.config import load_config, update_config
        config = load_config()
        current_volume = config.get('tts_volume', 50)
        new_volume = max(0, min(100, current_volume + delta))
        
        # 保存到配置
        update_config(tts_volume=new_volume)
        
        # 更新当前实例的音量设置
        self.voice_volume = new_volume / 100.0
        
        # 显示当前音量
        if hasattr(self.app, 'speech_bubble'):
            self.app.speech_bubble.show(f"语音音量已调整为: {new_volume}% 🎤", duration=2000)
    
    def _media_control(self, action: str) -> None:
        """
        媒体控制
        
        Args:
            action: 控制动作 (play, pause, stop, next, prev)
        """
        if os.name == 'nt':  # Windows
            media_keys = {
                "play": "[char]176",
                "pause": "[char]179",
                "stop": "[char]178",
                "next": "[char]176",
                "prev": "[char]177"
            }
            
            if action in media_keys:
                subprocess.run(f"powershell -command \"(New-Object -comObject WScript.Shell).SendKeys({media_keys[action]})\"", shell=True)
        else:  # Linux/Mac
            # 使用playerctl或其他媒体控制工具
            if action == "play":
                subprocess.run("playerctl play", shell=True)
            elif action == "pause":
                subprocess.run("playerctl pause", shell=True)
            elif action == "stop":
                subprocess.run("playerctl stop", shell=True)
            elif action == "next":
                subprocess.run("playerctl next", shell=True)
            elif action == "prev":
                subprocess.run("playerctl previous", shell=True)
    
    def _show_desktop(self) -> None:
        """显示桌面"""
        if os.name == 'nt':  # Windows
            subprocess.run("powershell -command \"(New-Object -comObject WScript.Shell).SendKeys('^d')\"", shell=True)
        else:  # Linux/Mac
            # Linux下可能需要根据桌面环境调整
            subprocess.run("xdotool key super+d", shell=True)
    
    def _refresh_desktop(self) -> None:
        """刷新桌面"""
        if os.name == 'nt':  # Windows
            subprocess.run("powershell -command \"(New-Object -comObject WScript.Shell).SendKeys('{F5}')\"", shell=True)
        else:  # Linux/Mac
            # Linux下可能需要根据桌面环境调整
            subprocess.run("xdotool key F5", shell=True)
    
    def _extract_app_name_from_error(self, error_message: str) -> Optional[str]:
        """
        从错误消息中提取应用程序名称
        
        Args:
            error_message: 错误消息
            
        Returns:
            应用程序名称，如果无法提取则返回None
        """
        # 应用程序映射
        app_mapping = {
            "notepad": "记事本",
            "calc": "计算器",
            "mspaint": "画图",
            "taskmgr": "任务管理器",
            "code": "vscode"
        }
        
        # 尝试从错误消息中提取应用程序名称
        for app_cmd, app_name in app_mapping.items():
            if app_cmd in error_message:
                return app_name
        
        return None
    
    def _launch_app_by_name(self, app_name: str, original_command: str = None) -> bool:
        """
        根据应用程序名称启动应用程序
        
        Args:
            app_name: 应用程序名称
            original_command: 原始命令（如"打开微信"）
            
        Returns:
            如果启动成功返回True，否则返回False
        """
        # 优先检查自定义命令
        config = load_config()
        custom_commands = config.get("custom_commands", {})
        
        # 首先检查原始命令（如果有）
        if original_command and original_command in custom_commands:
            command_data = custom_commands[original_command]
            if command_data.get("action") == "launch_app":
                app_path = command_data.get("params", {}).get("path")
                if app_path:
                    print(f"🔧 调试模式: 找到原始命令 {original_command}，路径: {app_path}")
                    try:
                        subprocess.Popen(app_path)
                        if hasattr(self.app, 'speech_bubble'):
                            self.app.speech_bubble.show(f"{original_command}已启动! ✅", duration=3000)
                        return True
                    except Exception as e:
                        print(f"🔧 调试模式: 启动原始命令失败: {str(e)}")
                        if hasattr(self.app, 'speech_bubble'):
                            self.app.speech_bubble.show(f"无法启动{original_command}: {str(e)}", duration=3000)
                        
                        # 尝试调用修复对话框
                        try:
                            from src.voice.voice_assistant import VoiceAssistant
                            # 查找VoiceAssistant实例
                            voice_assistant = None
                            if hasattr(self.app, 'voice_assistant'):
                                voice_assistant = self.app.voice_assistant
                            
                            if voice_assistant:
                                # 创建一个临时结果对象
                                class TempResult:
                                    def __init__(self, command):
                                        self.command = command
                                
                                temp_result = TempResult(original_command)
                                voice_assistant._show_command_fix_dialog(original_command, temp_result)
                                print(f"🔧 调试模式: 已调用显示修复对话框")
                        except Exception as fix_error:
                            print(f"🔧 调试模式: 调用修复对话框失败: {str(fix_error)}")
                        
                        return False
        
        # 先检查自定义命令
        # 检查完整命令（如"打开微信"）和简单命令（如"微信"）
        command_to_check = app_name
        
        # 如果是"动作+目标"组合，提取目标部分
        for action_word in ["打开", "启动", "运行"]:
            if app_name.startswith(action_word):
                command_to_check = app_name[len(action_word):].strip()
                break
        
        print(f"🔧 调试模式: 提取的目标应用: {command_to_check}")
        
        # 检查自定义命令中的目标应用
        if command_to_check in custom_commands:
            command_data = custom_commands[command_to_check]
            if command_data.get("action") == "launch_app":
                app_path = command_data.get("params", {}).get("path")
                if app_path:
                    print(f"🔧 调试模式: 找到目标应用 {command_to_check}，路径: {app_path}")
                    try:
                        subprocess.Popen(app_path)
                        if hasattr(self.app, 'speech_bubble'):
                            self.app.speech_bubble.show(f"{command_to_check}已启动! ✅", duration=3000)
                        return True
                    except Exception as e:
                        print(f"🔧 调试模式: 启动目标应用失败: {str(e)}")
                        if hasattr(self.app, 'speech_bubble'):
                            self.app.speech_bubble.show(f"无法启动{command_to_check}: {str(e)}", duration=3000)
                        return False
        else:
            print(f"🔧 调试模式: 自定义命令中未找到目标应用 {command_to_check}")
        
        # 检查自定义命令中的完整命令
        if app_name in custom_commands:
            command_data = custom_commands[app_name]
            if command_data.get("action") == "launch_app":
                app_path = command_data.get("params", {}).get("path")
                if app_path:
                    print(f"🔧 调试模式: 找到完整命令 {app_name}，路径: {app_path}")
                    try:
                        subprocess.Popen(app_path)
                        if hasattr(self.app, 'speech_bubble'):
                            self.app.speech_bubble.show(f"{app_name}已启动! ✅", duration=3000)
                        return True
                    except Exception as e:
                        print(f"🔧 调试模式: 启动完整命令失败: {str(e)}")
                        if hasattr(self.app, 'speech_bubble'):
                            self.app.speech_bubble.show(f"无法启动{app_name}: {str(e)}", duration=3000)
                        return False
        else:
            print(f"🔧 调试模式: 自定义命令中未找到完整命令 {app_name}")
        
        # 应用程序路径映射（仅在没有自定义命令时使用）
        app_paths = {
            "记事本": "notepad",
            "计算器": "calc",
            "画图": "mspaint",
            "任务管理器": "taskmgr",
            "vscode": "code",
            "微信": "WeChat.exe",
            "浏览器": "start chrome"
        }
        
        # 检查预设应用（最后尝试）
        if app_name in app_paths:
            try:
                app_path = app_paths[app_name]
                if os.name == 'nt':  # Windows
                    subprocess.Popen(app_path, shell=True)
                else:  # Linux/Mac
                    subprocess.Popen(app_path.split())
                
                if hasattr(self.app, 'speech_bubble'):
                    self.app.speech_bubble.show(f"{app_name}已启动! ✅", duration=3000)
                return True
            except Exception as e:
                if hasattr(self.app, 'speech_bubble'):
                    self.app.speech_bubble.show(f"无法启动{app_name}: {str(e)}", duration=3000)
                return False
        
        # 如果找不到应用，提示用户
        if hasattr(self.app, 'speech_bubble'):
            self.app.speech_bubble.show(f"找不到应用程序: {app_name}", duration=3000)
        return False
    
    def _close_app_by_name(self, app_name: str) -> bool:
        """
        根据应用程序名称关闭应用程序
        
        Args:
            app_name: 应用程序名称
            
        Returns:
            如果关闭成功返回True，否则返回False
        """
        # 进程名称映射
        process_names = {
            "记事本": "notepad.exe",
            "计算器": "Calculator.exe",
            "画图": "mspaint.exe",
            "任务管理器": "Taskmgr.exe",
            "vscode": "Code.exe",
            "微信": "WeChat.exe"
        }
        
        # 获取进程名称
        process_name = process_names.get(app_name)
        if not process_name:
            # 尝试使用应用名作为进程名
            process_name = f"{app_name}.exe"
        
        try:
            if os.name == 'nt':  # Windows
                # 使用taskkill命令关闭进程
                subprocess.run(f"taskkill /f /im {process_name}", shell=True, check=False)
                if hasattr(self.app, 'speech_bubble'):
                    self.app.speech_bubble.show(f"{app_name}已关闭! ✅", duration=3000)
                return True
            else:  # Linux/Mac
                # 使用pkill命令关闭进程
                subprocess.run(f"pkill -f {app_name}", shell=True, check=False)
                if hasattr(self.app, 'speech_bubble'):
                    self.app.speech_bubble.show(f"{app_name}已关闭! ✅", duration=3000)
                return True
        except Exception as e:
            if hasattr(self.app, 'speech_bubble'):
                self.app.speech_bubble.show(f"无法关闭{app_name}: {str(e)}", duration=3000)
            return False
        
        return None
    
    def process_unified_command(self, message: str) -> bool:
        """
        统一的命令处理方法
        
        按优先级顺序处理命令：
        1. 精确匹配
        2. 模糊匹配
        3. LLM辅助理解
        
        Args:
            message: 用户语音消息
            
        Returns:
            如果是命令并已执行返回True，否则返回False
        """
        # 加载配置
        config = load_config()
        system_commands_enabled = config.get("system_commands_enabled", True)
        
        if not system_commands_enabled:
            return False
        
        # 1. 尝试精确匹配
        if self.process_exact_command(message):
            return True
        
        # 2. 尝试模糊匹配
        if self.process_command(message):
            return True
        
        # 3. 检查是否需要LLM辅助
        if self.should_use_llm_assistance(message):
            # 这里可以调用LLM进行命令理解
            # 暂时返回False，让上层处理
            return False
        
        return False