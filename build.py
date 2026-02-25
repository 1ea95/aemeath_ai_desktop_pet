#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Aemeath 桌面宠物打包工具
使用PyInstaller将项目打包成可执行文件
支持生成窗口版本和控制台版本
"""

import os
import sys
import shutil
import subprocess
import platform
from pathlib import Path
import time


def get_version():
    """从README.md获取当前版本号"""
    try:
        with open('README.md', 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith('**当前版本：'):
                    return line.split('v')[1].strip('**\n')
        return "3.0.3"  # 默认版本
    except Exception as e:
        print(f"获取版本号失败: {e}")
        return "3.0.3"


def update_version_in_spec():
    """更新spec文件中的版本信息"""
    version = get_version()
    try:
        with open('aemeath.spec', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查是否已经有版本注释
        if '# 版本: v' in content:
            # 更新现有版本
            import re
            content = re.sub(r'# 版本: v.*', f'# 版本: v{version}', content)
        else:
            # 在文件开头添加版本注释
            content = f'# 版本: v{version}\n' + content
        
        with open('aemeath.spec', 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✅ 已更新spec文件版本为: v{version}")
        return True
    except Exception as e:
        print(f"❌ 更新spec文件版本失败: {e}")
        return False


def update_version_in_main():
    """更新main.py中的版本信息"""
    version = get_version()
    try:
        with open('src/main.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 查找并更新版本号
        import re
        # 匹配版本号行，格式如: __version__ = "3.0.1"
        pattern = r'(__version__\s*=\s*")[\d.]+("")'
        if re.search(pattern, content):
            content = re.sub(pattern, f'\\g<1>{version}\\g<2>', content)
            
            with open('src/main.py', 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"✅ 已更新main.py版本为: v{version}")
            return True
        else:
            print("⚠️ 未找到main.py中的版本号行")
            return False
    except Exception as e:
        print(f"❌ 更新main.py版本失败: {e}")
        return False


def print_header(title):
    """打印标题"""
    print("\n" + "=" * 60)
    print(f" {title} ")
    print("=" * 60)


def print_step(step, description):
    """打印步骤"""
    print(f"\n[{step}] {description}")
    print("-" * 40)


def check_python_version():
    """检查Python版本"""
    print("检查Python版本...")
    version = sys.version_info
    print(f"当前Python版本: {version.major}.{version.minor}.{version.micro}")
    
    if version.major < 3 or (version.major == 3 and version.minor < 7):
        print("❌ Python版本过低，需要Python 3.7或更高版本")
        return False
    
    print("✅ Python版本符合要求")
    return True


def check_system_info():
    """检查系统信息"""
    print("\n检查系统信息...")
    print(f"操作系统: {platform.system()} {platform.release()}")
    print(f"架构: {platform.machine()}")
    print(f"处理器: {platform.processor()}")
    return True


def check_dependencies():
    """检查项目依赖"""
    print("\n检查项目依赖...")
    
    # 检查requirements.txt
    req_file = Path("requirements.txt")
    if not req_file.exists():
        print("❌ 找不到requirements.txt文件")
        return False
    
    print("✅ 找到requirements.txt文件")
    
    # 检查关键依赖
    key_packages = [
        ("Pillow", "PIL"),
        ("pystray", "pystray"),
        ("pygame", "pygame"),
        ("requests", "requests"), 
        ("pywin32", "win32api"),
        ("pyperclip", "pyperclip"),
        ("dashscope", "dashscope"),  # 阿里云大模型SDK，用于TTS语音合成 
        ("alibabacloud-nls", "nls"),  # 阿里云智能语音服务SDK，用于ASR语音识别
        ("aliyun-python-sdk-core", "aliyunsdkcore"),  # 阿里云SDK核心库，用于获取鉴权token
        ("pyaudio", "pyaudio"),
        ("numpy", "numpy"), 
        ("sounddevice", "sounddevice"),
        ("sherpa-onnx", "sherpa_onnx")
    ]
    
    missing_packages = []
    for package_name, import_name in key_packages:
        try:
            module = __import__(import_name)
            print(f"✅ {package_name}")
            
            # 为音频相关库添加额外检查
            if package_name == "pyaudio":
                try:
                    import pyaudio
                    pa = pyaudio.PyAudio()
                    device_count = pa.get_device_count()
                    print(f"   🎧 音频设备数量: {device_count}")
                    
                    # 检查默认输出设备
                    default_output = pa.get_default_output_device_info()
                    print(f"   🔊 默认输出设备: {default_output['name']}")
                    
                    pa.terminate()
                except Exception as e:
                    print(f"   ⚠️ 音频设备检查失败: {e}")
            
            elif package_name == "dashscope":
                try:
                    # 检查TTS模块是否可用
                    from dashscope.audio.tts_v2 import SpeechSynthesizer
                    print(f"   🔊 TTS模块可用")
                except Exception as e:
                    print(f"   ⚠️ TTS模块检查失败: {e}")
                    
        except ImportError:
            print(f"❌ {package_name} (未安装)")
            missing_packages.append(package_name)
    
    if missing_packages:
        print(f"\n⚠️ 缺少依赖包: {', '.join(missing_packages)}")
        print("请运行: pip install -r requirements.txt")
        
        # 提供自动安装选项
        install_choice = input("\n是否自动安装缺失的依赖包？(y/n): ").lower().strip()
        if install_choice == 'y':
            print("\n正在安装缺失的依赖包...")
            try:
                # 使用pip安装requirements.txt中的所有依赖
                cmd = f"{sys.executable} -m pip install -r requirements.txt"
                result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
                print("✅ 依赖包安装成功")
                
                # 重新检查
                print("\n重新检查依赖...")
                still_missing = []
                for package_name, import_name in key_packages:
                    try:
                        __import__(import_name)
                        print(f"✅ {package_name}")
                    except ImportError:
                        print(f"❌ {package_name} (仍未安装)")
                        still_missing.append(package_name)
                
                if still_missing:
                    print(f"\n⚠️ 仍有依赖包未安装: {', '.join(still_missing)}")
                    return False
                else:
                    print("\n✅ 所有关键依赖已安装")
                    return True
            except subprocess.CalledProcessError as e:
                print(f"❌ 安装失败: {e.stderr}")
                return False
        else:
            return False
    
    print("\n✅ 所有关键依赖已安装")
    return True

def check_tts_resources():
    """检查TTS相关资源"""
    print("\n🔊 检查TTS相关资源...")
    
    # 检查配置文件
    try:
        from src.config import load_config
        config = load_config()
        
        tts_enabled = config.get('voice_tts_enabled', False)
        tts_api_key = config.get('tts_api_key', '')
        tts_model = config.get('tts_model', '')
        tts_voice = config.get('tts_voice', '')
        
        print(f"TTS功能状态: {'启用' if tts_enabled else '禁用'}")
        print(f"TTS API密钥: {'已配置' if tts_api_key else '未配置'}")
        print(f"TTS模型: {tts_model}")
        print(f"TTS音色: {tts_voice}")
        
        if not tts_enabled:
            print("⚠️ TTS功能未启用，请在设置中启用")
        
        if not tts_api_key:
            print("⚠️ TTS API密钥未配置，请在设置中配置")
            
    except Exception as e:
        print(f"❌ 检查TTS配置失败: {e}")
    
    # 检查token管理器
    try:
        from src.voice.token_manager import get_token_manager
        token_manager = get_token_manager()
        print("\n🔑 Token管理器: 可用")
        
        # 检查阿里云凭证
        aliyun_access_key_id = config.get('aliyun_access_key_id', '')
        aliyun_access_key_secret = config.get('aliyun_access_key_secret', '')
        auto_token_refresh = config.get('auto_token_refresh', True)
        
        print(f"阿里云AccessKey ID: {'已配置' if aliyun_access_key_id else '未配置'}")
        print(f"阿里云AccessKey Secret: {'已配置' if aliyun_access_key_secret else '未配置'}")
        print(f"自动刷新Token: {'启用' if auto_token_refresh else '禁用'}")
        
        if not aliyun_access_key_id or not aliyun_access_key_secret:
            print("⚠️ 阿里云凭证未配置，请在设置中配置")
            
    except Exception as e:
        print(f"\n❌ 检查Token管理器失败: {e}")
    
    # 检查音频文件
    audio_dir = Path("assets/voice")
    if audio_dir.exists():
        audio_files = list(audio_dir.glob("*.wav"))
        print(f"\n📁 本地音频文件: {len(audio_files)}个")
        for audio_file in audio_files[:3]:  # 只显示前3个
            print(f"   - {audio_file.name}")
        if len(audio_files) > 3:
            print(f"   ... 还有{len(audio_files)-3}个文件")
    else:
        print("\n⚠️ 未找到本地音频文件夹")
    
    return True


def check_ui_resources():
    """检查UI相关资源"""
    print("\n🎨 检查UI相关资源...")
    
    # 检查UI组件管理器
    try:
        from src.ui.ui_manager import UIManager
        print("✅ UI组件管理器: 可用")
    except Exception as e:
        print(f"❌ UI组件管理器检查失败: {e}")
    
    # 检查UI组件文件
    ui_components = [
        "src/ui/speech_bubble.py",
        "src/ui/music_panel.py",
        "src/ui/pomodoro_indicator.py",
        "src/ui/ai_chat_panel.py",
        "src/ui/ui_manager.py"
    ]
    
    for component in ui_components:
        if os.path.exists(component):
            print(f"✅ {component}")
        else:
            print(f"❌ {component} (文件不存在)")
    
    # 检查动画资源
    gifs_dir = Path("assets/gifs")
    if gifs_dir.exists():
        gif_files = list(gifs_dir.glob("*.gif"))
        print(f"\n📁 动画资源: {len(gif_files)}个")
        
        # 检查关键动画文件
        key_gifs = ["idle.gif", "idle1.gif", "idle2.gif", "idle3.gif", "idle4.gif"]
        for gif in key_gifs:
            if (gifs_dir / gif).exists():
                print(f"   ✅ {gif}")
            else:
                print(f"   ⚠️ {gif} (不存在)")
    else:
        print("\n⚠️ 未找到动画资源文件夹")
    
    # 检查图标资源
    icon_path = Path("assets/gifs/aemeath.ico")
    if icon_path.exists():
        print(f"\n✅ 应用图标: {icon_path}")
    else:
        print(f"\n⚠️ 应用图标不存在: {icon_path}")
    
    return True


def create_release_package(version, window_exe_path, console_exe_path):
    """创建发布包"""
    print_header(f"创建v{version}发布包")
    
    # 创建发布目录
    release_dir = Path(f"release/v{version}")
    release_dir.mkdir(parents=True, exist_ok=True)
    
    # 复制可执行文件
    try:
        # 只使用带版本号的文件名
        versioned_window_name = f"Aemeath{version}.exe"
        shutil.copy2(window_exe_path, release_dir / versioned_window_name)
        print(f"✅ 可执行文件已复制到: {release_dir}")
        print(f"   - {versioned_window_name}")
    except Exception as e:
        print(f"❌ 复制可执行文件失败: {e}")
        return False
    
    # 复制必要文档
    docs_to_copy = [
        "README.md",
        "CHANGELOG.md",
        "# Bug List - Aemeath 桌面宠物.md"
    ]
    
    for doc in docs_to_copy:
        if os.path.exists(doc):
            try:
                shutil.copy2(doc, release_dir)
                print(f"✅ 文档已复制: {doc}")
            except Exception as e:
                print(f"❌ 复制文档失败 {doc}: {e}")
        else:
            print(f"⚠️ 文档不存在: {doc}")
    
    # 创建快速启动脚本
    try:
        # 创建启动脚本
        with open(release_dir / "启动.bat", "w", encoding="gbk") as f:
            f.write(f"@echo off\n")
            f.write(f"title Aemeath桌面宠物 v{version}\n")
            f.write(f"echo 正在启动Aemeath桌面宠物...\n")
            f.write(f"start \"\"\"Aemeath{version}.exe\"\"\n")
            f.write(f"exit\n")
        
        print("✅ 快速启动脚本已创建")
    except Exception as e:
        print(f"❌ 创建启动脚本失败: {e}")
    
    # 创建说明文件
    try:
        with open(release_dir / "使用说明.txt", "w", encoding="utf-8") as f:
            f.write(f"Aemeath桌面宠物 v{version} 使用说明\n")
            f.write(f"{'='*50}\n\n")
            f.write(f"【文件说明】\n")
            f.write(f"Aemeath{version}.exe - 窗口版本，推荐日常使用\n")
            f.write(f"启动.bat - 快速启动窗口版本的批处理文件\n\n")
            f.write(f"【快速开始】\n")
            f.write(f"1. 双击'启动.bat'启动程序\n")
            f.write(f"2. 首次运行请在托盘菜单中配置API密钥\n")
            f.write(f"3. 右键点击系统托盘图标可以打开设置菜单\n\n")
            f.write(f"【注意事项】\n")
            f.write(f"1. 请确保网络连接正常，AI功能需要网络支持\n")
            f.write(f"2. 语音功能需要麦克风设备\n")
            f.write(f"3. 遇到问题请使用控制台版本查看错误信息\n\n")
            f.write(f"【更新日志】\n")
            f.write(f"请查看CHANGELOG.md了解详细更新内容\n\n")
            f.write(f"【问题反馈】\n")
            f.write(f"如遇到问题，请查看'# Bug List - Aemeath 桌面宠物.md'文件\n")
        
        print("✅ 使用说明文件已创建")
    except Exception as e:
        print(f"❌ 创建说明文件失败: {e}")
    
    # 创建压缩包
    try:
        import zipfile
        zip_path = Path(f"release/Aemeath_v{version}.zip")
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in release_dir.glob("*"):
                if file_path.is_file():
                    zipf.write(file_path, file_path.name)
        
        # 获取压缩包大小
        zip_size = zip_path.stat().st_size / (1024 * 1024)  # MB
        print(f"✅ 发布包已创建: {zip_path}")
        print(f"   压缩包大小: {zip_size:.2f} MB")
    except Exception as e:
        print(f"❌ 创建压缩包失败: {e}")
    
    print(f"\n🎉 发布包创建完成！")
    print(f"📁 发布目录: {release_dir.absolute()}")
    return True


def run_command(command, description, show_output=False):
    """运行命令并处理结果"""
    print(f"\n{description}...")
    
    try:
        if show_output:
            # 实时显示输出
            process = subprocess.Popen(
                command, 
                shell=True, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            # 实时输出
            for line in iter(process.stdout.readline, ''):
                print(line.rstrip())
            
            process.wait()
            
            if process.returncode == 0:
                print(f"✅ {description}成功")
                return True
            else:
                print(f"❌ {description}失败 (返回码: {process.returncode})")
                return False
        else:
            # 不显示输出，只显示结果
            result = subprocess.run(
                command, 
                shell=True, 
                check=True, 
                capture_output=True, 
                text=True
            )
            print(f"✅ {description}成功")
            return True
            
    except subprocess.CalledProcessError as e:
        print(f"❌ {description}失败")
        if not show_output:
            print(f"错误信息: {e.stderr}")
        return False
    except Exception as e:
        print(f"❌ {description}发生异常: {e}")
        return False


def check_pyinstaller():
    """检查PyInstaller是否已安装"""
    print("检查PyInstaller是否已安装...")
    try:
        result = subprocess.run([sys.executable, "-m", "PyInstaller", "--version"], 
                              capture_output=True, text=True)
        print(f"✅ PyInstaller已安装 (版本: {result.stdout.strip()})")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ PyInstaller未安装")
        return False


def install_pyinstaller():
    """安装PyInstaller"""
    print("正在安装PyInstaller...")
    return run_command(f"{sys.executable} -m pip install pyinstaller", "PyInstaller安装")


def clean_build_dirs():
    """清理之前的打包文件"""
    print("清理之前的打包文件...")
    dirs_to_clean = ["dist", "build"]
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            try:
                shutil.rmtree(dir_name)
                print(f"✅ 已清理 {dir_name} 目录")
            except Exception as e:
                print(f"❌ 清理 {dir_name} 目录失败: {e}")
                return False
    return True


def build_executable(console_mode=False, show_output=False):
    """使用PyInstaller打包
    
    参数:
        console_mode: 是否为控制台模式
        show_output: 是否显示打包过程输出
    """
    mode_text = "控制台" if console_mode else "窗口"
    print(f"开始打包Aemeath桌面宠物({mode_text}模式)...")
    
    # 设置环境变量来传递控制台模式参数
    import os
    if console_mode:
        os.environ['AEMEATH_CONSOLE_MODE'] = '1'
    else:
        os.environ.pop('AEMEATH_CONSOLE_MODE', None)
    
    # 使用spec文件打包
    cmd = f"{sys.executable} -m PyInstaller aemeath.spec"
    
    return run_command(cmd, f"项目打包({mode_text}模式)", show_output=show_output)


def main():
    """主函数"""
    print_header("Aemeath 桌面宠物打包工具")
    
    # 显示当前版本
    version = get_version()
    print(f"当前版本: v{version}")
    
    start_time = time.time()
    
    # 步骤1: 环境检查
    print_step("1/7", "环境检查")
    if not check_python_version():
        print("\n❌ Python版本检查失败")
        input("按回车键退出...")
        sys.exit(1)
    
    if not check_system_info():
        print("\n❌ 系统信息检查失败")
        input("按回车键退出...")
        sys.exit(1)
    
    # 步骤2: 依赖检查
    print_step("2/7", "依赖检查")
    if not check_dependencies():
        print("\n❌ 依赖检查失败")
        print("请先安装缺失的依赖包")
        input("按回车键退出...")
        sys.exit(1)
    
    # 步骤2.5: TTS和UI资源检查
    print_step("2.5/7", "TTS和UI资源检查")
    check_tts_resources()
    check_ui_resources()
    
    # 步骤3: 检查当前目录
    print_step("3/7", "项目文件检查")
    
    # 更新spec文件版本
    update_version_in_spec()
    update_version_in_main()
    
    if not os.path.exists("aemeath.spec"):
        print("❌ 错误: 当前目录中找不到 aemeath.spec 文件")
        print("请确保在项目根目录中运行此脚本")
        input("按回车键退出...")
        sys.exit(1)
    
    if not os.path.exists("main.py"):
        print("❌ 错误: 当前目录中找不到 main.py 文件")
        print("请确保在项目根目录中运行此脚本")
        input("按回车键退出...")
        sys.exit(1)
    
    if not os.path.exists("assets"):
        print("❌ 错误: 当前目录中找不到 assets 文件夹")
        print("请确保在项目根目录中运行此脚本")
        input("按回车键退出...")
        sys.exit(1)
    
    print("✅ 项目文件检查通过")
    
    # 步骤4: 检查并安装PyInstaller
    print_step("4/7", "PyInstaller检查")
    if not check_pyinstaller():
        if not install_pyinstaller():
            print("\n❌ 无法安装PyInstaller，请手动安装: pip install pyinstaller")
            input("按回车键退出...")
            sys.exit(1)
    
    # 步骤5: 清理之前的打包文件
    print_step("5/7", "清理旧文件")
    if not clean_build_dirs():
        print("\n❌ 清理打包目录失败")
        input("按回车键退出...")
        sys.exit(1)
    
    # 步骤6: 打包
    print_step("6/7", "打包应用程序")
    
    # 打包窗口版本
    print("\n" + "=" * 20 + " 窗口版本 " + "=" * 20)
    if not build_executable(console_mode=False, show_output=True):
        print("\n❌ 窗口版本打包失败！请检查错误信息。")
        input("按回车键退出...")
        sys.exit(1)
    
    # 保存窗口版本
    window_exe_path = Path("dist") / "Aemeath.exe"
    if window_exe_path.exists():
        # 获取当前版本号
        current_version = get_version()
        # 创建带版本号的文件名
        window_backup = Path("dist") / f"Aemeath{current_version}.exe"
        window_backup_alt = Path("dist") / "Aemeath_Window.exe"  # 保留原有的无版本号文件名
        
        # 复制为带版本号的文件
        shutil.copy2(window_exe_path, window_backup)
        print(f"✅ 窗口版本已保存为: {window_backup.absolute()}")
        
        # 同时保留原有的无版本号文件名
        shutil.copy2(window_exe_path, window_backup_alt)
        print(f"✅ 窗口版本已保存为: {window_backup_alt.absolute()}")
        
        # 获取文件大小
        file_size = window_backup.stat().st_size / (1024 * 1024)  # MB
        print(f"   文件大小: {file_size:.2f} MB")
    
    # 清理中间文件
    if os.path.exists("build"):
        shutil.rmtree("build")
        print("✅ 已清理中间文件")
    
    # 打包控制台版本
    print("\n" + "=" * 20 + " 控制台版本 " + "=" * 20)
    if not build_executable(console_mode=True, show_output=True):
        print("\n❌ 控制台版本打包失败！请检查错误信息。")
        input("按回车键退出...")
        sys.exit(1)
    
    # 步骤7: 检查打包结果
    print_step("7/7", "检查打包结果")
    console_exe_path = Path("dist") / "Aemeath_Console.exe"
    
    if window_exe_path.exists() and console_exe_path.exists():
        # 获取控制台版本大小
        console_size = console_exe_path.stat().st_size / (1024 * 1024)  # MB
        print(f"   控制台版本大小: {console_size:.2f} MB")
        
        # 计算总耗时
        total_time = time.time() - start_time
        minutes, seconds = divmod(total_time, 60)
        
        print_header("打包完成！")
        print("\n📦 已生成两个版本：")
        
        # 获取带版本号的文件路径
        current_version = get_version()
        versioned_window_exe_path = Path("dist") / f"Aemeath{current_version}.exe"
        
        print(f"\n1. 窗口版本: {versioned_window_exe_path.absolute()}")
        print(f"   文件大小: {file_size:.2f} MB")
        print(f"\n2. 控制台版本: {console_exe_path.absolute()}")
        print(f"   文件大小: {console_size:.2f} MB")
        
        print(f"\n📋 其他文件:")
        print(f"\n3. 无版本号窗口版本: {window_exe_path.absolute()}")
        print(f"   文件大小: {file_size:.2f} MB")
        print(f"\n4. 备份窗口版本: {Path('dist') / 'Aemeath_Window.exe'}")
        
        print(f"\n⏱️ 总耗时: {int(minutes)}分{int(seconds)}秒")
        
        print("\n" + "=" * 60)
        print("📋 使用说明:")
        print("=" * 60)
        print("\n1. 请确保在首次运行时配置API密钥")
        print("2. 如果遇到缺少模块的错误，请更新aemeath.spec文件中的hiddenimports")
        print("3. 如果遇到资源文件找不到的错误，请检查assets目录是否正确包含")
        print("4. 控制台版本会显示调试信息，适合排查问题")
        print("5. 窗口版本适合正常使用，不会显示控制台窗口")
        print("\n🎯 运行命令:")
        print(f"   窗口版本: {window_exe_path.absolute()}")
        print(f"   控制台版本: {console_exe_path.absolute()}")
        
        # 检查是否可以运行
        print("\n" + "=" * 60)
        print("🚀 测试运行:")
        print("=" * 60)
        test_choice = input("\n是否要测试运行窗口版本？(y/n): ").lower().strip()
        
        if test_choice == 'y':
            print("\n正在启动窗口版本...")
            try:
                subprocess.Popen([str(window_exe_path)])
                print("✅ 窗口版本已启动")
            except Exception as e:
                print(f"❌ 启动失败: {e}")
        
        print("\n打包任务完成！")
        
        # 询问是否创建发布包
        create_release = input("\n是否创建发布包？(y/n): ").lower().strip()
        if create_release == 'y':
            # 获取带版本号的窗口可执行文件路径
            current_version = get_version()
            versioned_window_exe_path = Path("dist") / f"Aemeath{current_version}.exe"
            if versioned_window_exe_path.exists():
                create_release_package(version, versioned_window_exe_path, console_exe_path)
            else:
                # 如果带版本号的文件不存在，使用不带版本号的文件
                create_release_package(version, window_exe_path, console_exe_path)
        
        input("按回车键退出...")
    else:
        print("❌ 打包完成但找不到可执行文件")
        input("按回车键退出...")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n用户中断打包过程")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 打包过程中发生未预期的错误: {e}")
        sys.exit(1)