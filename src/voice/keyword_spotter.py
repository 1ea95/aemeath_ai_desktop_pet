"""关键词检测模块

基于sherpa-onnx的关键词检测引擎
"""

import os
import sys
import threading
from pathlib import Path
from typing import Callable, Optional

try:
    import sounddevice as sd
except ImportError:

    sys.exit(-1)

try:
    import sherpa_onnx
except ImportError:

    sys.exit(-1)

from src.config import load_config


class KeywordSpotter:
    """
    关键词检测引擎类
    
    用于检测唤醒词，当检测到唤醒词时触发回调函数
    """
    
    def __init__(self, callback: Optional[Callable[[str], None]] = None):
        """
        初始化关键词检测引擎
        
        参数:
            callback: 检测到关键词时的回调函数
        """
        self.callback = callback
        self.is_running = False
        self._listening_thread: Optional[threading.Thread] = None
        
        # 检测计数器
        self.detection_count = 0
        
        # 音频参数
        self.sample_rate = 16000
        self.samples_per_read = int(0.1 * self.sample_rate)  # 100ms
        
        # 加载配置
        self._load_config()
        
        # 初始化关键词检测器
        self.keyword_spotter = None
        self._initialize_spotter()
        
        # 设备信息
        self._print_device_info()
    
    def _load_config(self):
        """加载配置"""
        config = load_config()
        
        # 获取当前脚本所在目录的绝对路径
        current_dir = Path(__file__).parent.parent.parent

        
        # 关键词检测模型路径 - 使用绝对路径
        model_dir = current_dir / "assets" / "models" / "kws"
        self.tokens_path = str(model_dir / "tokens.txt")
        self.encoder_path = str(model_dir / "encoder.onnx")
        self.decoder_path = str(model_dir / "decoder.onnx")
        self.joiner_path = str(model_dir / "joiner.onnx")
        self.keywords_file = str(model_dir / "keywords.txt")
        

        
        # 从配置中获取参数，如果没有则使用默认值
        self.keywords_score = config.get("voice_wakeup_score", 5.0)
        self.keywords_threshold = config.get("voice_wakeup_threshold", 0.05)
        
        # 如果配置中有自定义路径，则使用配置中的路径
        custom_model_path = config.get("kws_model_path", "")
        if custom_model_path and os.path.exists(custom_model_path):
            model_dir = Path(custom_model_path)
            self.tokens_path = str(model_dir / "tokens.txt")
            self.encoder_path = str(model_dir / "encoder.onnx")
            self.decoder_path = str(model_dir / "decoder.onnx")
            self.joiner_path = str(model_dir / "joiner.onnx")

        
        custom_keywords_file = config.get("kws_keywords_file", "")
        if custom_keywords_file and os.path.exists(custom_keywords_file):
            self.keywords_file = custom_keywords_file


    def _initialize_spotter(self):
        """初始化关键词检测器"""
        try:
            # 检查模型文件是否存在
            files_to_check = [
                ("tokens", self.tokens_path),
                ("encoder", self.encoder_path),
                ("decoder", self.decoder_path),
                ("joiner", self.joiner_path),
                ("keywords", self.keywords_file)
            ]
            
            missing_files = []
            for name, path in files_to_check:
                if not os.path.exists(path):
                    missing_files.append((name, path))

                else:
                    pass
            
            if missing_files:
                
                return
            
            # 检查关键词文件内容
            try:
                with open(self.keywords_file, 'r', encoding='utf-8') as f:
                    keywords_content = f.read().strip()
                    if not keywords_content:

                        return

            except Exception as e:
                return
            
            # 创建关键词检测器
            self.keyword_spotter = sherpa_onnx.KeywordSpotter(
                tokens=self.tokens_path,
                encoder=self.encoder_path,
                decoder=self.decoder_path,
                joiner=self.joiner_path,
                num_threads=1,
                max_active_paths=4,
                keywords_file=self.keywords_file,
                keywords_score=self.keywords_score,
                keywords_threshold=self.keywords_threshold,
                num_trailing_blanks=1,
                provider="cpu",
            )
            

        except Exception as e:
            import traceback

            traceback.print_exc()
            self.keyword_spotter = None
    
    def _print_device_info(self):
        """打印音频设备信息"""
        try:
            devices = sd.query_devices()
            if len(devices) == 0:

                return
            
            # 获取默认输入设备
            default_input_device_idx = sd.default.device[0]
            self.device_name = devices[default_input_device_idx]["name"]

        except Exception as e:
            pass
    
    def set_callback(self, callback: Callable[[str], None]):
        """
        设置关键词检测回调函数
        
        参数:
            callback: 回调函数，接收检测到的关键词字符串作为参数
        """
        if not callable(callback):
            raise TypeError("回调函数必须是可调用的")
        self.callback = callback
    
    def _process_audio_stream(self):
        """处理音频流的核心循环"""
        if not self.keyword_spotter:

            return
            
        stream = self.keyword_spotter.create_stream()
        
        try:
            with sd.InputStream(channels=1, dtype="float32", samplerate=self.sample_rate) as s:
                while self.is_running:
                    # 读取音频数据
                    samples, _ = s.read(self.samples_per_read)
                    samples = samples.reshape(-1)
                    
                    # 输入到检测器
                    stream.accept_waveform(self.sample_rate, samples)
                    
                    # 处理检测结果
                    while self.keyword_spotter.is_ready(stream):
                        self.keyword_spotter.decode_stream(stream)
                        result = self.keyword_spotter.get_result(stream)
                        
                        if result:
                            self.detection_count += 1
                            print(f"\n🎯 检测到关键词: {result}")
                            
                            # 调用回调函数
                            if self.callback:

                                try:
                                    self.callback(result)

                                except Exception as e:

                                    import traceback
                                    traceback.print_exc()
                            else:
                                pass
                            
                            # 重置流
                            self.keyword_spotter.reset_stream(stream)

        except Exception as e:
            import traceback
            traceback.print_exc()
    
    def start_listening(self, callback: Optional[Callable[[str], None]] = None):
        """
        开始监听麦克风（阻塞模式）
        
        参数:
            callback: 可选的回调函数，如果之前未设置则在此设置
        """
        if callback:
            self.set_callback(callback)
        
        if not self.callback:
            return
        
        if not self.keyword_spotter:
            return
            
        self.is_running = True

        
        try:
            self._process_audio_stream()
        except KeyboardInterrupt:

            self.stop_listening()
    
    def start_listening_async(self, callback: Optional[Callable[[str], None]] = None):
        """
        开始异步监听麦克风（非阻塞模式）
        
        参数:
            callback: 可选的回调函数
        """
        if callback:
            self.set_callback(callback)
            
        if self.is_running:
            return
        
        if not self.keyword_spotter:

            return
            
        self.is_running = True
        self._listening_thread = threading.Thread(target=self._process_audio_stream, daemon=True)
        self._listening_thread.start()

    
    def stop_listening(self):
        """停止监听"""
        if not self.is_running:
            return
            
        self.is_running = False
        
        if self._listening_thread and self._listening_thread.is_alive():
            self._listening_thread.join(timeout=2.0)
            

    
    def get_detection_count(self) -> int:
        """获取检测到的关键词总数"""
        return self.detection_count
    
    def is_available(self) -> bool:
        """检查关键词检测是否可用"""
        return self.keyword_spotter is not None
    
    def cleanup(self):
        """清理资源"""
        self.stop_listening()
        self.keyword_spotter = None