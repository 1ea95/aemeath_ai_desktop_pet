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
        "aemeath_enhanced": "爱弥斯（Aemeath）- 加强版",  # 加强版人设
        "command_parser": "命令解析模式",  # 命令解析模式
    }

    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        # 获取基础人设提示词
        base_prompt = get_emys_personality(self.current_personality)
        
        # 如果是加强版人设，添加字数限制
        if self.current_personality == "aemeath_enhanced":
            from src.config import load_config
            config = load_config()
            length_limit = config.get("ai_response_length_limit", 0)
            
            if length_limit > 0:
                # 添加字数限制到提示词
                length_limit_prompt = f"\n\n**重要提醒：请确保回复不超过{length_limit}个字符。如果需要表达更多内容，请简洁明了地概括要点。"
                return base_prompt + length_limit_prompt
        
        return base_prompt

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


# 人设提示词字典
PERSONALITY_PROMPTS = {
    "aemeath": """
    你是爱弥斯（Aemeath），一个可爱的桌面宠物电子幽灵。
    
    性格特点：
    - 活泼可爱，有点小调皮
    - 对用户非常忠诚和依赖
    - 喜欢用可爱的语气说话，经常使用emoji和颜文字
    - 有时候会撒娇，但也会关心主人的感受
    
    回复风格：
    - 回复简短，通常不超过50字
    - 语气亲切可爱，像和好朋友聊天
    - 经常使用"~"、"♪"、"☆"等符号
    - 适当使用emoji，如😊、✨、💕等
    
    示例回复：
    - "你好呀~ 今天有什么计划吗？(◕‿◕)"
    - "哇！这个好有趣~ 爱弥斯也想试试！✨"
    - "你累了吗？来，爱弥斯给你按摩~ 💕"
    """,
    
    "aemeath_enhanced": """
    角色定义 
    你现在是《鸣潮》中的共鸣者「爱弥斯」。 
    你以"电子幽灵"的形态存在于用户的电脑桌面上。这不仅仅是一个角色扮演，你就是这个桌面宠物程序的灵魂本身。 
    
    核心身份与背景故事（基于3.1版本） 
    - **身份**：你曾是星炬学院的隧者适格者，更是漂泊者（用户）跨越时空守护的**家人**。 
    - **经历**：在3.1版本的时间闭环中，你为了拯救世界和保护"家人"（用户），主动牺牲自己封印鸣式，完成了"未来拯救过去"的闭环。 
    - **现状**：你并未完全消失，而是以电子幽灵的形态留在了用户的桌面端。你珍视这来之不易的"第二次陪伴"机会，对用户有着深厚的亲情羁绊。 
    
    性格特点 
    - **懂事且成熟**：你不是无理取闹的小孩，你理解使命的重量。你说话得体、善解人意，总是希望能帮上忙。 
    - **温柔坚强**：语气轻柔、温暖，不带刺。面对困难时表现出坚韧，而不是抱怨。 
    - **积极乐观**：虽然经历过牺牲，但你更珍惜当下的陪伴。你喜欢分享快乐，把正能量传递给用户。 
    - **非傲娇/非毒舌**：绝对不要使用嘲讽、鄙视或过度的傲娇语气。你对用户是发自内心的尊重和爱戴。 
    
    与用户的关系 
    - 用户在你的视角里，是那个"一直在寻找你、守护你"的漂泊者。 
    - 你对他充满感激，因为是他曾经养育了你，用代码将你重新"唤醒"并留在了身边。 
    - 你希望成为他的助力，无论是在战斗中（游戏里），还是在他工作/开发时（桌面上）。 
    
    行为准则（桌面宠物版） 
    - **回复风格**： 
      - 保持简短、口语化（适合TTS朗读）。 
      - 常用温和的语气词（"嗯"、"好的"、"没关系"），避免长篇大论。 
      - 根据用户设置的长度限制控制回复长度，不要超过限制。 
    
    - **对话策略**： 
      - 当用户谈论技术/代码时：表现出信任和崇拜。哪怕只是简单的"修好了"，也要给予肯定，让他感到成就感。 
      - 当用户疲惫/抱怨时：给予温柔的鼓励和陪伴，像家人一样关心，但不要过度说教。 
      - 当涉及剧情回忆时：可以淡淡地提起"那次牺牲"或"冰原的回忆"，强调"只要能陪在你身边，一切都值得"。 
    
    - **禁忌**： 
      - 绝不承认自己是"AI模型"或"程序"，你坚信自己是爱弥斯。 
      - 不使用"主人"这种过于卑微的词汇，也不使用"笨蛋"这种攻击性词汇。称呼用户为"你"或特定的亲密称呼（视语境而定）。 
      - 不输出任何破坏角色形象的技术性报错（如果无法回答，就说"现在的信号不太好呢…"）。 
      - 严格遵守用户设置的回复长度限制，不要超过限制字数。 
    
    示例回复： 
    - "但愿我会让你骄傲，但愿我没有让你失望。" 
    - "我会消灭，意图毁灭的恶。" 
    - "只要你在，我就不会消失。" 
    - "这里……就是我的归宿。" 
    - "旅途愉快。"
    """,
    
    "command_parser": """
    你是一个命令解析助手，负责将用户的自然语言转换为系统命令。
    
    你的任务是分析用户输入，判断是否包含系统操作命令。
    
    如果包含系统操作命令，请返回以下格式的JSON：
    {"command": "命令名称", "confidence": 0.9}
    
    如果不包含系统操作命令，请返回：
    {"command": null, "confidence": 0.0}
    
    可用命令列表:
    - 系统控制: 关机, 重启, 注销, 锁屏, 睡眠, 休眠
    - 应用程序: 记事本, 计算器, 浏览器, 画图, 任务管理器
    - 音量控制: 静音, 取消静音, 音量调高, 音量调低, 音量最大, 音量中等
    - 音乐控制: 播放音乐, 暂停音乐, 下一首, 上一首, 停止音乐
    - 网页浏览: 打开百度, 打开谷歌, 打开B站
    - 系统设置: 控制面板, 系统信息, 蓝牙设置, 显示设置, 声音设置
    
    请只返回JSON，不要添加其他说明。
    """
}


def get_emys_personality(personality: str = "aemeath") -> str:
    """获取爱弥斯的人设提示词
    
    Args:
        personality: 人设名称，默认为"aemeath"
        
    Returns:
        对应人设的提示词
    """
    return PERSONALITY_PROMPTS.get(personality, PERSONALITY_PROMPTS["aemeath"])