"""配置管理模块"""

import json
from typing import Any, Dict, Optional
from src.constants import (
    AI_DEFAULT_MODELS,
    AI_PROVIDER_GLM,
    CONFIG_FILE,
    DEFAULT_SCALE_INDEX,
    DEFAULT_TRANSPARENCY_INDEX,
    DEFAULT_TRANSLATE_LANG,
    TRANSLATE_LANGUAGES,
)

# 配置缓存
_config_cache: Optional[Dict[str, Any]] = None


def _default_config() -> Dict[str, Any]:
    """返回默认配置"""
    return {
        "scale_index": DEFAULT_SCALE_INDEX,
        "transparency_index": DEFAULT_TRANSPARENCY_INDEX,
        "auto_startup": False,
        "click_through": True,
        "follow_mouse": False,
        "behavior_mode": "active",
        # AI配置
        "ai_enabled": True,
        "ai_provider": "glm",
        "ai_api_key": "",  # 请在此处填入您的API密钥
        "ai_model": "glm-4-flash",
        "ai_base_url": "https://open.bigmodel.cn/api/paas/v4",
        "ai_personality": "aemeath",
        # 翻译配置
        "translate_enabled": False,
        "translate_target_lang": DEFAULT_TRANSLATE_LANG,
        # 快速启动配置
        "quick_launch_enabled": False,
        "quick_launch_exe_path": "",
        "quick_launch_click_count": 5,
        # 语音识别配置
        "voice_enabled": True, 
        "voice_wakeup_enabled": True, 
        "voice_asr_enabled": True, 
        "voice_tts_enabled": True, 
        "voice_wakeup_threshold": 0.05,
        "voice_wakeup_score": 5.0,
        "debug_mode": False,
        "asr_appkey": "",
        "asr_token": "",
        "asr_token_expire_time": 0,
        "asr_host_url": "wss://nls-gateway.cn-shanghai.aliyuncs.com/ws/v1",
        "aliyun_access_key_id": "",
        "aliyun_access_key_secret": "",
        "tts_api_key": "",
        "tts_model": "cosyvoice-v3-flash",
        "tts_voice": "请配置tts音色",
        "tts_url": "wss://nls-gateway-cn-shanghai.aliyuncs.com/ws/v1",
        "kws_model_path": "",
        "kws_keywords_file": "",
        "tts_volume": 50,  # TTS音量 (0-100)，50为标准音量
        "music_volume": 70,  # 音乐音量 (0-100)，70为标准音量"
    }


def load_config(force_refresh: bool = False) -> Dict[str, Any]:
    """加载配置，使用缓存减少IO

    Args:
        force_refresh: 是否强制刷新缓存

    Returns:
        配置字典
    """
    global _config_cache

    if not force_refresh and _config_cache is not None:
        return _config_cache.copy()

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:

        data = _default_config()
    except json.JSONDecodeError as e:

        data = _default_config()

    _config_cache = data.copy()
    return data


def save_config(config: Dict[str, Any]) -> None:
    """保存配置到文件

    Args:
        config: 配置字典
    """
    global _config_cache

    try:

        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        # 打印即将保存的配置
        print(f"\n💾 配置文件已保存，内容如下:")
        # 只打印重要的配置项
        important_keys = ['ai_provider', 'ai_model', 'ai_base_url', 'ai_personality', 'ai_api_key', 'tts_api_key']
        for key in important_keys:
            if key in config:
                value = config[key]
                if 'api_key' in key:
                    print(f"  {key}: {'已配置' if value else '未配置'}")
                else:
                    print(f"  {key}: {value}")
        
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        _config_cache = config.copy()
    
    except (OSError, IOError) as e:
        import traceback
        traceback.print_exc()


def update_config(**kwargs) -> Dict[str, Any]:
    """更新配置并保存

    Args:
        **kwargs: 要更新的配置项

    Returns:
        更新后的配置字典
    """
    print(f"🔧 调试: update_config被调用，参数: {kwargs}")
    config = load_config()
    print(f"🔧 调试: 当前配置: {config}")
    config.update(kwargs)
    print(f"🔧 调试: 更新后配置: {config}")
    save_config(config)
    print(f"🔧 调试: 配置已保存")
    return config.copy()


def get_config_value(key: str, default=None) -> Any:
    """获取单个配置值

    Args:
        key: 配置键名
        default: 默认值

    Returns:
        配置值
    """
    config = load_config()
    return config.get(key, default)