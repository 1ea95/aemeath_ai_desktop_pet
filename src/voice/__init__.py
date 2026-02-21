"""语音功能模块

包含语音唤醒、语音识别和语音合成功能
"""

from .voice_recognition import VoiceRecognition
from .voice_assistant import VoiceAssistant
from .keyword_spotter import KeywordSpotter

__all__ = [
    "VoiceRecognition",
    "VoiceAssistant",
    "KeywordSpotter",
]