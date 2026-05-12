"""
控件检测模块
负责处理控件检测相关的功能，包括窗口控件获取、控件操作和操作记录
"""

import os
import time
import pyautogui
import pyperclip
import win32gui
import win32con
import win32process

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, 
    QListWidget, QListWidgetItem, QMessageBox, QInputDialog, QGroupBox, QLabel
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QPen, QBrush, QColor


class HighlightWindow(QWidget):
    """控件高亮窗口"""
    def __init__(self, rect):
        super().__init__()
        self.rect = rect
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)
        
        # 设置窗口位置和大小
        self.setGeometry(rect[0], rect[1], rect[2], rect[3])
    
    def paintEvent(self, event):
        """绘制高亮边框"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 绘制红色边框
        pen = QPen(QColor(255, 0, 0), 3)
        painter.setPen(pen)
        painter.drawRect(1, 1, self.width()-2, self.height()-2)
        
        # 绘制半透明背景
        brush = QBrush(QColor(255, 0, 0, 30))
        painter.setBrush(brush)
        painter.drawRect(0, 0, self.width(), self.height())


class InspectorWindow(QWidget):
    """控件检测器窗口"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("控件检测器")
        self.resize(600, 500)
        self.setWindowFlags(Qt.WindowStaysOnTopHint)
        
        layout = QVBoxLayout()
        
        # 顶部工具栏
        toolbar = QHBoxLayout()
        
        # 选择窗口按钮
        self.select_window_btn = QPushButton("👆 选择窗口")
        self.select_window_btn.clicked.connect(self.select_target_window)
        toolbar.addWidget(self.select_window_btn)
        
        self.refresh_btn = QPushButton("🔄 刷新")
        self.refresh_btn.clicked.connect(self.refresh_controls)
        toolbar.addWidget(self.refresh_btn)
        
        self.copy_btn = QPushButton("📋 复制信息")
        self.copy_btn.clicked.connect(self.copy_control_info)
        toolbar.addWidget(self.copy_btn)
        
        self.highlight_btn = QPushButton("🔦 高亮控件")
        self.highlight_btn.clicked.connect(self.highlight_control)
        toolbar.addWidget(self.highlight_btn)
        
        # 控件操作按钮
        self.click_btn = QPushButton("🖱️ 点击控件")
        self.click_btn.clicked.connect(self.click_control)
        toolbar.addWidget(self.click_btn)
        
        self.double_click_btn = QPushButton("🖱️🖱️ 双击控件")
        self.double_click_btn.clicked.connect(self.double_click_control)
        toolbar.addWidget(self.double_click_btn)
        
        self.right_click_btn = QPushButton("🖱️🔘 右键点击")
        self.right_click_btn.clicked.connect(self.right_click_control)
        toolbar.addWidget(self.right_click_btn)
        
        # 文本操作按钮
        self.input_text_btn = QPushButton("📝 输入文本")
        self.input_text_btn.clicked.connect(self.input_text_to_control)
        toolbar.addWidget(self.input_text_btn)
        
        self.get_text_btn = QPushButton("📖 获取文本")
        self.get_text_btn.clicked.connect(self.get_control_text)
        toolbar.addWidget(self.get_text_btn)
        
        self.clear_text_btn = QPushButton("🧹 清空文本")
        self.clear_text_btn.clicked.connect(self.clear_control_text)
        toolbar.addWidget(self.clear_text_btn)
        
        # 状态操作按钮
        self.enable_btn = QPushButton("✅ 启用控件")
        self.enable_btn.clicked.connect(self.enable_control)
        toolbar.addWidget(self.enable_btn)
        
        self.disable_btn = QPushButton("❌ 禁用控件")
        self.disable_btn.clicked.connect(self.disable_control)
        toolbar.addWidget(self.disable_btn)
        
        self.focus_btn = QPushButton("🎯 聚焦控件")
        self.focus_btn.clicked.connect(self.focus_control)
        toolbar.addWidget(self.focus_btn)
        
        # 自动化按钮
        self.record_btn = QPushButton("⏺️ 记录操作")
        self.record_btn.clicked.connect(self.toggle_recording)
        self.record_btn.setCheckable(True)
        toolbar.addWidget(self.record_btn)
        
        self.play_btn = QPushButton("▶️ 播放操作")
        self.play_btn.clicked.connect(self.play_recorded_actions)
        toolbar.addWidget(self.play_btn)
        
        toolbar.addStretch()
        layout.addLayout(toolbar)
        
        # 控件信息显示
        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        layout.addWidget(self.info_text)
        
        # 控件列表
        self.control_list = QListWidget()
        self.control_list.itemClicked.connect(self.on_control_selected)
        layout.addWidget(self.control_list)
        
        self.setLayout(layout)
        
        # 目标窗口句柄（手动选择后保存）
        self.target_hwnd = None
        
        # 初始化时刷新一次
        self.refresh_controls()
    
    def select_target_window(self):
        """手动选择目标窗口"""
        self.info_text.setText("请在3秒内点击目标窗口...")
        self.control_list.clear()
        
        # 3秒后获取鼠标位置下的窗口
        QTimer.singleShot(3000, self.capture_target_window)
    
    def capture_target_window(self):
        """捕获目标窗口"""
        try:
            # 获取鼠标位置
            x, y = pyautogui.position()
            
            # 获取鼠标位置下的窗口句柄
            hwnd = win32gui.WindowFromPoint((x, y))
            
            # 获取顶层窗口
            parent_hwnd = win32gui.GetAncestor(hwnd, win32con.GA_ROOT)
            
            # 检查是否是自身窗口
            if self.is_self_window(parent_hwnd):
                self.info_text.setText("检测到控件检测器窗口，请重新选择其他窗口")
                return
            
            # 保存目标窗口句柄
            self.target_hwnd = parent_hwnd
            
            # 刷新控件列表
            self.refresh_controls()
            
            # 显示选择成功信息
            window_info = self.get_window_info(parent_hwnd)
            if window_info:
                self.info_text.append(f"✅ 已选择窗口: {window_info['title']}")
        except Exception as e:
            self.info_text.setText(f"选择窗口失败: {str(e)}")
    
    def get_window_controls(self, hwnd):
        """获取窗口的所有控件信息"""
        controls = []
        
        def enum_child_windows(hwnd, lparam):
            try:
                # 获取控件类名
                class_name = win32gui.GetClassName(hwnd)
                
                # 获取控件文本
                text = win32gui.GetWindowText(hwnd)
                
                # 获取控件位置和大小
                rect = win32gui.GetWindowRect(hwnd)
                x, y, w, h = rect[0], rect[1], rect[2]-rect[0], rect[3]-rect[1]
                
                # 获取控件ID
                ctrl_id = win32gui.GetDlgCtrlID(hwnd)
                
                # 获取控件样式
                style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
                
                controls.append({
                    'hwnd': hwnd,
                    'class_name': class_name,
                    'text': text,
                    'rect': (x, y, w, h),
                    'ctrl_id': ctrl_id,
                    'style': style
                })
            except Exception as e:
                pass
            return True
        
        try:
            win32gui.EnumChildWindows(hwnd, enum_child_windows, None)
        except:
            pass
        
        return controls
    
    def get_window_info(self, hwnd):
        """获取窗口信息"""
        try:
            # 获取窗口标题
            title = win32gui.GetWindowText(hwnd)
            
            # 获取窗口类名
            class_name = win32gui.GetClassName(hwnd)
            
            # 获取窗口位置和大小
            rect = win32gui.GetWindowRect(hwnd)
            x, y, w, h = rect[0], rect[1], rect[2]-rect[0], rect[3]-rect[1]
            
            # 获取进程ID和进程名
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            try:
                process = psutil.Process(pid)
                process_name = process.name()
            except:
                process_name = "未知"
            
            return {
                'hwnd': hwnd,
                'title': title,
                'class_name': class_name,
                'rect': (x, y, w, h),
                'pid': pid,
                'process_name': process_name
            }
        except:
            return None
    
    def refresh_controls(self):
        """刷新控件列表"""
        try:
            # 如果已选择目标窗口，使用目标窗口；否则获取鼠标位置下的窗口
            if self.target_hwnd:
                parent_hwnd = self.target_hwnd
            else:
                # 获取鼠标位置
                x, y = pyautogui.position()
                
                # 获取鼠标位置下的窗口句柄
                hwnd = win32gui.WindowFromPoint((x, y))
                
                # 获取顶层窗口
                parent_hwnd = win32gui.GetAncestor(hwnd, win32con.GA_ROOT)
                
                # 检查是否是自身窗口（控件检测器窗口）
                if self.is_self_window(parent_hwnd):
                    self.info_text.setText("检测到控件检测器窗口，请先选择目标窗口或将鼠标移动到其他窗口")
                    self.control_list.clear()
                    return
            
            # 获取窗口信息
            window_info = self.get_window_info(parent_hwnd)
            
            if window_info:
                # 获取所有控件（过滤掉自身窗口的控件）
                controls = self.get_window_controls(parent_hwnd)
                
                # 过滤掉控件检测器窗口的控件
                filtered_controls = self.filter_self_controls(controls)
                
                # 更新控件列表
                self.control_list.clear()
                for ctrl in filtered_controls:
                    item_text = f"{ctrl['class_name']} - {ctrl['text']}"
                    item = QListWidgetItem(item_text)
                    item.setData(Qt.UserRole, ctrl)
                    self.control_list.addItem(item)
                
                # 显示窗口信息
                info = f"""窗口信息:
标题: {window_info['title']}
类名: {window_info['class_name']}
位置: ({window_info['rect'][0]}, {window_info['rect'][1]})
大小: {window_info['rect'][2]}x{window_info['rect'][3]}
进程: {window_info['process_name']} (PID: {window_info['pid']})
句柄: 0x{window_info['hwnd']:X}

找到 {len(filtered_controls)} 个控件 (已过滤自身窗口控件)
"""
                self.info_text.setText(info)
            else:
                self.info_text.setText("未检测到有效窗口")
                self.control_list.clear()
                
        except Exception as e:
            self.info_text.setText(f"检测错误: {str(e)}")
    
    def is_self_window(self, hwnd):
        """检查窗口是否是控件检测器窗口"""
        try:
            # 获取当前进程ID
            current_pid = os.getpid()
            
            # 获取窗口的进程ID
            _, window_pid = win32process.GetWindowThreadProcessId(hwnd)
            
            # 如果窗口属于当前进程，则认为是自身窗口
            if window_pid == current_pid:
                return True
            
            # 检查窗口标题是否包含控件检测器相关文本
            window_title = win32gui.GetWindowText(hwnd)
            if "控件检测器" in window_title or "Inspector" in window_title:
                return True
            
            # 检查窗口类名
            class_name = win32gui.GetClassName(hwnd)
            if "QWidget" in class_name and "控件检测器" in window_title:
                return True
                
            return False
        except:
            return False
    
    def filter_self_controls(self, controls):
        """过滤掉属于控件检测器窗口的控件"""
        try:
            # 获取当前进程ID
            current_pid = os.getpid()
            
            filtered_controls = []
            for ctrl in controls:
                try:
                    # 获取控件所属窗口的进程ID
                    _, ctrl_pid = win32process.GetWindowThreadProcessId(ctrl['hwnd'])
                    
                    # 如果控件不属于当前进程，则保留
                    if ctrl_pid != current_pid:
                        filtered_controls.append(ctrl)
                except:
                    # 如果获取进程ID失败，也保留该控件
                    filtered_controls.append(ctrl)
            
            return filtered_controls
        except:
            return controls
    
    def on_control_selected(self, item):
        """控件被选中时的处理"""
        control_info = item.data(Qt.UserRole)
        if control_info:
            info = f"""控件详细信息:
类名: {control_info['class_name']}
文本: {control_info['text']}
位置: ({control_info['rect'][0]}, {control_info['rect'][1]})
大小: {control_info['rect'][2]}x{control_info['rect'][3]}
控件ID: {control_info['ctrl_id']}
句柄: 0x{control_info['hwnd']:X}
样式: 0x{control_info['style']:X}
"""
            self.info_text.setText(info)
    
    def copy_control_info(self):
        """复制控件信息到剪贴板"""
        current_item = self.control_list.currentItem()
        if current_item:
            control_info = current_item.data(Qt.UserRole)
            if control_info:
                info_str = f"""控件信息:
类名: {control_info['class_name']}
文本: {control_info['text']}
位置: ({control_info['rect'][0]}, {control_info['rect'][1]})
大小: {control_info['rect'][2]}x{control_info['rect'][3]}
控件ID: {control_info['ctrl_id']}
句柄: 0x{control_info['hwnd']:X}
"""
                pyperclip.copy(info_str)
                QMessageBox.information(self, "成功", "控件信息已复制到剪贴板")
        else:
            QMessageBox.warning(self, "警告", "请先选择一个控件")
    
    def highlight_control(self):
        """高亮显示选中的控件"""
        current_item = self.control_list.currentItem()
        if current_item:
            control_info = current_item.data(Qt.UserRole)
            if control_info:
                # 创建高亮窗口
                self.highlight_window = HighlightWindow(control_info['rect'])
                self.highlight_window.show()
                
                # 3秒后自动关闭高亮
                QTimer.singleShot(3000, self.highlight_window.close)
        else:
            QMessageBox.warning(self, "警告", "请先选择一个控件")
    
    def get_selected_control(self):
        """获取当前选中的控件信息"""
        current_item = self.control_list.currentItem()
        if current_item:
            return current_item.data(Qt.UserRole)
        return None
    
    def click_control(self):
        """点击控件"""
        control_info = self.get_selected_control()
        if control_info:
            try:
                # 获取控件中心位置
                rect = control_info['rect']
                center_x = rect[0] + rect[2] // 2
                center_y = rect[1] + rect[3] // 2
                
                # 点击控件
                pyautogui.click(center_x, center_y)
                self.info_text.append(f"✅ 已点击控件: {control_info['class_name']}")
                
                # 记录操作
                self.record_action('click', control_info)
            except Exception as e:
                QMessageBox.warning(self, "错误", f"点击控件失败: {str(e)}")
        else:
            QMessageBox.warning(self, "警告", "请先选择一个控件")
    
    def double_click_control(self):
        """双击控件"""
        control_info = self.get_selected_control()
        if control_info:
            try:
                # 获取控件中心位置
                rect = control_info['rect']
                center_x = rect[0] + rect[2] // 2
                center_y = rect[1] + rect[3] // 2
                
                # 双击控件
                pyautogui.doubleClick(center_x, center_y)
                self.info_text.append(f"✅ 已双击控件: {control_info['class_name']}")
                
                # 记录操作
                self.record_action('double_click', control_info)
            except Exception as e:
                QMessageBox.warning(self, "错误", f"双击控件失败: {str(e)}")
        else:
            QMessageBox.warning(self, "警告", "请先选择一个控件")
    
    def right_click_control(self):
        """右键点击控件"""
        control_info = self.get_selected_control()
        if control_info:
            try:
                # 获取控件中心位置
                rect = control_info['rect']
                center_x = rect[0] + rect[2] // 2
                center_y = rect[1] + rect[3] // 2
                
                # 右键点击
                pyautogui.rightClick(center_x, center_y)
                self.info_text.append(f"✅ 已右键点击控件: {control_info['class_name']}")
                
                # 记录操作
                self.record_action('right_click', control_info)
            except Exception as e:
                QMessageBox.warning(self, "错误", f"右键点击失败: {str(e)}")
        else:
            QMessageBox.warning(self, "警告", "请先选择一个控件")
    
    def input_text_to_control(self):
        """向控件输入文本"""
        control_info = self.get_selected_control()
        if control_info:
            try:
                # 获取输入文本
                text, ok = QInputDialog.getText(self, "输入文本", "请输入要输入的文本:")
                if ok and text:
                    # 先点击控件获取焦点
                    rect = control_info['rect']
                    center_x = rect[0] + rect[2] // 2
                    center_y = rect[1] + rect[3] // 2
                    pyautogui.click(center_x, center_y)
                    time.sleep(0.1)
                    
                    # 输入文本
                    pyautogui.write(text)
                    self.info_text.append(f"✅ 已输入文本到控件: {text}")
                    
                    # 记录操作
                    self.record_action('input', control_info, text=text)
            except Exception as e:
                QMessageBox.warning(self, "错误", f"输入文本失败: {str(e)}")
        else:
            QMessageBox.warning(self, "警告", "请先选择一个控件")
    
    def get_control_text(self):
        """获取控件文本"""
        control_info = self.get_selected_control()
        if control_info:
            try:
                # 使用Windows API获取控件文本
                text = win32gui.GetWindowText(control_info['hwnd'])
                QMessageBox.information(self, "控件文本", f"控件文本内容:\n{text}")
                self.info_text.append(f"📖 控件文本: {text}")
            except Exception as e:
                QMessageBox.warning(self, "错误", f"获取文本失败: {str(e)}")
        else:
            QMessageBox.warning(self, "警告", "请先选择一个控件")
    
    def clear_control_text(self):
        """清空控件文本"""
        control_info = self.get_selected_control()
        if control_info:
            try:
                # 先点击控件获取焦点
                rect = control_info['rect']
                center_x = rect[0] + rect[2] // 2
                center_y = rect[1] + rect[3] // 2
                pyautogui.click(center_x, center_y)
                time.sleep(0.1)
                
                # 全选并删除
                pyautogui.hotkey('ctrl', 'a')
                time.sleep(0.1)
                pyautogui.press('delete')
                
                self.info_text.append(f"✅ 已清空控件文本")
            except Exception as e:
                QMessageBox.warning(self, "错误", f"清空文本失败: {str(e)}")
        else:
            QMessageBox.warning(self, "警告", "请先选择一个控件")
    
    def enable_control(self):
        """启用控件"""
        control_info = self.get_selected_control()
        if control_info:
            try:
                # 启用控件
                win32gui.EnableWindow(control_info['hwnd'], True)
                self.info_text.append(f"✅ 已启用控件: {control_info['class_name']}")
            except Exception as e:
                QMessageBox.warning(self, "错误", f"启用控件失败: {str(e)}")
        else:
            QMessageBox.warning(self, "警告", "请先选择一个控件")
    
    def disable_control(self):
        """禁用控件"""
        control_info = self.get_selected_control()
        if control_info:
            try:
                # 禁用控件
                win32gui.EnableWindow(control_info['hwnd'], False)
                self.info_text.append(f"✅ 已禁用控件: {control_info['class_name']}")
            except Exception as e:
                QMessageBox.warning(self, "错误", f"禁用控件失败: {str(e)}")
        else:
            QMessageBox.warning(self, "警告", "请先选择一个控件")
    
    def focus_control(self):
        """聚焦控件"""
        control_info = self.get_selected_control()
        if control_info:
            try:
                # 聚焦控件
                win32gui.SetFocus(control_info['hwnd'])
                self.info_text.append(f"✅ 已聚焦控件: {control_info['class_name']}")
            except Exception as e:
                QMessageBox.warning(self, "错误", f"聚焦控件失败: {str(e)}")
        else:
            QMessageBox.warning(self, "警告", "请先选择一个控件")
    
    def toggle_recording(self):
        """切换操作记录状态"""
        if not hasattr(self, 'recording_actions'):
            self.recording_actions = []
            self.recording_start_time = time.time()
        
        if self.record_btn.isChecked():
            # 开始记录
            self.recording_actions = []
            self.recording_start_time = time.time()
            self.record_btn.setText("⏹️ 停止记录")
            self.info_text.append("⏺️ 开始记录操作...")
        else:
            # 停止记录
            self.record_btn.setText("⏺️ 记录操作")
            duration = time.time() - self.recording_start_time
            self.info_text.append(f"⏹️ 停止记录，共记录 {len(self.recording_actions)} 个操作，耗时 {duration:.1f} 秒")
    
    def play_recorded_actions(self):
        """播放记录的操作"""
        if not hasattr(self, 'recording_actions') or not self.recording_actions:
            QMessageBox.warning(self, "警告", "没有记录的操作可以播放")
            return
        
        try:
            self.info_text.append("▶️ 开始播放记录的操作...")
            
            for i, action in enumerate(self.recording_actions):
                action_type = action.get('type', '')
                control_info = action.get('control', {})
                
                if action_type == 'click':
                    rect = control_info.get('rect', (0, 0, 0, 0))
                    center_x = rect[0] + rect[2] // 2
                    center_y = rect[1] + rect[3] // 2
                    pyautogui.click(center_x, center_y)
                    self.info_text.append(f"   {i+1}. 点击: {control_info.get('class_name', '')}")
                
                elif action_type == 'input':
                    text = action.get('text', '')
                    rect = control_info.get('rect', (0, 0, 0, 0))
                    center_x = rect[0] + rect[2] // 2
                    center_y = rect[1] + rect[3] // 2
                    pyautogui.click(center_x, center_y)
                    time.sleep(0.1)
                    pyautogui.write(text)
                    self.info_text.append(f"   {i+1}. 输入: {text}")
                
                time.sleep(0.5)  # 操作间隔
            
            self.info_text.append("✅ 操作播放完成")
            
        except Exception as e:
            QMessageBox.warning(self, "错误", f"播放操作失败: {str(e)}")
    
    def record_action(self, action_type, control_info, **kwargs):
        """记录操作（供其他方法调用）"""
        if hasattr(self, 'recording_actions') and self.record_btn.isChecked():
            action = {
                'type': action_type,
                'control': control_info,
                'timestamp': time.time() - self.recording_start_time
            }
            action.update(kwargs)
            self.recording_actions.append(action)


def create_inspector_window():
    """创建控件检测窗口"""
    return InspectorWindow()