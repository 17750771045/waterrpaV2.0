import sys
import os
import time
import json
import traceback
import ctypes
import threading
import win32gui
import win32con
import win32process
import win32api
import winreg

# 导入超时配置模块
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from timeout import TimeoutManager, create_timeout_page, handle_timeout_retry
from inspector import InspectorWindow, create_inspector_window
from autostart import AutoStartWindow, check_auto_start
from template_manager import TemplateManagerWindow

# ---------------------------------------------------------
# 核心库导入和DPI设置
# ---------------------------------------------------------
try:
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    ctypes.windll.shcore.SetProcessDpiAwareness(1) 
except:
    try: ctypes.windll.user32.SetProcessDPIAware()
    except: pass

from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                               QPushButton, QLabel, QComboBox, QLineEdit, QScrollArea, 
                               QFileDialog, QTextEdit, QMessageBox, QFrame, QCheckBox, QGroupBox, QToolTip,
                               QListWidget, QListWidgetItem, QAbstractItemView, QRubberBand, QInputDialog,
                               QStackedWidget, QDialog)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QSize, QRect, QSettings, QPoint
from PySide6.QtGui import QCursor, QFont, QColor, QPalette, QBrush, QPen, QPainter, QRegion
import pyperclip
from PIL import Image
import pyautogui

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

GetAsyncKeyState = ctypes.windll.user32.GetAsyncKeyState
try:
    GetCurrentProcessorNumber = ctypes.windll.kernel32.GetCurrentProcessorNumber
    GetCurrentProcessorNumber.restype = ctypes.c_ulong
    HAS_KERNEL_CPU = True
except:
    HAS_KERNEL_CPU = False

pyautogui.FAILSAFE = False 
pyautogui.PAUSE = 0

# ---------------------------------------------------------
# 全局配置
# ---------------------------------------------------------
GLOBAL_CONFIG = {
    "log_to_file": False,
    "log_to_ui": True
}

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

def get_log_path():
    return os.path.join(get_base_dir(), "rpa_debug_log.txt")

def write_log(msg):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    formatted_msg = f"[{timestamp}] {msg}"
    if GLOBAL_CONFIG["log_to_file"]:
        try:
            with open(get_log_path(), "a", encoding="utf-8") as f:
                f.write(formatted_msg + "\n")
        except: pass

def global_exception_handler(exctype, value, tb):
    err_msg = "".join(traceback.format_exception(exctype, value, tb))
    write_log(f"!!! 严重崩溃 !!! {value}\n{err_msg}")
    sys.__excepthook__(exctype, value, tb)

sys.excepthook = global_exception_handler

