import os
import time
import json

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QPushButton, QTextEdit, QMessageBox, QGroupBox,
                               QListWidget, QListWidgetItem, QScrollArea, QCheckBox,
                               QLineEdit, QSplitter, QMenu)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


class TemplateManagerWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("📋 模板管理")
        self.resize(800, 600)
        self.setWindowFlags(Qt.Window | Qt.WindowTitleHint | Qt.WindowCloseButtonHint | Qt.WindowMinimizeButtonHint)
        
        self._drag_pos = None
        self._setup_styles()
        self._setup_ui()
        self.update_last_template_info()
        self.refresh_recent_list()
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
    
    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self._drag_pos)
            event.accept()
    
    def mouseReleaseEvent(self, event):
        self._drag_pos = None
    
    def _setup_styles(self):
        self.style_sheet = """
            QWidget {
                font-family: 'Microsoft YaHei', sans-serif;
                background-color: #ffffff;
            }
            
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                color: #2c3e50;
                border: 2px solid #ecf0f1;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
                background-color: #ffffff;
            }
            
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px 0 8px;
                color: #3498db;
            }
            
            QPushButton {
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
                border: none;
                min-width: 80px;
            }
            
            QPushButton:hover {
                opacity: 0.9;
            }
            
            QPushButton:pressed {
                padding: 7px 15px;
            }
            
            QPushButton#primaryBtn {
                background-color: #3498db;
                color: white;
            }
            
            QPushButton#successBtn {
                background-color: #2ecc71;
                color: white;
            }
            
            QPushButton#warningBtn {
                background-color: #f39c12;
                color: white;
            }
            
            QPushButton#dangerBtn {
                background-color: #e74c3c;
                color: white;
            }
            
            QPushButton#infoBtn {
                background-color: #17a2b8;
                color: white;
            }
            
            QTextEdit {
                font-family: 'Consolas', monospace;
                font-size: 12px;
                border: 1px solid #ecf0f1;
                border-radius: 6px;
                background-color: #fafafa;
            }
            
            QListWidget {
                border: 1px solid #ecf0f1;
                border-radius: 6px;
                selection-background-color: #3498db;
                alternate-background-color: #f8f9fa;
            }
            
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #ecf0f1;
            }
            
            QListWidget::item:hover {
                background-color: #e8f4f8;
            }
            
            QLineEdit {
                padding: 8px 12px;
                border: 1px solid #ced4da;
                border-radius: 6px;
                font-size: 13px;
            }
            
            QLineEdit:focus {
                border-color: #3498db;
                outline: none;
            }
            
            QCheckBox {
                padding: 8px;
                font-size: 13px;
                color: #495057;
                background-color: #ffffff;
            }
            
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #ced4da;
                border-radius: 3px;
                background-color: #ffffff;
            }
            
            QCheckBox::indicator:checked {
                background-color: #3498db;
                border-color: #3498db;
            }
            
            QCheckBox::indicator:unchecked {
                background-color: #ffffff;
            }
            
            QScrollArea {
                border: none;
            }
        """
        self.setStyleSheet(self.style_sheet)
    
    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        
        header_layout = QHBoxLayout()
        
        title_label = QLabel("📋 模板管理")
        title_font = QFont()
        title_font.setPointSize(20)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #2c3e50;")
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 搜索模板...")
        self.search_edit.setFixedWidth(200)
        self.search_edit.textChanged.connect(self.filter_recent_list)
        header_layout.addWidget(self.search_edit)
        
        main_layout.addLayout(header_layout)
        
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(15)
        
        last_template_group = self._create_last_template_group()
        left_layout.addWidget(last_template_group)
        
        auto_load_group = self._create_auto_load_group()
        left_layout.addWidget(auto_load_group)
        
        splitter.addWidget(left_panel)
        splitter.setStretchFactor(0, 1)
        
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setSpacing(15)
        
        recent_group = self._create_recent_group()
        right_layout.addWidget(recent_group)
        
        preview_group = self._create_preview_group()
        right_layout.addWidget(preview_group)
        
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(1, 1)
        
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        
        self.import_btn = QPushButton("📥 导入模板")
        self.import_btn.setObjectName("primaryBtn")
        self.import_btn.clicked.connect(self.import_template)
        bottom_layout.addWidget(self.import_btn)
        
        self.export_btn = QPushButton("📤 导出模板")
        self.export_btn.setObjectName("successBtn")
        self.export_btn.clicked.connect(self.export_template)
        bottom_layout.addWidget(self.export_btn)
        
        close_btn = QPushButton("✖️ 关闭")
        close_btn.setObjectName("infoBtn")
        close_btn.clicked.connect(self.close)
        bottom_layout.addWidget(close_btn)
        
        main_layout.addLayout(bottom_layout)
    
    def _create_last_template_group(self):
        group = QGroupBox("📁 最近使用的模板")
        
        layout = QVBoxLayout(group)
        layout.setSpacing(12)
        
        self.last_template_info = QTextEdit()
        self.last_template_info.setReadOnly(True)
        self.last_template_info.setMaximumHeight(120)
        layout.addWidget(self.last_template_info)
        
        btn_layout = QHBoxLayout()
        
        self.load_last_btn = QPushButton("📥 载入模板")
        self.load_last_btn.setObjectName("primaryBtn")
        self.load_last_btn.clicked.connect(self.load_last_template)
        btn_layout.addWidget(self.load_last_btn)
        
        self.clear_last_btn = QPushButton("🗑️ 清除记录")
        self.clear_last_btn.setObjectName("dangerBtn")
        self.clear_last_btn.clicked.connect(self.clear_last_template)
        btn_layout.addWidget(self.clear_last_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        return group
    
    def _create_auto_load_group(self):
        group = QGroupBox("⚙️ 启动设置")
        
        layout = QVBoxLayout(group)
        layout.setSpacing(10)
        
        self.auto_load_chk = QCheckBox("📤 启动时自动载入上一次模板")
        self.auto_load_chk.setChecked(self.parent.settings.value("auto_load_template", True, type=bool))
        self.auto_load_chk.stateChanged.connect(self.toggle_auto_load)
        layout.addWidget(self.auto_load_chk)
        
        self.ask_load_chk = QCheckBox("❓ 启动时询问是否载入")
        self.ask_load_chk.setChecked(self.parent.settings.value("ask_load_template", False, type=bool))
        self.ask_load_chk.stateChanged.connect(self.toggle_ask_load)
        layout.addWidget(self.ask_load_chk)
        
        btn_layout = QHBoxLayout()
        self.save_settings_btn = QPushButton("💾 保存设置")
        self.save_settings_btn.setObjectName("primaryBtn")
        self.save_settings_btn.clicked.connect(self.save_settings)
        btn_layout.addWidget(self.save_settings_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        return group
    
    def _create_recent_group(self):
        group = QGroupBox("📋 模板历史记录")
        
        layout = QVBoxLayout(group)
        layout.setSpacing(10)
        
        toolbar_layout = QHBoxLayout()
        
        self.refresh_btn = QPushButton("🔄 刷新")
        self.refresh_btn.setObjectName("infoBtn")
        self.refresh_btn.setFixedWidth(80)
        self.refresh_btn.clicked.connect(self.refresh_recent_list)
        toolbar_layout.addWidget(self.refresh_btn)
        
        self.clear_all_btn = QPushButton("🗑️ 清空")
        self.clear_all_btn.setObjectName("dangerBtn")
        self.clear_all_btn.setFixedWidth(80)
        self.clear_all_btn.clicked.connect(self.clear_recent_history)
        toolbar_layout.addWidget(self.clear_all_btn)
        
        toolbar_layout.addStretch()
        layout.addLayout(toolbar_layout)
        
        self.recent_list = QListWidget()
        self.recent_list.setMinimumHeight(200)
        self.recent_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.recent_list.customContextMenuRequested.connect(self.show_context_menu)
        self.recent_list.itemDoubleClicked.connect(self.load_selected_template)
        layout.addWidget(self.recent_list)
        
        return group
    
    def _create_preview_group(self):
        group = QGroupBox("👁️ 模板预览")
        
        layout = QVBoxLayout(group)
        layout.setSpacing(10)
        
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setPlaceholderText("选择一个模板查看预览...")
        self.preview_text.setMinimumHeight(150)
        layout.addWidget(self.preview_text)
        
        self.template_stats = QLabel("")
        self.template_stats.setStyleSheet("font-size: 12px; color: #7f8c8d;")
        layout.addWidget(self.template_stats)
        
        return group
    
    def show_context_menu(self, position):
        menu = QMenu()
        
        selected_items = self.recent_list.selectedItems()
        if selected_items:
            menu.addAction("📥 载入模板", lambda: self.load_selected_template(selected_items[0]))
            menu.addAction("📄 查看详情", lambda: self.show_template_details(selected_items[0]))
            menu.addSeparator()
            menu.addAction("🗑️ 删除记录", lambda: self.delete_selected_record(selected_items[0]))
        
        menu.exec(self.recent_list.mapToGlobal(position))
    
    def show_template_details(self, item):
        template_path = item.data(Qt.UserRole)
        if template_path and os.path.exists(template_path):
            try:
                with open(template_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                info = f"📄 文件: {os.path.basename(template_path)}\n"
                info += f"📁 路径: {template_path}\n"
                info += f"📊 大小: {self._format_size(os.path.getsize(template_path))}\n"
                info += f"🕐 修改时间: {time.ctime(os.path.getmtime(template_path))}\n\n"
                info += "--- 内容预览 ---\n"
                info += content[:500] + ("..." if len(content) > 500 else "")
                
                QMessageBox.information(self, "模板详情", info)
            except Exception as e:
                QMessageBox.warning(self, "错误", f"无法读取模板文件: {str(e)}")
    
    def delete_selected_record(self, item):
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除模板记录 \"{item.text()}\" 吗？\n这不会删除模板文件本身。",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.recent_list.takeItem(self.recent_list.row(item))
            QMessageBox.information(self, "成功", "模板记录已删除")
    
    def _format_size(self, size_bytes):
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.2f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.2f} MB"
    
    def filter_recent_list(self, keyword):
        keyword = keyword.lower()
        for i in range(self.recent_list.count()):
            item = self.recent_list.item(i)
            item.setHidden(keyword and keyword not in item.text().lower())
    
    def update_last_template_info(self):
        last_template_path = self.parent.settings.value("last_template_path", "")
        
        if last_template_path and os.path.exists(last_template_path):
            file_info = f"📄 文件: {os.path.basename(last_template_path)}\n"
            file_info += f"📁 路径: {last_template_path}\n"
            file_info += f"📊 大小: {self._format_size(os.path.getsize(last_template_path))}\n"
            file_info += f"🕐 修改时间: {time.ctime(os.path.getmtime(last_template_path))}"
            
            self.last_template_info.setText(file_info)
            self.load_last_btn.setEnabled(True)
            self.clear_last_btn.setEnabled(True)
            
            self._preview_template(last_template_path)
        else:
            self.last_template_info.setText("暂无最近使用的模板\n\n💡 提示：使用「导入模板」功能加载模板文件")
            self.load_last_btn.setEnabled(False)
            self.clear_last_btn.setEnabled(False)
            self.preview_text.clear()
            self.template_stats.setText("")
    
    def _preview_template(self, template_path):
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            try:
                data = json.loads(content)
                tasks = data.get('tasks', [])
                task_count = len(tasks)
                self.template_stats.setText(f"📊 包含 {task_count} 个任务")
                
                preview_content = json.dumps(data, ensure_ascii=False, indent=2)[:1000]
                self.preview_text.setText(preview_content + ("\n\n..." if len(content) > 1000 else ""))
            except json.JSONDecodeError:
                self.preview_text.setText(content[:1000] + ("\n\n..." if len(content) > 1000 else ""))
                self.template_stats.setText("")
        except Exception as e:
            self.preview_text.setText(f"无法预览模板: {str(e)}")
            self.template_stats.setText("")
    
    def load_last_template(self):
        last_template_path = self.parent.settings.value("last_template_path", "")
        
        if last_template_path and os.path.exists(last_template_path):
            self.parent.load_template_from_path(last_template_path)
            self.close()
        else:
            QMessageBox.warning(self, "警告", "模板文件不存在或路径无效")
    
    def clear_last_template(self):
        reply = QMessageBox.question(
            self,
            "确认清除",
            "确定要清除最近使用的模板记录吗？\n这不会删除模板文件本身。",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.parent.settings.remove("last_template_path")
            self.update_last_template_info()
            self.refresh_recent_list()
            QMessageBox.information(self, "成功", "模板记录已清除")
    
    def toggle_auto_load(self, state):
        """切换自动载入设置"""
        self._save_setting("auto_load_template", state == Qt.Checked)
    
    def toggle_ask_load(self, state):
        """切换询问设置"""
        self._save_setting("ask_load_template", state == Qt.Checked)
    
    def _save_setting(self, key, value):
        """通用设置保存方法"""
        self.parent.settings.setValue(key, value)
        self.parent.settings.sync()
    
    def save_settings(self):
        """保存所有启动设置"""
        self._save_setting("auto_load_template", self.auto_load_chk.isChecked())
        self._save_setting("ask_load_template", self.ask_load_chk.isChecked())
        QMessageBox.information(self, "成功", "启动设置已保存")
    
    def closeEvent(self, event):
        """窗口关闭时确保所有设置被保存"""
        self.parent.settings.sync()
        event.accept()
    
    def refresh_recent_list(self):
        self.recent_list.clear()
        
        recent_templates = self.parent.settings.value("recent_templates", [], type=list)
        
        for template_info in recent_templates:
            if isinstance(template_info, dict) and 'path' in template_info:
                path = template_info['path']
                if os.path.exists(path):
                    item = QListWidgetItem(f"📄 {os.path.basename(path)}")
                    item.setData(Qt.UserRole, path)
                    
                    if 'time' in template_info:
                        time_str = time.ctime(template_info['time'])
                        item.setToolTip(f"修改时间: {time_str}")
                    
                    self.recent_list.addItem(item)
    
    def load_selected_template(self, item):
        template_path = item.data(Qt.UserRole)
        if template_path and os.path.exists(template_path):
            self.parent.settings.setValue("last_template_path", template_path)
            
            recent_templates = self.parent.settings.value("recent_templates", [], type=list)
            recent_templates = [t for t in recent_templates if isinstance(t, dict) and t.get('path') != template_path]
            recent_templates.insert(0, {'path': template_path, 'time': time.time()})
            
            if len(recent_templates) > 10:
                recent_templates = recent_templates[:10]
            
            self.parent.settings.setValue("recent_templates", recent_templates)
            
            self.parent.load_template_from_path(template_path)
            self.update_last_template_info()
            self.refresh_recent_list()
            self.close()
    
    def clear_recent_history(self):
        reply = QMessageBox.question(
            self,
            "确认清空",
            "确定要清空所有模板历史记录吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.parent.settings.remove("recent_templates")
            self.parent.settings.remove("last_template_path")
            self.update_last_template_info()
            self.refresh_recent_list()
            QMessageBox.information(self, "成功", "模板历史记录已清空")
    
    def import_template(self):
        from PySide6.QtWidgets import QFileDialog
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "导入模板",
            "",
            "JSON 文件 (*.json);;所有文件 (*.*)"
        )
        
        if file_path:
            try:
                self.parent.settings.setValue("last_template_path", file_path)
                
                recent_templates = self.parent.settings.value("recent_templates", [], type=list)
                recent_templates = [t for t in recent_templates if isinstance(t, dict) and t.get('path') != file_path]
                recent_templates.insert(0, {'path': file_path, 'time': time.time()})
                
                if len(recent_templates) > 10:
                    recent_templates = recent_templates[:10]
                
                self.parent.settings.setValue("recent_templates", recent_templates)
                
                self.parent.load_template_from_path(file_path)
                self.update_last_template_info()
                self.refresh_recent_list()
                
                QMessageBox.information(self, "成功", "模板导入成功")
            except Exception as e:
                QMessageBox.warning(self, "错误", f"导入失败: {str(e)}")
    
    def export_template(self):
        from PySide6.QtWidgets import QFileDialog
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出模板",
            "template.json",
            "JSON 文件 (*.json)"
        )
        
        if file_path:
            try:
                tasks_data = []
                for i in range(self.parent.task_list.count()):
                    item = self.parent.task_list.item(i)
                    row_widget = self.parent.task_list.itemWidget(item)
                    if row_widget:
                        tasks_data.append(row_widget.get_data())
                
                template_data = {
                    'version': '1.0',
                    'export_time': time.time(),
                    'tasks': tasks_data
                }
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(template_data, f, ensure_ascii=False, indent=2)
                
                self.parent.settings.setValue("last_template_path", file_path)
                
                recent_templates = self.parent.settings.value("recent_templates", [], type=list)
                recent_templates = [t for t in recent_templates if isinstance(t, dict) and t.get('path') != file_path]
                recent_templates.insert(0, {'path': file_path, 'time': time.time()})
                
                if len(recent_templates) > 10:
                    recent_templates = recent_templates[:10]
                
                self.parent.settings.setValue("recent_templates", recent_templates)
                
                self.update_last_template_info()
                self.refresh_recent_list()
                
                QMessageBox.information(self, "成功", f"模板已导出到:\n{file_path}")
            except Exception as e:
                QMessageBox.warning(self, "错误", f"导出失败: {str(e)}")