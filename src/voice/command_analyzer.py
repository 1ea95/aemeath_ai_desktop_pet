
"""命令分析模块

负责分析用户语音消息，识别可能的命令意图
"""

import os
import random
import re
from typing import Dict, List, Optional, NamedTuple, TYPE_CHECKING

from src.config import load_config

if TYPE_CHECKING:
    from src.core.pet_core import DesktopPet


class AnalysisResult(NamedTuple):
    """分析结果"""
    type: str  # "exact_command", "fuzzy_command", "potential_command", "llm_command", "normal_chat"
    command: Optional[str]  # 命令名称
    confidence: float  # 置信度
    action: Optional[str]  # 建议的操作
    details: Optional[Dict] = None  # 额外详情


class MatchResult(NamedTuple):
    """匹配结果"""
    is_match: bool
    command: Optional[str] = None
    action: Optional[str] = None
    details: Optional[Dict] = None


class IntentResult(NamedTuple):
    """意图分析结果"""
    has_intent: bool
    suggested_command: Optional[str] = None
    suggested_action: Optional[str] = None
    confidence: float = 0.0


class LLMResult(NamedTuple):
    """LLM分析结果"""
    is_command: bool
    command: Optional[str] = None
    confidence: float = 0.0
    action: Optional[str] = None
    raw_response: Optional[str] = None


