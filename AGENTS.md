# AGENTS.md - Aemeath Coding Guidelines

## 🎯 v3.0版本更新内容

### 语音交互系统架构

新增完整的语音交互系统，采用模块化设计：

```
src/voice/
├── __init__.py
├── voice_assistant.py      # 语音助手主控制器
├── voice_recognition.py     # 语音识别引擎（阿里云ASR）
├── keyword_spotter.py      # 关键词检测引擎（sherpa-onnx）
└── voice_recognition.py     # 语音识别模块
```

**语音交互流程：**
1. `KeywordSpotter` 监听唤醒词（离线处理）
2. 检测到唤醒词后触发 `VoiceAssistant`
3. 启动 `VoiceRecognition` 进行语音识别（在线处理）
4. 识别结果发送给 `LLMEngine` 处理
5. AI回复通过TTS服务转换为语音播放

### LLM引擎重构

重构AI对话引擎，支持流式回复：

```
src/ai/
├── __init__.py
├── llm_engine.py           # LLM引擎主控制器（新增）
├── chat_engine.py          # 聊天引擎（重构）
├── emys_character.py       # 人格设定（增强）
├── config_dialog.py        # 配置对话框
└── simple_config_dialog.py # 简化配置对话框（新增）
```

**主要改进：**
- 流式回复支持，提升交互体验
- 统一的多服务商API接口
- 增强的人格系统和角色设定
- 完善的错误处理和重试机制

### 架构优化

**模块化设计：**
- 清晰的模块划分和职责分离
- 统一的配置管理系统
- 完善的错误处理和日志记录
- 优化的性能和资源占用

**新增工具：**
- `fix_config.py` - 配置文件修复工具
- `fix_glm_config.py` - GLM配置快速设置工具

---

## 📜 先前版本内容

## Project Overview
Aemeath is a Windows desktop pet application built with tkinter, Pillow, and pystray.
Python 3.12+ is required. The repo uses a `src/` module layout with a thin
bootstrap in `main.py`.

## Build, Run, Lint, Test

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Run the App (Development)
```bash
python main.py
```

### Build Windows Executable
```bash
pyinstaller Aemeath.spec
```

### Lint with Ruff
```bash
ruff check .
ruff check --fix .
```

### Syntax Check (All Modules)
```bash
python -m py_compile main.py src/*.py
```

### Tests
- Manual test: run `python main.py` and exercise tray/menu actions.
- If a pytest suite is added later, use:
```bash
pytest
pytest path/to/test_file.py::test_name
```

## Code Style Guidelines

### Imports
Group imports in this order with a blank line between groups:
1. Standard library
2. Third-party
3. Local modules (absolute imports; no relative imports)

Example:
```python
# 1. Standard library
import json
from pathlib import Path
from typing import Any, Dict, Optional

# 2. Third-party
import tkinter as tk
from PIL import Image, ImageTk
import pystray

# 3. Local modules (relative imports not used)
from constants import CONFIG_FILE
from config import load_config
```

### Formatting
- 4 spaces indentation
- UTF-8 encoding; Chinese comments and docstrings are preferred
- Max line length around 100 characters
- Use double quotes for strings
- Avoid trailing whitespace

### Naming Conventions
- Constants: `UPPER_CASE` (e.g., `GIF_DIR`, `SPEED_X`)
- Classes: `PascalCase` (e.g., `DesktopPet`, `TrayController`)
- Functions/variables: `snake_case` (e.g., `load_config`, `move_frames`)
- Private: `_leading_underscore` (e.g., `_config_cache`, `_init_window`)

### Type Hints
Use type hints for public functions and key helpers.
```python
def load_config(force_refresh: bool = False) -> Dict[str, Any]:
    """加载配置"""
    ...

def resource_path(relative_path: str) -> str:
    """获取资源路径"""
    ...
```

### Docstrings
Use Chinese with Google style.
```python
def function_name(param: type) -> return_type:
    """简短描述

    Args:
        param: 参数说明

    Returns:
        返回值说明
    """
```

### Error Handling
Use specific exceptions; avoid bare `except:`.
```python
try:
    with open(file, "r", encoding="utf-8") as f:
        data = json.load(f)
except FileNotFoundError:
    data = default_value
except json.JSONDecodeError as e:
    print(f"解析失败: {e}")
    data = default_value
```

### Windows API Handling
Wrap Windows API calls and log failures with specific exceptions.
```python
try:
    ctypes.windll.user32.SetWindowPos(...)
except (OSError, ctypes.WinError) as e:
    print(f"操作失败: {e}")
    return False
```

### Resource Paths (PyInstaller compatible)
Always resolve assets with `resource_path`.
```python
from utils import resource_path

path = resource_path("assets/gifs/move.gif")
```

### Configuration Management
Use config helpers and cache appropriately.
```python
from config import load_config, update_config

config = load_config()
update_config(scale_index=3)
```

### Performance Notes
- Cache config in memory (`_config_cache`)
- Avoid excessive `winfo_pointer` calls; cache mouse positions
- Use squared distance for comparisons

## Cursor/Copilot Rules
No `.cursor/rules/`, `.cursorrules`, or `.github/copilot-instructions.md` found.