# Aemeath 项目重构说明

*"爱弥斯（Aemeath），你的桌面AI伙伴~"*

## v3.0版本架构优化

基于v2.0版本的模块化结构，v3.0版本进一步优化了代码架构，添加了语音交互系统，并重构了LLM引擎。

## v3.0版本项目结构

v3.0版本在v2.0基础上进一步优化了架构，添加了语音交互系统，并重构了LLM引擎：

```
├── constants.py           # 所有常量定义（配置值、Windows API 常量等）
├── config.py             # 配置管理（加载、保存、更新）
├── utils.py            # 通用工具函数（资源路径、版本获取等）
├── system.py           # Windows 系统功能（DPI、窗口置顶、鼠标穿透）
├── startup.py          # 开机自启管理
├── main.py             # 程序入口（53行）
├── src/
│   ├── core/           # 核心功能模块
│   │   ├── pet_core.py         # 桌面宠物主类
│   │   ├── state_manager.py    # 状态管理
│   │   └── window_manager.py  # 窗口管理
│   ├── ai/             # AI相关功能
│   │   ├── llm_engine.py       # LLM引擎（新增）
│   │   ├── chat_engine.py      # 聊天引擎
│   │   ├── config_dialog.py    # AI配置对话框
│   │   └── emys_character.py  # 人格设定
│   ├── voice/          # 语音交互系统（新增）
│   │   ├── voice_assistant.py   # 语音助手主控制器
│   │   ├── voice_recognition.py # 语音识别引擎
│   │   └── keyword_spotter.py # 关键词检测引擎
│   ├── ui/             # 用户界面组件
│   │   ├── ai_chat_panel.py    # AI聊天面板
│   │   ├── speech_bubble.py   # 对话气泡
│   │   ├── quick_menu.py      # 快捷菜单
│   │   ├── music_panel.py     # 音乐控制面板
│   │   └── pomodoro_indicator.py # 番茄钟指示器
│   ├── src_platform/    # 平台相关功能
│   │   ├── tray.py           # 系统托盘
│   │   ├── hotkey.py        # 全局快捷键
│   │   └── system.py         # 系统功能
│   ├── interaction/    # 交互处理
│   │   ├── click_handler.py   # 点击处理
│   │   └── drag_handler.py    # 拖动处理
│   ├── animation/     # 动画系统
│   │   ├── animation_manager.py # 动画管理器
│   │   ├── gif_utils.py       # GIF工具
│   │   └── cache.py          # 动画缓存
│   ├── behavior/      # 行为系统
│   │   ├── behavior_modes.py   # 行为模式
│   │   ├── motion_controller.py # 运动控制
│   │   └── routine_manager.py # 例程管理
│   ├── media/         # 媒体功能
│   │   └── music_controller.py # 音乐控制器
│   ├── translate/     # 翻译功能
│   │   └── __init__.py       # 翻译模块
│   ├── productivity/  # 生产力功能
│   │   └── pomodoro.py       # 番茄钟
│   └── net/           # 网络功能
│       └── version_checker.py  # 版本检查
└── assets/             # 资源文件
    ├── gifs/           # 动画资源
    ├── icon/           # 图标资源
    ├── music/          # 音乐文件
    ├── voice/          # 语音文件
    └── models/          # 模型文件（新增）
```

## v2.0版本项目结构

重构后的代码从单个 `main.py`（1353行）拆分成了以下模块：

```
.
├── constants.py        # 所有常量定义（配置值、Windows API 常量等）
├── config.py          # 配置管理（加载、保存、更新）
├── utils.py           # 通用工具函数（资源路径、版本获取等）
├── system.py          # Windows 系统功能（DPI、窗口置顶、鼠标穿透）
├── startup.py         # 开机自启管理
├── animations.py      # GIF 动画加载和处理
├── tray.py            # 系统托盘控制器
├── pet.py             # 桌面宠物主类（DesktopPet）
├── version_checker.py # 版本检查功能
└── main.py            # 程序入口（53行）
```

## v3.0版本主要改进

### 1. 语音交互系统
- **模块化设计**：将语音功能拆分为独立模块，便于维护
- **离线唤醒**：基于sherpa-onnx的本地关键词检测
- **在线识别**：集成阿里云ASR服务，提高识别准确率
- **语音合成**：使用阿里云TTS服务，提供自然语音输出
- **智能集成**：与AI聊天引擎无缝集成，实现完整语音交互

