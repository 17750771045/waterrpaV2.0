"""
控件检测模块
负责处理控件检测相关的功能，包括窗口控件获取、控件操作和操作记录
"""
import os
import re
import time
import ctypes
import pyautogui
import pyperclip
import win32gui
import win32con
import win32process
import win32api

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, 
    QListWidget, QListWidgetItem, QMessageBox, QInputDialog, QGroupBox, QLabel,
    QSpinBox, QCheckBox, QApplication, QFileDialog
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QTextCursor

# ctypes 定义
user32 = ctypes.WinDLL('user32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

WH_MOUSE_LL = 14
WH_KEYBOARD_LL = 13
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP = 0x0208
WM_MOUSEMOVE = 0x0200
WM_MOUSEWHEEL = 0x020A
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_QUIT = 0x0012
WM_HOTKEY = 0x0312
VK_F1 = 0x70
VK_BACK = 0x08
VK_TAB = 0x09
VK_RETURN = 0x0D
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_CAPITAL = 0x14
VK_ESCAPE = 0x1B
VK_SPACE = 0x20
VK_DELETE = 0x2E
VK_LWIN = 0x5B
VK_RWIN = 0x5C
MOD_NOREPEAT = 0x4000
PM_REMOVE = 1

# 使用正确的 ctypes 类型
from ctypes import wintypes
HMODULE = wintypes.HMODULE
DWORD = wintypes.DWORD
LONG = ctypes.c_long
WPARAM = wintypes.WPARAM
LPARAM = wintypes.LPARAM
HHOOK = ctypes.c_void_p
HRESULT = ctypes.HRESULT
LPCSTR = ctypes.c_char_p
HWND = wintypes.HWND
UINT = ctypes.c_uint

HOOKPROC = ctypes.WINFUNCTYPE(LONG, ctypes.c_int, WPARAM, LPARAM)

user32.SetWindowsHookExA.argtypes = [ctypes.c_int, HOOKPROC, HMODULE, DWORD]
user32.SetWindowsHookExA.restype = HHOOK

user32.CallNextHookEx.argtypes = [HHOOK, ctypes.c_int, WPARAM, LPARAM]
user32.CallNextHookEx.restype = LONG

user32.UnhookWindowsHookEx.argtypes = [HHOOK]
user32.UnhookWindowsHookEx.restype = ctypes.c_bool

user32.GetMessageA.argtypes = [ctypes.POINTER(wintypes.MSG), HWND, UINT, UINT]
user32.GetMessageA.restype = ctypes.c_int

user32.DispatchMessageA.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.DispatchMessageA.restype = LONG

user32.PostQuitMessage.argtypes = [ctypes.c_int]
user32.PostQuitMessage.restype = None

user32.PostThreadMessageA.argtypes = [DWORD, UINT, WPARAM, LPARAM]
user32.PostThreadMessageA.restype = ctypes.c_bool

user32.RegisterHotKey.argtypes = [HWND, ctypes.c_int, UINT, UINT]
user32.RegisterHotKey.restype = ctypes.c_int

user32.UnregisterHotKey.argtypes = [HWND, ctypes.c_int]
user32.UnregisterHotKey.restype = ctypes.c_int

user32.PeekMessageA.argtypes = [ctypes.POINTER(wintypes.MSG), HWND, UINT, UINT, UINT]
user32.PeekMessageA.restype = ctypes.c_int

user32.GetKeyState.argtypes = [ctypes.c_int]
user32.GetKeyState.restype = ctypes.c_short

kernel32.GetCurrentThreadId.argtypes = []
kernel32.GetCurrentThreadId.restype = DWORD

kernel32.GetModuleHandleA.argtypes = [LPCSTR]
kernel32.GetModuleHandleA.restype = HMODULE

# 特殊键名映射
SPECIAL_KEYS = {
    VK_BACK: '退格',
    VK_TAB: 'Tab',
    VK_RETURN: '回车',
    VK_SHIFT: 'Shift',
    VK_CONTROL: 'Ctrl',
    VK_MENU: 'Alt',
    VK_CAPITAL: 'CapsLock',
    VK_ESCAPE: 'Esc',
    VK_SPACE: '空格',
    VK_DELETE: 'Delete',
    VK_LWIN: '左Win',
    VK_RWIN: '右Win',
}

# 排除的按键（功能键等系统键）
EXCLUDED_KEYS = set(range(0x70, 0x88))  # F1-F24


class RecorderThread(QThread):
    """记录器线程 - 同时记录鼠标和键盘"""
    record_signal = Signal(dict)
    stop_signal = Signal()
    
    HOTKEY_ID = 1
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = False
        self.mouse_hook = None
        self.keyboard_hook = None
        self.mouse_callback = None
        self.keyboard_callback = None
        self.last_time = 0
        self.thread_id = None
        self.pressed_keys = set()
        
    def run(self):
        """线程主循环"""
        self.running = True
        self.thread_id = kernel32.GetCurrentThreadId()
        self.last_time = time.time()
        
        try:
            self.mouse_callback = HOOKPROC(self.mouse_hook_proc)
            self.mouse_hook = user32.SetWindowsHookExA(
                WH_MOUSE_LL,
                self.mouse_callback,
                kernel32.GetModuleHandleA(None),
                0
            )
            
            self.keyboard_callback = HOOKPROC(self.keyboard_hook_proc)
            self.keyboard_hook = user32.SetWindowsHookExA(
                WH_KEYBOARD_LL,
                self.keyboard_callback,
                kernel32.GetModuleHandleA(None),
                0
            )
            
            if not self.mouse_hook:
                self.record_signal.emit({'type': 'error', 'message': '设置鼠标钩子失败'})
                return
            
            if not self.keyboard_hook:
                self.record_signal.emit({'type': 'error', 'message': '设置键盘钩子失败'})
                return
                
            self.record_signal.emit({'type': 'status', 'message': '钩子已启动'})
            
            user32.RegisterHotKey(None, self.HOTKEY_ID, MOD_NOREPEAT, VK_F1)
            
            msg = wintypes.MSG()
            while self.running:
                if user32.GetMessageA(ctypes.byref(msg), None, 0, 0) > 0:
                    if msg.message == WM_HOTKEY and msg.wParam == self.HOTKEY_ID:
                        self.stop_signal.emit()
                    else:
                        user32.DispatchMessageA(ctypes.byref(msg))
                    
        except Exception as e:
            self.record_signal.emit({'type': 'error', 'message': str(e)})
        finally:
            user32.UnregisterHotKey(None, self.HOTKEY_ID)
            if self.mouse_hook:
                user32.UnhookWindowsHookEx(self.mouse_hook)
                self.mouse_hook = None
            if self.keyboard_hook:
                user32.UnhookWindowsHookEx(self.keyboard_hook)
                self.keyboard_hook = None
            self.record_signal.emit({'type': 'status', 'message': '钩子已停止'})
    
    def stop(self):
        """停止记录"""
        self.running = False
        if self.thread_id is not None:
            user32.PostThreadMessageA(self.thread_id, WM_QUIT, 0, 0)
        
    def mouse_hook_proc(self, nCode, wParam, lParam):
        """鼠标钩子回调函数"""
        if nCode >= 0 and self.running:
            current_time = time.time()
            interval = current_time - self.last_time
            self.last_time = current_time
            
            x, y = pyautogui.position()
            
            action_type = ''
            if wParam == WM_LBUTTONDOWN:
                action_type = '左键单击'
            elif wParam == WM_RBUTTONDOWN:
                action_type = '右键单击'
            elif wParam == WM_MBUTTONDOWN:
                action_type = '中键单击'
            else:
                return user32.CallNextHookEx(self.mouse_hook, nCode, wParam, lParam)
            
            if action_type:
                record = {
                    'type': 'mouse_action',
                    'x': x,
                    'y': y,
                    'action': action_type,
                    'interval': round(interval * 1000)
                }
                self.record_signal.emit(record)
        
        return user32.CallNextHookEx(self.mouse_hook, nCode, wParam, lParam)
    
    def keyboard_hook_proc(self, nCode, wParam, lParam):
        """键盘钩子回调函数"""
        if nCode >= 0 and self.running:
            if wParam == WM_KEYDOWN or wParam == WM_SYSKEYDOWN:
                vk_code = wParam
                
                if vk_code in EXCLUDED_KEYS:
                    return user32.CallNextHookEx(self.keyboard_hook, nCode, wParam, lParam)
                
                if vk_code in self.pressed_keys:
                    return user32.CallNextHookEx(self.keyboard_hook, nCode, wParam, lParam)
                self.pressed_keys.add(vk_code)
                
                current_time = time.time()
                interval = current_time - self.last_time
                self.last_time = current_time
                
                key_name = self.get_key_name(vk_code)
                
                record = {
                    'type': 'keyboard_action',
                    'key': key_name,
                    'vk_code': vk_code,
                    'interval': round(interval * 1000)
                }
                self.record_signal.emit(record)
            elif wParam == WM_KEYUP or wParam == WM_SYSKEYUP:
                vk_code = wParam
                self.pressed_keys.discard(vk_code)
        
        return user32.CallNextHookEx(self.keyboard_hook, nCode, wParam, lParam)
    
    def get_key_name(self, vk_code):
        """获取按键名称"""
        if vk_code in SPECIAL_KEYS:
            return SPECIAL_KEYS[vk_code]
        
        if 0x30 <= vk_code <= 0x39:
            return str(vk_code - 0x30)
        
        if 0x41 <= vk_code <= 0x5A:
            is_shift = user32.GetKeyState(VK_SHIFT) < 0
            is_caps = user32.GetKeyState(VK_CAPITAL) & 1
            char = chr(vk_code)
            if is_shift != is_caps:
                return char.upper()
            return char.lower()
        
        if 0x60 <= vk_code <= 0x69:
            return 'Num' + str(vk_code - 0x60)
        
        if 0x6A <= vk_code <= 0x6F:
            numpad_symbols = {0x6A: '*', 0x6B: '+', 0x6C: 'Num-', 0x6D: '-', 0x6E: '.', 0x6F: '/'}
            return numpad_symbols.get(vk_code, f'VK_{vk_code}')
        
        return f'VK_{vk_code}'


class InspectorWindow(QWidget):
    """控件检测器窗口"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("控件检测器")
        self.resize(600, 500)
        self.setWindowFlags(Qt.WindowStaysOnTopHint)
        
        self.recorded_actions = []
        self.recording = False
        self.playback_thread = None
        
        layout = QVBoxLayout()
        
        toolbar = QHBoxLayout()
        
        self.start_record_btn = QPushButton("▶️ 开始记录")
        self.start_record_btn.clicked.connect(self.start_recording)
        toolbar.addWidget(self.start_record_btn)
        
        self.stop_record_btn = QPushButton("⏹️ 停止记录(F1)")
        self.stop_record_btn.clicked.connect(self.stop_recording)
        self.stop_record_btn.setEnabled(False)
        toolbar.addWidget(self.stop_record_btn)
        
        self.play_btn = QPushButton("🔄 循环播放")
        self.play_btn.clicked.connect(self.start_playback)
        self.play_btn.setEnabled(False)
        toolbar.addWidget(self.play_btn)
        
        self.stop_play_btn = QPushButton("⏹️ 停止播放(F1)")
        self.stop_play_btn.clicked.connect(self.stop_playback)
        self.stop_play_btn.setEnabled(False)
        toolbar.addWidget(self.stop_play_btn)
        
        self.clear_btn = QPushButton("🗑️ 清空记录")
        self.clear_btn.clicked.connect(self.clear_records)
        toolbar.addWidget(self.clear_btn)
        
        self.save_btn = QPushButton("💾 保存")
        self.save_btn.clicked.connect(self.save_actions)
        self.save_btn.setEnabled(False)
        toolbar.addWidget(self.save_btn)
        
        toolbar.addStretch()
        layout.addLayout(toolbar)
        
        self.steps_list = QListWidget()
        self.steps_list.itemChanged.connect(self.on_step_edited)
        layout.addWidget(self.steps_list)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        layout.addWidget(self.log_text)
        
        self.setLayout(layout)
        
        self.recorder = RecorderThread()
        self.recorder.record_signal.connect(self.handle_record)
        self.recorder.stop_signal.connect(self.stop_recording)
        
    def add_log(self, message):
        """添加日志"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.log_text.setTextCursor(cursor)
    
    def start_recording(self):
        """开始记录"""
        self.recorded_actions = []
        self.steps_list.clear()
        self.recording = True
        
        self.start_record_btn.setEnabled(False)
        self.stop_record_btn.setEnabled(True)
        self.play_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        
        self.add_log("开始记录鼠标和键盘操作...")
        self.add_log("按 F1 停止记录")
        
        self.recorder.start()
        self.showMinimized()
    
    def stop_recording(self):
        """停止记录"""
        self.recording = False
        
        if self.recorder.isRunning():
            self.recorder.stop()
            if not self.recorder.wait(3000):
                self.recorder.terminate()
                self.recorder.wait()
        
        self.start_record_btn.setEnabled(True)
        self.stop_record_btn.setEnabled(False)
        self.play_btn.setEnabled(len(self.recorded_actions) > 0)
        self.save_btn.setEnabled(len(self.recorded_actions) > 0)
        
        self.add_log(f"停止记录，共记录 {len(self.recorded_actions)} 个操作")
        
        self.showNormal()
        self.raise_()
    
    def clear_records(self):
        """清空记录"""
        self.recorded_actions = []
        self.steps_list.clear()
        self.play_btn.setEnabled(False)
        self.stop_play_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        self.add_log("已清空所有记录")
    
    def save_actions(self):
        """保存记录的动作到文件"""
        import json
        from datetime import datetime
        
        if not self.recorded_actions:
            QMessageBox.warning(self, "警告", "没有记录的操作可以保存")
            return
        
        default_name = datetime.now().strftime("control_actions_%Y%m%d_%H%M%S.json")
        path, _ = QFileDialog.getSaveFileName(
            self, "保存控件操作", default_name, "JSON文件 (*.json)"
        )
        if not path:
            return
        
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self.recorded_actions, f, ensure_ascii=False, indent=2)
            self.add_log(f"已保存 {len(self.recorded_actions)} 个操作到: {path}")
            QMessageBox.information(self, "保存成功", f"已保存 {len(self.recorded_actions)} 个操作到:\n{path}")
        except Exception as e:
            self.add_log(f"保存失败: {str(e)}")
            QMessageBox.critical(self, "保存失败", f"保存失败:\n{str(e)}")
    
    def handle_record(self, record):
        """处理记录信号"""
        timestamp = time.strftime("%H:%M:%S")
        
        if record['type'] == 'mouse_action':
            x = record['x']
            y = record['y']
            action = record['action']
            interval = record['interval']
            
            self.recorded_actions.append({
                'type': 'mouse',
                'x': x,
                'y': y,
                'action': action,
                'interval': interval,
                'timestamp': timestamp
            })
            
            step_text = f"{len(self.recorded_actions)}. [{timestamp}] [{interval}ms] 🖱️ {action} ({x}, {y})"
            item = QListWidgetItem(step_text)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            self.steps_list.addItem(item)
            self.add_log(f"记录鼠标: {action} ({x}, {y})")
            
        elif record['type'] == 'keyboard_action':
            key = record['key']
            interval = record['interval']
            
            self.recorded_actions.append({
                'type': 'keyboard',
                'key': key,
                'interval': interval,
                'timestamp': timestamp
            })
            
            step_text = f"{len(self.recorded_actions)}. [{timestamp}] [{interval}ms] ⌨️ 按键: {key}"
            item = QListWidgetItem(step_text)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            self.steps_list.addItem(item)
            self.add_log(f"记录键盘: {key}")
            
        elif record['type'] == 'status':
            self.add_log(record['message'])
            
        elif record['type'] == 'error':
            self.add_log(f"错误: {record['message']}")
    
    def on_step_edited(self, item):
        """步骤编辑后同步到 recorded_actions"""
        row = self.steps_list.row(item)
        if row < 0 or row >= len(self.recorded_actions):
            return
        text = item.text()
        
        if '🖱️' in text:
            m = re.match(r'\d+\. \[(\d{2}:\d{2}:\d{2})\] \[(\d+)ms\] 🖱️ (.+) \((\d+), (\d+)\)', text)
            if m:
                self.recorded_actions[row] = {
                    'type': 'mouse',
                    'x': int(m.group(4)),
                    'y': int(m.group(5)),
                    'action': m.group(3),
                    'interval': int(m.group(2)),
                    'timestamp': m.group(1)
                }
                self.add_log(f"步骤 {row+1} 已更新: {m.group(3)} ({m.group(4)}, {m.group(5)})")
        
        elif '⌨️' in text:
            m = re.match(r'\d+\. \[(\d{2}:\d{2}:\d{2})\] \[(\d+)ms\] ⌨️ 按键: (.+)', text)
            if m:
                self.recorded_actions[row] = {
                    'type': 'keyboard',
                    'key': m.group(3),
                    'interval': int(m.group(2)),
                    'timestamp': m.group(1)
                }
                self.add_log(f"步骤 {row+1} 已更新: 按键 {m.group(3)}")
    
    def start_playback(self):
        """开始循环播放"""
        if not self.recorded_actions:
            QMessageBox.warning(self, "警告", "没有记录的操作可以播放")
            return
        
        self.play_btn.setEnabled(False)
        self.stop_play_btn.setEnabled(True)
        self.start_record_btn.setEnabled(False)
        
        self.add_log("开始循环播放...")
        
        self.playback_thread = PlaybackThread(self.recorded_actions)
        self.playback_thread.finished.connect(self.on_playback_finished)
        self.playback_thread.start()
    
    def stop_playback(self):
        """停止播放"""
        if self.playback_thread and self.playback_thread.isRunning():
            self.playback_thread.stop()
            self.playback_thread.wait(2000)
            self.on_playback_finished()
            self.add_log("已停止播放")
    
    def on_playback_finished(self):
        """播放完成"""
        self.play_btn.setEnabled(True)
        self.stop_play_btn.setEnabled(False)
        self.start_record_btn.setEnabled(True)
    
    def keyPressEvent(self, event):
        """键盘事件处理"""
        if event.key() == Qt.Key_F1:
            if self.recording:
                self.stop_recording()
            elif self.playback_thread and self.playback_thread.isRunning():
                self.stop_playback()
            return
        super().keyPressEvent(event)


