import sys
import os
import winreg
import time

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QPushButton, QTextEdit, QMessageBox, QGroupBox)
from PySide6.QtCore import Qt, QSettings


class AutoStartWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("开机自启动设置")
        self.resize(400, 300)
        self.setWindowFlags(Qt.WindowStaysOnTopHint)
        
        layout = QVBoxLayout()
        
        title_label = QLabel("开机自启动设置")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        layout.addWidget(title_label)
        
        desc_label = QLabel("设置WaterRPA工具在系统启动时自动运行")
        desc_label.setStyleSheet("color: gray; margin: 5px;")
        layout.addWidget(desc_label)
        
        layout.addSpacing(20)
        
        self.status_label = QLabel()
        self.status_label.setStyleSheet("font-size: 14px; margin: 10px;")
        layout.addWidget(self.status_label)
        
        btn_layout = QHBoxLayout()
        
        self.enable_btn = QPushButton("✅ 启用自启动")
        self.enable_btn.clicked.connect(self.enable_auto_start)
        self.enable_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        btn_layout.addWidget(self.enable_btn)
        
        self.disable_btn = QPushButton("❌ 禁用自启动")
        self.disable_btn.clicked.connect(self.disable_auto_start)
        self.disable_btn.setStyleSheet("background-color: #f44336; color: white; font-weight: bold;")
        btn_layout.addWidget(self.disable_btn)
        
        layout.addLayout(btn_layout)
        
        layout.addSpacing(20)
        
        info_group = QGroupBox("自启动信息")
        info_layout = QVBoxLayout()
        
        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setMaximumHeight(100)
        info_layout.addWidget(self.info_text)
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)
        
        self.setLayout(layout)
        
        self.update_status()
    
    def get_auto_start_registry_path(self):
        return r"Software\Microsoft\Windows\CurrentVersion\Run"
    
    def get_auto_start_key_name(self):
        return "WaterRPA"
    
    def get_executable_path(self):
        if getattr(sys, 'frozen', False):
            return sys.executable
        else:
            script_path = os.path.abspath(__file__)
            python_exe = sys.executable
            return f'"{python_exe}" "{script_path}"'
    
    def is_auto_start_enabled(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.get_auto_start_registry_path())
            try:
                value, _ = winreg.QueryValueEx(key, self.get_auto_start_key_name())
                return True
            except FileNotFoundError:
                return False
            finally:
                winreg.CloseKey(key)
        except Exception as e:
            self.info_text.append(f"检查自启动状态失败: {str(e)}")
            return False
    
    def enable_auto_start(self):
        try:
            reg_path = self.get_auto_start_registry_path()
            key_name = self.get_auto_start_key_name()
            exe_path = self.get_executable_path()
            
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, key_name, 0, winreg.REG_SZ, exe_path)
            winreg.CloseKey(key)
            
            self.info_text.append("✅ 已启用开机自启动")
            self.info_text.append(f"   程序路径: {exe_path}")
            self.update_status()
            
            QMessageBox.information(self, "成功", "开机自启动已启用！\nWaterRPA将在下次系统启动时自动运行。")
            
        except Exception as e:
            error_msg = f"启用自启动失败: {str(e)}"
            self.info_text.append(error_msg)
            QMessageBox.warning(self, "错误", error_msg)
    
    def disable_auto_start(self):
        try:
            reg_path = self.get_auto_start_registry_path()
            key_name = self.get_auto_start_key_name()
            
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_SET_VALUE)
            
            try:
                winreg.DeleteValue(key, key_name)
                self.info_text.append("✅ 已禁用开机自启动")
                QMessageBox.information(self, "成功", "开机自启动已禁用！")
            except FileNotFoundError:
                self.info_text.append("⚠️ 自启动设置不存在")
                QMessageBox.information(self, "提示", "自启动设置不存在")
            
            winreg.CloseKey(key)
            self.update_status()
            
        except Exception as e:
            error_msg = f"禁用自启动失败: {str(e)}"
            self.info_text.append(error_msg)
            QMessageBox.warning(self, "错误", error_msg)
    
    def update_status(self):
        if self.is_auto_start_enabled():
            self.status_label.setText("当前状态: ✅ 已启用开机自启动")
            self.status_label.setStyleSheet("color: green; font-size: 14px; margin: 10px;")
            self.enable_btn.setEnabled(False)
            self.disable_btn.setEnabled(True)
        else:
            self.status_label.setText("当前状态: ❌ 未启用开机自启动")
            self.status_label.setStyleSheet("color: red; font-size: 14px; margin: 10px;")
            self.enable_btn.setEnabled(True)
            self.disable_btn.setEnabled(False)
        
        self.info_text.clear()
        self.info_text.append("自启动详细信息:")
        self.info_text.append(f"注册表路径: HKEY_CURRENT_USER\\{self.get_auto_start_registry_path()}")
        self.info_text.append(f"键名: {self.get_auto_start_key_name()}")
        self.info_text.append(f"程序路径: {self.get_executable_path()}")
        
        if self.is_auto_start_enabled():
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.get_auto_start_registry_path())
                value, _ = winreg.QueryValueEx(key, self.get_auto_start_key_name())
                self.info_text.append(f"当前值: {value}")
                winreg.CloseKey(key)
            except:
                pass


def check_auto_start():
    try:
        if any("autostart" in arg.lower() for arg in sys.argv):
            return True
        return False
    except:
        return False