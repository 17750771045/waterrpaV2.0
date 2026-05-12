"""
超时配置模块
负责处理超时相关的功能，包括超时检测、重试机制和超时后执行步骤
"""

import time
import json
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit, 
    QGroupBox, QListWidget, QListWidgetItem, QComboBox
)
from PySide6.QtCore import Qt, QSize

# 避免循环导入，在运行时动态获取


class TimeoutManager:
    """超时管理器"""
    
    def __init__(self, parent=None):
        """初始化超时管理器"""
        self.parent = parent
        self.retry_count = 1
        self.retry_interval = 5.0
        self.timeout_tasks = []
        self.response_tasks = []  # 应对步骤
    
    def get_retry_count(self):
        """获取重试次数"""
        if self.parent and hasattr(self.parent, 'timeout_retry_count'):
            try:
                return int(self.parent.timeout_retry_count.text())
            except:
                pass
        return self.retry_count
    
    def get_retry_interval(self):
        """获取重试间隔"""
        if self.parent and hasattr(self.parent, 'timeout_retry_interval'):
            try:
                return float(self.parent.timeout_retry_interval.text())
            except:
                pass
        return self.retry_interval
    
    def get_timeout_tasks(self):
        """获取超时后执行步骤"""
        if self.parent and hasattr(self.parent, 'timeout_task_list'):
            timeout_tasks = []
            try:
                for i in range(self.parent.timeout_task_list.count()):
                    item = self.parent.timeout_task_list.item(i)
                    widget = self.parent.timeout_task_list.itemWidget(item)
                    if widget:
                        timeout_tasks.append(widget.get_data())
                return timeout_tasks
            except:
                pass
        return self.timeout_tasks
    
    def get_response_tasks(self):
        """获取应对步骤"""
        if self.parent and hasattr(self.parent, 'response_task_list'):
            response_tasks = []
            try:
                for i in range(self.parent.response_task_list.count()):
                    item = self.parent.response_task_list.item(i)
                    widget = self.parent.response_task_list.itemWidget(item)
                    if widget:
                        response_tasks.append(widget.get_data())
                return response_tasks
            except:
                pass
        return self.response_tasks
    
    def save_config(self, settings):
        """保存超时配置"""
        if self.parent:
            settings.setValue("timeout_retry_count", self.parent.timeout_retry_count.text())
            settings.setValue("timeout_retry_interval", self.parent.timeout_retry_interval.text())
            
            # 保存应对步骤
            response_tasks = self.get_response_tasks()
            settings.setValue("response_tasks", json.dumps(response_tasks))
            
            # 保存超时步骤
            timeout_tasks = self.get_timeout_tasks()
            settings.setValue("timeout_tasks", json.dumps(timeout_tasks))
    
    def load_config(self, settings):
        """加载超时配置"""
        if self.parent:
            self.parent.timeout_retry_count.setText(settings.value("timeout_retry_count", "1"))
            self.parent.timeout_retry_interval.setText(settings.value("timeout_retry_interval", "5"))
            
            # 加载应对步骤
            try:
                response_tasks_json = settings.value("response_tasks", "[]")
                response_tasks = json.loads(response_tasks_json)
                
                self.parent.response_task_list.clear()
                for task in response_tasks:
                    item = QListWidgetItem()
                    item.setSizeHint(QSize(0, 40))
                    row_widget = TaskRow(task)
                    self.parent.response_task_list.addItem(item)
                    self.parent.response_task_list.setItemWidget(item, row_widget)
            except:
                pass
            
            # 加载超时步骤
            try:
                timeout_tasks_json = settings.value("timeout_tasks", "[]")
                timeout_tasks = json.loads(timeout_tasks_json)
                
                self.parent.timeout_task_list.clear()
                for task in timeout_tasks:
                    item = QListWidgetItem()
                    item.setSizeHint(QSize(0, 40))
                    row_widget = TaskRow(task)
                    self.parent.timeout_task_list.addItem(item)
                    self.parent.timeout_task_list.setItemWidget(item, row_widget)
            except:
                pass


