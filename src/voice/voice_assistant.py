"""语音助手模块

整合语音识别、AI对话和语音合成功能
"""

import threading
import time
from typing import Optional, Callable

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

        self.debug_mode = True
    
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
    
    def _send_to_ai(self, message: str):
        """发送消息给AI"""
        print(f"\n📤 发送消息给AI: {message}")
        
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
            
            # 直接进行TTS合成，基于云端版1.0的架构
            if self.voice_tts_enabled and self.tts_api_key:
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
            
            # 显示完整回复
            if hasattr(self.app, 'speech_bubble'):
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
    
    def cleanup(self):
        """清理资源"""
        self.stop()
        
        if self.keyword_spotter:
            self.keyword_spotter.cleanup()
        
        if self.voice_recognition:
            self.voice_recognition.cleanup()