### 2. LLM引擎重构
- **流式回复**：支持实时显示AI回复过程
- **多服务商支持**：统一API接口，支持多种AI服务商
- **人格系统**：增强的角色设定，提供更自然的对话体验
- **错误处理**：完善的异常处理和重试机制

### 3. 架构优化
- **依赖管理**：使用pyproject.toml管理项目依赖
- **配置系统**：统一的配置加载和保存机制
- **日志系统**：详细的运行日志，便于问题排查
- **性能优化**：减少资源占用，提高运行效率

### 4. Bug修复
- **音乐播放修复**：修复音乐自动连播时没有更新歌名的问题
- **导入错误修复**：修复platform包导入错误的问题
- **配置处理优化**：改进配置文件处理机制

## v2.0版本主要改进

### 1. 模块拆分
- **职责分离**：每个模块只负责一个功能领域
- **可维护性**：代码结构清晰，便于理解和修改
- **可测试性**：模块独立，便于单元测试

### 2. 性能优化
- **配置缓存**：使用 `_config_cache` 避免重复读取配置文件
- **鼠标位置缓存**：在 `move()` 中缓存鼠标位置，减少 `winfo_pointerx/y` 调用
- **距离计算优化**：使用平方距离比较避免开方运算
- **窗口更新优化**：仅在位置变化时调用 `geometry()`
- **抖动降频**：每 5 帧更新一次随机抖动

### 3. 异常处理改进
- **具体异常类型**：
  - `FileNotFoundError` 代替裸 `except`
  - `json.JSONDecodeError` 处理配置解析错误
  - `OSError` 和 `ctypes.WinError` 处理 Windows API 错误
- **错误信息**：提供有意义的错误提示
- **优雅降级**：出错时使用默认值，不影响程序运行

### 4. 代码质量
- **类型注解**：函数参数和返回值都有类型提示
- **文档字符串**：所有公共方法都有文档说明
- **命名规范**：清晰的命名，遵循 PEP 8
- **单一职责**：每个函数只做一件事

## 文件说明

### constants.py (2366 字节)
所有项目常量集中定义：
- 路径配置
- 缩放和透明度选项
- 运动参数
- Windows API 常量
- 状态机常量

### config.py (2249 字节)
配置管理模块：
- `load_config()`：带缓存的配置加载
- `save_config()`：配置保存
- `update_config()`：配置更新
- `get_config_value()`：获取单个配置值

### utils.py (2346 字节)
工具函数：
- `resource_path()`：PyInstaller 资源路径处理
- `get_version()`：获取当前版本（支持 version.txt 和 git）
- `normalize_version()`：版本号标准化
- `version_greater_than()`：版本比较

### system.py (2174 字节)
Windows 系统功能：
- `enable_dpi_awareness()`：DPI 感知
- `set_window_topmost()`：窗口置顶
- `set_click_through()`：鼠标穿透
- `get_window_handle()`：获取窗口句柄

### startup.py (2622 字节)
开机自启管理：
- `get_startup_executable_path()`：获取注册表路径
- `set_auto_startup()`：设置开机自启
- `check_and_fix_startup()`：检查和修复启动路径

### animations.py (2940 字节)
动画处理：
- `load_gif_frames()`：加载 GIF 帧
- `flip_frames()`：水平翻转帧
- `load_all_animations()`：加载所有动画资源

### tray.py (5458 字节)
系统托盘控制器：
- 菜单构建
- 事件处理
- 图标管理

### pet.py (18924 字节)
桌面宠物主类 `DesktopPet`：
- 窗口初始化
- 动画管理
- 运动系统（状态机）
- 事件处理
- 性能优化版本

### version_checker.py (3577 字节)
版本检查：
- `check_new_version()`：检查最新版本
- `show_update_dialog()`：显示更新对话框
- `check_version_and_notify()`：后台检查并通知

### main.py (1066 字节)
程序入口：
- DPI 感知初始化
- 创建宠物实例
- 启动托盘
- 版本检查
- 主循环

## 性能提升

### 优化前
- 每次 `move()` 调用都读取配置文件
- 多次调用 `winfo_pointerx/y`
- 频繁进行距离开方计算
- 每次移动都调用 `geometry()`

### 优化后
- 配置使用内存缓存，减少 IO
- 鼠标位置每帧只获取一次
- 使用平方距离比较，减少开方运算
- 仅在位置变化时更新窗口
- 抖动计算每 5 帧更新一次

## 如何运行

```bash
python main.py
```

## 打包

```bash
pyinstaller ameath.spec
```

注意：需要更新 `ameath.spec` 以包含新的模块文件。