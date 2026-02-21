"""语音识别模块

基于阿里云ASR的语音识别引擎
"""

import json
import threading
import time
from queue import Queue, Empty
from datetime import datetime
from typing import Optional, Callable, Dict

try:
    import nls
except ImportError:
    print("请先安装阿里云NLS SDK: pip install alibabacloud-nls")
    nls = None

try:
    import pyaudio
except ImportError:
    print("请先安装pyaudio: pip install pyaudio")
    pyaudio = None

import numpy as np

from src.config import load_config


class VoiceRecognition:
    """
    语音识别引擎类
    
    基于阿里云ASR的语音识别服务
    """
    
    def __init__(self, 
                 on_result: Optional[Callable[[str], None]] = None,
                 on_error: Optional[Callable[[str], None]] = None,
                 on_start: Optional[Callable[[], None]] = None,
                 on_stop: Optional[Callable[[], None]] = None):
        """
        初始化语音识别引擎
        
        参数:
            on_result: 识别结果回调函数
            on_error: 错误回调函数
            on_start: 开始识别回调函数
            on_stop: 停止识别回调函数
        """
        self.on_result = on_result
        self.on_error = on_error
        self.on_start = on_start
        self.on_stop = on_stop

        
        # 录音相关
        self.audio_interface = None
        self.stream = None
        self.is_recording = False
        self.recording_thread = None
        
        # 识别相关
        self.transcriber = None
        self.is_processing = False
        self.is_connected = False
        self._start_callback_received = False
        self.audio_queue = Queue()
        self.processing_thread = None
        
        # 识别结果
        self.final_results = []
        self.current_final_result = ""
        self.intermediate_result = ""
        
        # 音频参数
        self.sample_rate = 16000
        self.channels = 1
        self.format = pyaudio.paInt16 if pyaudio else 8
        self.chunk_size = 1600
        
        # 录音时间限制
        self.max_recording_time = 10
        
        # 加载配置
        self._load_config()
        
        # 初始化ASR引擎
        self._initialize_asr()
    
    def _load_config(self):
        """加载配置"""
        config = load_config()
        
        self.appkey = config.get("asr_appkey", "")
        self.token = config.get("asr_token", "")
        self.host_url = config.get("asr_host_url", "wss://nls-gateway.cn-shanghai.aliyuncs.com/ws/v1")
    
    def _initialize_asr(self):
        """初始化ASR引擎"""
        print(f"\n=== ASR引擎初始化检查 ===")
        print(f"nls库: {'已安装' if nls else '未安装'}")
        print(f"pyaudio库: {'已安装' if pyaudio else '未安装'}")
        print(f"appkey: {'已配置' if self.appkey else '未配置'}")
        print(f"token: {'已配置' if self.token else '未配置'}")
        
        if not nls:
            print("❌ 阿里云NLS SDK未安装")
            print("请运行: pip install alibabacloud-nls")
            return
            
        if not pyaudio:
            print("❌ PyAudio未安装")
            print("请运行: pip install pyaudio")
            return
            
        if not self.appkey or not self.token:
            print("❌ ASR配置不完整")
            if not self.appkey:
                print("  - 缺少appkey")
            if not self.token:
                print("  - 缺少token")
            print("请在配置中设置asr_appkey和asr_token")
            print("\n🔧 当前ASR配置:")
            print(f"  asr_appkey: {'已配置' if self.appkey else '未配置'}")
            print(f"  asr_token: {'已配置' if self.token else '未配置'}")
            return
        
        try:
            # 初始化PyAudio
            if not self.audio_interface:
                self.audio_interface = pyaudio.PyAudio()
                print("✅ PyAudio初始化成功")
            else:
                print("✅ PyAudio已初始化")
            
            print("✅ ASR引擎初始化成功")
        except Exception as e:
            import traceback
            print(f"❌ ASR引擎初始化失败: {e}")
            traceback.print_exc()
    
    def _on_start(self, message, *args):
        """内部：连接/识别开始回调"""
        print(f"ASR开始: {message}")
        self._start_callback_received = True
        self.is_connected = True
        if self.on_start:
            self.on_start()
    
    def _on_sentence_begin(self, message, *args):
        """内部：检测到一句话开始"""
        print(f"检测到语音开始: {message}")
    
    def _on_sentence_end(self, message, *args):
        """内部：检测到一句话结束（VAD触发）"""
        try:
            data = json.loads(message)
            result = data['payload'].get('result', '')
            if result:
                self.current_final_result = result
                self.final_results.append(result)
                print(f"识别到最终结果: {result}")
                
                if self.on_result:
                    self.on_result(result)
            else:
                # 没有识别到结果
                print("未识别到语音")
            
            # VAD结束录音
            if self.is_recording:
                self.stop_recording()
        except Exception as e:
            print(f"处理_on_sentence_end时出错: {e}")
    
    def _on_completed(self, message, *args):
        """内部：整个识别任务完成"""
        print(f"ASR完成: {message}")
        self.is_connected = False
    
    def _on_speech_end(self, message, *args):
        """内部：检测到语音结束（API VAD触发）"""
        try:
            data = json.loads(message)
            # 检查是否是因为静音结束
            if 'payload' in data and data['payload'].get('status') == 'silence':
                print("API检测到静音，未识别到语音")
                if self.on_silence_detected:
                    self.on_silence_detected()
        except Exception as e:
            print(f"处理_on_speech_end时出错: {e}")
    
    def _on_error(self, message, *args):
        """内部：错误处理回调"""
        self.is_connected = False
        
        try:
            error_data = json.loads(message) if isinstance(message, str) else message
            status_text = error_data.get('header', {}).get('status_text', 'Unknown error')
            
            if 'timeout' in status_text.lower():
                print(f"ASR连接因超时断开: {status_text}")
            else:
                print(f"ASR引擎发生错误: {message}")
                if self.on_error:
                    self.on_error(f"ASR错误: {status_text}")
        except Exception as e:
            print(f"ASR引擎发生无法解析的错误: {message}, 解析异常: {e}")
            if self.on_error:
                self.on_error("ASR识别发生错误")
    
    def _on_result_changed(self, message, *args):
        """内部：中间结果回调"""
        try:
            data = json.loads(message)
            result = data['payload'].get('result', '')
            if result:
                self.intermediate_result = result
        except Exception as e:
            print(f"处理_on_result_changed时出错: {e}")
    
    def _process_audio_queue(self):
        """处理音频队列的线程函数"""
        print("开始音频处理线程")
        while self.is_processing:
            try:
                audio_data = self.audio_queue.get(timeout=0.1)
                if self.transcriber and self.is_connected and audio_data:
                    self.transcriber.send_audio(audio_data)
                self.audio_queue.task_done()
            except Empty:
                continue
            except Exception as e:
                print(f"音频处理线程错误: {e}")
                break
        print("音频处理线程结束")
    
    def _recording_worker(self):
        """录音工作线程 - 只依赖API的VAD回调"""
        if not self.audio_interface or not self.stream:
            print("音频接口或流未初始化")
            return
            
        try:
            print("开始录音工作线程")
            while self.is_recording:
                # 读取音频数据
                try:
                    audio_data = self.stream.read(self.chunk_size, exception_on_overflow=False)
                    
                    # 将音频数据放入队列，由处理线程发送到ASR
                    self.audio_queue.put(audio_data)
                    
                except Exception as e:
                    print(f"读取音频数据失败: {e}")
                    break
                
                time.sleep(0.01)
        except Exception as e:
            print(f"录音工作线程发生异常: {e}")
        finally:
            print("录音工作线程结束")
            self._cleanup_stream()
    
    def _cleanup_stream(self):
        """清理音频流"""
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception as e:
                print(f"清理音频流时出错: {e}")
            finally:
                self.stream = None
    

    
    def connect(self):
        """启动与阿里云服务的连接"""
        if not nls:
            print("阿里云NLS SDK未安装")
            return False
            
        if self.is_connected:
            print("连接已存在")
            return True
        
        if not self.appkey or not self.token:
            print("ASR配置不完整")
            return False
        
        print("开始建立新连接...")
        self._start_callback_received = False
        
        try:
            # 创建NlsSpeechTranscriber实例
            self.transcriber = nls.NlsSpeechTranscriber(
                url=self.host_url,
                token=self.token,
                appkey=self.appkey,
                on_start=self._on_start,
                on_sentence_begin=self._on_sentence_begin,
                on_sentence_end=self._on_sentence_end,
                on_completed=self._on_completed,
                on_error=self._on_error,
                on_result_changed=self._on_result_changed,
            )
            
            # 启动识别会话
            start_invocation_result = self.transcriber.start(
                aformat="pcm",
                sample_rate=16000,
                enable_intermediate_result=True,
                enable_punctuation_prediction=True,
                enable_inverse_text_normalization=True
            )
            
            # 等待on_start回调确认连接真正建立
            wait_start = time.time()
            while time.time() - wait_start < 3:
                if self._start_callback_received:
                    self.is_connected = True
                    print("连接确认成功")
                    return True
                time.sleep(0.1)
            
            # 如果超时仍未收到回调
            print("等待连接就绪超时")
            if self.transcriber:
                self.transcriber.stop()
            self.transcriber = None
            return False
        
        except Exception as e:
            print(f"连接过程中发生异常: {e}")
            return False
    
    def disconnect(self):
        """停止连接并清理资源"""
        if not self.transcriber:
            print("识别器实例不存在，无需停止")
            self.is_connected = False
            self.is_processing = False
            return
        
        print("正在停止识别器连接...")
        
        def _stop_transcriber():
            try:
                if self.transcriber:
                    self.transcriber.stop(timeout=2)
                    print("识别器连接停止成功")
            except Exception as e:
                print(f"在停止线程中捕获到异常: {e}")
            finally:
                self.transcriber = None
        
        stop_thread = threading.Thread(target=_stop_transcriber)
        stop_thread.daemon = True
        stop_thread.start()
        
        stop_thread.join(timeout=3)
        
        if stop_thread.is_alive():
            print("警告：停止线程超时，强制放弃并清理状态")
            self.transcriber = None
        
        self.is_connected = False
        self.is_processing = False
        print("连接状态已重置")
    
    def start_recording(self):
        """开始录音"""
        if not pyaudio or not self.audio_interface:
            print("PyAudio未初始化")
            return False
            
        if self.is_recording:
            print("录音已在进行中")
            return True
        
        # 确保连接有效
        if not self.is_connected:
            if not self.connect():
                print("无法建立连接")
                return False
        
        try:
            # 打开音频流
            self.stream = self.audio_interface.open(
                format=self.format,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size,
                input_device_index=None,
            )
            print("音频流已打开")
            
            # 启动音频处理线程（先启动处理线程）
            if not self.is_processing or not self.processing_thread.is_alive():
                self.is_processing = True
                self.processing_thread = threading.Thread(target=self._process_audio_queue)
                self.processing_thread.daemon = True
                self.processing_thread.start()
                print("音频处理线程已启动")
            
            # 启动录音线程
            self.is_recording = True
            self.recording_thread = threading.Thread(target=self._recording_worker)
            self.recording_thread.daemon = True
            self.recording_thread.start()
            print("录音线程已启动")
            
            if self.on_start:
                self.on_start()
            
            print("录音已开始")
            return True
        
        except Exception as e:
            print(f"启动录音失败: {e}")
            self._cleanup_stream()
            return False
    
    def stop_recording(self):
        """停止录音"""
        if not self.is_recording:
            print("录音未在进行中")
            return True
        
        print("停止录音...")
        
        self.is_recording = False
        
        # 等待录音线程结束
        if self.recording_thread and self.recording_thread.is_alive():
            self.recording_thread.join(timeout=2.0)
        
        # 清理音频流
        self._cleanup_stream()
        
        if self.on_stop:
            self.on_stop()
        
        print("录音已停止")
        return True
    
    def get_last_result(self) -> str:
        """获取最新的一次识别结果"""
        result = self.current_final_result
        self.current_final_result = ""
        return result
    
    def get_all_results(self) -> str:
        """获取所有累积的识别结果，并清空列表"""
        combined_result = "".join(self.final_results).strip()
        self.final_results = []
        return combined_result
    
    def clear_results(self):
        """手动清空所有结果"""
        self.final_results = []
        self.current_final_result = ""
        self.intermediate_result = ""
    
    def is_available(self) -> bool:
        """检查语音识别是否可用"""
        return nls is not None and pyaudio is not None and bool(self.appkey) and bool(self.token)
    
    def cleanup(self):
        """清理资源"""
        self.stop_recording()
        self.is_processing = False
        
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=1)
        
        self.disconnect()
        
        if self.audio_interface:
            try:
                self.audio_interface.terminate()
            except Exception as e:
                print(f"终止PyAudio接口时出错: {e}")
            finally:
                self.audio_interface = None