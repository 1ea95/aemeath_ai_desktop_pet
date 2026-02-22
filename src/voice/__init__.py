"""语音功能模块

包含语音唤醒、语音识别和语音合成功能
"""

from .voice_recognition import VoiceRecognition
from .voice_assistant import VoiceAssistant
from .keyword_spotter import KeywordSpotter
from .token_manager import TokenManager, get_token_manager, get_asr_token, setup_aliyun_credentials

__all__ = [
    "VoiceRecognition",
    "VoiceAssistant",
    "KeywordSpotter",
    "TokenManager",
    "get_token_manager",
    "get_asr_token",
    "setup_aliyun_credentials",
]