class CommandAnalyzer:
    """
    命令分析器
    
    负责分析用户消息，识别可能的命令意图
    """
    
    def __init__(self, app: "DesktopPet", llm_callback=None) -> None:
        """
        初始化命令分析器
        
        Args:
            app: 桌面宠物应用实例
            llm_callback: LLM调用回调函数
        """
        self.app = app
        self.llm_callback = llm_callback
        
        # 系统命令映射
        self.system_commands = {
            "关机": "system_control",
            "重启": "system_control",
            "注销": "system_control",
            "锁屏": "system_control",
            "睡眠": "system_control",
            "休眠": "system_control",
            "静音": "volume_control",
            "取消静音": "volume_control",
            "音量最大": "volume_control",
            "音量中等": "volume_control",
            "音量调高": "volume_control",
            "音量调低": "volume_control",
            "播放音乐": "media_control",
            "暂停音乐": "media_control",
            "下一首": "media_control",
            "上一首": "media_control",
            "停止音乐": "media_control",
            "打开百度": "web_search",
            "打开谷歌": "web_search",
            "打开B站": "web_search",
            "控制面板": "system_setting",
            "系统信息": "system_setting",
            "蓝牙设置": "system_setting",
            "显示设置": "system_setting",
            "声音设置": "system_setting"
        }
        
        # 应用程序关键词
        self.app_keywords = {
            "记事本": ["记事本", "笔记本", "便签", "笔记"],
            "计算器": ["计算器", "计算", "算术", "数学"],
            "浏览器": ["浏览器", "上网", "网页", "浏览"],
            "画图": ["画图", "画画", "绘图", "画板"],
            "任务管理器": ["任务管理器", "任务", "进程", "任务栏"],
            "vscode": ["vscode", "visual studio code", "代码编辑器", "编辑器", "打代码", "写代码", "编程", "开发"],
            "微信": ["微信", "wechat", "weixin"]
        }
        
        # 意愿词
        self.intent_words = ["想", "要", "需要", "希望", "帮", "给我", "能不能", "可不可以"]
        
        # 动作词
        self.action_words = ["打开", "启动", "运行", "播放", "调", "设置", "切换", "关闭"]
        
        # 场景词
        self.scene_words = {
            "听歌": ["听歌", "放音乐", "播放音乐"],
            "上网": ["上网", "浏览网页", "打开网页"],
            "写代码": ["写代码", "打代码", "编程", "开发"],
            "看电影": ["看电影", "放电影", "播放视频"]
        }
    
    def analyze_message(self, message: str) -> AnalysisResult:
        """
        分析用户消息，返回分析结果
        
        Args:
            message: 用户语音消息
            
        Returns:
            分析结果
        """
        # 第一阶段：精确匹配
        exact_result = self._exact_match(message)
        if exact_result.is_match:
            return AnalysisResult(
                type="exact_command",
                command=exact_result.command,
                confidence=1.0,
                action=exact_result.action,
                details=exact_result.details
            )
        
        # 第二阶段：模糊匹配
        fuzzy_result = self._fuzzy_match(message)
        if fuzzy_result.is_match:
            return AnalysisResult(
                type="fuzzy_command",
                command=fuzzy_result.command,
                confidence=0.8,
                action=fuzzy_result.action,
                details=fuzzy_result.details
            )
        
        # 第三阶段：意图分析
        intent_result = self._intent_analysis(message)
        if intent_result.has_intent:
            return AnalysisResult(
                type="potential_command",
                command=intent_result.suggested_command,
                confidence=intent_result.confidence,
                action=intent_result.suggested_action,
                details={"intent": True}
            )
        
        # 第四阶段：LLM辅助判断
        if self._should_use_llm(message):
            llm_result = self._llm_analysis(message)
            if llm_result.is_command:
                return AnalysisResult(
                    type="llm_command",
                    command=llm_result.command,
                    confidence=llm_result.confidence,
                    action=llm_result.action,
                    details={"llm_response": llm_result.raw_response}
                )
        
        # 默认：普通对话
        return AnalysisResult(
            type="normal_chat",
            command=None,
            confidence=0.0,
            action=None
        )
    
    def _exact_match(self, message: str) -> MatchResult:
        """
        精确匹配系统预设命令
        
        Args:
            message: 用户语音消息
            
        Returns:
            匹配结果
        """
        message = message.strip()
        
        # 检查是否完全匹配系统命令
        if message in self.system_commands:
            return MatchResult(
                is_match=True,
                command=message,
                action=self.system_commands[message]
            )
        
        # 检查是否完全匹配应用程序名称
        for app_name in self.app_keywords.keys():
            if message == app_name:
                return MatchResult(
                    is_match=True,
                    command=app_name,
                    action="launch_app"
                )
        
        # 检查是否是"动作+目标"组合
        for action_word in ["打开", "启动", "运行", "关闭", "退出", "结束"]:
            if message.startswith(action_word):
                target = message[len(action_word):].strip()
                # 检查目标是否是应用程序
                if target in self.app_keywords:
                    return MatchResult(
                        is_match=True,
                        command=message,
                        action="launch_app"
                    )
                # 检查目标是否在自定义命令中
                config = load_config()
                custom_commands = config.get("custom_commands", {})
                if target in custom_commands:
                    return MatchResult(
                        is_match=True,
                        command=message,
                        action="custom_command",
                        details=custom_commands[target]
                    )
        
        # 检查自定义命令
        config = load_config()
        custom_commands = config.get("custom_commands", {})
        if message in custom_commands:
            return MatchResult(
                is_match=True,
                command=message,
                action="custom_command",
                details=custom_commands[message]
            )
        
        return MatchResult(is_match=False)
    
    def _fuzzy_match(self, message: str) -> MatchResult:
        """
        模糊匹配系统预设命令
        
        Args:
            message: 用户语音消息
            
        Returns:
            匹配结果
        """
        # 检查应用程序关键词
        for app_name, keywords in self.app_keywords.items():
            for keyword in keywords:
                if keyword in message:
                    # 尝试提取完整的命令（包括动作词）
                    full_command = self._extract_command_from_message(message)
                    if full_command and app_name in full_command:
                        # 如果提取的完整命令包含应用名称，使用完整命令
                        return MatchResult(
                            is_match=True,
                            command=full_command,
                            action=self._infer_action(message)
                        )
                    else:
                        # 否则使用应用名称
                        return MatchResult(
                            is_match=True,
                            command=app_name,
                            action="launch_app"
                        )
        
        # 检查系统控制关键词
        for command, action_type in self.system_commands.items():
            if command in message:
                return MatchResult(
                    is_match=True,
                    command=command,
                    action=action_type
                )
        
        # 检查自定义命令
        config = load_config()
        custom_commands = config.get("custom_commands", {})
        for cmd_name, cmd_data in custom_commands.items():
            if self._is_similar(message, cmd_name):
                return MatchResult(
                    is_match=True,
                    command=cmd_name,
                    action="custom_command",
                    details=cmd_data
                )
        
        return MatchResult(is_match=False)
    
    def _intent_analysis(self, message: str) -> IntentResult:
        """
        分析用户意图，判断是否可能是命令
        
        Args:
            message: 用户语音消息
            
        Returns:
            意图分析结果
        """
        message = message.strip()
        
        # 意愿词检测
        for word in self.intent_words:
            if word in message:
                suggested_command = self._extract_command_from_message(message)
                suggested_action = self._infer_action(message)
                
                if suggested_command:
                    return IntentResult(
                        has_intent=True,
                        suggested_command=suggested_command,
                        suggested_action=suggested_action,
                        confidence=0.6
                    )
        
        # 动作词检测
        for word in self.action_words:
            if word in message:
                suggested_command = self._extract_command_from_message(message)
                suggested_action = self._infer_action(message)
                
                if suggested_command:
                    return IntentResult(
                        has_intent=True,
                        suggested_command=suggested_command,
                        suggested_action=suggested_action,
                        confidence=0.5
                    )
        
        # 场景词检测
        for scene, keywords in self.scene_words.items():
            for keyword in keywords:
                if keyword in message:
                    return IntentResult(
                        has_intent=True,
                        suggested_command=scene,
                        suggested_action=self._infer_action_from_scene(scene),
                        confidence=0.7
                    )
        
        # 短消息检测
        if len(message) <= 8 and self._is_imperative_sentence(message):
            return IntentResult(
                has_intent=True,
                suggested_command=message,
                suggested_action="unknown",
                confidence=0.4
            )
        
        return IntentResult(has_intent=False)
    
    def _should_use_llm(self, message: str) -> bool:
        """
        判断是否应该使用LLM辅助
        
        Args:
            message: 用户语音消息
            
        Returns:
            如果应该使用LLM辅助返回True，否则返回False
        """
        # 消息长度检查
        if len(message) < 4 or len(message) > 30:
            return False
        
        # 检查是否包含内容词
        if not self._has_content_words(message):
            return False
        
        # 检查是否是疑问句
        if self._is_question(message):
            return False
        
        # 随机抽样，10%的概率使用LLM
        return random.random() < 0.1
    
    def _llm_analysis(self, message: str) -> LLMResult:
        """
        使用LLM分析消息
        
        Args:
            message: 用户语音消息
            
        Returns:
            LLM分析结果
        """
        try:
            # 构建命令分析提示词
            command_prompt = f"""
你是一个命令解析助手，负责将用户的自然语言转换为系统命令。

用户输入: "{message}"

请分析用户意图，如果包含已知的系统操作命令，请返回以下格式的JSON：
{{"is_command": true, "command": "命令名称", "confidence": 0.9, "action": "操作类型"}}

如果不包含已知的系统操作命令，请返回：
{{"is_command": false, "command": null, "confidence": 0.0, "action": null}}

可用命令列表:
- 系统控制: 关机, 重启, 注销, 锁屏, 睡眠, 休眠
- 应用程序: 记事本, 计算器, 浏览器, 画图, 任务管理器, vscode, 微信
- 音量控制: 静音, 取消静音, 音量调高, 音量调低, 音量最大, 音量中等
- 音乐控制: 播放音乐, 暂停音乐, 下一首, 上一首, 停止音乐
- 网页浏览: 打开百度, 打开谷歌, 打开B站
- 系统设置: 控制面板, 系统信息, 蓝牙设置, 显示设置, 声音设置

请只返回JSON，不要添加其他说明。
            """
            
            # 这里应该调用实际的LLM API
            # 由于我们在命令分析器中，不能直接访问voice_assistant的LLM
            # 所以这里返回一个默认结果，表示需要进一步处理
            # 在实际使用中，这个方法应该被voice_assistant重写或通过回调处理
            
            # 暂时返回非命令结果
            return LLMResult(
                is_command=False,
                command=None,
                confidence=0.0,
                action=None,
                raw_response="LLM分析需要进一步实现"
            )
            
        except Exception as e:
            # 错误处理
            return LLMResult(
                is_command=False,
                command=None,
                confidence=0.0,
                action=None,
                raw_response=f"LLM分析错误: {str(e)}"
            )
    
    def _extract_command_from_message(self, message: str) -> Optional[str]:
        """
        从消息中提取可能的命令
        
        Args:
            message: 用户语音消息
            
        Returns:
            提取的命令
        """
        # 改进的命令提取逻辑
        cleaned_message = message.strip()
        
        # 移除末尾的标点符号
        import re
        cleaned_message = re.sub(r'[。！？，、；：""''（）【】《》]+$', '', cleaned_message)
        
        # 移除常见的修饰词
        modifiers = ["一下", "帮我", "给我", "能不能", "可不可以"]
        for modifier in modifiers:
            if modifier in cleaned_message:
                cleaned_message = cleaned_message.replace(modifier, "").strip()
        
        # 识别动作+目标的完整组合
        for word in self.action_words:
            if word in cleaned_message:
                # 提取动作词后面的内容作为目标
                parts = cleaned_message.split(word, 1)
                if len(parts) > 1:
                    target = parts[1].strip()
                    # 返回完整的"动作+目标"组合
                    return f"{word}{target}"
        
        # 如果没有动作词，尝试直接提取关键词
        # 检查是否包含应用程序关键词
        for app_name, keywords in self.app_keywords.items():
            for keyword in keywords:
                if keyword in cleaned_message:
                    return app_name
        
        # 检查是否包含系统命令关键词
        for command in self.system_commands.keys():
            if command in cleaned_message:
                return command
        
        # 如果无法提取，返回清理后的消息（再次移除末尾标点）
        cleaned_message = re.sub(r'[。！？，、；：""''（）【】《》]+$', '', cleaned_message)
        return cleaned_message if cleaned_message else None
    
    def _infer_action(self, message: str) -> Optional[str]:
        """
        推断操作类型
        
        Args:
            message: 用户语音消息
            
        Returns:
            推断的操作类型
        """
        # 根据关键词推断操作类型
        if any(word in message for word in ["打开", "启动", "运行"]):
            return "launch_app"
        elif any(word in message for word in ["关闭", "退出", "结束"]):
            return "close_app"
        elif any(word in message for word in ["调", "设置", "切换"]):
            return "system_setting"
        elif any(word in message for word in ["播放", "暂停", "停止"]):
            return "media_control"
        elif any(word in message for word in ["搜索", "查找"]):
            return "web_search"
        
        return "unknown"
    
    def _infer_action_from_scene(self, scene: str) -> Optional[str]:
        """
        根据场景推断操作类型
        
        Args:
            scene: 场景描述
            
        Returns:
            推断的操作类型
        """
        scene_action_map = {
            "听歌": "media_control",
            "上网": "web_search",
            "写代码": "launch_app",
            "看电影": "media_control"
        }
        
        return scene_action_map.get(scene, "unknown")
    
    def _is_similar(self, message: str, command: str) -> bool:
        """
        判断消息是否与命令相似
        
        Args:
            message: 用户语音消息
            command: 命令名称
            
        Returns:
            如果相似返回True，否则返回False
        """
        # 简单实现：包含关系或长度相近
        message = message.lower()
        command = command.lower()
        
        # 包含关系
        if command in message or message in command:
            return True
        
        # 长度相近且包含相同字符
        if abs(len(message) - len(command)) <= 2:
            common_chars = set(message) & set(command)
            if len(common_chars) >= min(len(message), len(command)) * 0.7:
                return True
        
        return False
    
    def _is_imperative_sentence(self, message: str) -> bool:
        """
        判断是否是祈使句
        
        Args:
            message: 用户语音消息
            
        Returns:
            如果是祈使句返回True，否则返回False
        """
        # 简单实现：以动词开头或没有主语
        message = message.strip()
        
        # 检查是否以动作词开头
        for word in self.action_words:
            if message.startswith(word):
                return True
        
        # 检查是否没有主语（简单判断）
        if not any(word in message for word in ["我", "你", "他", "她", "它"]):
            return True
        
        return False
    
    def _has_content_words(self, message: str) -> bool:
        """
        检查消息是否包含内容词
        
        Args:
            message: 用户语音消息
            
        Returns:
            如果包含内容词返回True，否则返回False
        """
        # 简单实现：检查是否包含名词或动词
        content_words = self.action_words + list(self.app_keywords.keys())
        
        for word in content_words:
            if word in message:
                return True
        
        return False
    
    def _is_question(self, message: str) -> bool:
        """
        判断是否是疑问句
        
        Args:
            message: 用户语音消息
            
        Returns:
            如果是疑问句返回True，否则返回False
        """
        # 检查疑问词或问号
        question_indicators = ["吗", "呢", "什么", "怎么", "为什么", "哪里", "哪个", "？"]
        
        for indicator in question_indicators:
            if indicator in message:
                return True
        
        return False