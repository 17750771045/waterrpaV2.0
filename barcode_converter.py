# -*- coding: utf-8 -*-
"""
条码转换窗口
功能：将扫码枪输入的条码按规则转换为目标格式
"""
import sys
import csv
import os
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QTextEdit, QGroupBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont

HISTORY_FILE = "barcode_history.csv"

def transform_barcode(input_code):
    if not input_code:
        return None
    
    input_code = str(input_code).strip()
    
    if len(input_code) != 12:
        QMessageBox.warning(None, "输入错误", "输入条码长度错误，应为12位")
        return None
    
    suffix = input_code[-5:]
    
    prefix_replacement = {
        '5518000': 'VA1MG2K22511',
    }
    
    prefix_original = input_code[:7] if len(input_code) >= 7 else input_code
    
    if prefix_original in prefix_replacement:
        new_prefix = prefix_replacement[prefix_original]
    else:
        new_prefix = prefix_original
    
    result = new_prefix + suffix
    
    return result


def load_history():
    history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader)
                for row in reader:
                    if len(row) >= 3:
                        history.append((row[0], row[1], row[2]))
        except Exception as e:
            pass
    return history


def save_history(history):
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["原始条码", "转换结果", "时间"])
            for item in history:
                writer.writerow(item)
    except Exception as e:
        pass


class BarcodeConverterWindow(QWidget):
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("📷 条码转换工具")
        self.resize(600, 500)
        self.init_ui()
        self.history = load_history()
        self.update_history_table()
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        input_group = QGroupBox("扫码输入")
        input_layout = QVBoxLayout(input_group)
        
        input_hint = QLabel("请使用扫码枪扫描条码，或手动输入后按回车：")
        input_hint.setStyleSheet("color: #666;")
        input_layout.addWidget(input_hint)
        
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("扫描条码或输入条码...")
        self.input_edit.setStyleSheet("padding: 8px; font-size: 14px;")
        self.input_edit.returnPressed.connect(self.on_input_complete)
        input_layout.addWidget(self.input_edit)
        
        btn_layout = QHBoxLayout()
        self.convert_btn = QPushButton("🔄 转换")
        self.convert_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                padding: 10px 20px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        self.convert_btn.clicked.connect(self.on_convert)
        btn_layout.addWidget(self.convert_btn)
        
        self.clear_btn = QPushButton("🗑️ 清空")
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #757575;
                color: white;
                padding: 10px 20px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #616161;
            }
        """)
        self.clear_btn.clicked.connect(self.on_clear)
        btn_layout.addWidget(self.clear_btn)
        
        btn_layout.addStretch()
        input_layout.addLayout(btn_layout)
        layout.addWidget(input_group)
        
        output_group = QGroupBox("转换结果")
        output_layout = QVBoxLayout(output_group)
        
        self.result_edit = QLineEdit()
        self.result_edit.setReadOnly(True)
        self.result_edit.setStyleSheet("padding: 8px; font-size: 14px; font-weight: bold; color: #4CAF50;")
        output_layout.addWidget(self.result_edit)
        
        self.copy_btn = QPushButton("📋 复制结果")
        self.copy_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #388E3C;
            }
        """)
        self.copy_btn.clicked.connect(self.on_copy)
        output_layout.addWidget(self.copy_btn)
        layout.addWidget(output_group)
        
        history_group = QGroupBox("转换历史")
        history_layout = QVBoxLayout(history_group)
        
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(3)
        self.history_table.setHorizontalHeaderLabels(["原始条码", "转换结果", "时间"])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.history_table.setStyleSheet("""
            QTableWidget {
                background-color: white;
                gridline-color: #e0e0e0;
            }
            QHeaderView::section {
                background-color: #f5f5f5;
                padding: 8px;
                font-weight: bold;
                border: none;
                border-bottom: 2px solid #ddd;
            }
        """)
        history_layout.addWidget(self.history_table)
        
        self.clear_history_btn = QPushButton("🗑️ 清空历史")
        self.clear_history_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
        """)
        self.clear_history_btn.clicked.connect(self.on_clear_history)
        history_layout.addWidget(self.clear_history_btn)
        layout.addWidget(history_group)
        
        QTimer.singleShot(100, self.input_edit.setFocus)
    
    def on_input_complete(self):
        self.on_convert()
    
    def on_convert(self):
        input_code = self.input_edit.text().strip()
        if not input_code:
            return
        
        result = transform_barcode(input_code)
        if result:
            self.result_edit.setText(result)
            self.copy_btn.setStyleSheet("""
                QPushButton {
                    background-color: #2196F3;
                    color: white;
                    padding: 8px 16px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #1976D2;
                }
            """)
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.add_to_history(input_code, result, timestamp)
            
            self.input_edit.clear()
            self.input_edit.setFocus()
    
    def on_copy(self):
        from PySide6.QtWidgets import QApplication
        result = self.result_edit.text()
        if result:
            clipboard = QApplication.clipboard()
            clipboard.setText(result)
            self.copy_btn.setText("✅ 已复制!")
            
            self.copy_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    padding: 8px 16px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #388E3C;
                }
            """)
            
            QTimer.singleShot(1500, lambda: self.copy_btn.setText("📋 复制结果"))
    
    def on_clear(self):
        self.input_edit.clear()
        self.result_edit.clear()
        self.input_edit.setFocus()
    
    def on_clear_history(self):
        self.history_table.setRowCount(0)
        self.history = []
        # 注意：不调用 save_history()，保持CSV文件内容不变
    
    def add_to_history(self, original, result, timestamp):
        self.history.insert(0, (original, result, timestamp))
        
        if len(self.history) > 100:
            self.history = self.history[:100]
        
        self.update_history_table()
        save_history(self.history)
    
    def update_history_table(self):
        self.history_table.setRowCount(len(self.history))
        for i, (orig, res, ts) in enumerate(self.history):
            self.history_table.setItem(i, 0, QTableWidgetItem(orig))
            self.history_table.setItem(i, 1, QTableWidgetItem(res))
            self.history_table.setItem(i, 2, QTableWidgetItem(ts))
    
    def set_input_code(self, code):
        self.input_edit.setText(code)
        self.on_convert()
