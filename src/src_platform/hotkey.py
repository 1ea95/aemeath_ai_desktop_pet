"""全局快捷键模块"""

from __future__ import annotations

import ctypes
import threading
import time
from ctypes import wintypes
from typing import Callable, Dict, Optional, TYPE_CHECKING

try:
    import win32gui
    import win32clipboard

    HAS_PYWIN32 = True
except ImportError:
    HAS_PYWIN32 = False

if TYPE_CHECKING:
    from src.core.pet_core import DesktopPet


# Windows API 常量
WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008

# 虚拟键码
VK_F1 = 0x70
VK_F2 = 0x71
VK_F3 = 0x72
VK_F4 = 0x73
VK_F5 = 0x74
VK_F6 = 0x75
VK_F7 = 0x76
VK_F8 = 0x77
VK_F9 = 0x78
VK_F10 = 0x79
VK_F11 = 0x7A
VK_F12 = 0x7B
VK_H = 0x48
VK_P = 0x50
VK_Q = 0x51
VK_S = 0x53
VK_T = 0x54
VK_A = 0x41
VK_CONTROL = 0x11
VK_LCONTROL = 0xA2
VK_RCONTROL = 0xA3

# 剪贴板常量
CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002

# ctypes.wintypes 在部分 Python/平台组合下没有 ULONG_PTR
ULONG_PTR = getattr(wintypes, "ULONG_PTR", ctypes.c_size_t)


def _init_winapi_prototypes() -> None:
    """初始化常用 WinAPI 的 argtypes/restype。

    ctypes 默认 restype 是 c_int；在 64 位下会导致句柄/指针截断，进而触发访问冲突。
    """

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    # user32
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = wintypes.BOOL
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = wintypes.HANDLE
    user32.EmptyClipboard.argtypes = []
    user32.EmptyClipboard.restype = wintypes.BOOL
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE
    user32.GetClipboardSequenceNumber.argtypes = []
    user32.GetClipboardSequenceNumber.restype = wintypes.DWORD
    user32.GetAsyncKeyState.argtypes = [wintypes.INT]
    user32.GetAsyncKeyState.restype = wintypes.SHORT
    user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
    user32.GetCursorPos.restype = wintypes.BOOL
    user32.GetForegroundWindow.argtypes = []
    user32.GetForegroundWindow.restype = wintypes.HWND
    # 这里用 c_void_p 规避 INPUT 前置定义问题
    user32.SendInput.argtypes = [wintypes.UINT, ctypes.c_void_p, ctypes.c_int]
    user32.SendInput.restype = wintypes.UINT

    # kernel32
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = wintypes.LPVOID
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.restype = wintypes.BOOL
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalSize.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalSize.restype = ctypes.c_size_t
    kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalFree.restype = wintypes.HGLOBAL
    kernel32.GetConsoleWindow.argtypes = []
    kernel32.GetConsoleWindow.restype = wintypes.HWND


_init_winapi_prototypes()

# 键盘钩子常量
WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101


