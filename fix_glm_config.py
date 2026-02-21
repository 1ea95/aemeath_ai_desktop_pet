#!/usr/bin/env python3
"""语音功能检查和修复工具"""

import sys
import os
import subprocess
from pathlib import Path

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def check_voice_libraries():
    """检查语音相关库的安装情况"""
    print("🔍 检查语音相关库的安装情况...")
    
    # 检查ASR相关库
    print("\n📢 ASR（语音识别）相关库:")
    try:
        import nls
        print("✅ nls (阿里云智能语音服务SDK) - 已安装")
        print("   用途: 语音识别(ASR)")
        print("   官方文档: https://help.aliyun.com/zh/isi/")
    except ImportError:
        print("❌ nls (阿里云智能语音服务SDK) - 未安装")
        print("   安装命令: pip install alibabacloud-nls")
    
    # 检查TTS相关库
    print("\n🔊 TTS（语音合成）相关库:")
    try:
        import dashscope
        print("✅ dashscope (阿里云大模型SDK) - 已安装")
        print("   用途: 语音合成(TTS)")
        print("   官方文档: https://help.aliyun.com/zh/dashscope/")
    except ImportError:
        print("❌ dashscope (阿里云大模型SDK) - 未安装")
        print("   安装命令: pip install dashscope")
    
    # 检查音频处理库
    print("\n🎧 音频处理相关库:")
    try:
        import pyaudio
        print("✅ pyaudio - 已安装")
        print("   用途: 音频录制和播放")
    except ImportError:
        print("❌ pyaudio - 未安装")
        print("   安装命令: pip install pyaudio")
    
    try:
        import sounddevice
        print("✅ sounddevice - 已安装")
        print("   用途: 音频设备访问")
    except ImportError:
        print("❌ sounddevice - 未安装")
        print("   安装命令: pip install sounddevice")
    
    try:
        import numpy
        print("✅ numpy - 已安装")
        print("   用途: 音频数据处理")
    except ImportError:
        print("❌ numpy - 未安装")
        print("   安装命令: pip install numpy")

def install_voice_libraries():
    """安装语音相关库"""
    print("\n📦 安装语音相关库...")
    
    libraries = [
        "alibabacloud-nls",
        "dashscope", 
        "pyaudio",
        "sounddevice",
        "numpy"
    ]
    
    for lib in libraries:
        print(f"\n正在安装 {lib}...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", lib])
            print(f"✅ {lib} 安装成功")
        except subprocess.CalledProcessError as e:
            print(f"❌ {lib} 安装失败: {e}")

def check_voice_config():
    """检查语音配置"""
    print("\n⚙️ 检查语音配置...")
    
    try:
        from src.config import load_config
        config = load_config()
        
        print("\n🎤 ASR配置:")
        asr_appkey = config.get("asr_appkey", "")
        asr_token = config.get("asr_token", "")
        print(f"  asr_appkey: {'已配置' if asr_appkey else '未配置'}")
        print(f"  asr_token: {'已配置' if asr_token else '未配置'}")
        
        print("\n🔊 TTS配置:")
        tts_api_key = config.get("tts_api_key", "")
        voice_tts_enabled = config.get("voice_tts_enabled", False)
        tts_model = config.get("tts_model", "")
        tts_voice = config.get("tts_voice", "")
        tts_volume = config.get("tts_volume", 50)
        print(f"  tts_api_key: {'已配置' if tts_api_key else '未配置'}")
        print(f"  voice_tts_enabled: {voice_tts_enabled}")
        print(f"  tts_model: {tts_model}")
        print(f"  tts_voice: {tts_voice}")
        print(f"  tts_volume: {tts_volume}")
        
        print("\n🎯 语音功能总览:")
        voice_enabled = config.get("voice_enabled", False)
        voice_wakeup_enabled = config.get("voice_wakeup_enabled", False)
        voice_asr_enabled = config.get("voice_asr_enabled", False)
        print(f"  voice_enabled: {voice_enabled}")
        print(f"  voice_wakeup_enabled: {voice_wakeup_enabled}")
        print(f"  voice_asr_enabled: {voice_asr_enabled}")
        
    except Exception as e:
        print(f"❌ 检查配置失败: {e}")