def create_timeout_page(parent):
    """创建超时配置页面"""
    timeout_page = QWidget()
    timeout_page_layout = QVBoxLayout(timeout_page)
    
    # 超时配置标题
    timeout_title = QLabel("超时后执行步骤配置")
    timeout_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #2196F3;")
    timeout_page_layout.addWidget(timeout_title)
    
    # 超时重试设置
    retry_group = QGroupBox("超时重试设置")
    retry_layout = QHBoxLayout()
    retry_layout.addWidget(QLabel("重试次数:"))
    parent.timeout_retry_count = QLineEdit(parent.settings.value("timeout_retry_count", "1"))
    parent.timeout_retry_count.setFixedWidth(50)
    retry_layout.addWidget(parent.timeout_retry_count)
    
    # 动态获取HelpBtn类
    HelpBtn = parent.__class__.__module__.split('.')[0] + '.waterRPA.HelpBtn'
    try:
        import importlib
        module_name, class_name = HelpBtn.rsplit('.', 1)
        module = importlib.import_module(module_name)
        HelpBtn = getattr(module, class_name)
        retry_layout.addWidget(HelpBtn("【重试次数】\n超时后重试的次数，0表示不重试。"))
    except:
        pass
    
    retry_layout.addSpacing(20)
    retry_layout.addWidget(QLabel("重试间隔(s):"))
    parent.timeout_retry_interval = QLineEdit(parent.settings.value("timeout_retry_interval", "5"))
    parent.timeout_retry_interval.setFixedWidth(50)
    retry_layout.addWidget(parent.timeout_retry_interval)
    
    try:
        retry_layout.addWidget(HelpBtn("【重试间隔】\n每次重试之间的等待时间。"))
    except:
        pass
    
    retry_layout.addStretch()
    retry_group.setLayout(retry_layout)
    timeout_page_layout.addWidget(retry_group)
    
    # 应对步骤
    response_group = QGroupBox("应对步骤（超时后先执行）")
    response_layout = QVBoxLayout()
    
    response_toolbar = QHBoxLayout()
    add_response_step_btn = QPushButton("+ 添加应对步骤")
    add_response_step_btn.clicked.connect(lambda: parent.add_response_step())
    response_toolbar.addWidget(add_response_step_btn)
    
    response_toolbar.addStretch()
    response_layout.addLayout(response_toolbar)
    
    # 应对步骤列表
    parent.response_task_list = parent.__class__.__module__.split('.')[0] + '.waterRPA.DraggableListWidget'
    try:
        import importlib
        module_name, class_name = parent.response_task_list.rsplit('.', 1)
        module = importlib.import_module(module_name)
        DraggableListWidget = getattr(module, class_name)
        parent.response_task_list = DraggableListWidget()
    except:
        from PySide6.QtWidgets import QListWidget
        parent.response_task_list = QListWidget()
    
    response_layout.addWidget(parent.response_task_list)
    
    response_group.setLayout(response_layout)
    timeout_page_layout.addWidget(response_group)
    
    # 超时后执行步骤
    steps_group = QGroupBox("超时后执行步骤（应对失败后执行）")
    steps_layout = QVBoxLayout()
    
    steps_toolbar = QHBoxLayout()
    add_timeout_step_btn = QPushButton("+ 添加步骤")
    add_timeout_step_btn.clicked.connect(lambda: parent.add_timeout_step())
    steps_toolbar.addWidget(add_timeout_step_btn)
    
    save_timeout_steps_btn = QPushButton("💾 保存配置")
    save_timeout_steps_btn.clicked.connect(parent.save_timeout_config)
    steps_toolbar.addWidget(save_timeout_steps_btn)
    
    steps_toolbar.addStretch()
    steps_layout.addLayout(steps_toolbar)
    
    # 超时步骤列表
    parent.timeout_task_list = parent.__class__.__module__.split('.')[0] + '.waterRPA.DraggableListWidget'
    try:
        import importlib
        module_name, class_name = parent.timeout_task_list.rsplit('.', 1)
        module = importlib.import_module(module_name)
        DraggableListWidget = getattr(module, class_name)
        parent.timeout_task_list = DraggableListWidget()
    except:
        from PySide6.QtWidgets import QListWidget
        parent.timeout_task_list = QListWidget()
    
    steps_layout.addWidget(parent.timeout_task_list)
    
    steps_group.setLayout(steps_layout)
    timeout_page_layout.addWidget(steps_group)
    
    # 说明文本
    info_text = QTextEdit()
    info_text.setReadOnly(True)
    info_text.setMaximumHeight(120)
    info_text.setStyleSheet("font-size: 12px; color: #666;")
    info_text.setText("""执行流程说明：
1. 单步骤超时后，先执行应对步骤
2. 应对步骤执行成功 → 继续执行当前单步骤
3. 应对步骤执行失败 → 执行超时后步骤 → 重新开始主任务流程

注意：设置合理的超时时间和重试次数，避免无限循环。""")
    timeout_page_layout.addWidget(info_text)
    
    return timeout_page


def handle_timeout_retry(worker, engine, tasks, loop_forever, callback_msg):
    """处理超时重试逻辑"""
    # 获取超时配置
    retry_count = 0
    retry_interval = 5
    timeout_tasks = []
    response_tasks = []
    timeout_action = "retry"  # 默认重试当前步骤
    
    if worker.parent_window:
        try:
            retry_count = int(worker.parent_window.timeout_retry_count.text())
            retry_interval = float(worker.parent_window.timeout_retry_interval.text())
            
            # 获取应对步骤
            response_tasks = []
            for i in range(worker.parent_window.response_task_list.count()):
                item = worker.parent_window.response_task_list.item(i)
                widget = worker.parent_window.response_task_list.itemWidget(item)
                if widget:
                    response_tasks.append(widget.get_data())
            
            # 获取超时后执行步骤
            timeout_tasks = []
            for i in range(worker.parent_window.timeout_task_list.count()):
                item = worker.parent_window.timeout_task_list.item(i)
                widget = worker.parent_window.timeout_task_list.itemWidget(item)
                if widget:
                    timeout_tasks.append(widget.get_data())
        except:
            pass
    
    # 创建超时回调函数：执行全局应对步骤
    def timeout_callback():
        if not response_tasks:
            # 没有全局应对步骤，直接执行超时配置
            if timeout_tasks:
                callback_msg("=== 没有全局应对步骤，执行超时配置 ===")
                saved_is_running = engine.is_running
                engine.run_tasks(timeout_tasks, False, callback_msg)
                engine.is_running = saved_is_running
            return False  # 返回False表示需要重新开始主步骤
        
        callback_msg("=== 执行全局应对步骤 ===")
        saved_is_running = engine.is_running
        
        # 执行全局应对步骤
        engine.run_tasks(response_tasks, False, callback_msg)
        
        callback_msg("=== 全局应对步骤执行完成 ===")
        
        # 恢复 is_running 状态
        engine.is_running = saved_is_running
        
        # 全局应对完成后总是重新开始主流程
        return False
    
    # 执行主任务，传递超时回调
    # 超时回调返回True表示应对成功，继续当前步骤
    # 超时回调返回False表示应对失败，重新开始主步骤
    result = engine.run_tasks(tasks, loop_forever, callback_msg, timeout_callback)
    
    return result


from PySide6.QtWidgets import QTextEdit