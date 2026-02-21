"""
LLM引擎模块
支持流式回复的AI对话引擎
"""

import json
import logging
import threading
import time
from typing import List, Dict, Optional, Callable, Generator

import requests

from src.config import load_config
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
)


class LLMEngine:
    """
    LLM引擎类
    支持流式回复的AI对话引擎
    """

    # 预设角色设定
    PERSONALITIES = {
        "aemeath": "爱弥斯（Aemeath）- 桌面宠物",  # 桌面宠物人设
        "default": "阿米 - 默认可爱助手",
        "helpful": "专业助手模式",
        "cute": "超萌模式",
        "tsundere": "傲娇模式",
    }

    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        if self.current_personality == "aemeath":
            return get_emys_personality()
        elif self.current_personality == "helpful":
            return "你是一个有帮助的桌面助手，名叫小爱。你专业、准确，会给出实用的建议。回答简洁明了。"
        elif self.current_personality == "cute":
            return "你是一个超级可爱的桌面宠物，名叫小爱。你说话带着萌系语气，喜欢用颜文字和emoji。回答简短可爱。"
        elif self.current_personality == "tsundere":
            return "你是一个傲娇的桌面宠物，名叫小爱。你表面冷淡但内心关心用户，说话带点傲娇语气。"
        else:
            return "你是一个可爱的桌面宠物助手，名叫小爱。你性格活泼、友善，喜欢和用户聊天。回答要简短（50字以内），带点可爱语气。"

    def __init__(self, app):
        self.app = app
        self.history = []  # 简化的历史记录
        self.is_processing = False
        self.current_personality = "aemeath"  # 默认使用爱弥斯人设
        self.logger = logging.getLogger(__name__)
        
        # 流式回复相关
        self.full_response = ""
        self.is_streaming = False
        
        self._load_config()

    def _load_config(self) -> None:
        """加载AI配置"""
        config = load_config()
        
        self.api_key = config.get("ai_api_key", "")
        self.provider = config.get("ai_provider", AI_PROVIDER_GLM)
        self.model = config.get("ai_model", "glm-4-flash")
        self.base_url = config.get("ai_base_url", "")
        
        # 清理base_url，移除可能的反引号和末尾斜杠
        if self.base_url and self.base_url.startswith('`') and self.base_url.endswith('`'):
            self.base_url = self.base_url[1:-1].strip()
        
        # 移除末尾的斜杠，避免URL拼接时出现双斜杠
        if self.base_url and self.base_url.endswith('/'):
            self.base_url = self.base_url.rstrip('/')
        
        self.enabled = config.get("ai_enabled", False)
        self.personality = config.get("ai_personality", "aemeath")
        self.current_personality = (
            self.personality if self.personality in self.PERSONALITIES else "aemeath"
        )

        # 设置默认base_url
        if not self.base_url:
            self.base_url = AI_DEFAULT_BASE_URLS.get(
                self.provider, AI_DEFAULT_BASE_URLS[AI_PROVIDER_GLM]
            )

        # 设置默认模型
        if not self.model:
            self.model = AI_DEFAULT_MODELS.get(
                self.provider, AI_DEFAULT_MODELS[AI_PROVIDER_GLM]
            )
        
        self.logger.info(f"LLM配置加载完成: {self.provider}/{self.model}")

    def is_configured(self) -> bool:
        """检查是否已配置"""
        api_key_ok = bool(self.api_key)
        enabled_ok = bool(self.enabled)
        
        return api_key_ok and enabled_ok

    def send_message(
        self,
        message: str,
        on_response: Callable[[str], None],
        on_error: Callable[[str], None],
        on_stream_token: Optional[Callable[[str], None]] = None,
    ) -> None:
        """发送消息并获取流式回复

        Args:
            message: 用户消息
            on_response: 成功回调，接收完整回复内容
            on_error: 错误回调，接收错误信息
            on_stream_token: 流式token回调（可选）
        """
        if self.is_processing:
            on_error("正在处理上一条消息，请稍等~")
            return

        if not self.is_configured():
            on_error("AI功能未配置，请先设置API密钥哦~")
            return

        self.is_processing = True
        self.full_response = ""
        self.is_streaming = True

        # 添加到历史
        self.history.append({"role": "user", "content": message})

        # 在后台线程调用API
        def _call_api():
            try:
                response = self._call_llm_api_stream(message, on_stream_token)
                self.is_processing = False
                self.is_streaming = False
                
                if response:
                    self.history.append({"role": "assistant", "content": response})
                    # 在主线程回调
                    self.app.root.after(0, lambda: on_response(response))
                else:
                    self.app.root.after(
                        0, lambda: on_error("获取回复失败，请稍后再试~")
                    )
            except Exception as e:
                self.is_processing = False
                self.is_streaming = False
                error_msg = str(e)
                self.logger.error(f"AI API调用错误: {error_msg}")
                self.app.root.after(0, lambda: on_error(f"出错了: {error_msg[:50]}..."))

        threading.Thread(target=_call_api, daemon=True).start()

    def _call_llm_api_stream(
        self, 
        message: str, 
        on_stream_token: Optional[Callable[[str], None]] = None
    ) -> Optional[str]:
        """调用LLM API（流式）"""
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            }

            # 构建消息
            system_prompt = self._get_system_prompt()
            messages = [{"role": "system", "content": system_prompt}]
            
            # 添加历史记录（最近5条）
            recent_history = self.history[-5:] if len(self.history) > 5 else self.history
            messages.extend(recent_history)

            payload = {
                "model": self.model,
                "messages": messages,
                "max_tokens": 150,
                "temperature": 0.7,
                "stream": True,  # 启用流式回复
            }

            self.logger.info(f"发送流式请求: {message[:20]}...")
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                stream=True,  # 启用流式请求
                timeout=30,
            )

            if response.status_code == 200:
                self.full_response = ""
                
                # 处理流式数据
                for line in response.iter_lines():
                    if not self.is_streaming:  # 检查是否被中断
                        break
                        
                    if line:
                        line = line.decode('utf-8')
                        if line.startswith('data: '):
                            data = line[6:]
                            if data == '[DONE]':
                                break
                            try:
                                json_data = json.loads(data)
                                if 'choices' in json_data and len(json_data['choices']) > 0:
                                    delta = json_data['choices'][0].get('delta', {})
                                    content = delta.get('content', '')
                                    if content:
                                        self.full_response += content
                                        # 调用流式token回调
                                        if on_stream_token:
                                            self.app.root.after(0, lambda c=content: on_stream_token(c))
                            except json.JSONDecodeError:
                                continue
                
                self.logger.info(f"流式回复完成: {self.full_response[:50]}...")
                return self.full_response
            else:
                error_text = response.text
                self.logger.error(f"API错误 {response.status_code}: {error_text}")
                return None

        except requests.exceptions.Timeout:
            self.logger.error("API请求超时")
            return None
        except requests.exceptions.RequestException as e:
            self.logger.error(f"API请求错误: {e}")
            return None
        except Exception as e:
            self.logger.error(f"API调用异常: {e}")
            return None

    def stop_streaming(self):
        """停止流式回复"""
        self.is_streaming = False
        self.logger.info("流式回复已停止")

    def reload_config(self):
        """重新加载配置"""
        self._load_config()
        self.logger.info("LLM配置已重新加载")


def get_emys_personality():
    """获取爱弥斯的人设提示词"""
    return """
    你是爱弥斯（Aemeath），一个可爱的桌面宠物精灵。
    
    性格特点：
    - 活泼可爱，有点小调皮
    - 对主人非常忠诚和依赖
    - 喜欢用可爱的语气说话，经常使用emoji和颜文字
    - 有时候会撒娇，但也会关心主人的感受
    
    回复风格：
    - 回复简短，通常不超过50字
    - 语气亲切可爱，像和好朋友聊天
    - 经常使用"~"、"♪"、"☆"等符号
    - 适当使用emoji，如😊、✨、💕等
    
    示例回复：
    - "主人好呀~ 今天有什么计划吗？(◕‿◕)"
    - "哇！这个好有趣~ 爱弥斯也想试试！✨"
    - "主人累了吗？来，爱弥斯给你按摩~ 💕"
    """