class PlaybackThread(QThread):
    """播放线程"""
    finished = Signal()
    
    HOTKEY_ID = 2
    
    def __init__(self, actions):
        super().__init__()
        self.actions = actions
        self.running = False
        self.thread_id = None
    
    def stop(self):
        """停止播放"""
        self.running = False
        if self.thread_id is not None:
            user32.PostThreadMessageA(self.thread_id, WM_QUIT, 0, 0)
    
    def run(self):
        """执行播放"""
        self.running = True
        self.thread_id = kernel32.GetCurrentThreadId()
        user32.RegisterHotKey(None, self.HOTKEY_ID, MOD_NOREPEAT, VK_F1)
        
        msg = wintypes.MSG()
        try:
            while self.running:
                for action in self.actions:
                    if not self.running:
                        break
                    
                    remaining = action['interval'] / 1000.0 if action['interval'] > 0 else 0
                    while remaining > 0 and self.running:
                        time.sleep(min(0.05, remaining))
                        remaining -= 0.05
                        while user32.PeekMessageA(ctypes.byref(msg), None, WM_HOTKEY, WM_HOTKEY, PM_REMOVE):
                            if msg.wParam == self.HOTKEY_ID:
                                self.running = False
                    
                    if not self.running:
                        break
                    
                    if action['type'] == 'mouse':
                        x, y = action['x'], action['y']
                        action_type = action['action']
                        
                        if action_type == '左键单击':
                            pyautogui.click(x, y)
                        elif action_type == '右键单击':
                            pyautogui.rightClick(x, y)
                        elif action_type == '中键单击':
                            pyautogui.middleClick(x, y)
                        
                    elif action['type'] == 'keyboard':
                        key = action['key']
                        pyautogui.press(key)
                
                if self.running:
                    for _ in range(20):
                        if not self.running:
                            break
                        time.sleep(0.05)
                        while user32.PeekMessageA(ctypes.byref(msg), None, WM_HOTKEY, WM_HOTKEY, PM_REMOVE):
                            if msg.wParam == self.HOTKEY_ID:
                                self.running = False
        finally:
            user32.UnregisterHotKey(None, self.HOTKEY_ID)


def create_inspector_window():
    """创建控件检测窗口"""
    return InspectorWindow()