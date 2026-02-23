# Aemeath 待实现功能清单

*"爱弥斯（Aemeath），你的桌面AI伙伴~"*

## 1. 人格选择功能

### 功能概述
实现AI人格选择功能，允许用户在多种预设人格之间切换，每种人格有不同的说话风格和性格特点。

### 当前状态
- 后端已实现5种人格：爱弥斯、默认、专业助手、超萌、傲娇
- 人格定义在 `src/ai/emys_character.py` 和 `src/ai/llm_engine.py`
- **问题**：UI界面中缺少人格选择选项，目前默认使用"爱弥斯"人格

### 实现步骤

#### 1.1 更新 `src/ai/config_dialog.py`
在LLM配置选项卡中添加人格选择区域：
- [ ] 添加"人格选择"标签和下拉框
- [ ] 从 `llm_engine.py` 的 `PERSONALITIES` 字典加载选项
- [ ] 保存选择的人格到配置文件

#### 1.2 更新 `src/ai/simple_config_dialog.py`
在简单配置对话框中添加人格选择：
- [ ] 添加人格选择单选按钮组
- [ ] 保存选择的人格到配置文件

#### 1.3 更新托盘菜单（可选）
在托盘菜单中添加快速人格切换选项：
- [ ] 在AI助手子菜单中添加人格选择子菜单
- [ ] 实现快速切换功能

### 配置项（已存在）
```python
# config.py 中已存在
"ai_personality": "aemeath",  # 当前选择的人格
```

### 技术细节
- 人格切换后需要重新加载AI引擎配置
- 不同人格使用不同的系统提示词
- 人格提示词在 `llm_engine.py` 的 `_get_system_prompt()` 方法中定义

---

## 2. 屏幕识别AI对话功能

### 功能概述
监听用户切换窗口，触发截屏并调用AI分析屏幕内容，桌宠通过气泡回复。

### 技术方案
- **模型**: 智谱 GLM-4V-Flash（免费）
- **触发方式**: Windows API `SetWinEventHook` 监听 `EVENT_SYSTEM_FOREGROUND`
- **截图**: `mss` 库
- **调用方式**: 智谱官方 SDK `zhipuai`

### 配置项（新增）
```python
# config.py 新增配置
"screen_ai_enabled": False,           # 是否启用
"screen_ai_trigger_prob": 0.3,        # 触发概率 0.0-1.0
"screen_ai_model": "glm-4v-flash",    # 识图模型
"screen_ai_api_key": "",               # API密钥（可复用ai_api_key）
"screen_ai_base_url": "https://open.bigmodel.cn/api/paas/v4"
```

### 实现步骤

#### 2.1 新建 `src/ai/screen_analyzer.py`
- `ScreenAnalyzer` 类
- `start_listening()` - 启动窗口监听
- `stop_listening()` - 停止监听
- `capture_screen()` - 截取屏幕
- `analyze_screen(image)` - 调用智谱API分析
- `trigger_speaking(response)` - 触发气泡回复

#### 2.2 更新 `src/config.py`
- 添加屏幕识别相关配置项

#### 2.3 更新 `src/ai/config_dialog.py`
添加识图AI配置区域：
- [ ] 启用屏幕识别复选框
- [ ] 触发概率滑块 (0-100%)
- [ ] API密钥输入（可选择复用现有AI配置）
- [ ] 测试连接按钮

#### 2.4 更新 `src/platform/tray.py`
AI助手子菜单添加：
- [ ] "屏幕识别" 开关（勾选状态关联配置）

#### 2.5 更新 `src/core/pet_core.py`
- 初始化 `ScreenAnalyzer`
- 接入气泡回复系统

### 依赖
```bash
pip install zhipuai mss
```

### 参考代码结构
```python
# src/ai/screen_analyzer.py
import ctypes
from ctypes import wintypes
import mss
import base64
from zhipuai import ZhipuAI

class ScreenAnalyzer:
    def __init__(self, app):
        self.app = app
        self.enabled = False
        self.trigger_prob = 0.3
        self.client = None
    
    def start_listening(self):
        # 使用 SetWinEventHook 监听窗口切换
        pass
    
    def _on_window_change(self, ...):
        if random.random() < self.trigger_prob:
            self._analyze_current_screen()
    
    def _analyze_current_screen(self):
        # 截图 -> base64 -> 调用智谱API -> 气泡回复
        pass
```

---

## 3. 音效添加


---

## 4. 翻译功能