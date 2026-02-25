"""语音助手模块

整合语音识别、AI对话和语音合成功能
"""

import os
import sys
import time
import threading
import queue
import subprocess
import importlib
from typing import Optional, Callable, Dict, List, Any

try:
    import dashscope
except ImportError:
    dashscope = None

from src.config import load_config
from src.voice.voice_recognition import VoiceRecognition
from src.voice.keyword_spotter import KeywordSpotter


class VoiceAssistant:
    """
    语音助手类
    
    整合语音识别、AI对话和语音合成功能
    """
    
    def __init__(self, app):
        """
        初始化语音助手
        
        参数:
            app: 桌面宠物应用实例
        """
        self.app = app
        self.logger = None  # 可以添加日志记录器
        
        # 预初始化音频播放器
        self._preinit_audio_player()
        
        # 加载配置
        self._load_config()
        
        # 初始化各个模块
        self.keyword_spotter = None
        self.voice_recognition = None
        
        # 控制标志
        self.is_running = False
        self.is_listening = False
        
        # 声音检测相关
        self.sound_detection_thread = None
        self.sound_detection_active = False
        self.sound_timeout = 3.0  # 3秒超时
        
        # 初始化模块
        self._initialize_modules()

        # 缓存的命令提示词
        self._cached_command_prompt = None
        
        # 初始化命令提示词
        self._refresh_command_prompt()

        self.debug_mode = True  # 临时启用调试模式
    
    def _preinit_audio_player(self):
        """预初始化音频播放器，避免第一次播放时的卡顿"""
        try:
            import pyaudio
            # 在后台线程中预初始化PyAudio
            import threading
            
            def init_audio():
                try:
                    # 创建一个临时的PyAudio实例来初始化音频系统
                    temp_player = pyaudio.PyAudio()
                    # 创建一个临时的音频流来预热音频系统
                    temp_stream = temp_player.open(
                        format=pyaudio.paInt16,
                        channels=1,
                        rate=22050,
                        output=True
                    )
                    # 立即关闭，只是为了让系统初始化
                    temp_stream.close()
                    temp_player.terminate()
                    if self.debug_mode:
                        print(f"🔧 调试模式: 音频系统预初始化完成")
                except Exception as e:
                    if self.debug_mode:
                        print(f"🔧 调试模式: 音频系统预初始化失败: {e}")
            
            # 在后台线程中执行初始化
            init_thread = threading.Thread(target=init_audio, daemon=True)
            init_thread.start()
        except Exception as e:
            if self.debug_mode:
                print(f"🔧 调试模式: 音频预初始化失败: {e}")
    
    def _load_config(self):
        """加载配置"""
        from ..config import load_config
        config = load_config()
        
        # 语音功能开关
        self.voice_enabled = config.get('voice_enabled', False)
        self.debug_mode = config.get('debug_mode', False)
        
        # 强制启用调试模式
        self.debug_mode = True
        print("🔧 调试模式已强制启用")
        
        # 在控制台版本中强制启用调试模式
        import sys
        if hasattr(sys, 'frozen') and hasattr(sys, '_MEIPASS'):
            # 这是打包后的版本
            self.debug_mode = True
            print("🔧 检测到打包版本，已自动启用调试模式")
        
        # 语音唤醒配置
        self.voice_wakeup_enabled = config.get('voice_wakeup_enabled', False)
        
        # 语音识别配置
        self.voice_asr_enabled = config.get('voice_asr_enabled', False)
        self.asr_token = config.get('asr_token', '')  # ASR使用token而不是api_key
        self.asr_appkey = config.get('asr_appkey', '')
        self.asr_url = config.get('asr_host_url', 'wss://nls-gateway.cn-shanghai.aliyuncs.com/ws/v1')
        
        # TTS配置
        self.voice_tts_enabled = config.get('voice_tts_enabled', False)
        self.tts_api_key = config.get('tts_api_key', '')
        self.tts_model = config.get('tts_model', 'cosyvoice-v3-flash')
        self.tts_voice = config.get('tts_voice', 'cosyvoice-v3-flash-anbao1-69f1b1345bb9496b9eab08e6d5462bb2')
        self.tts_url = config.get('tts_url', 'wss://nls-gateway-cn-shanghai.aliyuncs.com/ws/v1')
        self.tts_volume = config.get('tts_volume', 50)  # TTS音量 (0-100)，50为标准音量
        
        # 如果TTS API密钥存在，则启用TTS
        if self.tts_api_key and not self.voice_tts_enabled:
            self.voice_tts_enabled = True
        
        # 加载音量配置
        self.voice_volume = config.get('voice_volume', 0.8)
    
    def _initialize_modules(self):
        """初始化各个模块"""
        # 专门的DashScope导入检查
        self._check_dashscope_import()
        
        # 初始化关键词检测器
        if self.voice_wakeup_enabled:
            try:
                from .keyword_spotter import KeywordSpotter
                self.keyword_spotter = KeywordSpotter(
                    callback=self._on_keyword_detected
                )
                if self.debug_mode and not self.keyword_spotter.is_available():
                    print(f"🔧 调试模式: 关键词检测器不可用")
                    self.keyword_spotter = None
                elif self.debug_mode:
                    print(f"🔧 调试模式: 关键词检测器初始化成功")
            except Exception as e:
                if self.debug_mode:
                    print(f"🔧 调试模式: 关键词检测器初始化失败: {e}")
                self.keyword_spotter = None
        
        # 初始化语音识别
        if self.voice_asr_enabled:
            try:
                from .voice_recognition import VoiceRecognition
                self.voice_recognition = VoiceRecognition(
                    on_result=self._on_speech_result,
                    on_error=self._on_speech_error,
                    on_start=self._on_speech_start,
                    on_stop=self._on_speech_stop
                )
                if self.debug_mode and not self.voice_recognition.is_available():
                    print(f"🔧 调试模式: 语音识别模块不可用")
                    print(f"🔧 调试模式: asr_token: {'已配置' if self.asr_token else '未配置'}")
                    print(f"🔧 调试模式: asr_appkey: {'已配置' if self.asr_appkey else '未配置'}")
                    self.voice_recognition = None
                elif self.debug_mode:
                    print(f"🔧 调试模式: 语音识别模块初始化成功")
            except Exception as e:
                if self.debug_mode:
                    print(f"🔧 调试模式: 语音识别模块初始化失败: {e}")
                self.voice_recognition = None
        
        # 初始化TTS
        if self.voice_tts_enabled:
            self._init_tts_module()
        
        return True
    
    def _check_dashscope_import(self):
        """专门的DashScope导入检查方法"""
        global dashscope
        
        if self.debug_mode:
            print(f"🔧 调试模式: 开始专门的DashScope导入检查")
        
        # 尝试多种导入方式
        import sys
        import importlib
        
        # 方式1: 直接导入
        try:
            import dashscope
            globals()['dashscope'] = dashscope
            if self.debug_mode:
                print(f"🔧 调试模式: 方式1成功 - 直接导入dashscope")
                try:
                    print(f"🔧 调试模式: dashscope版本: {dashscope.__version__}")
                except:
                    print(f"🔧 调试模式: 无法获取dashscope版本")
            return
        except Exception as e1:
            if self.debug_mode:
                print(f"🔧 调试模式: 方式1失败: {e1}")
        
        # 方式2: 使用importlib
        try:
            dashscope = importlib.import_module('dashscope')
            globals()['dashscope'] = dashscope
            if self.debug_mode:
                print(f"🔧 调试模式: 方式2成功 - 使用importlib导入dashscope")
            return
        except Exception as e2:
            if self.debug_mode:
                print(f"🔧 调试模式: 方式2失败: {e2}")
        
        # 方式3: 从sys.modules查找
        if 'dashscope' in sys.modules:
            dashscope = sys.modules['dashscope']
            globals()['dashscope'] = dashscope
            if self.debug_mode:
                print(f"🔧 调试模式: 方式3成功 - 从sys.modules找到dashscope")
            return
        
        # 所有方式都失败
        if self.debug_mode:
            print(f"🔧 调试模式: 所有导入方式都失败")
            # 列出所有可用模块
            available_modules = [m for m in sys.modules.keys() if 'dash' in m.lower()]
            if available_modules:
                print(f"🔧 调试模式: 找到相关模块: {available_modules}")
            else:
                print(f"🔧 调试模式: 没有找到任何相关模块")
        dashscope = None
    
    def _init_tts_module(self):
        """初始化TTS模块"""
        try:
            if self.debug_mode:
                print(f"🔧 调试模式: 开始初始化TTS模块")
            
            if dashscope and self.tts_api_key:
                dashscope.api_key = self.tts_api_key
                if self.debug_mode:
                    print(f"🔧 调试模式: TTS模块初始化成功")
                    
                # 测试TTS模块导入
                try:
                    from dashscope.audio.tts_v2 import SpeechSynthesizer, AudioFormat
                    if self.debug_mode:
                        print(f"🔧 调试模式: TTS子模块导入成功")
                except Exception as e:
                    if self.debug_mode:
                        print(f"🔧 调试模式: TTS子模块导入失败: {e}")
            else:
                if self.debug_mode:
                    print(f"🔧 调试模式: TTS模块不可用 - dashscope: {dashscope is not None}, api_key: {bool(self.tts_api_key)}")
        except Exception as e:
            if self.debug_mode:
                print(f"🔧 调试模式: TTS模块初始化失败: {e}")
                import traceback
                traceback.print_exc()
    
    def _refresh_command_prompt(self):
        """
        刷新缓存的命令提示词
        """
        from src.config import load_config
        from src.voice.system_commands import SystemCommandProcessor
        
        # 加载配置
        config = load_config()
        custom_commands = config.get("custom_commands", {})
        
        # 获取所有命令
        command_processor = SystemCommandProcessor(self.app)
        all_commands = command_processor._get_all_commands()
        
        # 按分类整理命令
        system_commands = ["关机", "重启", "注销", "锁屏", "睡眠", "休眠"]
        app_commands = ["记事本", "计算器", "浏览器", "画图", "任务管理器", "vscode"]
        volume_commands = ["静音", "取消静音", "音量调高", "音量调低", "音量最大", "音量中等"]
        music_commands = ["播放音乐", "暂停音乐", "下一首", "上一首", "停止音乐"]
        web_commands = ["打开百度", "打开谷歌", "打开B站"]
        settings_commands = ["控制面板", "系统信息", "蓝牙设置", "显示设置", "声音设置"]
        
        # 获取自定义应用程序名称
        custom_app_commands = []
        for cmd_name, cmd_data in custom_commands.items():
            if cmd_data.get("action") == "launch_app":
                custom_app_commands.append(cmd_name)
        
        # 合并应用程序命令（包括自定义）
        all_app_commands = app_commands + custom_app_commands
        
        # 生成提示词模板
        prompt_template = """
你是一个命令解析助手，负责将用户的自然语言转换为系统命令。

用户输入: "{message}"

请分析用户意图，如果包含已知的系统操作命令，请返回以下格式的JSON：
{{"is_command": true, "command": "命令名称", "confidence": 0.9, "action": "操作类型"}}

如果不包含已知的系统操作命令，请返回：
{{"is_command": false, "command": null, "confidence": 0.0, "action": null}}

可用命令列表:
- 系统控制: {system_commands}
- 应用程序: {app_commands}
- 音量控制: {volume_commands}
- 音乐控制: {music_commands}
- 网页浏览: {web_commands}
- 系统设置: {settings_commands}
- 自定义应用程序: {custom_app_commands}

特别注意:
- 当用户提到"写东西"、"写文档"、"记笔记"等类似表达时，应该解析为"记事本"命令
- 当用户提到"算数"、"计算"等类似表达时，应该解析为"计算器"命令
- 当用户提到"上网"、"浏览网页"等类似表达时，应该解析为"浏览器"命令
- 当用户提到"打代码"、"写代码"、"编程"、"开发"等类似表达时，应该解析为"vscode"命令
- 对于自定义应用程序，请直接匹配命令名称

请只返回JSON，不要添加其他说明。
        """
        
        # 保存提示词模板（不包含具体消息）
        self._cached_command_prompt = prompt_template
    
    def start(self):
        """启动语音助手"""
        if not self.voice_enabled:
            return False
        
        if self.is_running:
            return True
        
        self.is_running = True
        
        # 启动关键词检测
        if self.keyword_spotter and self.voice_wakeup_enabled:
            try:
                self.keyword_spotter.start_listening_async()
            except Exception as e:
                if self.debug_mode:
                    print(f"🔧 调试模式: 启动关键词检测失败: {e}")
                pass
        
        return True
    
    def stop(self):
        """停止语音助手"""
        if not self.is_running:
            return True
        
        self.is_running = False
        
        # 停止关键词检测
        if self.keyword_spotter:
            try:
                self.keyword_spotter.stop_listening()
            except Exception as e:
                pass
        
        # 停止语音识别
        if self.voice_recognition:
            try:
                self.voice_recognition.stop_recording()
            except Exception as e:
                pass
        
        return True
    
    def _start_recording_with_timeout(self):
        """开始录音，并启动超时检测线程"""
        import threading
        import time
        
        # 启动超时检测线程
        self.sound_detection_active = True
        self.sound_detection_thread = threading.Thread(target=self._monitor_sound_timeout, daemon=True)
        self.sound_detection_thread.start()
        
        # 开始录音
        self.start_voice_recognition()
        
        if self.debug_mode:
            print(f"🔧 调试模式: 开始录音，启动{self.sound_timeout}秒超时检测")
    
    def _monitor_sound_timeout(self):
        """监控录音过程中的声音，如果超时未检测到声音则掐断ASR请求"""
        try:
            import numpy as np
            import pyaudio
            import time
            
            # 音频参数
            FORMAT = pyaudio.paInt16
            CHANNELS = 1
            RATE = 16000
            CHUNK = 1024
            
            # 音量阈值（可根据实际情况调整）
            THRESHOLD = 500
            
            audio = pyaudio.PyAudio()
            stream = audio.open(format=FORMAT, channels=CHANNELS,
                              rate=RATE, input=True,
                              frames_per_buffer=CHUNK)
            
            sound_detected = False
            start_time = time.time()
            
            if self.debug_mode:
                print(f"🔧 调试模式: 开始监控录音声音，超时时间: {self.sound_timeout}秒")
            
            while self.sound_detection_active and (time.time() - start_time) < self.sound_timeout:
                try:
                    data = stream.read(CHUNK, exception_on_overflow=False)
                    audio_data = np.frombuffer(data, dtype=np.int16)
                    volume = np.abs(audio_data).mean()
                    
                    if volume > THRESHOLD:
                        sound_detected = True
                        if self.debug_mode:
                            print(f"🔧 调试模式: 检测到声音，音量: {volume}")
                        break
                        
                except Exception as e:
                    if self.debug_mode:
                        print(f"🔧 调试模式: 声音监控异常: {e}")
                    break
            
            # 清理资源
            stream.stop_stream()
            stream.close()
            audio.terminate()
            
            # 如果超时且未检测到声音，掐断ASR请求
            if not sound_detected and self.sound_detection_active:
                if self.debug_mode:
                    print(f"🔧 调试模式: {self.sound_timeout}秒内未检测到声音，掐断ASR请求")
                
                # 显示超时提示
                if hasattr(self.app, 'speech_bubble'):
                    try:
                        self.app.speech_bubble.show("未检测到声音，请重试~ 😊", duration=2000)
                    except Exception as e:
                        pass
                
                # 停止语音识别
                self.stop_voice_recognition()
            
        except Exception as e:
            if self.debug_mode:
                print(f"🔧 调试模式: 声音监控初始化失败: {e}")
    
    def _on_keyword_detected(self, keyword: str):
        """关键词检测回调"""
        print(f"\n🎯 检测到关键词: {keyword}")
        
        if self.debug_mode:
            print(f"🔧 调试模式: 关键词检测完成")
            print(f"🔧 调试模式: 语音识别状态: {'可用' if self.voice_recognition else '不可用'}")
            if self.voice_recognition:
                print(f"🔧 调试模式: 语音识别可用性: {self.voice_recognition.is_available()}")
        
        # 显示唤醒动画或文字
        if hasattr(self.app, 'speech_bubble'):
            try:
                self.app.speech_bubble.show("我在听~ 🎤", duration=2000)
            except Exception as e:
                if self.debug_mode:
                    print(f"🔧 调试模式: 显示唤醒提示失败: {e}")
                pass
        
        # 直接开始录音，同时启动声音监控
        if self.voice_recognition:
            try:
                self._start_recording_with_timeout()
                if self.debug_mode:
                    print(f"🔧 调试模式: 录音和声音监控已启动")
            except Exception as e:
                if self.debug_mode:
                    print(f"🔧 调试模式: 启动录音失败: {e}")
                pass

    
    def _on_speech_start(self):
        """语音识别开始回调"""
        self.is_listening = True
        
        if self.debug_mode:
            print(f"🔧 调试模式: 语音识别已开始")
        
        # 显示正在听的动画
        if hasattr(self.app, 'speech_bubble'):
            try:
                self.app.speech_bubble.show("正在听... 🎧", duration=None)
                if self.debug_mode:
                    print(f"🔧 调试模式: 正在听提示已显示")
            except Exception as e:
                if self.debug_mode:
                    print(f"🔧 调试模式: 显示正在听提示失败: {e}")
                pass

    def _on_speech_stop(self):
        """语音识别停止回调"""
        self.is_listening = False
        
        # 显示思考中动画
        if hasattr(self.app, 'speech_bubble'):
            try:
                self.app.speech_bubble.show("思考中... 💭", duration=None)
            except Exception as e:
                pass
    
    def _on_speech_result(self, result: str):
        """语音识别结果回调"""
        print(f"\n🎯 语音识别结果: {result}")
        
        if self.debug_mode:
            print(f"🔧 调试模式: 语音识别完成")
            print(f"🔧 AI聊天状态: {'可用' if hasattr(self.app, 'ai_chat') and self.app.ai_chat else '不可用'}")
        
        # 发送给AI处理
        if hasattr(self.app, 'ai_chat') and self.app.ai_chat:
            try:
                if self.debug_mode:
                    print(f"🔧 调试模式: 开始发送给AI处理")
                self._send_to_ai(result)
                if self.debug_mode:
                    print(f"🔧 调试模式: 已发送给AI处理")
            except Exception as e:
                if self.debug_mode:
                    print(f"🔧 调试模式: 发送给AI处理失败: {e}")
                pass
        else:
            if self.debug_mode:
                print(f"🔧 调试模式: AI聊天功能不可用")
            if hasattr(self.app, 'speech_bubble'):
                try:
                    self.app.speech_bubble.show("AI功能未启用哦~", duration=3000)
                    if self.debug_mode:
                        print(f"🔧 调试模式: AI未启用提示已显示")
                except Exception as e:
                    if self.debug_mode:
                        print(f"🔧 调试模式: 显示AI未启用提示失败: {e}")
                    pass
    
    def _on_speech_error(self, error: str):
        """语音识别错误回调"""
        # 显示错误信息
        if hasattr(self.app, 'speech_bubble'):
            self.app.speech_bubble.show(f"识别出错了: {error}", duration=3000)
    
    def _on_speech_start(self):
        """语音识别开始回调"""
        if self.debug_mode:
            print(f"🔧 调试模式: 语音识别已开始")
    
    def _on_speech_stop(self):
        """语音识别停止回调"""
        if self.debug_mode:
            print(f"🔧 调试模式: 语音识别已停止")
    
    def _on_silence_detected(self):
        """静音检测回调 - API VAD触发"""
        if self.debug_mode:
            print(f"🔧 调试模式: API检测到静音，ASR已停止")
        
        # 显示提示信息
        if hasattr(self.app, 'speech_bubble'):
            try:
                self.app.speech_bubble.show("没听到声音，请再说一次~", duration=2000)
                if self.debug_mode:
                    print(f"🔧 调试模式: 静音提示已显示")
            except Exception as e:
                if self.debug_mode:
                    print(f"🔧 调试模式: 显示静音提示失败: {e}")
                pass
        
        # 延迟后重新启动语音识别
        import threading
        def restart_recognition():
            import time
            time.sleep(1)  # 等待1秒
            try:
                if self.debug_mode:
                    print(f"🔧 调试模式: 尝试重新启动语音识别")
                if self.voice_recognition and not self.voice_recognition.is_recording:
                    self.start_voice_recognition()
                    if self.debug_mode:
                        print(f"🔧 调试模式: 语音识别重新启动成功")
            except Exception as e:
                if self.debug_mode:
                    print(f"🔧 调试模式: 重新启动语音识别失败: {e}")
        
        restart_thread = threading.Thread(target=restart_recognition, daemon=True)
        restart_thread.start()
    
    def _on_silence_detected(self):
        """静音检测回调"""
        if self.debug_mode:
            print(f"🔧 调试模式: 检测到静音，准备重新启动语音识别")
        
        # 延迟一小段时间后重新启动语音识别
        def restart_recognition():
            time.sleep(0.5)  # 等待500ms
            if self.is_running and self.voice_recognition:
                try:
                    self.voice_recognition.start_recording()
                    if self.debug_mode:
                        print(f"🔧 调试模式: 语音识别已重新启动")
                except Exception as e:
                    if self.debug_mode:
                        print(f"🔧 调试模式: 重新启动语音识别失败: {e}")
        
        # 在后台线程中执行重启
        threading.Thread(target=restart_recognition, daemon=True).start()
    
    def _generate_command_prompt(self, message: str) -> str:
        """
        生成命令解析提示词
        
        Args:
            message: 用户语音消息
            
        Returns:
            命令解析提示词
        """
        from src.config import load_config
        config = load_config()
        custom_commands = config.get("custom_commands", {})
        
        # 获取自定义应用程序名称
        custom_app_commands = []
        for cmd_name, cmd_data in custom_commands.items():
            if cmd_data.get("action") == "launch_app":
                custom_app_commands.append(cmd_name)
        
        # 合并应用程序命令（包括自定义）
        all_app_commands = ["记事本", "计算器", "浏览器", "画图", "任务管理器", "vscode"] + custom_app_commands
        
        # 生成提示词
        prompt = f"""
你是一个命令解析助手，负责将用户的自然语言转换为系统命令。

用户输入: "{message}"

请分析用户意图，如果包含已知的系统操作命令，请返回以下格式的JSON：
{{"is_command": true, "command": "命令名称", "confidence": 0.9, "action": "操作类型"}}

如果不包含已知的系统操作命令，请返回：
{{"is_command": false, "command": null, "confidence": 0.0, "action": null}}

可用命令列表:
- 系统控制: 关机, 重启, 注销, 锁屏, 睡眠, 休眠
- 应用程序: {', '.join(all_app_commands)}
- 音量控制: 静音, 取消静音, 音量调高, 音量调低, 音量最大, 音量中等
- 音乐控制: 播放音乐, 暂停音乐, 下一首, 上一首, 停止音乐
- 网页浏览: 打开百度, 打开谷歌, 打开B站
- 系统设置: 控制面板, 系统信息, 蓝牙设置, 显示设置, 声音设置

请只返回JSON，不要添加其他说明。
        """
        
        return prompt
    
    def _send_to_ai(self, message: str):
        """发送消息给AI"""
        # 使用命令分析器分析消息
        from src.voice.command_analyzer import CommandAnalyzer
        
        # 创建LLM回调函数
        def llm_callback(msg: str):
            # 构建命令分析提示词
            command_prompt = self._generate_command_prompt(msg)
            
            # 调用LLM API
            try:
                if hasattr(self.app, 'ai_chat') and self.app.ai_chat:
                    # 临时切换到命令解析模式
                    original_personality = self.app.ai_chat.current_personality
                    self.app.ai_chat.current_personality = "command_parser"
                    
                    # 使用事件来同步异步调用
                    import threading
                    result_container = {}
                    event = threading.Event()
                    
                    def on_response(response: str):
                        # 清理响应，移除可能的markdown标记
                        clean_response = response.strip()
                        if clean_response.startswith('```json'):
                            clean_response = clean_response[7:]  # 移除'```json'
                        if clean_response.endswith('```'):
                            clean_response = clean_response[:-3]  # 移除'```'
                        clean_response = clean_response.strip()
                        
                        try:
                            import json
                            parsed_result = json.loads(clean_response)
                            result_container['result'] = LLMResult(
                                is_command=parsed_result.get("is_command", False),
                                command=parsed_result.get("command"),
                                confidence=parsed_result.get("confidence", 0.0),
                                action=parsed_result.get("action"),
                                raw_response=response
                            )
                        except json.JSONDecodeError:
                            result_container['result'] = LLMResult(
                                is_command=False,
                                command=None,
                                confidence=0.0,
                                action=None,
                                raw_response=response
                            )
                        
                        event.set()
                    
                    def on_error(error: str):
                        result_container['result'] = LLMResult(
                            is_command=False,
                            command=None,
                            confidence=0.0,
                            action=None,
                            raw_response=f"LLM调用错误: {error}"
                        )
                        event.set()
                    
                    # 发送给AI引擎进行命令解析
                    self.app.ai_chat.send_message(
                        message=command_prompt,
                        on_response=on_response,
                        on_error=on_error
                    )
                    
                    # 等待结果（最多等待5秒）
                    if event.wait(timeout=5.0):
                        # 恢复原始人设
                        self.app.ai_chat.current_personality = original_personality
                        return result_container.get('result', LLMResult(
                            is_command=False,
                            command=None,
                            confidence=0.0,
                            action=None,
                            raw_response="等待超时"
                        ))
                    else:
                        # 超时处理
                        self.app.ai_chat.current_personality = original_personality
                        return LLMResult(
                            is_command=False,
                            command=None,
                            confidence=0.0,
                            action=None,
                            raw_response="等待超时"
                        )
                
                # 返回默认结果
                return LLMResult(
                    is_command=False,
                    command=None,
                    confidence=0.0,
                    action=None,
                    raw_response="LLM调用失败"
                )
                
            except Exception as e:
                return LLMResult(
                    is_command=False,
                    command=None,
                    confidence=0.0,
                    action=None,
                    raw_response=f"LLM调用错误: {str(e)}"
                )
        
        analyzer = CommandAnalyzer(self.app, llm_callback)
        result = analyzer.analyze_message(message)
        
        if self.debug_mode:
            print(f"🔧 调试模式: 命令分析结果 - 类型: {result.type}, 命令: {result.command}, 置信度: {result.confidence}")
        
        # 根据分析结果处理
        if result.type == "exact_command":
            # 精确匹配的命令，直接执行
            print(f"🔧 调试模式: _send_to_ai - exact_command 执行命令: {result.command}")
            success = self._execute_command_with_feedback(result.command, result.action, result.details)
            print(f"🔧 调试模式: _send_to_ai - exact_command 命令执行结果: {success}")
            # 如果执行失败，弹出修改或删除弹窗
            if not success:
                print(f"🔧 调试模式: _send_to_ai - exact_command 命令执行失败，准备显示修复对话框")
                self._show_command_fix_dialog(message, result)
                print(f"🔧 调试模式: _send_to_ai - exact_command 已调用显示修复对话框")
        elif result.type == "fuzzy_command":
            # 模糊匹配的命令，检查是否在预设列表中
            print(f"🔧 调试模式: _send_to_ai - fuzzy_command 检查命令: {result.command}")
            is_known_command = self._is_known_command(result.command)
            print(f"🔧 调试模式: _send_to_ai - fuzzy_command 命令是否已知: {is_known_command}")
            if is_known_command:
                # 已知命令，直接执行
                print(f"🔧 调试模式: _send_to_ai - fuzzy_command 执行已知命令: {result.command}")
                success = self._execute_command_with_feedback(result.command, result.action, result.details)
                print(f"🔧 调试模式: _send_to_ai - fuzzy_command 命令执行结果: {success}")
                # 如果执行失败，弹出修改或删除弹窗
                if not success:
                    print(f"🔧 调试模式: _send_to_ai - fuzzy_command 命令执行失败，准备显示修复对话框")
                    self._show_command_fix_dialog(message, result)
                    print(f"🔧 调试模式: _send_to_ai - fuzzy_command 已调用显示修复对话框")
            else:
                # 未知命令，询问用户是否添加
                self._show_command_confirmation_dialog(message, result)
        elif result.type == "potential_command":
            # 潜在命令，询问用户确认
            self._show_command_confirmation_dialog(message, result)
        elif result.type == "llm_command":
            # LLM识别的命令，根据置信度决定
            if result.confidence > 0.7:
                success = self._execute_command_with_feedback(result.command, result.action, result.details)
                # 如果执行失败，弹出修改或删除弹窗
                if not success:
                    self._show_command_fix_dialog(message, result)
            else:
                self._show_command_confirmation_dialog(message, result)
        else:
            # 普通对话
            print(f"\n📤 发送消息给AI: {message}")
            self._send_to_ai_for_chat(message)
    
    def _send_to_llm_for_command_parsing(self, message: str):
        """发送消息给LLM进行命令解析"""
        # 构建命令解析提示
        command_prompt = self._generate_command_prompt(message)
        
        def on_command_parsed(response: str):
            """处理LLM解析结果"""
            if self.debug_mode:
                print(f"🔧 调试模式: LLM命令解析原始响应: {response}")
                
            # 清理响应，移除可能的markdown标记
            clean_response = response.strip()
            if clean_response.startswith('```json'):
                clean_response = clean_response[7:]  # 移除'```json'
            if clean_response.endswith('```'):
                clean_response = clean_response[:-3]  # 移除'```'
            clean_response = clean_response.strip()
            
            # 始终在控制台显示JSON回复
            if self.debug_mode:
                print(f"🔧 调试模式: LLM命令解析JSON回复: {clean_response}")
            
            try:
                import json
                result = json.loads(clean_response)
                
                if self.debug_mode:
                    print(f"🔧 调试模式: LLM命令解析JSON结果: {result}")
                
                if result.get("command") and result.get("confidence", 0) > 0.7:
                    # 置信度足够高，执行命令
                    command = result["command"]
                    from src.voice.system_commands import SystemCommandProcessor
                    command_processor = SystemCommandProcessor(self.app)
                    
                    if self.debug_mode:
                        print(f"🔧 调试模式: 执行命令: {command}")
                    
                    # 直接执行命令
                    if command_processor.execute_command_by_name(command, original_command):
                        if hasattr(self.app, 'speech_bubble'):
                            self.app.speech_bubble.show(f"正在执行: {command}~", duration=2000)
                    else:
                        if hasattr(self.app, 'speech_bubble'):
                            self.app.speech_bubble.show(f"无法识别的命令: {command}", duration=3000)
                else:
                    # 不是命令或置信度不够，作为普通对话处理
                    if self.debug_mode:
                        print(f"🔧 调试模式: 未识别为命令，转为普通对话")
                    print(f"\n📤 发送消息给AI: {message}")
                    self._send_to_ai_for_chat(message)
                    
            except json.JSONDecodeError as e:
                # JSON解析失败，作为普通对话处理
                if self.debug_mode:
                    print(f"🔧 调试模式: JSON解析失败: {e}")
                print(f"\n📤 发送消息给AI: {message}")
                self._send_to_ai_for_chat(message)
        
        def on_parse_error(error: str):
            """处理解析错误"""
            # 解析失败，作为普通对话处理
            print(f"\n📤 发送消息给AI: {message}")
            self._send_to_ai_for_chat(message)
        
        # 发送给AI引擎进行命令解析
        if hasattr(self.app, 'ai_chat') and self.app.ai_chat:
            # 临时切换到命令解析模式
            original_personality = self.app.ai_chat.current_personality
            self.app.ai_chat.current_personality = "command_parser"
            
            # 发送命令解析请求，不使用流式回复和TTS
            def on_stream_token(token: str):
                # 命令解析不需要流式处理
                pass
            
            # 发送命令解析请求
            self.app.ai_chat.send_message(
                command_prompt,
                on_response=on_command_parsed,
                on_error=on_parse_error,
                on_stream_token=on_stream_token  # 空的流式处理函数
            )
            
            # 恢复原始人设
            self.app.ai_chat.current_personality = original_personality
        else:
            # AI不可用，作为普通对话处理
            print(f"\n📤 发送消息给AI: {message}")
            self._send_to_ai_for_chat(message)
    
    def _send_to_ai_for_chat(self, message: str):
        """发送消息给AI进行普通对话"""
        # 流式回复相关
        self.stream_response = ""
        self.is_streaming = True
        self.tts_synthesizer = None  # 存储TTS合成器
        
        def on_stream_token(token: str):
            """收到流式token"""
            if not self.is_streaming:
                return
                
            self.stream_response += token
            print(token, end="", flush=True)
            
            # 检查是否是JSON响应，如果是则不发送到TTS
            response_so_far = self.stream_response.strip()
            is_json_response = False
            
            # 简单检查是否是JSON响应
            if response_so_far.startswith('```json') or response_so_far.startswith('{'):
                is_json_response = True
            
            # 直接进行TTS合成，基于云端版1.0的架构
            if self.voice_tts_enabled and self.tts_api_key and not is_json_response:
                # 尝试导入dashscope（如果尚未导入）
                try:
                    import dashscope
                    if self.debug_mode:
                        print(f"🔧 调试模式: dashscope导入成功")
                except ImportError as e:
                    if self.debug_mode:
                        print(f"🔧 调试模式: dashscope导入失败: {e}")
                    dashscope = None
                
                if dashscope:
                    try:
                        # 懒加载TTS，只在需要时初始化
                        if not self.tts_synthesizer:
                            if self.debug_mode:
                                print(f"🔧 调试模式: 懒初始化TTS")
                            self._init_streaming_tts()
                        
                        if self.tts_synthesizer:
                            # 直接发送token到TTS，不需要缓冲
                            if self.debug_mode and len(token.strip()) > 0:  # 只对非空token输出
                                print(f"🔧 调试模式: 发送TTS token: '{token.strip()}' (长度: {len(token)})")
                            self.tts_synthesizer.streaming_call(token)
                        else:
                            if self.debug_mode:
                                print(f"🔧 调试模式: TTS合成器未初始化，跳过TTS")
                    except Exception as e:
                        if self.debug_mode:
                            print(f"🔧 调试模式: 流式TTS调用失败: {e}")
                            import traceback
                            traceback.print_exc()
                else:
                    if self.debug_mode and len(token.strip()) > 0:  # 只对非空token输出
                        print(f"🔧 调试模式: dashscope不可用，跳过TTS")
            else:
                if self.debug_mode and len(token.strip()) > 0:  # 只对非空token输出
                    print(f"🔧 调试模式: TTS未启用或配置不完整，跳过TTS")
                    print(f"   voice_tts_enabled: {self.voice_tts_enabled}")
                    print(f"   tts_api_key: {'已配置' if self.tts_api_key else '未配置'}")
            
            # 实时更新对话框
            if hasattr(self.app, 'speech_bubble'):
                try:
                    # 显示当前累积的回复
                    self.app.speech_bubble.show(self.stream_response, duration=None)
                except Exception as e:
                    pass
        
        def on_response(response: str):
            """收到完整回复"""
            print(f"\n📥 AI回复: {response}")
            self.is_streaming = False
            
            if self.debug_mode:
                print(f"🔧 调试模式: AI回复完成")
            
            # 完成流式TTS
            if self.tts_synthesizer:
                try:
                    self.tts_synthesizer.streaming_complete()
                    if self.debug_mode:
                        print(f"🔧 调试模式: 流式TTS完成")
                except Exception as e:
                    if self.debug_mode:
                        print(f"🔧 调试模式: 流式TTS完成失败: {e}")
            
            # 检查是否是JSON响应，如果是则不显示在对话框中
            is_json_response = False
            clean_response = response.strip()
            if clean_response.startswith('```json') or clean_response.startswith('{'):
                is_json_response = True
            
            # 显示完整回复（仅对非JSON响应）
            if hasattr(self.app, 'speech_bubble') and not is_json_response:
                try:
                    self.app.speech_bubble.show(response, duration=5000)
                    if self.debug_mode:
                        print(f"🔧 调试模式: AI回复已显示")
                except Exception as e:
                    if self.debug_mode:
                        print(f"🔧 调试模式: 显示AI回复失败: {e}")
                    pass
        
        def on_error(error_msg: str):
            """处理错误"""
            self.is_streaming = False
            
            if hasattr(self.app, 'speech_bubble'):
                try:
                    self.app.speech_bubble.show(error_msg, duration=3000)
                except Exception as e:
                    pass
        
        try:
            # 检查是否支持流式回复
            if hasattr(self.app.ai_chat, 'send_message'):
                # 检查send_message是否支持on_stream_token参数
                import inspect
                sig = inspect.signature(self.app.ai_chat.send_message)
                if 'on_stream_token' in sig.parameters:
                    # 支持流式回复
                    self.app.ai_chat.send_message(message, on_response, on_error, on_stream_token)
                else:
                    # 不支持流式回复，使用普通模式
                    self.app.ai_chat.send_message(message, on_response, on_error)
            else:
                pass
        except Exception as e:
            pass
    
    def _init_streaming_tts(self):
        """初始化流式TTS，基于云端版1.0的架构"""
        try:
            # 尝试导入dashscope
            try:
                import dashscope
                if self.debug_mode:
                    print(f"🔧 调试模式: _init_streaming_tts中dashscope导入成功")
            except ImportError as e:
                if self.debug_mode:
                    print(f"🔧 调试模式: _init_streaming_tts中dashscope导入失败: {e}")
                raise
                
            from dashscope.audio.tts_v2 import SpeechSynthesizer, AudioFormat
            
            # 创建回调实例，使用独立线程播放音频避免阻塞主线程
            import threading
            import queue
            
            class TtsCallback:
                def __init__(self, debug_mode=False):
                    self._player = None
                    self._stream = None
                    self.debug_mode = debug_mode
                    self.audio_queue = queue.Queue()
                    self.play_thread = None
                    self.stop_playing = False
                
                def on_open(self):
                    """WebSocket连接成功时调用的回调方法"""
                    if self.debug_mode:
                        print(f"🔧 调试模式: TTS WebSocket连接已建立")
                    
                    # 初始化PyAudio播放器
                    try:
                        import pyaudio
                        self._player = pyaudio.PyAudio()
                        # 使用更大的缓冲区减少音频卡顿
                        self._stream = self._player.open(
                            format=pyaudio.paInt16,
                            channels=1,
                            rate=22050,
                            output=True,
                            frames_per_buffer=1024  # 增加缓冲区大小
                        )
                        
                        # 启动音频播放线程
                        self.stop_playing = False
                        self.play_thread = threading.Thread(target=self._play_audio_worker, daemon=True)
                        self.play_thread.start()
                        
                    except Exception as e:
                        if self.debug_mode:
                            print(f"🔧 调试模式: 音频播放器初始化失败: {e}")
                
                def on_complete(self):
                    """语音合成任务成功完成时调用的回调方法"""
                    if self.debug_mode:
                        print(f"🔧 调试模式: 语音合成任务已完成")
                
                def on_error(self, message: str):
                    """语音合成任务出错时调用的回调方法"""
                    if self.debug_mode:
                        print(f"🔧 调试模式: 语音合成任务失败：{message}")
                
                def on_close(self):
                    """WebSocket连接关闭时调用的回调方法"""
                    if self.debug_mode:
                        print(f"🔧 调试模式: TTS WebSocket连接已关闭")
                    
                    # 等待队列中所有音频数据播放完成
                    try:
                        # 等待队列为空，表示所有数据都已处理
                        self.audio_queue.join()
                        if self.debug_mode:
                            print(f"🔧 调试模式: 所有音频数据已播放完成")
                    except Exception as e:
                        if self.debug_mode:
                            print(f"🔧 调试模式: 等待音频播放完成失败: {e}")
                    
                    # 停止播放线程
                    self.stop_playing = True
                    if self.play_thread and self.play_thread.is_alive():
                        self.play_thread.join(timeout=2.0)
                    
                    # 停止音频播放并释放资源
                    try:
                        if self._stream and self._player:
                            self._stream.stop_stream()
                            self._stream.close()
                            self._player.terminate()
                    except Exception as e:
                        if self.debug_mode:
                            print(f"🔧 调试模式: 音频播放器清理失败: {e}")
                
                def on_event(self, message):
                    """接收到语音合成事件消息时调用的回调方法"""
                    if self.debug_mode:
                        print(f"🔧 调试模式: 收到语音合成消息：{message}")
                
                def on_data(self, data: bytes) -> None:
                    """接收到音频数据时调用的回调方法"""
                    # 将音频数据放入队列，由独立线程处理播放
                    if data:
                        data_size = len(data)
                        if self.debug_mode:
                            print(f"🔧 调试模式: 收到音频数据: {data_size} 字节")
                        try:
                            # 使用阻塞方式放入队列，确保数据不丢失
                            self.audio_queue.put(data, block=True, timeout=1.0)
                            if self.debug_mode:
                                print(f"🔧 调试模式: 音频数据已放入队列，当前队列大小: {self.audio_queue.qsize()}")
                        except queue.Full:
                            if self.debug_mode:
                                print(f"🔧 调试模式: 音频队列已满，丢弃 {data_size} 字节数据")
                    else:
                        if self.debug_mode:
                            print(f"🔧 调试模式: 收到空音频数据")
                
                def _play_audio_worker(self):
                    """音频播放工作线程，从队列中取出数据并播放"""
                    total_bytes_played = 0
                    chunks_played = 0
                    
                    while not self.stop_playing:
                        try:
                            # 从队列中获取音频数据，使用较长的超时确保音频连续
                            data = self.audio_queue.get(timeout=0.5)
                            if self._stream and data:
                                data_size = len(data)
                                total_bytes_played += data_size
                                chunks_played += 1
                                
                                if self.debug_mode and chunks_played % 50 == 0:  # 每50个块输出一次
                                    print(f"🔧 调试模式: 已播放 {chunks_played} 个音频块, 总计 {total_bytes_played} 字节")
                                
                                self._stream.write(data)
                            self.audio_queue.task_done()
                        except queue.Empty:
                            # 队列为空，继续循环
                            continue
                        except Exception as e:
                            if self.debug_mode:
                                print(f"🔧 调试模式: 音频播放失败: {e}")
                    
                    if self.debug_mode:
                        print(f"🔧 调试模式: 音频播放线程结束, 总共播放了 {chunks_played} 个音频块, {total_bytes_played} 字节")
            
            callback = TtsCallback(debug_mode=self.debug_mode)
            
            # 初始化语音合成器，基于云端版1.0的配置
            if self.debug_mode:
                print(f"🔧 调试模式: 初始化TTS合成器 - 模型: {self.tts_model}, 音色: {self.tts_voice}")
                print(f"🔧 调试模式: TTS音量: {self.tts_volume}")
                print(f"🔧 调试模式: TTS API密钥: {'已配置' if self.tts_api_key else '未配置'}")
            
            self.tts_synthesizer = SpeechSynthesizer(
                model=self.tts_model,
                voice=self.tts_voice,
                format=AudioFormat.PCM_22050HZ_MONO_16BIT,
                callback=callback,
                volume=self.tts_volume,
            )
            
            if self.debug_mode:
                print(f"🔧 调试模式: TTS合成器创建成功")
                
        except Exception as e:
            if self.debug_mode:
                print(f"🔧 调试模式: 初始化流式TTS失败: {e}")
                import traceback
                traceback.print_exc()
            self.tts_synthesizer = None
        
    
    def _text_to_speech(self, text: str):
        """文本转语音，基于云端版1.0的简化实现"""
        if not dashscope or not self.tts_api_key:
            if self.debug_mode:
                print(f"🔧 调试模式: TTS不可用 - dashscope: {dashscope is not None}, api_key: {bool(self.tts_api_key)}")
            return
            
        try:
            if self.debug_mode:
                print(f"🔧 调试模式: 开始TTS合成")
            from dashscope.audio.tts_v2 import SpeechSynthesizer, AudioFormat
            
            # 创建回调实例，使用独立线程播放音频避免阻塞主线程
            import threading
            import queue
            
            class TtsCallback:
                def __init__(self, debug_mode=False):
                    self._player = None
                    self._stream = None
                    self.debug_mode = debug_mode
                    self.audio_queue = queue.Queue()
                    self.play_thread = None
                    self.stop_playing = False
                
                def on_open(self):
                    """WebSocket连接成功时调用的回调方法"""
                    if self.debug_mode:
                        print(f"🔧 调试模式: TTS WebSocket连接已建立")
                    
                    # 初始化PyAudio播放器
                    try:
                        import pyaudio
                        self._player = pyaudio.PyAudio()
                        # 使用更大的缓冲区减少音频卡顿
                        self._stream = self._player.open(
                            format=pyaudio.paInt16,
                            channels=1,
                            rate=22050,
                            output=True,
                            frames_per_buffer=1024  # 增加缓冲区大小
                        )
                        
                        # 启动音频播放线程
                        self.stop_playing = False
                        self.play_thread = threading.Thread(target=self._play_audio_worker, daemon=True)
                        self.play_thread.start()
                        
                    except Exception as e:
                        if self.debug_mode:
                            print(f"🔧 调试模式: 音频播放器初始化失败: {e}")
                
                def on_complete(self):
                    """语音合成任务成功完成时调用的回调方法"""
                    if self.debug_mode:
                        print(f"🔧 调试模式: 语音合成任务已完成")
                
                def on_error(self, message: str):
                    """语音合成任务出错时调用的回调方法"""
                    if self.debug_mode:
                        print(f"🔧 调试模式: 语音合成任务失败：{message}")
                
                def on_close(self):
                    """WebSocket连接关闭时调用的回调方法"""
                    if self.debug_mode:
                        print(f"🔧 调试模式: TTS WebSocket连接已关闭")
                    
                    # 等待队列中所有音频数据播放完成
                    try:
                        # 等待队列为空，表示所有数据都已处理
                        self.audio_queue.join()
                        if self.debug_mode:
                            print(f"🔧 调试模式: 所有音频数据已播放完成")
                    except Exception as e:
                        if self.debug_mode:
                            print(f"🔧 调试模式: 等待音频播放完成失败: {e}")
                    
                    # 停止播放线程
                    self.stop_playing = True
                    if self.play_thread and self.play_thread.is_alive():
                        self.play_thread.join(timeout=2.0)
                    
                    # 停止音频播放并释放资源
                    try:
                        if self._stream and self._player:
                            self._stream.stop_stream()
                            self._stream.close()
                            self._player.terminate()
                    except Exception as e:
                        if self.debug_mode:
                            print(f"🔧 调试模式: 音频播放器清理失败: {e}")
                
                def on_event(self, message):
                    """接收到语音合成事件消息时调用的回调方法"""
                    if self.debug_mode:
                        print(f"🔧 调试模式: 收到语音合成消息：{message}")
                
                def on_data(self, data: bytes) -> None:
                    """接收到音频数据时调用的回调方法"""
                    # 将音频数据放入队列，由独立线程处理播放
                    if data:
                        try:
                            # 使用阻塞方式放入队列，确保数据不丢失
                            self.audio_queue.put(data, block=True, timeout=1.0)
                        except queue.Full:
                            if self.debug_mode:
                                print(f"🔧 调试模式: 音频队列已满，丢弃数据")
                
                def _play_audio_worker(self):
                    """音频播放工作线程，从队列中取出数据并播放"""
                    while not self.stop_playing:
                        try:
                            # 从队列中获取音频数据，使用较长的超时确保音频连续
                            data = self.audio_queue.get(timeout=0.5)
                            if self._stream and data:
                                # 应用音量控制
                                if self.voice_volume < 1.0:
                                    # 使用更简单的方法控制音量，不依赖numpy
                                    import struct
                                    # 将字节数据转换为16位整数列表
                                    samples = struct.unpack('<' + 'h' * (len(data) // 2), data)
                                    # 应用音量
                                    samples = [int(s * self.voice_volume) for s in samples]
                                    # 转换回字节数据
                                    data = struct.pack('<' + 'h' * len(samples), *samples)
                                
                                self._stream.write(data)
                            self.audio_queue.task_done()
                        except queue.Empty:
                            # 队列为空，继续循环
                            continue
                        except Exception as e:
                            if self.debug_mode:
                                print(f"🔧 调试模式: 音频播放失败: {e}")
                    
            
            callback = TtsCallback(debug_mode=self.debug_mode)
                
            # 初始化语音合成器，基于云端版1.0的配置
            if self.debug_mode:
                print(f"🔧 调试模式: 初始化TTS合成器 - 模型: {self.tts_model}, 音色: {self.tts_voice}")
            synthesizer = SpeechSynthesizer(
                model=self.tts_model,
                voice=self.tts_voice,
                format=AudioFormat.PCM_22050HZ_MONO_16BIT,
                callback=callback,
                volume=self.tts_volume,
            )
            
            # 发送文本进行合成，基于云端版1.0的方式
            if self.debug_mode:
                print(f"🔧 调试模式: 发送文本进行TTS合成 - 长度: {len(text)}")
            synthesizer.streaming_call(text)
            synthesizer.streaming_complete()
            if self.debug_mode:
                print(f"🔧 调试模式: TTS合成完成")
            
        except Exception as e:
            if self.debug_mode:
                print(f"🔧 调试模式: TTS合成失败: {e}")
            pass
    
    def _execute_command_with_feedback(self, command: str, action: str, details: Optional[dict] = None) -> bool:
        """
        执行命令并返回是否成功
        
        Args:
            command: 命令名称
            action: 操作类型
            details: 额外详情
            
        Returns:
            如果执行成功返回True，否则返回False
        """
        from src.voice.system_commands import SystemCommandProcessor
        command_processor = SystemCommandProcessor(self.app)
        
        try:
            print(f"🔧 调试模式: _execute_command_with_feedback 开始执行命令: {command}, 动作: {action}")
            # 统一使用execute_command_by_name方法
            # 检查是否是"动作+目标"组合，如果是，传递原始命令
            original_command = command
            for action_word in ["打开", "启动", "运行", "关闭", "退出", "结束"]:
                if command.startswith(action_word):
                    # 已经是完整命令，直接传递
                    break
            
            success = command_processor.execute_command_by_name(command, original_command)
            print(f"🔧 调试模式: _execute_command_with_feedback 命令执行结果: {success}")
            if success:
                if hasattr(self.app, 'speech_bubble'):
                    self.app.speech_bubble.show(f"正在执行: {command}~", duration=2000)
                return True
            else:
                return False
        except Exception as e:
            if hasattr(self.app, 'speech_bubble'):
                self.app.speech_bubble.show(f"执行命令失败: {str(e)}", duration=3000)
            return False
    
    def _execute_command(self, command: str, action: str, details: Optional[dict] = None):
        """
        执行命令
        
        Args:
            command: 命令名称
            action: 操作类型
            details: 额外详情
        """
        from src.voice.system_commands import SystemCommandProcessor
        command_processor = SystemCommandProcessor(self.app)
        
        try:
            if action == "custom_command" and details:
                # 自定义命令
                if command_processor.execute_custom_command(command):
                    if hasattr(self.app, 'speech_bubble'):
                        self.app.speech_bubble.show(f"正在执行自定义命令: {command}~", duration=2000)
                else:
                    if hasattr(self.app, 'speech_bubble'):
                        self.app.speech_bubble.show(f"无法执行自定义命令: {command}", duration=3000)
            else:
                # 预设命令
                if command_processor.execute_command_by_name(command):
                    if hasattr(self.app, 'speech_bubble'):
                        self.app.speech_bubble.show(f"正在执行: {command}~", duration=2000)
                else:
                    if hasattr(self.app, 'speech_bubble'):
                        self.app.speech_bubble.show(f"无法识别的命令: {command}", duration=3000)
        except Exception as e:
            if self.debug_mode:
                print(f"🔧 调试模式: 执行命令失败: {str(e)}")
            if hasattr(self.app, 'speech_bubble'):
                self.app.speech_bubble.show(f"执行命令失败: {str(e)}", duration=3000)
    
    def _show_command_confirmation_dialog(self, message: str, result):
        """
        显示命令确认对话框
        
        Args:
            message: 用户原始消息
            result: 分析结果
        """
        try:
            import tkinter as tk
            from tkinter import messagebox, filedialog
            
            # 获取主窗口
            root = None
            if hasattr(self.app, 'root'):
                root = self.app.root
            elif hasattr(self.app, 'window'):
                root = self.app.window
            
            # 检查命令是否在预设列表中
            is_known_command = self._is_known_command(result.command)
            
            # 创建对话框
            print(f"🔧 调试模式: 创建对话框，is_known_command={is_known_command}")
            dialog = tk.Toplevel(root) if root else tk.Toplevel()
            if is_known_command:
                dialog.title("命令确认")
                dialog.geometry("400x270")
            else:
                dialog.title("添加新命令")
                dialog.geometry("530x400")
            
            dialog.resizable(False, False)
            if root:
                dialog.transient(root)
            dialog.grab_set()
            dialog.configure(bg="#FFF5F8")
            
            print(f"🔧 调试模式: 对话框已创建，标题={dialog.title()}")
            
            # 强制显示对话框
            dialog.lift()
            dialog.attributes('-topmost', True)
            dialog.after(100, lambda: dialog.attributes('-topmost', False))
            
            # 标题
            title_frame = tk.Frame(dialog, bg="#FF69B4", height=45)
            title_frame.pack(fill=tk.X)
            title_frame.pack_propagate(False)
            
            title_text = "命令确认" if is_known_command else "添加新命令"
            tk.Label(
                title_frame,
                text=title_text,
                bg="#FF69B4",
                fg="white",
                font=("Microsoft YaHei", 12, "bold"),
            ).pack(side=tk.LEFT, padx=15, pady=10)
            
            # 内容区域
            content_frame = tk.Frame(dialog, bg="#FFF5F8")
            content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
            
            if is_known_command:
                # 已知命令的确认界面
                # 说明
                tk.Label(
                    content_frame,
                    text=f"检测到可能的命令: {message}",
                    bg="#FFF5F8",
                    fg="#5C3B4A",
                    font=("Microsoft YaHei", 10, "bold"),
                    anchor="w"
                ).pack(fill=tk.X, pady=(0, 5))
                
                tk.Label(
                    content_frame,
                    text=f"建议执行: {result.command}",
                    bg="#FFF5F8",
                    fg="#5C3B4A",
                    font=("Microsoft YaHei", 10),
                    anchor="w"
                ).pack(fill=tk.X, pady=(0, 10))
                
                tk.Label(
                    content_frame,
                    text="是否执行此命令？",
                    bg="#FFF5F8",
                    fg="#5C3B4A",
                    font=("Microsoft YaHei", 10),
                    anchor="w"
                ).pack(fill=tk.X, pady=(0, 10))
                
                # 按钮区域
                button_frame = tk.Frame(content_frame, bg="#FFF5F8")
                button_frame.pack(fill=tk.X, pady=(10, 0))
                
                def confirm_command():
                    """确认执行命令"""
                    self._execute_command(result.command, result.action, result.details)
                    dialog.destroy()
                
                def cancel_command():
                    """取消命令"""
                    # 作为普通对话处理
                    print(f"\n📤 发送消息给AI: {message}")
                    self._send_to_ai_for_chat(message)
                    dialog.destroy()
                
                # 按钮
                tk.Button(
                    button_frame,
                    text="确认",
                    bg="#FF69B4",
                    fg="white",
                    font=("Microsoft YaHei", 10),
                    borderwidth=0,
                    padx=20,
                    pady=5,
                    cursor="hand2",
                    command=confirm_command
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
                    command=cancel_command
                ).pack(side=tk.RIGHT)
                
                # 居中显示
                dialog.update_idletasks()
                x = (dialog.winfo_screenwidth() // 2) - (400 // 2)
                y = (dialog.winfo_screenheight() // 2) - (270 // 2)
                dialog.geometry(f"+{x}+{y}")
            else:
                # 未知命令的添加界面
                # 说明
                tk.Label(
                    content_frame,
                    text=f"检测到新命令: {result.command}",
                    bg="#FFF5F8",
                    fg="#5C3B4A",
                    font=("Microsoft YaHei", 10, "bold"),
                    anchor="w"
                ).pack(fill=tk.X, pady=(0, 5))
                
                tk.Label(
                    content_frame,
                    text="此命令不在预设列表中，是否要添加到命令列表？",
                    bg="#FFF5F8",
                    fg="#5C3B4A",
                    font=("Microsoft YaHei", 10),
                    anchor="w"
                ).pack(fill=tk.X, pady=(0, 10))
                
                # 命令类型选择
                type_frame = tk.Frame(content_frame, bg="#FFF5F8")
                type_frame.pack(fill=tk.X, pady=(0, 5))
                
                tk.Label(
                    type_frame,
                    text="命令类型:",
                    bg="#FFF5F8",
                    fg="#5C3B4A",
                    font=("Microsoft YaHei", 10),
                    width=10,
                    anchor="w"
                ).pack(side=tk.LEFT)
                
                type_var = tk.StringVar(value="launch_app")
                type_combo = tk.ttk.Combobox(
                    type_frame,
                    textvariable=type_var,
                    values=["launch_app", "system_setting", "web_search", "media_control"],
                    state="readonly",
                    width=15
                )
                type_combo.pack(side=tk.LEFT, padx=(5, 0))
                
                # 命令路径/参数
                param_frame = tk.Frame(content_frame, bg="#FFF5F8")
                param_frame.pack(fill=tk.X, pady=(0, 5))
                
                tk.Label(
                    param_frame,
                    text="执行路径/参数:",
                    bg="#FFF5F8",
                    fg="#5C3B4A",
                    font=("Microsoft YaHei", 10),
                    width=12,
                    anchor="w"
                ).pack(side=tk.LEFT)
                
                param_var = tk.StringVar()
                param_entry = tk.Entry(
                    param_frame,
                    textvariable=param_var,
                    width=40,
                    font=("Microsoft YaHei", 9)
                )
                param_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
                
                def browse_file():
                    """浏览文件"""
                    try:
                        file_path = filedialog.askopenfilename(
                            title=f"选择{result.command}可执行文件",
                            filetypes=[("可执行文件", "*.exe"), ("所有文件", "*.*")],
                            parent=dialog
                        )
                        if file_path:
                            param_var.set(file_path)
                    except Exception as e:
                        print(f"文件选择器错误: {str(e)}")
                        if hasattr(self.app, 'speech_bubble'):
                            self.app.speech_bubble.show(f"文件选择失败: {str(e)}", duration=3000)
                
                # 按钮区域
                button_frame = tk.Frame(content_frame, bg="#FFF5F8")
                button_frame.pack(fill=tk.X, pady=(10, 0))
                
                def add_command():
                    """添加新命令"""
                    command_name = result.command.strip()
                    command_type = type_var.get()
                    command_param = param_var.get().strip()
                    
                    if not command_name:
                        messagebox.showerror("错误", "请输入命令名称", parent=dialog)
                        return
                    
                    if not command_param:
                        messagebox.showerror("错误", "请输入执行路径/参数", parent=dialog)
                        return
                    
                    # 保存到配置文件
                    from src.config import update_config, load_config
                    config = load_config()
                    custom_commands = config.get("custom_commands", {})
                    
                    custom_commands[command_name] = {
                        "action": command_type,
                        "params": {"path": command_param} if command_type == "launch_app" else command_param,
                        "confidence": 0.8,
                        "created_at": "",
                        "usage_count": 0
                    }
                    
                    update_config(custom_commands=custom_commands)
                    
                    # 刷新命令提示词
                    self._refresh_command_prompt()
                    
                    if hasattr(self.app, 'speech_bubble'):
                        self.app.speech_bubble.show(f"已添加新命令: {command_name}", duration=3000)
                    
                    # 关闭当前对话框
                    dialog.destroy()
                    
                    # 直接执行命令
                    print(f"🔧 调试模式: 命令确认对话框 - 开始执行新添加的命令: {command_name}")
                    success = self._execute_command_with_feedback(command_name, command_type, custom_commands[command_name])
                    print(f"🔧 调试模式: 命令确认对话框 - 新命令执行结果: {success}")
                    
                    # 如果执行失败，弹出修复对话框
                    if not success:
                        print(f"🔧 调试模式: 命令确认对话框 - 新命令执行失败，准备显示修复对话框")
                        # 创建一个临时结果对象
                        class TempResult:
                            def __init__(self, command):
                                self.command = command
                        
                        temp_result = TempResult(command_name)
                        self._show_command_fix_dialog(message, temp_result)
                        print(f"🔧 调试模式: 命令确认对话框 - 已调用显示修复对话框")
                
                def cancel_dialog():
                    """取消对话框"""
                    # 作为普通对话处理
                    print(f"\n📤 发送消息给AI: {message}")
                    self._send_to_ai_for_chat(message)
                    dialog.destroy()
                
                # 按钮
                tk.Button(
                    button_frame,
                    text="添加并执行",
                    bg="#FF69B4",
                    fg="white",
                    font=("Microsoft YaHei", 10),
                    borderwidth=0,
                    padx=20,
                    pady=5,
                    cursor="hand2",
                    command=add_command
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
                ).pack(side=tk.RIGHT, padx=(0, 5))
                
                # 浏览按钮
                tk.Button(
                    button_frame,
                    text="浏览...",
                    bg="#87CEEB",
                    fg="white",
                    font=("Microsoft YaHei", 10),
                    borderwidth=0,
                    padx=15,
                    pady=5,
                    cursor="hand2",
                    command=browse_file
                ).pack(side=tk.LEFT)
                
                # 居中显示
                dialog.update_idletasks()
                x = (dialog.winfo_screenwidth() // 2) - (530 // 2)
                y = (dialog.winfo_screenheight() // 2) - (400 // 2)
                dialog.geometry(f"+{x}+{y}")
            
        except Exception as e:
            # 如果无法创建对话框，作为普通对话处理
            print(f"无法显示命令确认对话框: {str(e)}")
            print(f"\n📤 发送消息给AI: {message}")
            self._send_to_ai_for_chat(message)
    
    def _show_command_fix_dialog(self, message: str, result):
        """
        显示命令修复对话框
        
        Args:
            message: 用户语音消息
            result: 命令分析结果
        """
        try:
            import tkinter as tk
            from tkinter import messagebox, filedialog
            
            # 获取主窗口
            root = None
            if hasattr(self.app, 'root'):
                root = self.app.root
            elif hasattr(self.app, 'window'):
                root = self.app.window
            
            # 创建对话框
            dialog = tk.Toplevel(root) if root else tk.Toplevel()
            dialog.title("修复命令")
            dialog.geometry("550x350")
            
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
                text="修复命令",
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
                text=f"命令 '{result.command}' 执行失败",
                bg="#FFF5F8",
                fg="#5C3B4A",
                font=("Microsoft YaHei", 10, "bold"),
                anchor="w"
            ).pack(fill=tk.X, pady=(0, 5))
            
            tk.Label(
                content_frame,
                text="请选择修复方式：",
                bg="#FFF5F8",
                fg="#5C3B4A",
                font=("Microsoft YaHei", 10),
                anchor="w"
            ).pack(fill=tk.X, pady=(0, 10))
            
            # 命令路径/参数
            param_frame = tk.Frame(content_frame, bg="#FFF5F8")
            param_frame.pack(fill=tk.X, pady=(0, 5))
            
            tk.Label(
                param_frame,
                text="执行路径/参数:",
                bg="#FFF5F8",
                fg="#5C3B4A",
                font=("Microsoft YaHei", 10),
                width=12,
                anchor="w"
            ).pack(side=tk.LEFT)
            
            param_var = tk.StringVar()
            param_entry = tk.Entry(
                param_frame,
                textvariable=param_var,
                width=50,
                font=("Microsoft YaHei", 9)
            )
            param_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
            
            def browse_file():
                """浏览文件"""
                try:
                    file_path = filedialog.askopenfilename(
                        title=f"选择{result.command}可执行文件",
                        filetypes=[("可执行文件", "*.exe"), ("所有文件", "*.*")],
                        parent=dialog
                    )
                    if file_path:
                        param_var.set(file_path)
                except Exception as e:
                    if hasattr(self.app, 'speech_bubble'):
                        self.app.speech_bubble.show(f"文件选择失败: {str(e)}", duration=3000)
            
            # 按钮区域
            button_frame = tk.Frame(content_frame, bg="#FFF5F8")
            button_frame.pack(fill=tk.X, pady=(10, 0))
            
            def fix_command():
                """修复命令"""
                command_name = result.command.strip()
                command_param = param_var.get().strip()
                
                if not command_param:
                    messagebox.showerror("错误", "请输入执行路径/参数", parent=dialog)
                    return
                
                # 保存到配置文件
                from src.config import update_config, load_config
                config = load_config()
                custom_commands = config.get("custom_commands", {})
                
                custom_commands[command_name] = {
                    "action": "launch_app",
                    "params": {"path": command_param},
                    "confidence": 0.8,
                    "created_at": "",
                    "usage_count": 0
                }
                
                update_config(custom_commands=custom_commands)
                
                # 刷新命令提示词
                self._refresh_command_prompt()
                
                if hasattr(self.app, 'speech_bubble'):
                    self.app.speech_bubble.show(f"已修复命令: {command_name}", duration=3000)
                
                # 关闭当前对话框
                dialog.destroy()
                
                # 直接执行命令
                print(f"🔧 调试模式: 修复对话框 - 开始执行修复后的命令: {command_name}")
                success = self._execute_command_with_feedback(command_name, "custom_command", custom_commands[command_name])
                print(f"🔧 调试模式: 修复对话框 - 修复后命令执行结果: {success}")
                
                # 如果执行失败，再次弹出修复对话框
                if not success:
                    print(f"🔧 调试模式: 修复对话框 - 修复后命令仍然执行失败，准备再次显示修复对话框")
                    # 创建一个临时结果对象
                    class TempResult:
                        def __init__(self, command):
                            self.command = command
                    
                    temp_result = TempResult(command_name)
                    self._show_command_fix_dialog(message, temp_result)
            
            def delete_command():
                """删除命令"""
                if messagebox.askyesno("确认", f"确定要删除命令 '{result.command}' 吗？", parent=dialog):
                    # 从配置中删除命令
                    from src.config import update_config, load_config
                    config = load_config()
                    custom_commands = config.get("custom_commands", {})
                    
                    if result.command in custom_commands:
                        del custom_commands[result.command]
                        update_config(custom_commands=custom_commands)
                    
                    if hasattr(self.app, 'speech_bubble'):
                        self.app.speech_bubble.show(f"已删除命令: {result.command}", duration=3000)
                    
                    dialog.destroy()
            
            def cancel_dialog():
                """取消对话框"""
                dialog.destroy()
            
            # 按钮
            tk.Button(
                button_frame,
                text="浏览...",
                bg="#87CEEB",
                fg="white",
                font=("Microsoft YaHei", 10),
                borderwidth=0,
                padx=20,
                pady=5,
                cursor="hand2",
                command=browse_file
            ).pack(side=tk.LEFT, padx=(0, 5))
            
            tk.Button(
                button_frame,
                text="修复并执行",
                bg="#FF69B4",
                fg="white",
                font=("Microsoft YaHei", 10),
                borderwidth=0,
                padx=20,
                pady=5,
                cursor="hand2",
                command=fix_command
            ).pack(side=tk.RIGHT, padx=(0, 5))
            
            tk.Button(
                button_frame,
                text="删除命令",
                bg="#FF6B6B",
                fg="white",
                font=("Microsoft YaHei", 10),
                borderwidth=0,
                padx=20,
                pady=5,
                cursor="hand2",
                command=delete_command
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
            x = (dialog.winfo_screenwidth() // 2) - (550 // 2)
            y = (dialog.winfo_screenheight() // 2) - (350 // 2)
            dialog.geometry(f"+{x}+{y}")
            
            # 强制显示对话框
            dialog.lift()
            dialog.attributes('-topmost', True)
            dialog.after(100, lambda: dialog.attributes('-topmost', False))
            
        except Exception as e:
            # 如果无法创建对话框，作为普通对话处理
            print(f"无法显示命令修复对话框: {str(e)}")
            print(f"\n📤 发送消息给AI: {message}")
            self._send_to_ai_for_chat(message)
    
    def _is_known_command(self, command: str) -> bool:
        """
        检查命令是否在预设列表中
        
        Args:
            command: 命令名称
            
        Returns:
            如果是已知命令返回True，否则返回False
        """
        if not command:
            return False
        
        # 检查系统命令
        from src.voice.command_analyzer import CommandAnalyzer
        analyzer = CommandAnalyzer(self.app)
        
        if command in analyzer.system_commands:
            return True
        
        # 检查应用程序命令
        if command in analyzer.app_keywords:
            return True
        
        # 检查自定义命令
        from src.config import load_config
        config = load_config()
        custom_commands = config.get("custom_commands", {})
        
        # 首先检查完整命令
        if command in custom_commands:
            return True
        
        # 检查是否是"动作+目标"组合（如"打开微信"）
        for action_word in ["打开", "启动", "运行"]:
            if command.startswith(action_word):
                target = command[len(action_word):].strip()
                # 检查目标是否在应用程序关键词中
                if target in analyzer.app_keywords:
                    return True
                # 检查目标是否在自定义命令中
                if target in custom_commands:
                    return True
        
        return False
    
    def start_voice_recognition(self):
        """手动开始语音识别"""
        if not self.voice_recognition:
            print(f"❌ 语音识别模块不可用")
            if self.debug_mode:
                print(f"🔧 调试模式: 语音识别模块不可用")
            return False
        
        print(f"🎤 调用语音识别start_recording方法...")
        if self.debug_mode:
            print(f"🔧 调试模式: 调用语音识别start_recording方法")
        result = self.voice_recognition.start_recording()
        print(f"🎤 语音识别start_recording结果: {result}")
        if self.debug_mode:
            print(f"🔧 调试模式: 语音识别start_recording结果: {result}")
        return result
    
    def stop_voice_recognition(self):
        """手动停止语音识别"""
        # 停止声音监控
        self.sound_detection_active = False
        
        if not self.voice_recognition:
            return False
        
        return self.voice_recognition.stop_recording()
    
    def toggle_voice_assistant(self):
        """切换语音助手状态"""
        if self.is_running:
            return self.stop()
        else:
            return self.start()
    

    
    def is_available(self) -> bool:
        """检查语音助手是否可用"""
        return self.voice_enabled and (
            (self.keyword_spotter and self.keyword_spotter.is_available()) or
            (self.voice_recognition and self.voice_recognition.is_available())
        )
    
    def set_tts_volume(self, volume: int) -> None:
        """设置TTS音量
        
        Args:
            volume: 音量值 (0-100)，50为标准音量
        """
        # 确保音量在有效范围内
        volume = max(0, min(100, volume))
        self.tts_volume = volume
        
        # 保存到配置
        from ..config import update_config
        update_config(tts_volume=volume)
        
        # 重新初始化TTS合成器以应用新音量
        self._init_streaming_tts()
    
    def get_tts_volume(self) -> int:
        """获取当前TTS音量
        
        Returns:
            当前音量值 (0-100)
        """
        return self.tts_volume
    
    def test_tts(self, text="这是一个测试"):
        """测试TTS功能
        
        参数:
            text: 测试文本
        """
        if self.debug_mode:
            print(f"🔧 调试模式: 开始TTS测试，测试文本: {text}")
        
        if not self.voice_tts_enabled:
            if self.debug_mode:
                print(f"🔧 调试模式: TTS未启用，无法测试")
            return False
        
        try:
            import dashscope
            if not dashscope or not self.tts_api_key:
                if self.debug_mode:
                    print(f"🔧 调试模式: TTS配置不完整，无法测试")
                return False
            
            # 设置API密钥
            dashscope.api_key = self.tts_api_key
            
            # 初始化TTS（如果尚未初始化）
            if not self.tts_synthesizer:
                self._init_streaming_tts()
            
            if not self.tts_synthesizer:
                if self.debug_mode:
                    print(f"🔧 调试模式: TTS合成器初始化失败，无法测试")
                return False
            
            if self.debug_mode:
                print(f"🔧 调试模式: TTS合成器已准备就绪，开始测试...")
            
            # 这里只是测试合成器是否可用，不实际调用API
            if self.debug_mode:
                print(f"🔧 调试模式: TTS测试通过（合成器可用）")
            
            return True
            
        except Exception as e:
            if self.debug_mode:
                print(f"🔧 调试模式: TTS测试失败: {e}")
                import traceback
                traceback.print_exc()
            return False
    
    def _refresh_command_prompt(self):
        """刷新命令提示词"""
        try:
            # 重新加载配置以获取最新的自定义命令
            from src.config import load_config
            config = load_config()
            custom_commands = config.get("custom_commands", {})
            
            # 如果AI聊天模块可用，刷新其命令提示词
            if hasattr(self.app, 'ai_chat') and self.app.ai_chat:
                # 重新生成命令提示词
                command_list = []
                
                # 添加系统命令
                from src.voice.command_analyzer import CommandAnalyzer
                analyzer = CommandAnalyzer(self.app)
                command_list.extend(list(analyzer.system_commands.keys()))
                command_list.extend(list(analyzer.app_keywords.keys()))
                
                # 添加自定义命令
                command_list.extend(list(custom_commands.keys()))
                
                # 更新AI聊天模块的命令提示词
                if hasattr(self.app.ai_chat, 'update_command_prompts'):
                    self.app.ai_chat.update_command_prompts(command_list)
                
                if self.debug_mode:
                    print(f"🔧 调试模式: 命令提示词已刷新，共 {len(command_list)} 个命令")
        except Exception as e:
            if self.debug_mode:
                print(f"🔧 调试模式: 刷新命令提示词失败: {e}")
    
    def cleanup(self):
        """清理资源"""
        self.stop()
        
        if self.keyword_spotter:
            self.keyword_spotter.cleanup()
        
        if self.voice_recognition:
            self.voice_recognition.cleanup()