def debug_tts():
    """调试TTS功能"""
    print("\n🔍 调试TTS功能...")
    
    try:
        # 检查dashscope
        import dashscope
        print(f"✅ dashscope版本: {dashscope.__version__}")
        
        # 检查TTS模块
        from dashscope.audio.tts_v2 import SpeechSynthesizer
        print("✅ TTS模块导入成功")
        
        # 检查配置
        from src.config import load_config
        config = load_config()
        
        tts_api_key = config.get("tts_api_key", "")
        if not tts_api_key:
            print("❌ TTS API密钥未配置")
            return False
        
        print("✅ TTS API密钥已配置")
        
        # 设置API密钥
        dashscope.api_key = tts_api_key
        
        # 尝试创建TTS合成器
        tts_model = config.get("tts_model", "cosyvoice-v3-flash")
        tts_voice = config.get("tts_voice", "cosyvoice-v3-flash-anbao1-69f1b1345bb9496b9eab08e6d5462bb2")
        
        print(f"🔧 尝试创建TTS合成器...")
        print(f"   模型: {tts_model}")
        print(f"   音色: {tts_voice}")
        
        synthesizer = SpeechSynthesizer(
            model=tts_model,
            voice=tts_voice,
            format=AudioFormat.PCM_16000_MONO_16BIT
        )
        
        print("✅ TTS合成器创建成功")
        
        # 尝试合成测试文本
        test_text = "这是一个测试"
        print(f"🔊 尝试合成测试文本: {test_text}")
        
        # 这里只是测试创建，不实际调用API
        print("✅ TTS功能测试通过（未实际调用API）")
        
        return True
        
    except Exception as e:
        print(f"❌ TTS功能测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_audio_playback():
    """测试音频播放功能"""
    print("\n🔊 测试音频播放功能...")
    
    try:
        import pygame
        pygame.mixer.init()
        print("✅ pygame.mixer初始化成功")
        
        # 检查音频设备
        print(f"   音频驱动: {pygame.mixer.get_init()}")
        
        # 检查本地音频文件
        audio_dir = Path("assets/voice")
        if audio_dir.exists():
            audio_files = list(audio_dir.glob("*.wav"))
            if audio_files:
                test_file = audio_files[0]
                print(f"🔊 尝试播放测试音频: {test_file.name}")
                
                sound = pygame.mixer.Sound(str(test_file))
                print(f"   音频长度: {sound.get_length():.2f}秒")
                
                # 这里只是测试加载，不实际播放
                print("✅ 音频文件加载成功（未实际播放）")
            else:
                print("⚠️ 未找到测试音频文件")
        else:
            print("⚠️ 音频文件夹不存在")
        
        return True
        
    except Exception as e:
        print(f"❌ 音频播放测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("=" * 60)
    print("Aemeath 桌面宠物 - 语音功能检查和修复工具")
    print("=" * 60)
    
    # 检查语音库
    check_voice_libraries()
    
    # 检查配置
    check_voice_config()
    
    # 提供修复选项
    print("\n" + "=" * 60)
    print("🔧 修复选项:")
    print("=" * 60)
    
    choice = input("\n选择操作:\n1. 安装缺失的语音库\n2. 检查GLM配置\n3. 调试TTS功能\n4. 测试音频播放\n5. 退出\n请输入选项(1-5): ").strip()
    
    if choice == "1":
        install_voice_libraries()
        print("\n✅ 安装完成，请重新运行程序")
    elif choice == "2":
        try:
            from src.config import update_config
            
            print("\n🔧 设置GLM配置...")
            
            # 直接设置GLM配置
            config = update_config(
                ai_enabled=True,
                ai_provider="glm",
                ai_api_key="YOUR_API_KEY_HERE",  # 请替换为您的API密钥
                ai_model="glm-4-flash",
                ai_base_url="https://open.bigmodel.cn/api/paas/v4",
                ai_personality="aemeath"
            )
            
            print("\n✅ GLM配置设置完成:")
            print(f"  ai_enabled: {config.get('ai_enabled', '未找到')}")
            print(f"  ai_provider: {config.get('ai_provider', '未找到')}")
            print(f"  ai_api_key: {'已配置' if config.get('ai_api_key', '') else '未配置'}")
            print(f"  ai_model: {config.get('ai_model', '未找到')}")
            print(f"  ai_base_url: {config.get('ai_base_url', '未找到')}")
            print(f"  ai_personality: {config.get('ai_personality', '未找到')}")
            
            print("\n🎉 现在可以重新启动程序了！")
        except Exception as e:
            print(f"❌ 设置GLM配置失败: {e}")
    elif choice == "3":
        debug_tts()
    elif choice == "4":
        test_audio_playback()
    elif choice == "5":
        print("👋 退出")
    else:
        print("❌ 无效选项")
    
    input("\n按回车键退出...")

if __name__ == "__main__":
    main()