class GlobalHotkey:
    """全局快捷键管理器"""

    _instance: Optional["GlobalHotkey"] = None
    _hotkey_id = 1000

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self.app: DesktopPet | None = None
        self._hotkeys: Dict[int, tuple] = {}  # id -> (modifiers, vk, callback)
        self._is_running = False
        self._original_wndproc = None
        self._hwnd = None
        self._ctrl_pressed_time: float | None = None
        self._ctrl_triggered = False
        self._ctrl_after_id: str | None = None
        self._ctrl_suppress_until: float | None = None

        # 鼠标划词相关
        self._mouse_hook = None
        self._is_dragging = False
        self._drag_start_pos: tuple[int, int] | None = None
        self._mouse_after_id: str | None = None
        self._last_left_down = False
        self._last_selected_text = ""
        self._last_selected_at: float | None = None
        self._translate_panel_shown = False  # 防止重复弹出
        self._old_clipboard_text: str = ""  # 备份旧剪贴板内容

    def _backup_clipboard(self) -> str:
        """备份当前剪贴板文本内容"""
        return self._get_clipboard_text()

    def _restore_clipboard(self, text: str) -> bool:
        """恢复剪贴板文本内容"""
        if text is None:
            text = ""
        return self._set_clipboard_text(text)

    def _get_clipboard_text(self) -> str:
        """读取Windows剪贴板文本"""
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        text = ""
        # 剪贴板可能被其它进程短暂占用，做一次短重试
        opened = False
        for _ in range(20):
            if user32.OpenClipboard(None):
                opened = True
                break
            time.sleep(0.01)
        if not opened:
            return ""
        try:
            handle = user32.GetClipboardData(CF_UNICODETEXT)
            if not handle:
                return ""

            ptr = kernel32.GlobalLock(handle)
            if not ptr:
                return ""
            try:
                size = 0
                try:
                    size = int(kernel32.GlobalSize(handle))
                except Exception:
                    size = 0

                if size <= 0:
                    return ""

                # 以 GlobalSize 限制读取长度，避免 wstring_at 扫描越界
                max_chars = max(0, (size // ctypes.sizeof(ctypes.c_wchar)))
                if max_chars <= 0:
                    return ""

                try:
                    raw = ctypes.wstring_at(ptr, max_chars)
                except (OSError, ValueError):
                    return ""

                text = raw.split("\x00", 1)[0]
            finally:
                kernel32.GlobalUnlock(handle)
        finally:
            user32.CloseClipboard()

        return text

    def _is_foreground_console(self) -> bool:
        """当前前台窗口是否为本进程控制台窗口。

        如果是，发送 Ctrl+C 会触发 KeyboardInterrupt，应避免。
        """
        if HAS_PYWIN32:
            try:
                hwnd = win32gui.GetForegroundWindow()
                class_name = win32gui.GetClassName(hwnd)
                window_title = win32gui.GetWindowText(hwnd)

                # 常见控制台类名
                console_classes = [
                    "ConsoleWindowClass",  # CMD / PowerShell
                    "CASCADIA_HOSTING_WINDOW_CLASS",  # Windows Terminal
                    "Terminator",  # 其他终端
                    "mintty",  # Git Bash
                ]

                if class_name in console_classes:
                    return True

                # 检查标题关键词（更保守）
                title_lower = window_title.lower()
                unsafe_titles = [
                    "cmd.exe",
                    "powershell",
                    "windows terminal",
                    "anaconda",
                ]
                for t in unsafe_titles:
                    if t in title_lower:
                        return True

                return False
            except Exception:
                pass

        # 兜底：使用原有方式
        try:
            fg = ctypes.windll.user32.GetForegroundWindow()
            console = ctypes.windll.kernel32.GetConsoleWindow()
            return bool(fg) and bool(console) and int(fg) == int(console)
        except Exception:
            return False

    def _is_foreground_our_window(self) -> bool:
        """当前前台窗口是否为主窗口（尽量避免给自己发 Ctrl+C）。"""

        if not self._hwnd:
            return False

        if HAS_PYWIN32:
            try:
                hwnd = win32gui.GetForegroundWindow()
                return bool(hwnd) and int(hwnd) == int(self._hwnd)
            except Exception:
                pass

        # 兜底
        try:
            fg = ctypes.windll.user32.GetForegroundWindow()
            return bool(fg) and int(fg) == int(self._hwnd)
        except Exception:
            return False

    def _is_safe_to_copy(self) -> bool:
        """检查当前窗口是否适合执行 Ctrl+C 复制操作

        返回 True 表示安全可以复制，False 表示应该跳过
        """
        # 检查是否是控制台窗口
        if self._is_foreground_console():
            return False

        # 检查是否是我们自己的窗口
        if self._is_foreground_our_window():
            return False

        # 使用 pywin32 进行更精确的检测
        if HAS_PYWIN32:
            try:
                hwnd = win32gui.GetForegroundWindow()
                class_name = win32gui.GetClassName(hwnd)
                window_title = win32gui.GetWindowText(hwnd)

                # 额外安全检查：常见的 IDE、编辑器类名
                unsafe_classes = [
                    "ConsoleWindowClass",
                    "CASCADIA_HOSTING_WINDOW_CLASS",
                    "Terminator",
                    "mintty",
                    "vim",  # Vim Terminal
                    "Windows.UI.Core.CoreWindow",  # UWP 应用
                ]

                if class_name in unsafe_classes:
                    return False

                # 检查标题中的不安全关键词
                title_lower = window_title.lower()
                unsafe_keywords = ["main.py", "debug", "python", "cmd", "powershell"]
                for keyword in unsafe_keywords:
                    if keyword in title_lower and (
                        "visual studio" not in title_lower and "code" not in title_lower
                    ):
                        # 排除 VS Code（它可以安全复制）
                        return False

                return True
            except Exception:
                pass

        return True

    def _set_clipboard_text(self, text: str) -> bool:
        """写入Windows剪贴板文本"""
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        opened = False
        for _ in range(20):
            if user32.OpenClipboard(None):
                opened = True
                break
            time.sleep(0.01)
        if not opened:
            return False

        hglob = None
        try:
            user32.EmptyClipboard()

            buf = ctypes.create_unicode_buffer(text)
            size = ctypes.sizeof(buf)
            hglob = kernel32.GlobalAlloc(GMEM_MOVEABLE, size)
            if not hglob:
                return False

            ptr = kernel32.GlobalLock(hglob)
            if not ptr:
                return False

            try:
                ctypes.memmove(ptr, buf, size)
            finally:
                kernel32.GlobalUnlock(hglob)

            if not user32.SetClipboardData(CF_UNICODETEXT, hglob):
                return False

            # 成功后句柄归系统所有，不要释放
            hglob = None
            return True
        finally:
            user32.CloseClipboard()
            if hglob:
                try:
                    kernel32.GlobalFree(hglob)
                except Exception:
                    pass

    def register_app(self, app: DesktopPet) -> bool:
        """注册应用程序

        Args:
            app: DesktopPet 实例

        Returns:
            是否成功
        """
        self.app = app

        # 获取窗口句柄
        try:
            self._hwnd = ctypes.windll.user32.GetParent(app.root.winfo_id())
            if not self._hwnd:
                print("获取窗口句柄失败")
                return False
        except Exception as e:
            print(f"获取窗口句柄失败: {e}")
            return False

        # 设置窗口消息处理
        try:
            self._setup_message_handler()
            self._register_default_hotkeys()
            self._start_ctrl_key_monitor()
            self._start_mouse_hook()
            self._is_running = True
            print("全局快捷键已注册")
            return True
        except Exception as e:
            print(f"注册全局快捷键失败: {e}")
            return False

    def _setup_message_handler(self) -> None:
        """设置窗口消息处理器"""
        # 保存原始窗口过程
        GWL_WNDPROC = -4
        WndProcType = ctypes.WINFUNCTYPE(
            wintypes.LPARAM,
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
        )

        def wndproc(hwnd, msg, wparam, lparam):
            if msg == WM_HOTKEY:
                hotkey_id = wparam
                if hotkey_id in self._hotkeys:
                    _, _, callback = self._hotkeys[hotkey_id]
                    try:
                        callback()
                    except Exception as e:
                        print(f"执行快捷键回调失败: {e}")
                return 0

            # 调用原始窗口过程
            if self._original_wndproc:
                return ctypes.windll.user32.CallWindowProcW(
                    self._original_wndproc, hwnd, msg, wparam, lparam
                )
            return 0

        self._wndproc = WndProcType(wndproc)
        self._original_wndproc = ctypes.windll.user32.SetWindowLongW(
            self._hwnd, GWL_WNDPROC, self._wndproc
        )

    def _register_default_hotkeys(self) -> None:
        """注册默认快捷键（已禁用）"""
        # 快捷键功能已移除
        pass

    def register(
        self,
        modifiers: int,
        vk: int,
        callback: Callable[[], None],
    ) -> bool:
        """注册快捷键

        Args:
            modifiers: 修饰键（MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN 的组合）
            vk: 虚拟键码
            callback: 回调函数

        Returns:
            是否成功
        """
        if not self._hwnd:
            return False

        hotkey_id = GlobalHotkey._hotkey_id
        GlobalHotkey._hotkey_id += 1

        try:
            result = ctypes.windll.user32.RegisterHotKey(
                self._hwnd,
                hotkey_id,
                modifiers,
                vk,
            )
            if result:
                self._hotkeys[hotkey_id] = (modifiers, vk, callback)
                return True
            else:
                print(f"注册快捷键失败: {modifiers}+{vk}")
                return False
        except Exception as e:
            print(f"注册快捷键失败: {e}")
            return False

    def unregister_all(self) -> None:
        """注销所有快捷键"""
        # 停止Tk after轮询
        if self.app and self.app.root and self.app.root.winfo_exists():
            try:
                if self._ctrl_after_id:
                    self.app.root.after_cancel(self._ctrl_after_id)
            except Exception:
                pass
            try:
                if self._mouse_after_id:
                    self.app.root.after_cancel(self._mouse_after_id)
            except Exception:
                pass

        self._ctrl_after_id = None
        self._mouse_after_id = None

        if not self._hwnd:
            return

        for hotkey_id in list(self._hotkeys.keys()):
            try:
                ctypes.windll.user32.UnregisterHotKey(self._hwnd, hotkey_id)
            except Exception:
                pass

        self._hotkeys.clear()
        self._is_running = False

        # 恢复原始窗口过程
        if self._original_wndproc and self._hwnd:
            try:
                GWL_WNDPROC = -4
                ctypes.windll.user32.SetWindowLongW(
                    self._hwnd, GWL_WNDPROC, self._original_wndproc
                )
            except Exception:
                pass

        print("全局快捷键已注销")

    def _toggle_visible(self) -> None:
        """切换显示/隐藏"""
        if self.app:
            if self.app.root.state() == "withdrawn":
                self.app.root.deiconify()
                # 显示宠物时，如果音乐面板之前是显示的，也显示音乐面板
                if hasattr(self.app, "music_panel") and self.app.music_panel and hasattr(self.app.music_panel, "_was_visible") and self.app.music_panel._was_visible:
                    self.app.music_panel.show()
                # 显示宠物时，如果语音气泡之前是显示的，也显示语音气泡
                if hasattr(self.app, "speech_bubble") and self.app.speech_bubble and hasattr(self.app.speech_bubble, "_was_visible") and self.app.speech_bubble._was_visible:
                    # 重新显示歌名
                    title = self.app.get_current_music_title()
                    if title:
                        self.app.speech_bubble.show(f"🎵 {title}", duration=None, allow_during_music=True)
            else:
                # 隐藏宠物时，记录音乐面板的显示状态并隐藏音乐面板
                if hasattr(self.app, "music_panel") and self.app.music_panel and self.app.music_panel.window and self.app.music_panel.window.winfo_exists() and self.app.music_panel.window.state() != "withdrawn":
                    self.app.music_panel._was_visible = True
                    self.app.music_panel.hide()
                else:
                    if hasattr(self.app, "music_panel") and self.app.music_panel:
                        self.app.music_panel._was_visible = False
                # 隐藏宠物时，记录语音气泡的显示状态并隐藏语音气泡
                if hasattr(self.app, "speech_bubble") and self.app.speech_bubble and self.app.speech_bubble.window and self.app.speech_bubble.window.winfo_exists() and self.app.speech_bubble.window.state() != "withdrawn":
                    self.app.speech_bubble._was_visible = True
                    self.app.speech_bubble.hide()
                else:
                    if hasattr(self.app, "speech_bubble") and self.app.speech_bubble:
                        self.app.speech_bubble._was_visible = False
                self.app.root.withdraw()

    def _quit(self) -> None:
        """退出程序"""
        if self.app:
            self.app.request_quit()

    def _show_quick_menu(self) -> None:
        """显示快捷菜单"""
        if self.app:
            self.app.quick_menu.show()

    def _open_ai_chat(self) -> None:
        """打开AI对话"""
        if self.app:
            self.app.open_ai_chat_dialog()

    def _start_ctrl_key_monitor(self) -> None:
        """启动Ctrl键监听（Tk after轮询）"""
        if not self.app or not self.app.root:
            return

        # 防止重复启动
        if self._ctrl_after_id:
            return

        self._ctrl_pressed_time = None
        self._ctrl_triggered = False

        def _tick() -> None:
            if not self.app or not self.app.root or not self.app.root.winfo_exists():
                self._ctrl_after_id = None
                return

            try:
                now = time.time()
                if (
                    self._ctrl_suppress_until is not None
                    and now < self._ctrl_suppress_until
                ):
                    # 复制模拟按键期间，忽略Ctrl状态，避免误触发
                    self._ctrl_pressed_time = None
                    self._ctrl_triggered = False
                else:
                    ctrl_down = False
                    try:
                        ctrl_down = (
                            (
                                ctypes.windll.user32.GetAsyncKeyState(VK_LCONTROL)
                                & 0x8000
                            )
                            or (
                                ctypes.windll.user32.GetAsyncKeyState(VK_RCONTROL)
                                & 0x8000
                            )
                            or (
                                ctypes.windll.user32.GetAsyncKeyState(VK_CONTROL)
                                & 0x8000
                            )
                        )
                    except Exception:
                        ctrl_down = (
                            ctypes.windll.user32.GetAsyncKeyState(VK_CONTROL) & 0x8000
                        ) != 0

                    if ctrl_down:
                        if self._ctrl_pressed_time is None:
                            self._ctrl_pressed_time = now
                            self._ctrl_triggered = False
                        else:
                            elapsed = (now - self._ctrl_pressed_time) * 1000
                            if elapsed >= 500 and not self._ctrl_triggered:
                                self._ctrl_triggered = True
                                self._on_ctrl_long_press()
                    else:
                        self._ctrl_pressed_time = None
                        self._ctrl_triggered = False
            except Exception as e:
                print(f"Ctrl键监听异常: {e}")

            self._ctrl_after_id = self.app.root.after(50, _tick)

        self._ctrl_after_id = self.app.root.after(50, _tick)

    def _on_ctrl_long_press(self) -> None:
        """Ctrl键长按触发翻译"""
        if not self.app:
            return

        from src.config import load_config

        config = load_config()
        if not config.get("translate_enabled", False):
            return

        # 如果翻译窗口已经显示，不重复弹出
        if self._translate_panel_shown:
            return

        # 前台是控制台时，给用户提示
        if not self._is_safe_to_copy():
            print("提示: 请在浏览器等应用中选中文本，然后长按Ctrl触发翻译")
            print("      (避免在控制台窗口前台按下Ctrl导致程序中断)")
            return

        # 优先使用最近一次划词捕获的文本（避免剪贴板被其它程序改写）
        try:
            text = ""
            if self._last_selected_at is not None:
                if (
                    time.time() - self._last_selected_at
                ) <= 10 and self._last_selected_text.strip():
                    text = self._last_selected_text.strip()

            if not text:
                text = self._get_clipboard_text().strip()

            if text:
                # 设置标志防止重复触发
                self._translate_panel_shown = True

                # 显示翻译窗口
                if hasattr(self.app, "translate_window"):
                    self.app.translate_window.show(text)

                # 300ms后允许再次触发
                def reset_flag():
                    self._translate_panel_shown = False

                if self.app and self.app.root and self.app.root.winfo_exists():
                    self.app.root.after(300, reset_flag)

        except Exception as e:
            print(f"读取剪贴板失败: {e}")

    def _start_mouse_hook(self) -> None:
        """启动鼠标轮询监听划词（Tk after轮询）"""
        if not self.app or not self.app.root:
            return

        if self._mouse_after_id:
            return

        self._last_left_down = False

        def _cursor_pos() -> tuple[int, int]:
            pt = wintypes.POINT()
            ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
            return int(pt.x), int(pt.y)

        def _tick() -> None:
            if not self.app or not self.app.root or not self.app.root.winfo_exists():
                self._mouse_after_id = None
                return

            try:
                left_down = (ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000) != 0

                if left_down and not self._last_left_down:
                    self._is_dragging = True
                    self._drag_start_pos = _cursor_pos()
                elif (not left_down) and self._last_left_down:
                    if self._is_dragging:
                        self._is_dragging = False
                        start = self._drag_start_pos
                        end = _cursor_pos()
                        self._drag_start_pos = None
                        if start:
                            dx = end[0] - start[0]
                            dy = end[1] - start[1]
                            if (dx * dx + dy * dy) >= 400:
                                self.app.root.after(120, self._on_text_selection)

                self._last_left_down = left_down
            except Exception as e:
                print(f"鼠标检测异常: {e}")

            self._mouse_after_id = self.app.root.after(50, _tick)

        self._mouse_after_id = self.app.root.after(50, _tick)

    def _stop_mouse_hook(self) -> None:
        """停止鼠标钩子"""
        # 兼容旧接口：实际停止在 unregister_all 里做 after_cancel
        self._mouse_hook = None

    def _on_text_selection(self) -> None:
        """检测到划词后自动复制到剪贴板"""
        from src.config import load_config

        config = load_config()
        if not config.get("translate_enabled", False):
            return

        if not self.app or not self.app.root or not self.app.root.winfo_exists():
            return

        # 在后台线程执行复制与剪贴板读取，避免阻塞Tk主线程
        threading.Thread(
            target=self._capture_selection_to_clipboard, daemon=True
        ).start()

    def _capture_selection_to_clipboard(self) -> None:
        """触发Ctrl+C并捕获剪贴板内容"""
        try:
            user32 = ctypes.windll.user32
            seq_before = 0
            try:
                seq_before = int(user32.GetClipboardSequenceNumber())
            except Exception:
                seq_before = 0

            # 检查当前窗口是否适合执行复制操作
            if not self._is_safe_to_copy():
                return

            # 备份当前剪贴板内容（用于事后恢复）
            self._old_clipboard_text = self._backup_clipboard()

            # 抑制Ctrl长按检测（模拟按键期间）
            self._ctrl_suppress_until = time.time() + 0.35
            self._simulate_ctrl_c()

            # 等待剪贴板变更（浏览器复制有时较慢，放宽到800ms）
            deadline = time.time() + 0.8
            seq_changed = False
            while time.time() < deadline:
                try:
                    seq_now = int(user32.GetClipboardSequenceNumber())
                except Exception:
                    seq_now = seq_before
                if seq_now != seq_before:
                    seq_changed = True
                    break
                time.sleep(0.02)

            text = self._get_clipboard_text().strip()
            if seq_changed and text:
                self._last_selected_text = text
                self._last_selected_at = time.time()

            # 恢复旧剪贴板内容（无感恢复）
            self._restore_clipboard(self._old_clipboard_text)
            self._old_clipboard_text = ""
        except Exception as e:
            print(f"划词复制失败: {e}")

    def _simulate_ctrl_c(self) -> None:
        """模拟Ctrl+C按键"""
        user32 = ctypes.windll.user32

        INPUT_KEYBOARD = 1
        KEYEVENTF_KEYUP = 0x0002
        VK_C = 0x43

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [
                ("wVk", wintypes.WORD),
                ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR),
            ]

        class INPUT(ctypes.Structure):
            class _I(ctypes.Union):
                _fields_ = [("ki", KEYBDINPUT)]

            _anonymous_ = ("i",)
            _fields_ = [("type", wintypes.DWORD), ("i", _I)]

        inputs = (INPUT * 4)(
            INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(wVk=VK_CONTROL, dwFlags=0)),
            INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(wVk=VK_C, dwFlags=0)),
            INPUT(
                type=INPUT_KEYBOARD, ki=KEYBDINPUT(wVk=VK_C, dwFlags=KEYEVENTF_KEYUP)
            ),
            INPUT(
                type=INPUT_KEYBOARD,
                ki=KEYBDINPUT(wVk=VK_CONTROL, dwFlags=KEYEVENTF_KEYUP),
            ),
        )

        try:
            # 现在 INPUT 已定义，设置精确签名避免参数解析错误
            user32.SendInput.argtypes = [
                wintypes.UINT,
                ctypes.POINTER(INPUT),
                ctypes.c_int,
            ]
            user32.SendInput.restype = wintypes.UINT
            user32.SendInput(4, ctypes.byref(inputs), ctypes.sizeof(INPUT))
        except Exception:
            # 兜底：老接口
            user32.keybd_event(VK_CONTROL, 0, 0, 0)
            user32.keybd_event(VK_C, 0, 0, 0)
            user32.keybd_event(VK_C, 0, KEYEVENTF_KEYUP, 0)
            user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)

        # 模拟按键结束后稍晚解除抑制（给系统处理剪贴板留一点时间）
        try:
            self._ctrl_suppress_until = time.time() + 0.15
        except Exception:
            pass


# 全局实例
hotkey_manager = GlobalHotkey()