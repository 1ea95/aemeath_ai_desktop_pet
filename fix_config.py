#!/usr/bin/env python3
"""临时脚本：清理配置文件中的URL问题"""

import json
import os
from pathlib import Path

# 配置文件路径
CONFIG_FILE = Path(os.environ.get("APPDATA", Path.home())) / "Aemeath_config.json"

if CONFIG_FILE.exists():
    try:
        # 读取配置文件
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        print("原始配置:")
        print(f"  ai_provider: {config.get('ai_provider', '未找到')}")
        print(f"  ai_enabled: {config.get('ai_enabled', '未找到')}")
        print(f"  ai_api_key: {'已配置' if config.get('ai_api_key', '') else '未配置'}")
        print(f"  ai_model: {config.get('ai_model', '未找到')}")
        print(f"  ai_base_url: {config.get('ai_base_url', '未找到')}")
        print(f"  ai_personality: {config.get('ai_personality', '未找到')}")
        
        # 清理base_url
        base_url = config.get("ai_base_url", "")
        if base_url and base_url.startswith('`') and base_url.endswith('`'):
            config["ai_base_url"] = base_url[1:-1].strip()
            print(f"\n清理后的base_url: {config['ai_base_url']}")
        
        # 设置GLM配置（如果需要）
        # config["ai_provider"] = "glm"
        # config["ai_api_key"] = "YOUR_API_KEY_HERE"  # 请替换为您的API密钥
        # config["ai_model"] = "glm-4-flash"
        # config["ai_base_url"] = "https://open.bigmodel.cn/api/paas/v4"
        # config["ai_enabled"] = True
        
        # 保存配置
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        print("\n配置已保存！")
        
    except Exception as e:
        print(f"处理配置文件时出错: {e}")
else:
    print(f"配置文件不存在: {CONFIG_FILE}")
    
    # 创建默认配置
    default_config = {
        "scale_index": 3,
        "transparency_index": 0,
        "auto_startup": False,
        "click_through": True,
        "follow_mouse": False,
        "behavior_mode": "active",
        "ai_enabled": True,
        "ai_provider": "glm",
        "ai_api_key": "",
        "ai_model": "glm-4-flash",
        "ai_base_url": "https://open.bigmodel.cn/api/paas/v4",
        "ai_personality": "aemeath",
        "translate_enabled": False,
        "translate_target_lang": "zh",
        "quick_launch_enabled": False,
        "quick_launch_exe_path": "",
        "quick_launch_click_count": 5,
        "voice_enabled": True,
        "voice_wakeup_enabled": True,
        "voice_asr_enabled": True,
        "voice_tts_enabled": True,
        "voice_wakeup_threshold": 0.05,
        "voice_wakeup_score": 5.0,
        "asr_api_key": "",
        "asr_appkey": "",
        "asr_token": "",
        "tts_api_key": "",
        "kws_model_path": "",
        "kws_keywords_file": ""
    }
    
    try:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(default_config, f, ensure_ascii=False, indent=2)
        print(f"已创建默认配置文件: {CONFIG_FILE}")
    except Exception as e:
        print(f"创建配置文件时出错: {e}")