# --------------------------
# 区域选择窗口
# --------------------------
class RegionWindow(QWidget):
    region_selected = Signal(tuple) # x, y, w, h

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)
        
        self.setCursor(Qt.CrossCursor)
        self.setMouseTracking(True)
        
        virtual_rect = QApplication.primaryScreen().virtualGeometry()
        self.setGeometry(virtual_rect)
        
        phys_w, phys_h = pyautogui.size()
        log_w = virtual_rect.width()
        log_h = virtual_rect.height()
        self.scale_x = phys_w / log_w
        self.scale_y = phys_h / log_h
        
        self.start_point = None
        self.end_point = None
        self.current_pos = QPoint(0, 0)
        self.selection_rect = QRect()
        
        self.show()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        bg_color = QColor(0, 0, 0, 100) 
        
        if self.selection_rect.isValid():
            mask_region = QRegion(self.rect())
            selection_region = QRegion(self.selection_rect)
            overlay_region = mask_region.subtracted(selection_region)
            
            painter.setClipRegion(overlay_region)
            painter.fillRect(self.rect(), bg_color)
            
            painter.setClipping(False)
            pen = QPen(QColor(0, 255, 0), 2)
            pen.setStyle(Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(self.selection_rect)
            
            real_w = int(self.selection_rect.width() * self.scale_x)
            real_h = int(self.selection_rect.height() * self.scale_y)
            info_text = f"选区:{self.selection_rect.width()}x{self.selection_rect.height()} (实际: {real_w}x{real_h})"
            
            painter.setPen(QColor(255, 255, 255))
            painter.setFont(QFont("Arial", 12, QFont.Bold)) 
            text_y = self.selection_rect.y() - 10
            if text_y < 30: text_y = self.selection_rect.y() + 30
            painter.drawText(self.selection_rect.x(), text_y, info_text)
            
        else:
            painter.fillRect(self.rect(), bg_color)
            painter.setPen(QColor(255, 255, 255))
            painter.setFont(QFont("Arial", 16, QFont.Bold))
            hint = f"请框选区域 | 右键取消 | 缩放比: {self.scale_x:.2f}"
            fm = painter.fontMetrics()
            tw = fm.horizontalAdvance(hint)
            painter.drawText((self.width() - tw)//2, 100, hint)

        painter.setClipping(False)
        coord_text = f"Pos: {self.current_pos.x()},{self.current_pos.y()}"
        painter.setPen(QColor(255, 255, 0))
        painter.setFont(QFont("Arial", 10))
        painter.drawText(self.current_pos.x() + 20, self.current_pos.y() + 30, coord_text)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.start_point = event.pos()
            self.selection_rect = QRect()
            self.update()
        elif event.button() == Qt.RightButton:
            self.close()

    def mouseMoveEvent(self, event):
        self.current_pos = event.pos()
        if self.start_point:
            self.end_point = event.pos()
            self.selection_rect = QRect(self.start_point, self.end_point).normalized()
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.start_point:
            rect = self.selection_rect
            self.close() 
            if rect.width() > 10 and rect.height() > 10:
                real_x = int(rect.x() * self.scale_x)
                real_y = int(rect.y() * self.scale_y)
                real_w = int(rect.width() * self.scale_x)
                real_h = int(rect.height() * self.scale_y)
                self.region_selected.emit((real_x, real_y, real_w, real_h))

# --------------------------
# 自定义帮助按钮
# --------------------------
class HelpBtn(QPushButton):
    def __init__(self, tip_text):
        super().__init__("?")
        self.setFixedSize(20, 20)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("""
            QPushButton {
                background-color: #2196F3; color: white; 
                border-radius: 10px; font-weight: bold; border: none;
            }
            QPushButton:hover { background-color: #1976D2; }
        """)
        self.tip_text = tip_text
        self.clicked.connect(self.show_tip)

    def show_tip(self):
        QToolTip.showText(QCursor.pos(), self.tip_text, self, QRect(), 5000)

# --------------------------
# 独立看门狗线程
# --------------------------
class FailsafeWatchdog(threading.Thread):
    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self.daemon = True 
        self.running = True

    def run(self):
        write_log(">>> 看门狗线程启动")
        while self.running:
            try:
                if self.engine.enable_key_stop:
                    if GetAsyncKeyState(0x1B) & 0x8000: 
                        self.trigger_stop("用户按下了【ESC键】")
                        return
                    if GetAsyncKeyState(0x04) & 0x8000: 
                        self.trigger_stop("用户按下了【鼠标中键】")
                        return

                if self.engine.enable_tr_stop:
                    x, y = pyautogui.position()
                    w, h = pyautogui.size()
                    if x > (w - 10) and y < 10:
                        self.trigger_stop("检测到鼠标【右上角急停】")
                        return

                if self.engine.enable_tm_stop:
                    if int(time.time() * 100) % 10 == 0: 
                        hwnd = ctypes.windll.user32.GetForegroundWindow()
                        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                        if length > 0:
                            buff = ctypes.create_unicode_buffer(length + 1)
                            ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
                            if "任务管理器" in buff.value or "Task Manager" in buff.value:
                                self.trigger_stop("检测到【任务管理器】前台")
                                return
                time.sleep(0.02)
            except Exception as e:
                time.sleep(1)

    def trigger_stop(self, reason):
        if not self.engine.stop_requested:
            write_log(f">>> 看门狗触发: {reason}")
            self.engine.log(f"!!! {reason} -> 停止 !!!")
            
            # 发送详细停止信息到UI日志
            if hasattr(self.engine, 'callback_msg') and self.engine.callback_msg:
                self.engine.callback_msg(f">>> 安全检测触发停止")
                self.engine.callback_msg(f"   原因: {reason}")
                self.engine.callback_msg(f"   时间: {time.strftime('%H:%M:%S')}")
                self.engine.callback_msg("!!! 任务已安全停止 !!!")
            
            self.engine.stop() 
            try: ctypes.windll.user32.MessageBeep(0xFFFFFFFF)
            except: pass

    def kill(self):
        self.running = False

# --------------------------
# 核心引擎 (V45+ 内核)
# --------------------------

class RPAEngine:
    def __init__(self):
        self.is_running = False
        self.stop_requested = False
        
        self.min_scale = 1.0
        self.max_scale = 1.0
        self.confidence = 0.8
        self.scan_region = None 
        
        self.dodge_x1 = 100
        self.dodge_y1 = 100
        self.dodge_x2 = 200
        self.dodge_y2 = 100
        self.enable_dodge = False
        self.enable_double_dodge = False
        self.double_dodge_wait = 0.015
        
        self.move_duration = 0.0
        self.click_hold = 0.04
        self.settlement_wait = 0.0
        self.timeout_val = 0.0
        self.step_start_time = 0.0  # 步骤级别的开始时间
        
        self.enable_tm_stop = True 
        self.enable_tr_stop = True 
        self.enable_key_stop = True
        
        self.callback_msg = None
        self.opencv_available = False 
        self.img_cache = {} 
        self.scaled_templates_cache = {}

        self.check_engine_status()
        self.dx_camera = None
        self.dxcam_available = False
        try:
            import dxcam
            self.dx_camera = dxcam.create()
            self.dxcam_available = True
        except Exception as e:
            self.dxcam_available = False
            print(f"[RPAEngine] dxcam 初始化失败，将使用 pyautogui 截图回退: {e}")
            write_log(f"dxcam 初始化失败: {e}")
        self.set_high_priority()

    def set_high_priority(self):
        try:
            pid = os.getpid()
            handle = ctypes.windll.kernel32.OpenProcess(0x0100, True, pid)
            ctypes.windll.kernel32.SetPriorityClass(handle, 0x00000080)
        except: pass

    def check_engine_status(self):
        try:
            import cv2
            import numpy
            img = numpy.zeros((10, 10, 3), dtype=numpy.uint8)
            cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            self.opencv_available = True
            write_log("OpenCV/NumPy 引擎就绪。")
        except:
            self.opencv_available = False
            write_log("OpenCV 引擎不可用。")

    def stop(self):
        self.stop_requested = True
        self.is_running = False

    def log(self, msg):
        write_log(msg)
        if self.callback_msg: self.callback_msg(msg)

    def check_stop_flag(self):
        return self.stop_requested

    def load_and_precompute(self, tasks):
        if not self.opencv_available: return
        try:
            import cv2
            import numpy as np
            
            write_log("正在预加载资源...")
            for task in tasks:
                path = str(task.get("value", ""))
                if not path or not os.path.exists(path): continue
                if task.get("type") not in [1.0, 2.0, 3.0, 8.0]: continue
                
                img = Image.open(path)
                img.load()
                self.img_cache[path] = img
                
                if self.min_scale != 1.0 or self.max_scale != 1.0:
                    if img.mode != 'L': img = img.convert('L')
                    template = np.array(img)
                    
                    templates_list = []
                    steps = int((self.max_scale - self.min_scale) / 0.05) + 1
                    for scale in np.linspace(self.min_scale, self.max_scale, steps):
                        if 0.99 < scale < 1.01: continue
                        rw = int(template.shape[1] * scale)
                        rh = int(template.shape[0] * scale)
                        if rw < 1 or rh < 1: continue
                        resized_tpl = cv2.resize(template, (rw, rh))
                        templates_list.append(resized_tpl)
                    
                    self.scaled_templates_cache[path] = templates_list
            write_log("资源预加载完成。")
        except Exception as e:
            write_log(f"预计算失败: {e}")

    def parse_coordinate(self, value):
        """解析坐标输入，返回 (x, y) 或 None
        支持格式: "100,200" 或 "100，200" 或 "(100,200)" 或 "100x200"
        兼容中英文标点符号
        """
        if not value:
            return None
        
        value = str(value).strip()
        if not value:
            return None
        
        # 检查是否是文件路径
        if os.path.exists(value):
            return None
        
        # 检查是否是坐标格式
        import re
        
        # 先标准化：将中文标点替换为英文
        # 中文逗号 (，) -> 英文逗号 (,)
        # 中文乘号 (×) -> 字母 x
        # 全角逗号 (，) -> 英文逗号 (,)
        normalized = value.replace('，', ',').replace('×', 'x').replace('✕', 'x').replace('X', 'x')
        
        # 匹配 X,Y 或 (X,Y) 格式（英文/中文逗号）
        patterns = [
            r'^\s*\(?\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)?\s*$',  # (100, 200) 或 100, 200
            r'^\s*(-?\d+(?:\.\d+)?)\s*x\s*(-?\d+(?:\.\d+)?)\s*$',  # 100x200 或 100 x 200
        ]
        
        for pattern in patterns:
            match = re.match(pattern, normalized)
            if match:
                try:
                    x = float(match.group(1))
                    y = float(match.group(2))
                    # 确保坐标是正数（屏幕坐标）
                    if x >= 0 and y >= 0:
                        return (int(x), int(y))
                    # 负数坐标也允许（相对坐标）
                    return (int(x), int(y))
                except ValueError:
                    continue
        
        return None

    def parse_region(self, value):
        """解析区域输入，返回 (region, path) 元组，region为(x, y, width, height)或None
        支持格式: 
        - "(100,200,300,400),保存路径/文件名"
        - "(100,200,300,400)"
        - "100,200,300,400,保存路径/文件名"
        """
        if not value:
            return (None, None)
        
        value = str(value).strip()
        if not value:
            return (None, None)
        
        import re
        
        # 先标准化标点符号（中文逗号转英文逗号）
        normalized = value.replace('，', ',')
        
        # 匹配格式：(x,y,width,height),保存路径
        # 括号内是区域坐标，逗号后面是保存路径
        pattern = r'^\s*\(\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)\s*,\s*(.+?)\s*$'
        match = re.match(pattern, normalized)
        if match:
            try:
                x = float(match.group(1))
                y = float(match.group(2))
                w = float(match.group(3))
                h = float(match.group(4))
                save_path = match.group(5).strip()
                # 确保都是正数（屏幕区域）
                if x >= 0 and y >= 0 and w >= 0 and h >= 0:
                    return ((int(x), int(y), int(w), int(h)), save_path)
            except ValueError:
                pass
        
        # 匹配格式：(x,y,width,height) 只有区域，没有路径
        pattern = r'^\s*\(\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)\s*$'
        match = re.match(pattern, normalized)
        if match:
            try:
                x = float(match.group(1))
                y = float(match.group(2))
                w = float(match.group(3))
                h = float(match.group(4))
                if x >= 0 and y >= 0 and w >= 0 and h >= 0:
                    return ((int(x), int(y), int(w), int(h)), None)
            except ValueError:
                pass
        
        # 匹配格式：x,y,width,height,保存路径（无括号）
        pattern = r'^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*(.+?)\s*$'
        match = re.match(pattern, normalized)
        if match:
            try:
                x = float(match.group(1))
                y = float(match.group(2))
                w = float(match.group(3))
                h = float(match.group(4))
                save_path = match.group(5).strip()
                if x >= 0 and y >= 0 and w >= 0 and h >= 0:
                    return ((int(x), int(y), int(w), int(h)), save_path)
            except ValueError:
                pass
        
        return (None, None)

    def find_target_optimized(self, img_path):
        offset_x = self.scan_region[0] if self.scan_region else 0
        offset_y = self.scan_region[1] if self.scan_region else 0

        if not self.opencv_available:
            try:
                screenshot_pil = pyautogui.screenshot(region=self.scan_region)
            except: return None
            if img_path in self.img_cache:
                try: 
                    res = pyautogui.locate(self.img_cache[img_path], screenshot_pil, confidence=self.confidence)
                    if res:
                        cx = res.left + (res.width / 2) + offset_x
                        cy = res.top + (res.height / 2) + offset_y
                        return (cx, cy)
                except: pass
            elif os.path.exists(img_path):
                 try:
                    res = pyautogui.locate(img_path, screenshot_pil, confidence=self.confidence)
                    if res:
                        cx = res.left + (res.width / 2) + offset_x
                        cy = res.top + (res.height / 2) + offset_y
                        return (cx, cy)
                 except: pass
            return None

        import cv2
        import numpy as np
        
        # 使用 dxcam 截图（直接返回 numpy 数组，跳过 PIL 转换，速度更快）
        if self.dxcam_available and self.dx_camera:
            try:
                if self.scan_region:
                    x, y, w, h = self.scan_region
                    frame = self.dx_camera.grab(region=(x, y, x + w, y + h))
                else:
                    frame = self.dx_camera.grab()
                if frame is None:
                    return None
                screen_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            except:
                # dxcam 失败时回退到 pyautogui
                try:
                    screenshot_pil = pyautogui.screenshot(region=self.scan_region)
                    screen_np = np.array(screenshot_pil)
                    screen_gray = cv2.cvtColor(screen_np, cv2.COLOR_RGB2GRAY)
                except:
                    return None
        else:
            try:
                screenshot_pil = pyautogui.screenshot(region=self.scan_region)
            except:
                return None
            screen_np = np.array(screenshot_pil)
            screen_gray = cv2.cvtColor(screen_np, cv2.COLOR_RGB2GRAY)
        
        if img_path not in self.img_cache:
            if os.path.exists(img_path):
                try:
                    img = Image.open(img_path)
                    img.load()
                    self.img_cache[img_path] = img
                except: return None
            else:
                return None
        
        pil_template = self.img_cache[img_path]
        
        try:
            if pil_template.mode != 'L': pil_template = pil_template.convert('L')
            tpl_gray = np.array(pil_template)
            
            if tpl_gray.shape[0] > screen_gray.shape[0] or tpl_gray.shape[1] > screen_gray.shape[1]:
                pass 
            else:
                res = cv2.matchTemplate(screen_gray, tpl_gray, cv2.TM_CCOEFF_NORMED)
                min_v, max_v, min_l, max_l = cv2.minMaxLoc(res)
                if max_v >= self.confidence:
                    h, w = tpl_gray.shape[:2]
                    final_x = max_l[0] + w//2 + offset_x
                    final_y = max_l[1] + h//2 + offset_y
                    return (final_x, final_y)
        except: pass
        
        if img_path in self.scaled_templates_cache:
            for resized_tpl in self.scaled_templates_cache[img_path]:
                if self.check_stop_flag(): return None
                try:
                    if resized_tpl.shape[0] > screen_gray.shape[0] or resized_tpl.shape[1] > screen_gray.shape[1]:
                        continue
                    res = cv2.matchTemplate(screen_gray, resized_tpl, cv2.TM_CCOEFF_NORMED)
                    min_v, max_v, min_l, max_l = cv2.minMaxLoc(res)
                    if max_v >= self.confidence:
                        h, w = resized_tpl.shape[:2]
                        final_x = max_l[0] + w//2 + offset_x
                        final_y = max_l[1] + h//2 + offset_y
                        return (final_x, final_y)
                except: continue
        
        return None

    def _dx_save_screenshot(self, path, region):
        """使用 dxcam 保存截图，失败时回退到 pyautogui"""
        if self.dxcam_available and self.dx_camera:
            try:
                import cv2
                if region:
                    x, y, w, h = region
                    frame = self.dx_camera.grab(region=(x, y, x + w, y + h))
                else:
                    frame = self.dx_camera.grab()
                if frame is not None:
                    cv2.imwrite(path, cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                    return
            except:
                pass
        pyautogui.screenshot(path, region=region)

    def mouseClick(self, clickTimes, lOrR, img_path, reTry):
        start_time = time.time()
        
        _move = self.move_duration
        _hold = self.click_hold
        _dodge_en = self.enable_dodge
        _dx1, _dy1 = self.dodge_x1, self.dodge_y1
        _dx2, _dy2 = self.dodge_x2, self.dodge_y2
        _dbl_dodge = self.enable_double_dodge
        _dbl_wait = self.double_dodge_wait
        _timeout = self.timeout_val
        _settle = self.settlement_wait
        
        while True:
            if self.check_stop_flag(): return False
            if _timeout > 0.001 and (time.time() - start_time > _timeout): return True  # 返回True表示超时
            
            location_tuple = self.find_target_optimized(img_path)

            if location_tuple:
                try:
                    x, y = location_tuple
                    
                    pyautogui.moveTo(x, y, duration=_move)
                    for _ in range(clickTimes):
                        pyautogui.mouseDown(button=lOrR)
                        time.sleep(_hold)
                        pyautogui.mouseUp(button=lOrR)
                        if clickTimes > 1: time.sleep(0.02)
                    
                    if _settle > 0: time.sleep(_settle)
                    
                    if _dodge_en:
                        pyautogui.moveTo(_dx1, _dy1, duration=0)
                        if _dbl_dodge:
                            time.sleep(_dbl_wait) 
                            pyautogui.moveTo(_dx2, _dy2, duration=0)
                    
                except Exception as e: self.log(f"Err: {e}")
                
                if reTry != -1: return False
                else:
                    time.sleep(0.01)
                    continue
            
            if _timeout <= 0.001: return False 
            time.sleep(0.001) 

    def run_tasks(self, tasks, loop_forever=False, callback_msg=None, timeout_callback=None, enable_timeout=True):
        self.is_running = True
        self.stop_requested = False
        self.callback_msg = callback_msg
        
        self.img_cache = {}
        self.scaled_templates_cache = {}
        self.load_and_precompute(tasks)
        
        if self.scan_region:
            write_log(f"区域模式: {self.scan_region}")
        
        # 记录开始时间用于超时检查
        start_time = time.time()
        start_time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        write_log(f"任务开始时间: {start_time_str}")
        
        try:
            loop_count = 0
            while True:
                loop_count += 1
                if callback_msg: callback_msg(f"=== 开始第 {loop_count} 轮循环 ===")
                
                for idx, task in enumerate(tasks):
                    if self.check_stop_flag():
                        if callback_msg: callback_msg("任务由看门狗终止")
                        return True  # 返回True表示正常停止

                    # 记录步骤开始时间，用于超时检查和UI显示
                    self.step_start_time = time.time()

                    cmd = task.get("type")
                    val = task.get("value")
                    retry = task.get("retry", 1)
                    
                    # 详细的任务执行日志
                    task_types = {
                        1.0: "左键单击", 2.0: "左键双击", 3.0: "右键单击", 
                        4.0: "输入文本", 5.0: "等待", 6.0: "滚轮滑动", 
                        7.0: "系统按键", 8.0: "鼠标悬停", 9.0: "截图保存",
                        10.0: "比对", 11.0: "多条件检测", 12.0: "消失触发",
                        13.0: "控件调用", 14.0: "图片条件分支", 15.0: "鼠标拖动"
                    }
                    
                    if callback_msg: callback_msg(f"执行步骤 {idx+1}/{len(tasks)}: {task_types.get(cmd, '未知')} -> {val}")
                    
                    # 执行步骤，检测超时
                    step_timeout = False
                    step_success = False
                    
                    # 记录步骤开始时间，用于超时检查
                    self.step_start_time = time.time()
                    
                    while not step_success and not self.check_stop_flag():
                        if cmd == 1.0: 
                            # 支持坐标点击或图片识别点击
                            coord = self.parse_coordinate(val)
                            if coord:
                                x, y = coord
                                pyautogui.click(x, y, button='left')
                                step_success = True
                            else:
                                result = self.mouseClick(1, "left", val, retry)
                                if result:
                                    step_timeout = True
                                else:
                                    step_success = True
                        elif cmd == 2.0: 
                            coord = self.parse_coordinate(val)
                            if coord:
                                x, y = coord
                                pyautogui.doubleClick(x, y, button='left')
                                step_success = True
                            else:
                                result = self.mouseClick(2, "left", val, retry)
                                if result:
                                    step_timeout = True
                                else:
                                    step_success = True
                        elif cmd == 3.0: 
                            coord = self.parse_coordinate(val)
                            if coord:
                                x, y = coord
                                pyautogui.click(x, y, button='right')
                                step_success = True
                            else:
                                result = self.mouseClick(1, "right", val, retry)
                                if result:
                                    step_timeout = True
                                else:
                                    step_success = True
                        elif cmd == 8.0:
                            loc = self.find_target_optimized(val)
                            if loc: 
                                pyautogui.moveTo(loc[0], loc[1], duration=self.move_duration)
                            step_success = True
                        elif cmd == 4.0: 
                            pyperclip.copy(str(val)); pyautogui.hotkey('ctrl', 'v'); time.sleep(0.2)
                            step_success = True
                        elif cmd == 5.0: 
                            t_end = time.time() + float(val)
                            wait_timeout_occurred = False
                            while time.time() < t_end and not wait_timeout_occurred:
                                if self.check_stop_flag(): 
                                    return True
                                if enable_timeout and self.timeout_val > 0:
                                    elapsed_time = time.time() - self.step_start_time
                                    if elapsed_time > self.timeout_val:
                                        if callback_msg: callback_msg(f"⏰ 等待超时 ({elapsed_time:.1f}秒 > {self.timeout_val}秒)")
                                        wait_timeout_occurred = True
                                        step_timeout = True
                                time.sleep(0.05)
                            if not wait_timeout_occurred:
                                step_success = True
                        elif cmd == 6.0: 
                            pyautogui.scroll(int(val))
                            step_success = True
                        elif cmd == 7.0: 
                            pyautogui.hotkey(*[k.strip() for k in str(val).lower().split('+')])
                            step_success = True
                        elif cmd == 9.0:
                            # 截图保存功能：支持指定坐标区域
                            path = str(val)
                            
                            # 先尝试从输入中解析区域和路径
                            input_region, input_path = self.parse_region(val)
                            
                            # 确定保存路径优先级：输入路径 > 自动生成
                            if input_path:
                                path = input_path
                            elif input_region:
                                path = time.strftime("ss_%H%M%S.png")
                            elif os.path.isdir(path): 
                                path = os.path.join(path, time.strftime("ss_%H%M%S.png"))
                            
                            try:
                                step_region = task.get("screenshot_region", None)
                                if callback_msg: 
                                    if input_region:
                                        callback_msg(f"📷 截图保存：使用指定坐标区域 {input_region}")
                                    elif step_region:
                                        callback_msg(f"📷 截图保存：使用步骤区域 {step_region}")
                                    elif self.scan_region:
                                        callback_msg(f"📷 截图保存：使用全局区域 {self.scan_region}")
                                    else:
                                        callback_msg(f"📷 截图保存：全屏截图")
                                
                                if input_region:
                                    self._dx_save_screenshot(path, input_region)
                                elif step_region:
                                    self._dx_save_screenshot(path, step_region)
                                elif self.scan_region:
                                    self._dx_save_screenshot(path, self.scan_region)
                                else:
                                    self._dx_save_screenshot(path, None)
                                
                                if callback_msg: 
                                    callback_msg(f"✅ 截图保存成功：{path}")
                            except Exception as e: 
                                if callback_msg: 
                                    callback_msg(f"❌ 截图保存失败：{str(e)}")
                                pass
                            step_success = True
                        elif cmd == 10.0:
                            # 比对功能：检查图片，如果能发现则停留在这一步，有变化则进入下一步
                            if self.check_stop_flag():
                                return True
                            
                            # 检查超时
                            if enable_timeout and self.timeout_val > 0:
                                elapsed_time = time.time() - self.step_start_time
                                if elapsed_time > self.timeout_val:
                                    if callback_msg: callback_msg(f"⏰ 比对超时 ({elapsed_time:.1f}秒 > {self.timeout_val}秒)")
                                    step_timeout = True
                                
                            if not step_timeout:
                                loc = self.find_target_optimized(val)
                                if loc:
                                    if callback_msg: callback_msg(f"📷 比对中：图片存在，继续监控...")
                                    step_success = False
                                    time.sleep(0.5)
                                else:
                                    if callback_msg: callback_msg(f"📷 比对完成：图片消失，进入下一步")
                                    step_success = True
                        elif cmd == 11.0:
                            # 多条件检测：根据配置的逻辑类型检测图片
                            if self.check_stop_flag():
                                return True
                            
                            # 检查超时
                            if enable_timeout and self.timeout_val > 0:
                                elapsed_time = time.time() - self.step_start_time
                                if elapsed_time > self.timeout_val:
                                    if callback_msg: callback_msg(f"⏰ 多条件检测超时 ({elapsed_time:.1f}秒 > {self.timeout_val}秒)")
                                    step_timeout = True
                                
                            if not step_timeout:
                                try:
                                    config = json.loads(str(val))
                                    if isinstance(config, dict) and "images" in config:
                                        images = config["images"]
                                        logic = config.get("logic", "AND")
                                    else:
                                        images = config
                                        logic = "AND"
                                    
                                    if not images:
                                        if callback_msg: callback_msg(f"⚠️ 多条件检测：未配置任何图片")
                                        step_success = True
                                    else:
                                        found_count = 0
                                        for img_path in images:
                                            loc = self.find_target_optimized(img_path)
                                            if loc:
                                                found_count += 1
                                        
                                        if logic == "AND":
                                            if found_count == len(images):
                                                if callback_msg: callback_msg(f"✅ 多条件检测(AND)：所有 {len(images)} 个图片均找到，进入下一步")
                                                step_success = True
                                            else:
                                                if callback_msg: callback_msg(f"🔍 多条件检测(AND)：已找到 {found_count}/{len(images)} 个图片，继续检测...")
                                                step_success = False
                                                time.sleep(0.5)
                                        else:
                                            if found_count > 0:
                                                if callback_msg: callback_msg(f"✅ 多条件检测(OR)：找到 {found_count}/{len(images)} 个图片，进入下一步")
                                                step_success = True
                                            else:
                                                if callback_msg: callback_msg(f"🔍 多条件检测(OR)：未找到任何图片，继续检测...")
                                                step_success = False
                                                time.sleep(0.5)
                                except Exception as e:
                                    if callback_msg: callback_msg(f"❌ 多条件检测配置错误：{str(e)}")
                                    step_success = True
                        elif cmd == 12.0:
                            # 消失触发：检测图片元素，当所有/任一元素消失后进入下一步
                            if self.check_stop_flag():
                                return True
                            
                            # 检查超时
                            if enable_timeout and self.timeout_val > 0:
                                elapsed_time = time.time() - self.step_start_time
                                if elapsed_time > self.timeout_val:
                                    if callback_msg: callback_msg(f"⏰ 消失触发超时 ({elapsed_time:.1f}秒 > {self.timeout_val}秒)")
                                    step_timeout = True
                                
                            if not step_timeout:
                                try:
                                    config = json.loads(str(val))
                                    if isinstance(config, dict) and "images" in config:
                                        images = config["images"]
                                        logic = config.get("logic", "AND")
                                    else:
                                        images = [val]
                                        logic = "AND"
                                    
                                    if not images:
                                        if callback_msg: callback_msg(f"⚠️ 消失触发：未配置任何图片")
                                        step_success = True
                                    else:
                                        vanish_count = 0
                                        for img_path in images:
                                            loc = self.find_target_optimized(img_path)
                                            if not loc:
                                                vanish_count += 1
                                        
                                        if logic == "AND":
                                            # AND逻辑：所有图片都消失才进入下一步
                                            if vanish_count == len(images):
                                                if callback_msg: callback_msg(f"✅ 消失触发(AND)：所有 {len(images)} 个图片均已消失，进入下一步")
                                                step_success = True
                                            else:
                                                if callback_msg: callback_msg(f"🎯 消失触发(AND)：已消失 {vanish_count}/{len(images)} 个图片，继续等待...")
                                                step_success = False
                                                time.sleep(0.8)
                                        else:
                                            # OR逻辑：只要有一个图片消失就进入下一步
                                            if vanish_count > 0:
                                                if callback_msg: callback_msg(f"✅ 消失触发(OR)：{vanish_count}/{len(images)} 个图片已消失，进入下一步")
                                                step_success = True
                                            else:
                                                if callback_msg: callback_msg(f"🎯 消失触发(OR)：所有 {len(images)} 个图片仍存在，继续等待...")
                                                step_success = False
                                                time.sleep(0.8)
                                except Exception as e:
                                    # 兼容旧格式：单个图片路径
                                    loc = self.find_target_optimized(val)
                                    if loc:
                                        if callback_msg: callback_msg(f"🎯 消失触发：元素存在，等待消失...")
                                        step_success = False
                                        time.sleep(0.8)
                                    else:
                                        # 图片消失，进入下一步
                                        if callback_msg: callback_msg(f"✅ 消失触发：元素已消失，进入下一步")
                                        step_success = True
                        elif cmd == 13.0:
                            # 控件调用：加载JSON文件并执行记录的操作
                            import json as json_mod
                            file_path = str(val)
                            try:
                                with open(file_path, 'r', encoding='utf-8') as f:
                                    control_actions = json_mod.load(f)
                                if callback_msg: callback_msg(f"📂 控件调用：加载 {len(control_actions)} 个操作")
                                
                                for act in control_actions:
                                    if self.check_stop_flag():
                                        return True
                                    
                                    # 等待间隔
                                    interval = act.get('interval', 0)
                                    if interval > 0:
                                        time.sleep(interval / 1000.0)
                                    
                                    if act['type'] == 'mouse':
                                        x, y = act['x'], act['y']
                                        action_type = act.get('action', '左键单击')
                                        if action_type == '左键单击':
                                            pyautogui.click(x, y)
                                        elif action_type == '右键单击':
                                            pyautogui.rightClick(x, y)
                                        elif action_type == '中键单击':
                                            pyautogui.middleClick(x, y)
                                        elif action_type == '左键双击':
                                            pyautogui.doubleClick(x, y)
                                        else:
                                            pyautogui.click(x, y)
                                        if callback_msg: callback_msg(f"  🖱️ {action_type} ({x}, {y})")
                                    elif act['type'] == 'keyboard':
                                        key = act.get('key', '')
                                        pyautogui.press(key)
                                        if callback_msg: callback_msg(f"  ⌨️ 按键: {key}")
                                
                                step_success = True
                            except FileNotFoundError:
                                if callback_msg: callback_msg(f"❌ 控件调用：文件不存在 {file_path}")
                                step_success = True
                            except Exception as e:
                                if callback_msg: callback_msg(f"❌ 控件调用失败：{str(e)}")
                                step_success = True
                        elif cmd == 14.0:
                            # 图片条件分支：检测图片，存在走成功分支，不存在走失败分支
                            if self.check_stop_flag():
                                return True
                            try:
                                config = json.loads(str(val)) if isinstance(val, str) else val
                                if isinstance(config, str):
                                    config = json.loads(config)
                                image_path = config.get("image", "")
                                max_wait = float(config.get("max_wait", 5))
                                success_tasks = config.get("success_tasks", [])
                                failure_tasks = config.get("failure_tasks", [])
                            except Exception as e:
                                if callback_msg: callback_msg(f"❌ 条件分支配置解析失败：{str(e)}")
                                step_success = True
                                continue
                            
                            if not image_path:
                                if callback_msg: callback_msg(f"⚠️ 条件分支：未配置检测图片")
                                step_success = True
                                continue
                            
                            if callback_msg: callback_msg(f"🔀 条件分支：检测图片 {os.path.basename(image_path)}，等待 {max_wait} 秒")
                            
                            # 在等待时间内尝试查找图片
                            found = False
                            branch_start_time = time.time()
                            while time.time() - branch_start_time < max_wait:
                                if self.check_stop_flag():
                                    return True
                                loc = self.find_target_optimized(image_path)
                                if loc:
                                    found = True
                                    break
                                time.sleep(0.2)
                            
                            saved_is_running = self.is_running
                            if found:
                                if callback_msg: callback_msg(f"✅ 条件分支：图片存在，执行成功分支")
                                if success_tasks:
                                    self.run_tasks(success_tasks, False, callback_msg, enable_timeout=False)
                                else:
                                    if callback_msg: callback_msg(f"  成功分支无步骤，继续主流程")
                            else:
                                if callback_msg: callback_msg(f"❌ 条件分支：图片不存在，执行失败分支")
                                if failure_tasks:
                                    self.run_tasks(failure_tasks, False, callback_msg, enable_timeout=False)
                                else:
                                    if callback_msg: callback_msg(f"  失败分支无步骤，继续主流程")
                            self.is_running = saved_is_running
                            if callback_msg: callback_msg(f"🔀 条件分支完成，继续主流程")
                            step_success = True
                        elif cmd == 15.0:
                            # 鼠标拖动：从起点拖动到终点
                            if self.check_stop_flag():
                                return True
                            
                            val_str = str(val)
                            
                            # 尝试解析坐标格式：start_x,start_y,end_x,end_y[,duration]
                            import re
                            coords = re.findall(r'-?\d+(?:\.\d+)?', val_str)
                            
                            if len(coords) >= 4:
                                try:
                                    sx, sy = float(coords[0]), float(coords[1])
                                    ex, ey = float(coords[2]), float(coords[3])
                                    duration = float(coords[4]) if len(coords) >= 5 else 0.2
                                    
                                    if callback_msg: callback_msg(f"🖱️ 鼠标拖动：({sx:.0f},{sy:.0f}) → ({ex:.0f},{ey:.0f}) 耗时{duration:.1f}秒")
                                    pyautogui.moveTo(sx, sy)
                                    pyautogui.drag(ex - sx, ey - sy, duration=duration)
                                    step_success = True
                                except Exception as e:
                                    if callback_msg: callback_msg(f"❌ 鼠标拖动坐标执行失败：{str(e)}")
                                    step_success = True
                            else:
                                # 图片模式：找图并从图片中心拖动
                                if callback_msg: callback_msg(f"🖱️ 鼠标拖动（图片模式）：{os.path.basename(val_str)}")
                                loc = self.find_target_optimized(val_str)
                                if loc:
                                    try:
                                        sx, sy = loc
                                        ex, ey = sx + 50, sy  # 默认向右拖动50像素
                                        pyautogui.moveTo(sx, sy)
                                        pyautogui.drag(ex - sx, ey - sy, duration=0.2)
                                        if callback_msg: callback_msg(f"  ✅ 从 ({sx:.0f},{sy:.0f}) 拖动到 ({ex:.0f},{ey:.0f})")
                                    except Exception as e:
                                        if callback_msg: callback_msg(f"❌ 鼠标拖动图片模式失败：{str(e)}")
                                else:
                                    if callback_msg: callback_msg(f"⚠️ 鼠标拖动：未找到图片 {os.path.basename(val_str)}")
                                step_success = True
                        
                        # 处理超时
                        if step_timeout and enable_timeout:
                            # 获取当前步骤的应对步骤配置
                            response_data = task.get("response_data", {})
                            response_tasks = response_data.get("tasks", [])
                            timeout_action = response_data.get("timeout_action", "retry")
                            
                            if response_tasks:
                                # 有步骤级别的应对步骤
                                if callback_msg: callback_msg(f"⏰ 步骤超时，执行步骤级应对步骤")
                                saved_is_running = self.is_running
                                
                                # 从步骤配置中获取应对步骤超时时间
                                response_data = task.get("response_data", {})
                                response_timeout_str = response_data.get("response_timeout", "100")
                                try:
                                    max_response_time = float(response_timeout_str) if float(response_timeout_str) > 0 else float('inf')
                                except:
                                    max_response_time = 100.0
                                
                                start_response_time = time.time()
                                
                                # 创建一个检查函数来限制应对步骤的执行时间
                                def check_response_timeout():
                                    elapsed = time.time() - start_response_time
                                    if elapsed > max_response_time:
                                        if callback_msg: callback_msg(f"⚠️ 应对步骤执行超时 ({elapsed:.1f}秒 > {max_response_time:.1f}秒)")
                                        return True
                                    return False
                                
                                # 临时替换检查停止标志的方法，添加应对步骤超时检查
                                original_check_stop = self.check_stop_flag
                                def wrapped_check_stop():
                                    if check_response_timeout():
                                        return True
                                    return original_check_stop()
                                self.check_stop_flag = wrapped_check_stop
                                
                                try:
                                    self.run_tasks(response_tasks, False, callback_msg, enable_timeout=False)
                                finally:
                                    # 恢复原方法
                                    self.check_stop_flag = original_check_stop
                                
                                self.is_running = saved_is_running
                                if callback_msg: callback_msg("=== 步骤级应对步骤执行完成 ===")
                                
                                # 应对完成后根据步骤配置的动作处理
                                if timeout_action == "retry":
                                    if callback_msg: callback_msg("=== 重新执行当前步骤 ===")
                                    step_timeout = False  # 重置超时标志，继续循环
                                elif timeout_action == "skip":
                                    if callback_msg: callback_msg("=== 跳过当前步骤，执行下一个步骤 ===")
                                    step_success = True  # 标记为成功，继续下一个步骤
                                else:
                                    if callback_msg: callback_msg("=== 重新开始主步骤 ===")
                                    break
                            elif timeout_callback:
                                # 使用全局超时回调（只在步骤级别没有应对步骤时使用）
                                if callback_msg: callback_msg(f"⏰ 步骤超时，执行全局应对步骤")
                                response_success = timeout_callback()
                                if response_success:
                                    # 全局应对成功后总是重新开始主流程
                                    if callback_msg: callback_msg("=== 全局应对成功，重新开始主步骤 ===")
                                else:
                                    if callback_msg: callback_msg("=== 全局应对失败，重新开始主步骤 ===")
                                break
                            else:
                                # 没有应对步骤，直接重新开始
                                if callback_msg: callback_msg("=== 步骤超时，重新开始主步骤 ===")
                                break
                    
                    # 如果是因为应对失败而跳出，继续外层 while 循环
                    if step_timeout:
                        continue

                if not loop_forever: 
                    if callback_msg: callback_msg("=== 单次循环执行完成 ===")
                    break
                if self.check_stop_flag(): return True
                
                if callback_msg: callback_msg(f"=== 第 {loop_count} 轮循环完成，准备下一轮 ===")
                
        except Exception as e:
            self.log(f"引擎异常: {e}")
        finally:
            self.is_running = False
            if callback_msg: callback_msg("结束")
        
        return True  # 返回True表示正常完成

# --------------------------
# GUI 界面
# --------------------------
class WorkerThread(QThread):
    log_signal = Signal(str)
    finished_signal = Signal()
    def __init__(self, engine, tasks, loop_forever, parent_window=None):
        super().__init__()
        self.engine = engine
        self.tasks = tasks
        self.loop_forever = loop_forever
        self.parent_window = parent_window
        self.watchdog = None 

    def run(self):
        self.watchdog = FailsafeWatchdog(self.engine)
        self.watchdog.start()
        
        # 使用超时管理器处理重试逻辑
        handle_timeout_retry(self, self.engine, self.tasks, self.loop_forever, self.log_callback)
        
        if self.watchdog: 
            self.watchdog.kill()
        self.finished_signal.emit()

    def log_callback(self, msg): 
        if GLOBAL_CONFIG["log_to_ui"]:
            self.log_signal.emit(msg)

class TaskRow(QFrame):
    move_up_signal = Signal(object)
    move_down_signal = Signal(object)
    
    def __init__(self, delete_callback=None, data=None, index=0):
        super().__init__()
        self.parent_item = None
        self.setFrameShape(QFrame.StyledPanel)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(2, 2, 2, 2)
        
        # 处理参数
        if isinstance(delete_callback, dict):
            # 如果传递的是字典，将其作为data
            data = delete_callback
            delete_callback = None
        
        self.delete_callback = delete_callback
        self.index = index
        self.screenshot_region = None
        
        # 步骤序号
        self.index_label = QLabel(f"{index + 1}.")
        self.index_label.setFixedWidth(30)
        self.index_label.setStyleSheet("font-weight: bold; color: #2196F3;")
        self.layout.addWidget(self.index_label)
        
        self.type_combo = QComboBox()
        self.type_combo.addItems(["左键单击", "左键双击", "右键单击", "输入文本", "等待(秒)", "滚轮滑动", "系统按键", "鼠标悬停", "截图保存", "比对", "多条件检测", "消失触发", "控件调用", "鼠标拖动", "图片条件分支"])
        self.type_combo.currentTextChanged.connect(self.on_type_changed)
        self.layout.addWidget(self.type_combo)
        
        self.value_input = QLineEdit()
        self.value_input.setPlaceholderText("参数")
        self.value_input.textChanged.connect(self.sync_data)
        self.layout.addWidget(self.value_input)
        
        self.file_btn = QPushButton("选择")
        self.file_btn.clicked.connect(self.select_file)
        self.layout.addWidget(self.file_btn)
        
        # 应对步骤配置按钮
        self.response_btn = QPushButton("⚙️ 应对")
        self.response_btn.setStyleSheet("background-color: #FF9800; color: white;")
        self.response_btn.setFixedWidth(80)
        self.response_btn.clicked.connect(self.open_response_config)
        self.layout.addWidget(self.response_btn)
        
        self.del_btn = QPushButton("X")
        self.del_btn.setStyleSheet("color: red; font-weight: bold;")
        self.del_btn.setFixedWidth(25)
        if self.delete_callback:
            self.del_btn.clicked.connect(lambda: self.delete_callback(self))
        else:
            # 如果没有delete_callback，隐藏删除按钮
            self.del_btn.setVisible(False)
        self.layout.addWidget(self.del_btn)
        
        # 设置数据
        if data:
            self.set_data(data)
        
        self.on_type_changed(self.type_combo.currentText())

    def set_parent_item(self, item):
        self.parent_item = item
        self.sync_data() 
    
    def set_index(self, index):
        """设置步骤序号"""
        self.index = index
        self.index_label.setText(f"{index + 1}.")
    
    def sync_data(self):
        if getattr(self, 'parent_item', None):
            self.parent_item.setData(Qt.UserRole, self.get_data())

    def on_type_changed(self, text):
        is_image_type = "单击" in text or "双击" in text or "悬停" in text or "截图" in text or "比对" in text or "消失触发" in text or "拖动" in text
        is_multi_condition = text == "多条件检测"
        is_vanish_trigger = text == "消失触发"
        is_screenshot = text == "截图保存"
        is_click_type = "单击" in text or "双击" in text
        is_control_call = text == "控件调用"
        is_condition_branch = text == "图片条件分支"
        is_drag = text == "鼠标拖动"
        
        self.file_btn.setVisible((is_image_type and not is_screenshot and not is_multi_condition and not is_vanish_trigger and not is_condition_branch) or is_control_call)
        
        if is_screenshot:
            if not hasattr(self, 'region_btn'):
                self.region_btn = QPushButton("📍 选区域")
                self.region_btn.clicked.connect(self.select_screenshot_region)
                self.layout.insertWidget(4, self.region_btn)
            self.region_btn.show()
            self.value_input.setPlaceholderText("保存路径 或 (x,y,w,h),保存路径(如: (100,200,300,400),test.png)")
        elif is_click_type:
            if hasattr(self, 'region_btn'):
                self.region_btn.hide()
            self.value_input.setPlaceholderText("图片路径 或 坐标(如: 100,200 或 100，200)")
        elif is_control_call:
            if hasattr(self, 'region_btn'):
                self.region_btn.hide()
            self.value_input.setPlaceholderText("控件操作JSON文件路径")
        elif is_condition_branch:
            if hasattr(self, 'region_btn'):
                self.region_btn.hide()
            self.value_input.setPlaceholderText("检测的图片路径（自动生成配置）")
            self.file_btn.setVisible(True)
            if not hasattr(self, 'branch_config_btn'):
                self.branch_config_btn = QPushButton("🔀 配置分支")
                self.branch_config_btn.clicked.connect(self.open_branch_config)
                self.layout.insertWidget(4, self.branch_config_btn)
            self.branch_config_btn.show()
        elif is_drag:
            if hasattr(self, 'region_btn'):
                self.region_btn.hide()
            if hasattr(self, 'branch_config_btn'):
                self.branch_config_btn.hide()
            self.value_input.setPlaceholderText("起点x,起点y,终点x,终点y 或 图片路径")
        else:
            if hasattr(self, 'region_btn'):
                self.region_btn.hide()
            self.value_input.setPlaceholderText("参数")
        
        if is_multi_condition:
            self.file_btn.setVisible(False)
            if not hasattr(self, 'multi_condition_btn'):
                self.multi_condition_btn = QPushButton("🔧 配置")
                self.multi_condition_btn.clicked.connect(self.open_multi_condition_config)
                self.layout.insertWidget(4, self.multi_condition_btn)
            self.multi_condition_btn.show()
            if hasattr(self, 'vanish_trigger_btn'):
                self.vanish_trigger_btn.hide()
            if hasattr(self, 'branch_config_btn'):
                self.branch_config_btn.hide()
        elif is_vanish_trigger:
            self.file_btn.setVisible(False)
            if not hasattr(self, 'vanish_trigger_btn'):
                self.vanish_trigger_btn = QPushButton("🔧 配置")
                self.vanish_trigger_btn.clicked.connect(self.open_vanish_trigger_config)
                self.layout.insertWidget(4, self.vanish_trigger_btn)
            self.vanish_trigger_btn.show()
            if hasattr(self, 'multi_condition_btn'):
                self.multi_condition_btn.hide()
            if hasattr(self, 'branch_config_btn'):
                self.branch_config_btn.hide()
        elif is_condition_branch:
            if hasattr(self, 'multi_condition_btn'):
                self.multi_condition_btn.hide()
            if hasattr(self, 'vanish_trigger_btn'):
                self.vanish_trigger_btn.hide()
        elif is_drag:
            if hasattr(self, 'multi_condition_btn'):
                self.multi_condition_btn.hide()
            if hasattr(self, 'vanish_trigger_btn'):
                self.vanish_trigger_btn.hide()
            if hasattr(self, 'branch_config_btn'):
                self.branch_config_btn.hide()
        else:
            if hasattr(self, 'multi_condition_btn'):
                self.multi_condition_btn.hide()
            if hasattr(self, 'vanish_trigger_btn'):
                self.vanish_trigger_btn.hide()
            if hasattr(self, 'branch_config_btn'):
                self.branch_config_btn.hide()
        self.sync_data()
            
    def set_data(self, data):
        self.value_input.setText(str(data.get("value", "")))
        TYPES_REV = {1.0: "左键单击", 2.0: "左键双击", 3.0: "右键单击", 4.0: "输入文本", 5.0: "等待(秒)", 6.0: "滚轮滑动", 7.0: "系统按键", 8.0: "鼠标悬停", 9.0: "截图保存", 10.0: "比对", 11.0: "多条件检测", 12.0: "消失触发", 13.0: "控件调用", 14.0: "图片条件分支", 15.0: "鼠标拖动"}
        t = data.get("type", 1.0)
        if t in TYPES_REV:
            self.type_combo.setCurrentText(TYPES_REV[t])
        
        if t == 9.0:
            self.screenshot_region = data.get("screenshot_region", None)
            if self.screenshot_region and hasattr(self, 'region_btn'):
                x, y, w, h = self.screenshot_region
                self.region_btn.setText(f"📍 {w}x{h}")
        
        if t == 11.0:
            self.on_type_changed("多条件检测")
        elif t == 12.0:
            self.on_type_changed("消失触发")
        elif t == 14.0:
            self.on_type_changed("图片条件分支")
            # 从 value 中解析分支配置
            val_str = str(data.get("value", ""))
            if val_str:
                try:
                    parsed = json.loads(val_str)
                    if isinstance(parsed, dict):
                        self.branch_data = parsed
                except:
                    self.branch_data = {"image": val_str, "max_wait": 5, "success_tasks": [], "failure_tasks": []}
        
        self.response_data = data.get("response_data", {})
        self.update_response_btn_display()
    
    def open_multi_condition_config(self):
        """打开多条件检测配置对话框"""
        dialog = MultiConditionConfigDialog(self)
        dialog.exec_()
    
    def open_vanish_trigger_config(self):
        """打开消失触发配置对话框"""
        dialog = VanishTriggerConfigDialog(self)
        dialog.exec_()
    
    def select_file(self):
        if self.type_combo.currentText() == "控件调用":
            filter_text = "JSON文件 (*.json)"
        else:
            filter_text = "Images (*.png *.jpg *.bmp)"
        path, _ = QFileDialog.getOpenFileName(self, "选择", filter=filter_text)
        if path:
            self.value_input.setText(path)
            if self.type_combo.currentText() == "图片条件分支":
                # 把选中的图片同步到 branch_data
                branch_data = getattr(self, 'branch_data', {})
                branch_data["image"] = path
                self.branch_data = branch_data
    
    def select_screenshot_region(self):
        """选择截图区域并保存到配置中"""
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QEventLoop, Signal
        
        write_log("开始选择截图区域...")
        
        class ScreenshotRegionSelector(QWidget):
            closed = Signal()
            
            def __init__(self):
                super().__init__()
                self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
                self.setAttribute(Qt.WA_TranslucentBackground)
                self.setCursor(Qt.CrossCursor)
                self.setMouseTracking(True)
                virtual_rect = QApplication.primaryScreen().virtualGeometry()
                self.setGeometry(virtual_rect)
                
                phys_w, phys_h = pyautogui.size()
                log_w = virtual_rect.width()
                log_h = virtual_rect.height()
                self.scale_x = phys_w / log_w
                self.scale_y = phys_h / log_h
                
                self.start_point = None
                self.end_point = None
                self.selected_region = None
                self.show()
            
            def paintEvent(self, event):
                painter = QPainter(self)
                painter.setRenderHint(QPainter.Antialiasing)
                bg_color = QColor(0, 0, 0, 100)
                
                if self.start_point and self.end_point:
                    rect = QRect(self.start_point, self.end_point).normalized()
                    mask_region = QRegion(self.rect())
                    selection_region = QRegion(rect)
                    overlay_region = mask_region.subtracted(selection_region)
                    painter.setClipRegion(overlay_region)
                    painter.fillRect(self.rect(), bg_color)
                    
                    painter.setClipping(False)
                    pen = QPen(QColor(0, 255, 0), 2)
                    pen.setStyle(Qt.DashLine)
                    painter.setPen(pen)
                    painter.setBrush(Qt.NoBrush)
                    painter.drawRect(rect)
                    
                    real_w = int(rect.width() * self.scale_x)
                    real_h = int(rect.height() * self.scale_y)
                    info_text = f"选区:{rect.width()}x{rect.height()} (实际: {real_w}x{real_h})"
                    painter.setPen(QColor(255, 255, 255))
                    painter.setFont(QFont("Arial", 12, QFont.Bold))
                    text_y = rect.y() - 10
                    if text_y < 30: text_y = rect.y() + 30
                    painter.drawText(rect.x(), text_y, info_text)
                else:
                    painter.fillRect(self.rect(), bg_color)
                    painter.setPen(QColor(255, 255, 255))
                    painter.setFont(QFont("Arial", 16, QFont.Bold))
                    hint = "请框选截图区域 | 左键拖动选择 | 右键取消"
                    fm = painter.fontMetrics()
                    tw = fm.horizontalAdvance(hint)
                    painter.drawText((self.width() - tw)//2, 100, hint)
            
            def mousePressEvent(self, event):
                if event.button() == Qt.LeftButton:
                    self.start_point = event.pos()
                    self.end_point = None
                    self.update()
                elif event.button() == Qt.RightButton:
                    self.selected_region = None
                    self.close()
            
            def mouseMoveEvent(self, event):
                if self.start_point:
                    self.end_point = event.pos()
                    self.update()
            
            def mouseReleaseEvent(self, event):
                if event.button() == Qt.LeftButton and self.start_point and self.end_point:
                    rect = QRect(self.start_point, self.end_point).normalized()
                    if rect.width() > 10 and rect.height() > 10:
                        x = int(rect.x() * self.scale_x)
                        y = int(rect.y() * self.scale_y)
                        w = int(rect.width() * self.scale_x)
                        h = int(rect.height() * self.scale_y)
                        self.selected_region = (x, y, w, h)
                    self.close()
            
            def closeEvent(self, event):
                self.closed.emit()
                event.accept()
        
        selector = ScreenshotRegionSelector()
        loop = QEventLoop()
        
        selector.closed.connect(loop.quit)
        
        loop.exec()
        
        result_region = selector.selected_region
        
        selector.deleteLater()
        
        if result_region:
            self.screenshot_region = result_region
            write_log(f"截图区域选择成功: {self.screenshot_region}")
            if hasattr(self, 'region_btn'):
                x, y, w, h = result_region
                self.region_btn.setText(f"📍 {w}x{h}")
        else:
            self.screenshot_region = None
            write_log("截图区域选择取消或未选择")
            if hasattr(self, 'region_btn'):
                self.region_btn.setText("📍 选区域")
    
    def update_response_btn_display(self):
        """更新应对按钮的可视化显示"""
        response_data = getattr(self, 'response_data', {})
        response_tasks = response_data.get("tasks", [])
        timeout_action = response_data.get("timeout_action", "retry")
        
        action_labels = {
            "retry": "🔄重试",
            "skip": "⏭️跳过", 
            "restart": "🔁重启"
        }
        
        if response_tasks:
            # 有配置应对步骤
            task_count = len(response_tasks)
            action_label = action_labels.get(timeout_action, "🔄重试")
            self.response_btn.setText(f"🛡️ 应对({task_count})")
            self.response_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
            # 添加工具提示显示详细信息
            action_text = {"retry": "重试当前步骤", "skip": "跳过当前步骤", "restart": "重新开始主流程"}
            tip_text = f"已配置 {task_count} 个应对步骤\n超时后动作: {action_text.get(timeout_action, '重试')}"
            self.response_btn.setToolTip(tip_text)
        else:
            # 未配置应对步骤
            self.response_btn.setText("⚙️ 应对")
            self.response_btn.setStyleSheet("background-color: #FF9800; color: white;")
            self.response_btn.setToolTip("点击配置应对步骤")
    
    def get_data(self):
        TYPES = {"左键单击": 1.0, "左键双击": 2.0, "右键单击": 3.0, "输入文本": 4.0, "等待(秒)": 5.0, "滚轮滑动": 6.0, "系统按键": 7.0, "鼠标悬停": 8.0, "截图保存": 9.0, "比对": 10.0, "多条件检测": 11.0, "消失触发": 12.0, "控件调用": 13.0, "图片条件分支": 14.0, "鼠标拖动": 15.0}
        val = self.value_input.text()
        t = TYPES.get(self.type_combo.currentText(), 1.0)
        if t in [5.0, 6.0] and not val: val = "0"
        
        data = {"type": t, "value": val, "response_data": getattr(self, 'response_data', {})}
        
        if t == 9.0:
            region = getattr(self, 'screenshot_region', None)
            data["screenshot_region"] = region
            write_log(f"截图保存步骤 - get_data: screenshot_region={region}")
        
        if t == 14.0:
            # 将分支配置序列化为 JSON 存入 value
            branch_data = getattr(self, 'branch_data', {})
            if branch_data:
                data["value"] = json.dumps(branch_data, ensure_ascii=False)
            else:
                data["value"] = val
        
        return data
    
    def open_response_config(self):
        """打开应对步骤配置对话框"""
        dialog = ResponseConfigDialog(self)
        dialog.exec_()
        # 对话框关闭后更新按钮显示
        self.update_response_btn_display()
    
    def open_branch_config(self):
        """打开图片条件分支配置对话框"""
        dialog = ConditionBranchConfigDialog(self)
        dialog.exec_()
        # 对话框关闭后更新 value 显示
        branch_data = getattr(self, 'branch_data', {})
        if branch_data.get("image"):
            self.value_input.setText(branch_data.get("image", ""))

class DraggableListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setSelectionMode(QAbstractItemView.SingleSelection)

    def dropEvent(self, event):
        super().dropEvent(event)
        for i in range(self.count()):
            item = self.item(i)
            if self.itemWidget(item) is None:
                data = item.data(Qt.UserRole)
                if data:
                    self.window().restore_row_widget(item, data)

class VanishTriggerConfigDialog(QDialog):
    """消失触发配置对话框"""
    def __init__(self, parent_row):
        super().__init__()
        self.parent_row = parent_row
        self.setWindowTitle("🎯 消失触发配置")
        self.resize(600, 550)
        self.setStyleSheet("QDialog { background-color: #f8f9fa; }")
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        logic_group = QGroupBox("🔧 检测逻辑")
        logic_layout = QVBoxLayout(logic_group)
        
        logic_label = QLabel("选择多个图片之间的检测逻辑：")
        logic_layout.addWidget(logic_label)
        
        self.logic_combo = QComboBox()
        self.logic_combo.addItems(["AND 逻辑", "OR 逻辑"])
        self.logic_combo.setStyleSheet("padding: 5px; min-width: 150px;")
        logic_layout.addWidget(self.logic_combo)
        
        logic_desc = QLabel()
        logic_desc.setStyleSheet("font-size: 12px; color: #666;")
        logic_desc.setText("""
        <ul>
        <li><b>AND 逻辑</b>：所有图片都消失才进入下一步（全部消失）</li>
        <li><b>OR 逻辑</b>：只要有一个图片消失就进入下一步（任一消失）</li>
        </ul>
        """)
        logic_layout.addWidget(logic_desc)
        layout.addWidget(logic_group)
        
        title_group = QGroupBox("📋 监控图片列表")
        title_layout = QVBoxLayout(title_group)
        
        title_label = QLabel("配置需要监控消失的图片列表")
        title_label.setWordWrap(True)
        title_layout.addWidget(title_label)
        
        self.image_list = QListWidget()
        self.image_list.setStyleSheet("background-color: white; border: 1px solid #ddd; border-radius: 4px;")
        title_layout.addWidget(self.image_list)
        
        btn_layout = QHBoxLayout()
        add_img_btn = QPushButton("➕ 添加图片")
        add_img_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 5px 15px; border-radius: 4px;")
        add_img_btn.clicked.connect(self.add_image)
        btn_layout.addWidget(add_img_btn)
        
        del_img_btn = QPushButton("🗑️ 删除选中")
        del_img_btn.setStyleSheet("background-color: #f44336; color: white; padding: 5px 15px; border-radius: 4px;")
        del_img_btn.clicked.connect(self.delete_image)
        btn_layout.addWidget(del_img_btn)
        
        btn_layout.addStretch()
        title_layout.addLayout(btn_layout)
        
        layout.addWidget(title_group)
        
        dialog_btn_layout = QHBoxLayout()
        ok_btn = QPushButton("✅ 确定")
        ok_btn.setStyleSheet("background-color: #2196F3; color: white; padding: 8px 25px; border-radius: 4px; font-weight: bold;")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("❌ 取消")
        cancel_btn.setStyleSheet("background-color: #f0f0f0; color: #333; padding: 8px 25px; border-radius: 4px;")
        cancel_btn.clicked.connect(self.reject)
        dialog_btn_layout.addStretch()
        dialog_btn_layout.addWidget(ok_btn)
        dialog_btn_layout.addWidget(cancel_btn)
        layout.addLayout(dialog_btn_layout)
        
        self.load_data()
    
    def load_data(self):
        self.image_list.clear()
        data = self.parent_row.get_data()
        if data.get("type") == 12.0:
            value_str = data.get("value", "")
            if value_str:
                try:
                    config = json.loads(value_str)
                    if isinstance(config, dict) and "images" in config:
                        images = config["images"]
                        logic = config.get("logic", "AND")
                        self.logic_combo.setCurrentIndex(0 if logic == "AND" else 1)
                    else:
                        images = config
                        self.logic_combo.setCurrentIndex(0)
                    
                    for img_path in images:
                        item = QListWidgetItem(os.path.basename(img_path))
                        item.setData(Qt.UserRole, img_path)
                        self.image_list.addItem(item)
                except:
                    pass
    
    def add_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择图片", filter="Images (*.png *.jpg *.bmp)")
        if path:
            item = QListWidgetItem(os.path.basename(path))
            item.setData(Qt.UserRole, path)
            self.image_list.addItem(item)
    
    def delete_image(self):
        current_item = self.image_list.currentItem()
        if current_item:
            self.image_list.takeItem(self.image_list.row(current_item))
    
    def accept(self):
        images = []
        for i in range(self.image_list.count()):
            item = self.image_list.item(i)
            images.append(item.data(Qt.UserRole))
        
        logic = "AND" if self.logic_combo.currentIndex() == 0 else "OR"
        
        config = {
            "logic": logic,
            "images": images
        }
        self.parent_row.value_input.setText(json.dumps(config, ensure_ascii=False))
        super().accept()

class MultiConditionConfigDialog(QDialog):
    """多条件检测配置对话框"""
    def __init__(self, parent_row):
        super().__init__()
        self.parent_row = parent_row
        self.setWindowTitle("🔍 多条件检测配置")
        self.resize(600, 550)
        self.setStyleSheet("QDialog { background-color: #f8f9fa; }")
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 逻辑选择
        logic_group = QGroupBox("🔧 检测逻辑")
        logic_layout = QVBoxLayout(logic_group)
        
        logic_label = QLabel("选择多个图片之间的检测逻辑：")
        logic_layout.addWidget(logic_label)
        
        self.logic_combo = QComboBox()
        self.logic_combo.addItems(["AND 逻辑", "OR 逻辑"])
        self.logic_combo.setStyleSheet("padding: 5px; min-width: 150px;")
        logic_layout.addWidget(self.logic_combo)
        
        logic_desc = QLabel()
        logic_desc.setStyleSheet("font-size: 12px; color: #666;")
        logic_desc.setText("""
        <ul>
        <li><b>AND 逻辑</b>：所有图片都找到才进入下一步（需要同时存在）</li>
        <li><b>OR 逻辑</b>：只要有一个图片找到就进入下一步（满足任一即可）</li>
        </ul>
        """)
        logic_layout.addWidget(logic_desc)
        layout.addWidget(logic_group)
        
        # 标题和说明
        title_group = QGroupBox("📋 图片列表")
        title_layout = QVBoxLayout(title_group)
        
        title_label = QLabel("配置需要检测的图片列表")
        title_label.setWordWrap(True)
        title_layout.addWidget(title_label)
        
        # 图片列表
        self.image_list = QListWidget()
        self.image_list.setStyleSheet("background-color: white; border: 1px solid #ddd; border-radius: 4px;")
        title_layout.addWidget(self.image_list)
        
        # 操作按钮
        btn_layout = QHBoxLayout()
        add_img_btn = QPushButton("➕ 添加图片")
        add_img_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 5px 15px; border-radius: 4px;")
        add_img_btn.clicked.connect(self.add_image)
        btn_layout.addWidget(add_img_btn)
        
        del_img_btn = QPushButton("🗑️ 删除选中")
        del_img_btn.setStyleSheet("background-color: #f44336; color: white; padding: 5px 15px; border-radius: 4px;")
        del_img_btn.clicked.connect(self.delete_image)
        btn_layout.addWidget(del_img_btn)
        
        btn_layout.addStretch()
        title_layout.addLayout(btn_layout)
        
        layout.addWidget(title_group)
        
        # 确认和取消按钮
        dialog_btn_layout = QHBoxLayout()
        ok_btn = QPushButton("✅ 确定")
        ok_btn.setStyleSheet("background-color: #2196F3; color: white; padding: 8px 25px; border-radius: 4px; font-weight: bold;")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("❌ 取消")
        cancel_btn.setStyleSheet("background-color: #f0f0f0; color: #333; padding: 8px 25px; border-radius: 4px;")
        cancel_btn.clicked.connect(self.reject)
        dialog_btn_layout.addStretch()
        dialog_btn_layout.addWidget(ok_btn)
        dialog_btn_layout.addWidget(cancel_btn)
        layout.addLayout(dialog_btn_layout)
        
        # 加载现有数据
        self.load_data()
    
    def load_data(self):
        """加载现有配置数据"""
        self.image_list.clear()
        data = self.parent_row.get_data()
        if data.get("type") == 11.0:
            value_str = data.get("value", "")
            if value_str:
                try:
                    config = json.loads(value_str)
                    if isinstance(config, dict) and "images" in config:
                        # 新格式：包含逻辑类型和图片列表
                        images = config["images"]
                        logic = config.get("logic", "AND")
                        self.logic_combo.setCurrentIndex(0 if logic == "AND" else 1)
                    else:
                        # 旧格式：仅图片列表
                        images = config
                        self.logic_combo.setCurrentIndex(0)
                    
                    for img_path in images:
                        item = QListWidgetItem(os.path.basename(img_path))
                        item.setData(Qt.UserRole, img_path)
                        self.image_list.addItem(item)
                except:
                    pass
    
    def add_image(self):
        """添加图片"""
        path, _ = QFileDialog.getOpenFileName(self, "选择图片", filter="Images (*.png *.jpg *.bmp)")
        if path:
            item = QListWidgetItem(os.path.basename(path))
            item.setData(Qt.UserRole, path)
            self.image_list.addItem(item)
    
    def delete_image(self):
        """删除选中的图片"""
        current_item = self.image_list.currentItem()
        if current_item:
            self.image_list.takeItem(self.image_list.row(current_item))
    
    def accept(self):
        """保存配置"""
        images = []
        for i in range(self.image_list.count()):
            item = self.image_list.item(i)
            images.append(item.data(Qt.UserRole))
        
        # 获取逻辑类型
        logic = "AND" if self.logic_combo.currentIndex() == 0 else "OR"
        
        # 保存为JSON字符串（新格式）
        config = {
            "logic": logic,
            "images": images
        }
        self.parent_row.value_input.setText(json.dumps(config, ensure_ascii=False))
        super().accept()


class ResponseConfigDialog(QDialog):
    """应对步骤配置对话框"""
    def __init__(self, parent_row):
        super().__init__()
        self.parent_row = parent_row
        self.setWindowTitle("🛡️ 步骤应对配置")
        self.resize(550, 500)
        self.setStyleSheet("QDialog { background-color: #f8f9fa; }")
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题区域
        title_box = QGroupBox()
        title_layout = QVBoxLayout(title_box)
        title = QLabel(f"⚙️ 配置步骤 {parent_row.index + 1} 的应对策略")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #333;")
        title_layout.addWidget(title)
        
        # 流程说明
        flow_desc = QLabel()
        flow_desc.setStyleSheet("color: #666;")
        flow_desc.setText("""
        <span style="color:#FF9800">⏰ 步骤超时</span> 
        → <span style="color:#4CAF50">执行应对步骤</span> 
        → <span style="color:#2196F3">应对成功 → 继续执行当前步骤</span>
        → <span style="color:#f44336">应对失败 → 执行超时后动作</span>
        """)
        flow_desc.setWordWrap(True)
        title_layout.addWidget(flow_desc)
        layout.addWidget(title_box)
        
        # 应对步骤列表区域
        steps_box = QGroupBox("📋 应对步骤列表")
        steps_layout = QVBoxLayout(steps_box)
        
        self.task_list = DraggableListWidget()
        self.task_list.setStyleSheet("background-color: white; border: 1px solid #ddd; border-radius: 4px;")
        steps_layout.addWidget(self.task_list)
        
        toolbar = QHBoxLayout()
        add_btn = QPushButton("➕ 添加步骤")
        add_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 5px 15px; border-radius: 4px;")
        add_btn.clicked.connect(self.add_step)
        toolbar.addWidget(add_btn)
        toolbar.addStretch()
        steps_layout.addLayout(toolbar)
        layout.addWidget(steps_box)
        
        # 应对步骤超时时间配置
        timeout_box = QGroupBox("⏱️ 应对步骤超时时间")
        timeout_layout = QHBoxLayout(timeout_box)
        
        timeout_label = QLabel("最大执行时间:")
        timeout_layout.addWidget(timeout_label)
        
        self.response_timeout_edit = QLineEdit()
        self.response_timeout_edit.setPlaceholderText("100")
        self.response_timeout_edit.setFixedWidth(80)
        timeout_layout.addWidget(self.response_timeout_edit)
        
        timeout_unit = QLabel("秒 (0=不限制)")
        timeout_layout.addWidget(timeout_unit)
        timeout_layout.addStretch()
        
        timeout_hint = QLabel("设置应对步骤的最大执行时间，超过此时间将终止执行并视为失败")
        timeout_hint.setStyleSheet("color: #888; font-size: 11px;")
        timeout_layout.addWidget(timeout_hint)
        
        layout.addWidget(timeout_box)
        
        # 超时后动作区域
        action_box = QGroupBox("🎯 超时后动作（应对失败时执行）")
        action_layout = QVBoxLayout(action_box)
        
        action_hint = QLabel("选择应对步骤执行失败后的处理方式：")
        action_hint.setStyleSheet("color: #666; font-size: 13px;")
        action_layout.addWidget(action_hint)
        
        combo_layout = QHBoxLayout()
        self.timeout_action_combo = QComboBox()
        self.timeout_action_combo.setStyleSheet("padding: 5px; min-width: 200px;")
        self.timeout_action_combo.addItems(["🔄 重试当前步骤", "⏭️ 跳过当前步骤", "🔁 重新开始主流程"])
        combo_layout.addWidget(self.timeout_action_combo)
        combo_layout.addStretch()
        action_layout.addLayout(combo_layout)
        
        # 动作说明
        action_desc = QLabel()
        action_desc.setStyleSheet("font-size: 12px; color: #888;")
        action_desc.setText("""
        <ul>
        <li><b>🔄 重试当前步骤</b>：重新执行当前超时的步骤</li>
        <li><b>⏭️ 跳过当前步骤</b>：跳过当前步骤，执行下一步</li>
        <li><b>🔁 重新开始主流程</b>：从头开始执行整个流程</li>
        </ul>
        """)
        action_layout.addWidget(action_desc)
        layout.addWidget(action_box)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        ok_btn = QPushButton("✅ 确定")
        ok_btn.setStyleSheet("background-color: #2196F3; color: white; padding: 8px 25px; border-radius: 4px; font-weight: bold;")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("❌ 取消")
        cancel_btn.setStyleSheet("background-color: #f0f0f0; color: #333; padding: 8px 25px; border-radius: 4px;")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(ok_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
        
        # 加载现有应对步骤
        self.load_tasks()
    
    def load_tasks(self):
        """加载现有的应对步骤"""
        self.task_list.clear()
        response_data = getattr(self.parent_row, 'response_data', {})
        response_tasks = response_data.get("tasks", [])
        timeout_action = response_data.get("timeout_action", "retry")
        response_timeout = response_data.get("response_timeout", "100")
        
        # 设置超时动作
        action_index = {"retry": 0, "skip": 1, "restart": 2}.get(timeout_action, 0)
        self.timeout_action_combo.setCurrentIndex(action_index)
        
        # 设置应对步骤超时时间
        self.response_timeout_edit.setText(str(response_timeout))
        
        for task in response_tasks:
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, 40))
            row_widget = TaskRow(delete_callback=self.del_step, data=task)
            self.task_list.addItem(item)
            self.task_list.setItemWidget(item, row_widget)
    
    def add_step(self):
        """添加应对步骤"""
        default_task = {"type": 5.0, "value": "2"}
        item = QListWidgetItem()
        item.setSizeHint(QSize(0, 40))
        row_widget = TaskRow(delete_callback=self.del_step, data=default_task)
        self.task_list.addItem(item)
        self.task_list.setItemWidget(item, row_widget)
    
    def del_step(self, row_widget):
        """删除应对步骤"""
        for i in range(self.task_list.count()):
            item = self.task_list.item(i)
            if self.task_list.itemWidget(item) == row_widget:
                self.task_list.takeItem(i)
                break
    
    def accept(self):
        """保存应对步骤配置"""
        response_tasks = []
        for i in range(self.task_list.count()):
            item = self.task_list.item(i)
            widget = self.task_list.itemWidget(item)
            if widget:
                response_tasks.append(widget.get_data())
        
        # 保存超时动作
        action_index = self.timeout_action_combo.currentIndex()
        timeout_action = ["retry", "skip", "restart"][action_index]
        
        # 保存应对步骤超时时间
        response_timeout = self.response_timeout_edit.text() or "100"
        
        self.parent_row.response_data = {
            "tasks": response_tasks,
            "timeout_action": timeout_action,
            "response_timeout": response_timeout
        }
        self.parent_row.sync_data()
        super().accept()


class ConditionBranchConfigDialog(QDialog):
    """图片条件分支配置对话框"""
    def __init__(self, parent_row):
        super().__init__()
        self.parent_row = parent_row
        self.setWindowTitle("🔀 图片条件分支配置")
        self.resize(600, 550)
        self.setStyleSheet("QDialog { background-color: #f8f9fa; }")
        
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # 图片路径
        image_group = QGroupBox("📷 检测图片")
        image_layout = QHBoxLayout(image_group)
        self.image_path_edit = QLineEdit()
        self.image_path_edit.setPlaceholderText("选择要检测的图片路径...")
        image_layout.addWidget(self.image_path_edit)
        browse_btn = QPushButton("📂 浏览")
        browse_btn.clicked.connect(self.browse_image)
        image_layout.addWidget(browse_btn)
        layout.addWidget(image_group)
        
        # 最大等待时间
        timeout_group = QGroupBox("⏱️ 等待时间")
        timeout_layout = QHBoxLayout(timeout_group)
        timeout_label = QLabel("最大等待时间（秒）：")
        timeout_layout.addWidget(timeout_label)
        self.max_wait_edit = QLineEdit()
        self.max_wait_edit.setPlaceholderText("5")
        self.max_wait_edit.setFixedWidth(80)
        timeout_layout.addWidget(self.max_wait_edit)
        timeout_layout.addStretch()
        timeout_desc = QLabel("超过此时间未找到图片将进入失败分支")
        timeout_desc.setStyleSheet("color: #888; font-size: 11px;")
        timeout_layout.addWidget(timeout_desc)
        layout.addWidget(timeout_group)
        
        # 成功分支
        success_group = QGroupBox("✅ 成功分支（图片存在时执行）")
        success_layout = QVBoxLayout(success_group)
        self.success_task_list = QListWidget()
        self.success_task_list.setStyleSheet("background-color: white; border: 1px solid #ddd; border-radius: 4px; min-height: 120px;")
        success_layout.addWidget(self.success_task_list)
        success_toolbar = QHBoxLayout()
        add_success_btn = QPushButton("➕ 添加步骤")
        add_success_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 4px 12px; border-radius: 4px;")
        add_success_btn.clicked.connect(lambda: self.add_step(self.success_task_list))
        success_toolbar.addWidget(add_success_btn)
        success_toolbar.addStretch()
        success_layout.addLayout(success_toolbar)
        layout.addWidget(success_group)
        
        # 失败分支
        failure_group = QGroupBox("❌ 失败分支（图片不存在时执行）")
        failure_layout = QVBoxLayout(failure_group)
        self.failure_task_list = QListWidget()
        self.failure_task_list.setStyleSheet("background-color: white; border: 1px solid #ddd; border-radius: 4px; min-height: 120px;")
        failure_layout.addWidget(self.failure_task_list)
        failure_toolbar = QHBoxLayout()
        add_failure_btn = QPushButton("➕ 添加步骤")
        add_failure_btn.setStyleSheet("background-color: #FF9800; color: white; padding: 4px 12px; border-radius: 4px;")
        add_failure_btn.clicked.connect(lambda: self.add_step(self.failure_task_list))
        failure_toolbar.addWidget(add_failure_btn)
        failure_toolbar.addStretch()
        failure_layout.addLayout(failure_toolbar)
        layout.addWidget(failure_group)
        
        # 确定/取消按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        ok_btn = QPushButton("✅ 确定")
        ok_btn.setStyleSheet("background-color: #2196F3; color: white; padding: 8px 25px; border-radius: 4px; font-weight: bold;")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("❌ 取消")
        cancel_btn.setStyleSheet("background-color: #f0f0f0; color: #333; padding: 8px 25px; border-radius: 4px;")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        
        # 加载已有配置
        self.load_data()
    
    def browse_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择图片", filter="Images (*.png *.jpg *.bmp)")
        if path:
            self.image_path_edit.setText(path)
    
    def add_step(self, task_list):
        default_task = {"type": 5.0, "value": "2"}
        item = QListWidgetItem()
        item.setSizeHint(QSize(0, 40))
        row_widget = TaskRow(delete_callback=lambda w: self.del_step(task_list, w), data=default_task)
        task_list.addItem(item)
        task_list.setItemWidget(item, row_widget)
    
    def del_step(self, task_list, row_widget):
        for i in range(task_list.count()):
            item = task_list.item(i)
            if task_list.itemWidget(item) == row_widget:
                task_list.takeItem(i)
                break
    
    def load_data(self):
        """加载已有配置"""
        branch_data = getattr(self.parent_row, 'branch_data', {})
        if branch_data:
            self.image_path_edit.setText(branch_data.get("image", ""))
            self.max_wait_edit.setText(str(branch_data.get("max_wait", 5)))
            # 加载成功步骤
            for task in branch_data.get("success_tasks", []):
                item = QListWidgetItem()
                item.setSizeHint(QSize(0, 40))
                row_widget = TaskRow(delete_callback=lambda w: self.del_step(self.success_task_list, w), data=task)
                self.success_task_list.addItem(item)
                self.success_task_list.setItemWidget(item, row_widget)
            # 加载失败步骤
            for task in branch_data.get("failure_tasks", []):
                item = QListWidgetItem()
                item.setSizeHint(QSize(0, 40))
                row_widget = TaskRow(delete_callback=lambda w: self.del_step(self.failure_task_list, w), data=task)
                self.failure_task_list.addItem(item)
                self.failure_task_list.setItemWidget(item, row_widget)
    
    def accept(self):
        """保存分支配置"""
        # 收集成功步骤
        success_tasks = []
        for i in range(self.success_task_list.count()):
            item = self.success_task_list.item(i)
            widget = self.success_task_list.itemWidget(item)
            if widget:
                success_tasks.append(widget.get_data())
        
        # 收集失败步骤
        failure_tasks = []
        for i in range(self.failure_task_list.count()):
            item = self.failure_task_list.item(i)
            widget = self.failure_task_list.itemWidget(item)
            if widget:
                failure_tasks.append(widget.get_data())
        
        max_wait_str = self.max_wait_edit.text().strip()
        try:
            max_wait = float(max_wait_str) if max_wait_str else 5.0
        except:
            max_wait = 5.0
        
        self.parent_row.branch_data = {
            "image": self.image_path_edit.text(),
            "max_wait": max_wait,
            "success_tasks": success_tasks,
            "failure_tasks": failure_tasks
        }
        self.parent_row.sync_data()
        super().accept()


class RPAWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RAP工具V3.0 长弓")
        self.resize(900, 850)
        self.engine = RPAEngine()
        self.settings = QSettings("MyRPA", "Config")
        self.hotkey_vk = 0x78 # 默认 F9
        
        self.current_process = None
        if HAS_PSUTIL:
            try: self.current_process = psutil.Process()
            except: pass
            
            
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        
        # 页面切换栏
        page_bar = QHBoxLayout()
        self.main_page_btn = QPushButton("主页面")
        self.main_page_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.main_page_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(0))
        page_bar.addWidget(self.main_page_btn)
        
        self.timeout_page_btn = QPushButton("超时配置")
        self.timeout_page_btn.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold;")
        self.timeout_page_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(1))
        page_bar.addWidget(self.timeout_page_btn)
        
        page_bar.addStretch()
        main_layout.addLayout(page_bar)
        
        # 创建堆叠窗口
        self.stacked_widget = QStackedWidget()
        main_layout.addWidget(self.stacked_widget)
        
        # 主页面
        main_page = QWidget()
        main_page_layout = QVBoxLayout(main_page)
        
        # 顶部
        top_bar = QHBoxLayout()
        add_btn = QPushButton("+ 新增指令")
        add_btn.clicked.connect(lambda: self.add_row())
        top_bar.addWidget(add_btn)
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.save)
        top_bar.addWidget(save_btn)
        load_btn = QPushButton("导入")
        load_btn.clicked.connect(self.load)
        top_bar.addWidget(load_btn)
        
        # 设定区域
        region_btn = QPushButton("📷 设定识别区域")
        region_btn.setStyleSheet("background-color: #9C27B0; color: white; font-weight: bold;")
        region_btn.clicked.connect(self.open_region_selector)
        top_bar.addWidget(region_btn)
        
        # 控件检测
        inspect_btn = QPushButton("🔍 检测控件")
        inspect_btn.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold;")
        inspect_btn.clicked.connect(self.open_inspector)
        top_bar.addWidget(inspect_btn)
        
        # 条码转换
        barcode_btn = QPushButton("📷 条码转换")
        barcode_btn.setStyleSheet("background-color: #FF5722; color: white; font-weight: bold;")
        barcode_btn.clicked.connect(self.open_barcode_converter)
        top_bar.addWidget(barcode_btn)
        
        top_bar.addStretch()
        main_page_layout.addLayout(top_bar)

        # 1. 识别配置
        g1 = QGroupBox("识别配置")
        gl1 = QHBoxLayout()
        gl1.addWidget(QLabel("相似:"))
        self.conf_edit = QLineEdit(self.settings.value("conf", "0.8")); self.conf_edit.setFixedWidth(50); gl1.addWidget(self.conf_edit)
        gl1.addWidget(HelpBtn("【相似度 (0.1 - 1.0)】\n数值越低：越容易匹配。\n数值越高：越精确。\nFlash游戏建议 0.6 - 0.8。"))
        gl1.addSpacing(20)
        gl1.addWidget(QLabel("缩放:"))
        self.scale_min = QLineEdit(self.settings.value("scale_min", "0.8")); self.scale_min.setFixedWidth(50); gl1.addWidget(self.scale_min)
        gl1.addWidget(QLabel("-")); 
        self.scale_max = QLineEdit(self.settings.value("scale_max", "1.2")); self.scale_max.setFixedWidth(50); gl1.addWidget(self.scale_max)
        gl1.addWidget(HelpBtn("【缩放范围】\n程序启动时会预先生成缩放模板缓存。\n范围越小，启动越快，内存占用越小。"))
        gl1.addStretch()
        g1.setLayout(gl1)
        main_page_layout.addWidget(g1)
        
        # 2. 避让设置
        g_dodge = QGroupBox("避让设置")
        gl_dodge = QHBoxLayout()
        gl_dodge.addWidget(QLabel("坐标1 X:"))
        self.dodge_x1 = QLineEdit(self.settings.value("dodge_x1", "100")); self.dodge_x1.setFixedWidth(50); gl_dodge.addWidget(self.dodge_x1)
        gl_dodge.addWidget(QLabel("Y:"))
        self.dodge_y1 = QLineEdit(self.settings.value("dodge_y1", "100")); self.dodge_y1.setFixedWidth(50); gl_dodge.addWidget(self.dodge_y1)
        gl_dodge.addSpacing(15)
        gl_dodge.addWidget(QLabel("坐标2 X:"))
        self.dodge_x2 = QLineEdit(self.settings.value("dodge_x2", "200")); self.dodge_x2.setFixedWidth(50); gl_dodge.addWidget(self.dodge_x2)
        gl_dodge.addWidget(QLabel("Y:"))
        self.dodge_y2 = QLineEdit(self.settings.value("dodge_y2", "100")); self.dodge_y2.setFixedWidth(50); gl_dodge.addWidget(self.dodge_y2)
        self.dodge_chk = QCheckBox("启用"); self.dodge_chk.setChecked(self.settings.value("dodge_en", False, type=bool))
        gl_dodge.addWidget(self.dodge_chk)
        self.double_dodge_chk = QCheckBox("二段"); self.double_dodge_chk.setChecked(self.settings.value("dbl_dodge", False, type=bool))
        gl_dodge.addWidget(self.double_dodge_chk)
        gl_dodge.addWidget(QLabel("间隔:"))
        self.dbl_wait = QLineEdit(self.settings.value("dbl_wait", "0.015")); self.dbl_wait.setFixedWidth(60); gl_dodge.addWidget(self.dbl_wait)
        gl_dodge.addWidget(HelpBtn("【二段避让】\n强迫游戏更新鼠标位置。"))
        gl_dodge.addStretch()
        g_dodge.setLayout(gl_dodge)
        main_page_layout.addWidget(g_dodge)
        
        # 3. 速度控制
        g2 = QGroupBox("速度控制 (0为极速)")
        gl2 = QHBoxLayout()
        gl2.addWidget(QLabel("移动(s):")); self.move_spd = QLineEdit(self.settings.value("move_spd", "0.0")); self.move_spd.setFixedWidth(50); gl2.addWidget(self.move_spd)
        gl2.addWidget(HelpBtn("【移动耗时】\n0.0=瞬移。"))
        gl2.addWidget(QLabel("按住(s):")); self.click_hld = QLineEdit(self.settings.value("click_hld", "0.04")); self.click_hld.setFixedWidth(50); gl2.addWidget(self.click_hld)
        gl2.addWidget(HelpBtn("【按住时长】\nFlash游戏建议 0.04-0.08。"))
        gl2.addWidget(QLabel("缓冲(s):")); self.settle = QLineEdit(self.settings.value("settle", "0.0")); self.settle.setFixedWidth(50); gl2.addWidget(self.settle)
        gl2.addWidget(HelpBtn("【结算缓冲】\n点击后的等待时间。"))
        gl2.addWidget(QLabel("超时(s):")); self.timeout = QLineEdit(self.settings.value("timeout", "0.5")); self.timeout.setFixedWidth(50); gl2.addWidget(self.timeout)
        gl2.addWidget(HelpBtn("【任务超时】\n0.0=无超时限制。\n设置整体任务执行的最大时间。"))
        gl2.addStretch()
        g2.setLayout(gl2)
        main_page_layout.addWidget(g2)
        
        # 4. 系统设置
        g3 = QGroupBox("系统设置")
        gl3 = QHBoxLayout()
        
        # 热键选择
        gl3.addWidget(QLabel("热键:"))
        self.hotkey_combo = QComboBox()
        self.hotkey_combo.addItems([f"F{i}" for i in range(1, 13)])
        saved_key = self.settings.value("hotkey", "F9")
        self.hotkey_combo.setCurrentText(saved_key)
        self.hotkey_combo.currentTextChanged.connect(self.update_hotkey_display)
        self.hotkey_combo.setFixedWidth(80)
        gl3.addWidget(self.hotkey_combo)
        
        self.tm_failsafe = QCheckBox("任务管理器急停"); self.tm_failsafe.setChecked(True); gl3.addWidget(self.tm_failsafe)
        self.tr_failsafe = QCheckBox("右上角急停"); self.tr_failsafe.setChecked(True); gl3.addWidget(self.tr_failsafe)
        self.key_failsafe = QCheckBox("ESC/中键急停"); self.key_failsafe.setChecked(True); gl3.addWidget(self.key_failsafe)
        
        gl3.addSpacing(15)
        self.log_file_chk = QCheckBox("写入文件日志"); 
        self.log_file_chk.setChecked(self.settings.value("log_file", False, type=bool))
        gl3.addWidget(self.log_file_chk)
        self.log_ui_chk = QCheckBox("显示界面日志"); 
        self.log_ui_chk.setChecked(self.settings.value("log_ui", True, type=bool))
        gl3.addWidget(self.log_ui_chk)
        self.log_file_chk.stateChanged.connect(self.update_log_config)
        self.log_ui_chk.stateChanged.connect(self.update_log_config)
        
        # 开机自启动设置
        self.auto_start_btn = QPushButton("⚙️ 开机自启动")
        self.auto_start_btn.clicked.connect(self.manage_auto_start)
        gl3.addWidget(self.auto_start_btn)
        
        # 模板管理
        self.template_btn = QPushButton("📋 模板管理")
        self.template_btn.clicked.connect(self.manage_templates)
        gl3.addWidget(self.template_btn)
        
        gl3.addStretch()
        g3.setLayout(gl3)
        main_page_layout.addWidget(g3)

        # 任务列表
        self.task_list = DraggableListWidget()
        main_page_layout.addWidget(self.task_list)
        
        # 底部
        bot_layout = QHBoxLayout()
        self.loop_combo = QComboBox(); self.loop_combo.addItems(["单次", "无限"])
        bot_layout.addWidget(self.loop_combo)
        self.mini_chk = QCheckBox("最小化"); 
        self.mini_chk.setChecked(self.settings.value("mini", False, type=bool))
        bot_layout.addWidget(self.mini_chk)
        
        self.start_btn = QPushButton("启动"); self.start_btn.clicked.connect(self.start_task)
        self.start_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        bot_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("停止"); self.stop_btn.clicked.connect(self.stop_task)
        self.stop_btn.setStyleSheet("background-color: #f44336; color: white; font-weight: bold;")
        self.stop_btn.setEnabled(False)
        bot_layout.addWidget(self.stop_btn)
        
        main_page_layout.addLayout(bot_layout)
        
        self.log_text = QTextEdit(); self.log_text.setMaximumHeight(80)
        main_page_layout.addWidget(self.log_text)
        
        # 添加主页面到堆叠窗口
        self.stacked_widget.addWidget(main_page)
        
        # 超时配置页面
        timeout_page = create_timeout_page(self)
        
        # 添加超时配置页面到堆叠窗口
        self.stacked_widget.addWidget(timeout_page)
        
        # 状态栏
        self.status_layout = QHBoxLayout()
        self.log_path_label = QLabel(f"日志: {get_log_path()}")
        self.log_path_label.setStyleSheet("color: gray; font-size: 10px;")
        main_layout.addWidget(self.log_path_label)
        
        self.status_layout = QHBoxLayout()
        self.region_label = QLabel("范围: 全屏")
        self.region_label.setStyleSheet("color: green;")
        self.status_layout.addWidget(self.region_label)
        
        # 超时状态显示
        self.timeout_label = QLabel("超时: 无限制")
        self.timeout_label.setStyleSheet("color: orange;")
        self.status_layout.addWidget(self.timeout_label)
        
        self.status_layout.addStretch()
        self.cpu_label = QLabel("CPU: --")
        self.cpu_label.setStyleSheet("color: blue; font-weight: bold;")
        self.status_layout.addWidget(self.cpu_label)
        
        # 鼠标坐标显示
        self.mouse_pos_label = QLabel("鼠标: --")
        self.mouse_pos_label.setStyleSheet("color: #666; font-weight: bold; padding: 0 10px;")
        self.status_layout.addWidget(self.mouse_pos_label)
        
        main_layout.addLayout(self.status_layout)
        
        # 超时计时器
        self.timeout_timer = QTimer()
        self.timeout_timer.timeout.connect(self.update_timeout_status)
        self.execution_start_time = 0
        
        # 自动载入上一次模板
        self.auto_load_last_template()
        
        # 加载超时配置
        self.load_timeout_config()
        
        self.cpu_timer = QTimer()
        self.cpu_timer.timeout.connect(self.update_cpu_info)
        self.cpu_timer.start(1000)
        self.update_log_config()
        self.update_hotkey_display(self.hotkey_combo.currentText())

        # 快捷键轮询
        self.hotkey_timer = QTimer()
        self.hotkey_timer.timeout.connect(self.check_hotkey)
        self.hotkey_timer.start(100)
        
        # 鼠标坐标轮询
        self.mouse_timer = QTimer()
        self.mouse_timer.timeout.connect(self.update_mouse_pos)
        self.mouse_timer.start(50)  # 每50毫秒更新一次

    def update_hotkey_display(self, text):
        try:
            f_num = int(text.replace("F", ""))
            self.hotkey_vk = 0x70 + (f_num - 1)
            self.start_btn.setText(f"启动 ({text})")
            self.stop_btn.setText(f"停止 ({text})")
        except: pass

    def check_hotkey(self):
        if GetAsyncKeyState(self.hotkey_vk) & 0x8000:
            if self.engine.is_running:
                self.stop_task()
            else:
                self.start_task()
            self.hotkey_timer.stop()
            QTimer.singleShot(500, lambda: self.hotkey_timer.start(100))
    
    def update_mouse_pos(self):
        """更新鼠标坐标显示"""
        try:
            x, y = pyautogui.position()
            self.mouse_pos_label.setText(f"鼠标: ({x}, {y})")
        except:
            pass
    
    def mouseMoveEvent(self, event):
        """捕获鼠标移动事件（保留备用）"""
        super().mouseMoveEvent(event)

    def update_timeout_status(self):
        """更新超时状态显示"""
        if self.engine.is_running and self.engine.timeout_val > 0:
            # 使用步骤级别的开始时间，每个步骤会重置
            if self.engine.step_start_time > 0:
                elapsed_time = time.time() - self.engine.step_start_time
            else:
                elapsed_time = time.time() - self.execution_start_time
            remaining_time = max(0, self.engine.timeout_val - elapsed_time)
            progress_percent = (elapsed_time / self.engine.timeout_val) * 100
            self.timeout_label.setText(f"⏱️ 剩余: {remaining_time:.1f}秒 (已用: {elapsed_time:.1f}/{self.engine.timeout_val:.1f}秒, {progress_percent:.0f}%)")
            if remaining_time <= 0:
                self.timeout_label.setStyleSheet("color: red; font-weight: bold;")
            elif remaining_time < 5:
                self.timeout_label.setStyleSheet("color: red;")
            else:
                self.timeout_label.setStyleSheet("color: orange;")
        else:
            timeout_val = float(self.timeout.text())
            if timeout_val > 0:
                self.timeout_label.setText(f"超时: {timeout_val:.1f}秒")
                self.timeout_label.setStyleSheet("color: orange;")
            else:
                self.timeout_label.setText("超时: 无限制")
                self.timeout_label.setStyleSheet("color: orange;")

    def open_region_selector(self):
        self.region_win = RegionWindow()
        self.region_win.region_selected.connect(self.on_region_selected)

    def on_region_selected(self, rect_tuple):
        self.engine.scan_region = rect_tuple
        self.region_label.setText(f"范围(物理): {rect_tuple}")
        self.log_text.append(f"已锁定游戏区域(物理): {rect_tuple} (速度+++)")

    def closeEvent(self, event):
        self.settings.setValue("conf", self.conf_edit.text())
        self.settings.setValue("scale_min", self.scale_min.text())
        self.settings.setValue("scale_max", self.scale_max.text())
        self.settings.setValue("dodge_x1", self.dodge_x1.text())
        self.settings.setValue("dodge_y1", self.dodge_y1.text())
        self.settings.setValue("dodge_x2", self.dodge_x2.text())
        self.settings.setValue("dodge_y2", self.dodge_y2.text())
        self.settings.setValue("dodge_en", self.dodge_chk.isChecked())
        self.settings.setValue("dbl_dodge", self.double_dodge_chk.isChecked())
        self.settings.setValue("dbl_wait", self.dbl_wait.text())
        self.settings.setValue("move_spd", self.move_spd.text())
        self.settings.setValue("click_hld", self.click_hld.text())
        self.settings.setValue("settle", self.settle.text())
        self.settings.setValue("timeout", self.timeout.text())
        self.settings.setValue("log_file", self.log_file_chk.isChecked())
        self.settings.setValue("log_ui", self.log_ui_chk.isChecked())
        self.settings.setValue("mini", self.mini_chk.isChecked())
        self.settings.setValue("hotkey", self.hotkey_combo.currentText())
        event.accept()

    def update_log_config(self):
        GLOBAL_CONFIG["log_to_file"] = self.log_file_chk.isChecked()
        GLOBAL_CONFIG["log_to_ui"] = self.log_ui_chk.isChecked()

    def manage_auto_start(self):
        """管理开机自启动设置"""
        self.auto_start_window = AutoStartWindow()
        self.auto_start_window.show()

    def auto_load_last_template(self):
        """自动载入上一次模板"""
        try:
            # 检查是否启用自动载入
            auto_load_enabled = self.settings.value("auto_load_template", True, type=bool)
            
            if not auto_load_enabled:
                self.add_row()
                return
            
            # 检查是否需要询问用户
            ask_load_enabled = self.settings.value("ask_load_template", False, type=bool)
            
            # 获取上一次模板路径
            last_template_path = self.settings.value("last_template_path", "")
            
            if last_template_path and os.path.exists(last_template_path):
                # 如果需要询问用户
                if ask_load_enabled:
                    reply = QMessageBox.question(
                        self,
                        "自动载入模板",
                        f"是否自动载入上一次模板？\n{os.path.basename(last_template_path)}",
                        QMessageBox.Yes | QMessageBox.No
                    )
                    
                    if reply == QMessageBox.Yes:
                        self.load_template_from_path(last_template_path)
                        self.log_text.append(f"✅ 已自动载入上一次模板: {os.path.basename(last_template_path)}")
                    else:
                        self.add_row()
                else:
                    # 直接自动载入
                    self.load_template_from_path(last_template_path)
                    self.log_text.append(f"✅ 已自动载入上一次模板: {os.path.basename(last_template_path)}")
            else:
                # 没有上一次模板，添加一个空行
                self.add_row()
                
        except Exception as e:
            # 如果自动载入失败，添加一个空行并记录错误
            self.add_row()
            write_log(f"自动载入模板失败: {str(e)}")
    
    def load_template_from_path(self, template_path):
        """从指定路径载入模板"""
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # 清空当前任务列表
            self.task_list.clear()
            
            # 检查是否包含超时配置
            if isinstance(data, dict) and "tasks" in data:
                # 新格式：包含超时配置
                tasks = data["tasks"]
                # 载入任务列表
                for task_data in tasks:
                    self.add_row(task_data)
                
                # 加载超时配置
                timeout_config = data.get("timeout_config", {})
                if timeout_config:
                    # 加载重试设置
                    if "retry_count" in timeout_config:
                        self.timeout_retry_count.setText(timeout_config["retry_count"])
                    if "retry_interval" in timeout_config:
                        self.timeout_retry_interval.setText(timeout_config["retry_interval"])
                    
                    # 加载应对步骤
                    response_tasks = timeout_config.get("response_tasks", [])
                    self.response_task_list.clear()
                    for task in response_tasks:
                        item = QListWidgetItem()
                        item.setSizeHint(QSize(0, 40))
                        row_widget = TaskRow(delete_callback=self.del_response_step, data=task)
                        self.response_task_list.addItem(item)
                        self.response_task_list.setItemWidget(item, row_widget)
                    
                    # 加载超时步骤
                    timeout_tasks = timeout_config.get("timeout_tasks", [])
                    self.timeout_task_list.clear()
                    for task in timeout_tasks:
                        item = QListWidgetItem()
                        item.setSizeHint(QSize(0, 40))
                        row_widget = TaskRow(delete_callback=self.del_timeout_step, data=task)
                        self.timeout_task_list.addItem(item)
                        self.timeout_task_list.setItemWidget(item, row_widget)
                    
                    # 更新状态显示
                    template_name = os.path.basename(template_path)
                    self.log_text.append(f"✅ 模板载入成功: {template_name}")
                    self.log_text.append(f"   任务数量: {len(tasks)} 条")
                    self.log_text.append(f"   应对步骤: {len(response_tasks)} 条")
                    self.log_text.append(f"   超时步骤: {len(timeout_tasks)} 条")
            else:
                # 旧格式：仅任务列表
                tasks = data
                # 载入任务列表
                for task_data in tasks:
                    self.add_row(task_data)
                
                # 更新状态显示
                template_name = os.path.basename(template_path)
                self.log_text.append(f"✅ 模板载入成功: {template_name}")
                self.log_text.append(f"   任务数量: {len(tasks)} 条")
            
        except Exception as e:
            error_msg = f"载入模板失败: {str(e)}"
            self.log_text.append(f"❌ {error_msg}")
            QMessageBox.warning(self, "错误", error_msg)
            # 载入失败时添加一个空行
            self.add_row()
    
    def manage_templates(self):
        """管理模板设置"""
        self.template_window = TemplateManagerWindow(self)
        self.template_window.show()

    def update_cpu_info(self):
        core_str = "?"
        if HAS_KERNEL_CPU:
            try: core_str = str(GetCurrentProcessorNumber())
            except: pass
        sys_usage = "--"
        proc_usage = "--"
        if HAS_PSUTIL and self.current_process:
            try:
                sys_usage = f"{psutil.cpu_percent(interval=None):.1f}"
                raw_usage = self.current_process.cpu_percent(interval=None)
                proc_usage = f"{raw_usage:.1f}" 
            except: pass
        self.cpu_label.setText(f"逻辑核心: #{core_str} | 系统总占: {sys_usage}% | 脚本单核占: {proc_usage}%")

    def add_row(self, data=None):
        row_widget = TaskRow(delete_callback=self.del_row, data=data, index=self.task_list.count())
        item = QListWidgetItem(self.task_list)
        item.setSizeHint(row_widget.sizeHint())
        self.task_list.setItemWidget(item, row_widget)
        row_widget.set_parent_item(item)
        item.setData(Qt.UserRole, row_widget.get_data())
        self.update_row_indices()

    def restore_row_widget(self, item, data):
        row_widget = TaskRow(delete_callback=self.del_row, data=data)
        item.setSizeHint(row_widget.sizeHint())
        self.task_list.setItemWidget(item, row_widget)
        row_widget.set_parent_item(item)
        self.update_row_indices()

    def update_row_indices(self):
        """更新所有步骤的序号"""
        for i in range(self.task_list.count()):
            item = self.task_list.item(i)
            widget = self.task_list.itemWidget(item)
            if widget and hasattr(widget, 'set_index'):
                widget.set_index(i)

    def del_row(self, row_widget):
        for i in range(self.task_list.count()):
            item = self.task_list.item(i)
            if self.task_list.itemWidget(item) == row_widget:
                self.task_list.takeItem(i)
                break
        self.update_row_indices()

    def save(self):
        # 保存任务列表
        tasks = []
        for i in range(self.task_list.count()):
            item = self.task_list.item(i)
            widget = self.task_list.itemWidget(item)
            if widget: tasks.append(widget.get_data())
            else: tasks.append(item.data(Qt.UserRole))
        
        # 保存超时配置
        timeout_config = {
            "retry_count": self.timeout_retry_count.text(),
            "retry_interval": self.timeout_retry_interval.text(),
            "response_tasks": [],
            "timeout_tasks": []
        }
        
        # 保存应对步骤
        for i in range(self.response_task_list.count()):
            item = self.response_task_list.item(i)
            widget = self.response_task_list.itemWidget(item)
            if widget:
                timeout_config["response_tasks"].append(widget.get_data())
        
        # 保存超时步骤
        for i in range(self.timeout_task_list.count()):
            item = self.timeout_task_list.item(i)
            widget = self.timeout_task_list.itemWidget(item)
            if widget:
                timeout_config["timeout_tasks"].append(widget.get_data())
        
        # 组合数据
        save_data = {
            "tasks": tasks,
            "timeout_config": timeout_config
        }
        
        path, _ = QFileDialog.getSaveFileName(self, "保存", filter="JSON (*.json)")
        if path:
            with open(path, 'w', encoding='utf-8') as f: 
                json.dump(save_data, f, ensure_ascii=False, indent=2)
            
            # 记录上一次模板路径
            self.settings.setValue("last_template_path", path)
            self.log_text.append(f"✅ 模板已保存并记录: {os.path.basename(path)}")

    def load(self):
        path, _ = QFileDialog.getOpenFileName(self, "导入", filter="JSON (*.json)")
        if path:
            # 记录上一次模板路径
            self.settings.setValue("last_template_path", path)
            
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    # 检查是否包含超时配置
                    if isinstance(data, dict) and "tasks" in data:
                        # 新格式：包含超时配置
                        tasks = data["tasks"]
                        self.task_list.clear()
                        for d in tasks: self.add_row(d)
                        
                        # 加载超时配置
                        timeout_config = data.get("timeout_config", {})
                        # 即使timeout_config为空，也加载默认值
                        if "retry_count" in timeout_config:
                            self.timeout_retry_count.setText(timeout_config["retry_count"])
                        if "retry_interval" in timeout_config:
                            self.timeout_retry_interval.setText(timeout_config["retry_interval"])
                        
                        # 加载应对步骤
                        response_tasks = timeout_config.get("response_tasks", [])
                        self.response_task_list.clear()
                        for task in response_tasks:
                            item = QListWidgetItem()
                            item.setSizeHint(QSize(0, 40))
                            row_widget = TaskRow(delete_callback=self.del_response_step, data=task)
                            self.response_task_list.addItem(item)
                            self.response_task_list.setItemWidget(item, row_widget)
                        self.log_text.append(f"✅ 成功导入 {len(response_tasks)} 个应对步骤")
                        
                        # 加载超时步骤
                        timeout_tasks = timeout_config.get("timeout_tasks", [])
                        self.timeout_task_list.clear()
                        for task in timeout_tasks:
                            item = QListWidgetItem()
                            item.setSizeHint(QSize(0, 40))
                            row_widget = TaskRow(delete_callback=self.del_timeout_step, data=task)
                            self.timeout_task_list.addItem(item)
                            self.timeout_task_list.setItemWidget(item, row_widget)
                        self.log_text.append(f"✅ 成功导入 {len(timeout_tasks)} 个超时后执行步骤")
                    else:
                        # 旧格式：仅任务列表
                        tasks = data
                        self.task_list.clear()
                        for d in tasks: self.add_row(d)
                        # 旧格式不包含超时配置，保持当前设置
                        self.log_text.append("⚠️  旧格式模板，未包含超时配置")
                
                self.log_text.append(f"✅ 模板已载入并记录: {os.path.basename(path)}")
            except Exception as e:
                error_msg = f"载入模板失败: {str(e)}"
                self.log_text.append(f"❌ {error_msg}")
                QMessageBox.warning(self, "错误", error_msg)

    def start_task(self):
        tasks = []
        for i in range(self.task_list.count()):
            item = self.task_list.item(i)
            widget = self.task_list.itemWidget(item)
            if widget: tasks.append(widget.get_data())
        if not tasks: return
        try:
            self.engine.min_scale = float(self.scale_min.text())
            self.engine.max_scale = float(self.scale_max.text())
            self.engine.dodge_x1 = int(self.dodge_x1.text())
            self.engine.dodge_y1 = int(self.dodge_y1.text())
            self.engine.dodge_x2 = int(self.dodge_x2.text())
            self.engine.dodge_y2 = int(self.dodge_y2.text())
            self.engine.move_duration = float(self.move_spd.text())
            self.engine.click_hold = float(self.click_hld.text())
            self.engine.settlement_wait = float(self.settle.text())
            self.engine.timeout_val = float(self.timeout.text())
            self.engine.confidence = float(self.conf_edit.text())
            
            self.engine.enable_dodge = self.dodge_chk.isChecked()
            self.engine.enable_double_dodge = self.double_dodge_chk.isChecked()
            self.engine.double_dodge_wait = float(self.dbl_wait.text())
            
            self.engine.enable_tm_stop = self.tm_failsafe.isChecked()
            self.engine.enable_tr_stop = self.tr_failsafe.isChecked()
            self.engine.enable_key_stop = self.key_failsafe.isChecked()
        except: return QMessageBox.warning(self, "错误", "数值格式错误")

        if GLOBAL_CONFIG["log_to_ui"]:
            self.log_text.clear()
            self.log_text.append(f">>> 引擎启动({self.hotkey_combo.currentText()})...")
            self.log_text.append(f"   任务数量: {len(tasks)} 条")
            self.log_text.append(f"   循环模式: {'无限循环' if self.loop_combo.currentText() == "无限" else '单次执行'}")
            self.log_text.append(f"   检测区域: {self.engine.scan_region if self.engine.scan_region else '全屏'}")
            self.log_text.append(f"   安全设置: 按键停止={self.engine.enable_key_stop}, 鼠标停止={self.engine.enable_tr_stop}, 任务管理器检测={self.engine.enable_tm_stop}")
            
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        if self.mini_chk.isChecked(): self.showMinimized()
        
        # 记录执行开始时间
        self.execution_start_time = time.time()
        # 启动超时状态更新
        self.timeout_timer.start(1000)
        
        is_loop = self.loop_combo.currentText() == "无限"
        self.worker = WorkerThread(self.engine, tasks, is_loop, self)
        self.worker.log_signal.connect(self.log_text.append)
        self.worker.finished_signal.connect(self.on_finish)
        self.worker.start()

    def stop_task(self):
        if GLOBAL_CONFIG["log_to_ui"]:
            self.log_text.append(">>> 用户手动停止任务")
            self.log_text.append(f"   时间: {time.strftime('%H:%M:%S')}")
            self.log_text.append("   正在安全停止引擎...")
        
        self.engine.stop()
        
        # 停止超时计时器
        self.timeout_timer.stop()
        # 更新超时状态显示
        self.update_timeout_status()
        
        if GLOBAL_CONFIG["log_to_ui"]:
            self.log_text.append("   引擎已停止")
            self.log_text.append("!!! 任务已手动停止 !!!")
        
    def on_finish(self):
        # 停止超时计时器
        self.timeout_timer.stop()
        # 更新超时状态显示
        self.update_timeout_status()
        
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.showNormal()
        self.activateWindow()
        if GLOBAL_CONFIG["log_to_ui"]:
            self.log_text.append(">>> 任务执行完成")
            self.log_text.append("   状态: 正常结束")
            self.log_text.append("   窗口已恢复显示")
            self.log_text.append("   控制按钮已重置")
            self.log_text.append("=== 任务执行结束 ===")

    def open_inspector(self):
        """打开控件检测窗口"""
        self.inspector_window = InspectorWindow()
        self.inspector_window.show()

    def open_parallel_manager(self):
        """打开多任务并行管理器"""
        from parallel_manager import ParallelTaskManager
        self.parallel_window = ParallelTaskManager()
        self.parallel_window.show()

    def open_barcode_converter(self):
        """打开条码转换窗口"""
        from barcode_converter import BarcodeConverterWindow
        self.barcode_window = BarcodeConverterWindow()
        self.barcode_window.show()

    def del_response_step(self, row_widget):
        """删除应对步骤"""
        for i in range(self.response_task_list.count()):
            item = self.response_task_list.item(i)
            if self.response_task_list.itemWidget(item) == row_widget:
                self.response_task_list.takeItem(i)
                break

    def add_response_step(self):
        """添加应对步骤"""
        # 创建一个默认的应对步骤
        default_task = {"type": 5.0, "value": "2"}  # 默认等待2秒
        item = QListWidgetItem()
        item.setSizeHint(QSize(0, 40))
        
        row_widget = TaskRow(delete_callback=self.del_response_step, data=default_task)
        self.response_task_list.addItem(item)
        self.response_task_list.setItemWidget(item, row_widget)

    def del_timeout_step(self, row_widget):
        """删除超时后执行步骤"""
        for i in range(self.timeout_task_list.count()):
            item = self.timeout_task_list.item(i)
            if self.timeout_task_list.itemWidget(item) == row_widget:
                self.timeout_task_list.takeItem(i)
                break

    def add_timeout_step(self):
        """添加超时后执行步骤"""
        # 创建一个默认的超时步骤
        default_task = {"type": 5.0, "value": "2"}  # 默认等待2秒
        item = QListWidgetItem()
        item.setSizeHint(QSize(0, 40))
        
        row_widget = TaskRow(delete_callback=self.del_timeout_step, data=default_task)
        self.timeout_task_list.addItem(item)
        self.timeout_task_list.setItemWidget(item, row_widget)

    def save_timeout_config(self):
        """保存超时配置"""
        # 保存重试设置
        self.settings.setValue("timeout_retry_count", self.timeout_retry_count.text())
        self.settings.setValue("timeout_retry_interval", self.timeout_retry_interval.text())
        
        # 保存应对步骤
        response_tasks = []
        for i in range(self.response_task_list.count()):
            item = self.response_task_list.item(i)
            widget = self.response_task_list.itemWidget(item)
            if widget:
                response_tasks.append(widget.get_data())
        
        self.settings.setValue("response_tasks", json.dumps(response_tasks))
        
        # 保存超时步骤
        timeout_tasks = []
        for i in range(self.timeout_task_list.count()):
            item = self.timeout_task_list.item(i)
            widget = self.timeout_task_list.itemWidget(item)
            if widget:
                timeout_tasks.append(widget.get_data())
        
        self.settings.setValue("timeout_tasks", json.dumps(timeout_tasks))
        
        QMessageBox.information(self, "成功", "超时配置已保存")

    def load_timeout_config(self):
        """加载超时配置"""
        # 加载重试设置
        self.timeout_retry_count.setText(self.settings.value("timeout_retry_count", "1"))
        self.timeout_retry_interval.setText(self.settings.value("timeout_retry_interval", "5"))
        
        # 加载应对步骤
        try:
            response_tasks_json = self.settings.value("response_tasks", "[]")
            response_tasks = json.loads(response_tasks_json)
            
            self.response_task_list.clear()
            for task in response_tasks:
                item = QListWidgetItem()
                item.setSizeHint(QSize(0, 40))
                row_widget = TaskRow(delete_callback=self.del_response_step, data=task)
                self.response_task_list.addItem(item)
                self.response_task_list.setItemWidget(item, row_widget)
        except:
            pass
        
        # 加载超时步骤
        try:
            timeout_tasks_json = self.settings.value("timeout_tasks", "[]")
            timeout_tasks = json.loads(timeout_tasks_json)
            
            self.timeout_task_list.clear()
            for task in timeout_tasks:
                item = QListWidgetItem()
                item.setSizeHint(QSize(0, 40))
                row_widget = TaskRow(delete_callback=self.del_timeout_step, data=task)
                self.timeout_task_list.addItem(item)
                self.timeout_task_list.setItemWidget(item, row_widget)
        except:
            pass

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 检查是否由自启动启动
    is_auto_start = check_auto_start()
    
    win = RPAWindow()
    
    # 如果由自启动启动，可以设置最小化启动等行为
    if is_auto_start:
        win.showMinimized()
        # 可以添加自动开始任务等逻辑
    else:
        win.show()
    
    sys.exit(app.exec())