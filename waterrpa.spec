# -*- mode: python ; coding: utf-8 -*-

import os
import sys

# 获取当前目录
current_dir = os.path.dirname(os.path.abspath(SPEC))

a = Analysis(
    ['waterRPA.py'],
    pathex=[
        '.',
        current_dir,
    ],
    binaries=[],
    datas=[
        # 资源文件：debug 目录下的所有模板图片
        (os.path.join(current_dir, 'debug'), 'debug'),
        # 配置文件
        (os.path.join(current_dir, 'pyproject.toml'), '.'),
    ],
    hiddenimports=[
        # 自定义模块
        'timeout',
        'inspector',
        'autostart',
        'template_manager',
        'parallel_manager',
        'barcode_converter',
        
        # PySide6 核心模块
        'PySide6.QtWidgets',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtNetwork',
        'PySide6.QtOpenGL',
        'PySide6.QtOpenGLWidgets',
        
        # 图像处理和自动化相关
        'pyautogui',
        'pyperclip',
        'PIL',
        'PIL.Image',
        'PIL.ImageQt',
        'cv2',
        'numpy',
        'psutil',
        
        # Windows API
        'win32gui',
        'win32con',
        'win32process',
        'win32api',
        'win32ui',
        'win32print',
        'win32clipboard',
        'win32com.client',
        'winreg',
        'ctypes',
        
        # 标准库
        'json',
        'time',
        'datetime',
        'threading',
        'traceback',
        'os',
        'sys',
        're',
        'shutil',
        'subprocess',
        'hashlib',
        'urllib.request',
        'urllib.error',
        'xml.etree.ElementTree',
        
        # PyInstaller 运行时需要
        'pkg_resources',
        'setuptools',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除不需要的模块
        'matplotlib',
        'pandas',
        'scipy',
        'IPython',
        'notebook',
        'tkinter',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='WaterRPA',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[
        # 排除这些不压缩
        'vcruntime140.dll',
        'vcruntime140_1.dll',
    ],
    runtime_tmpdir=None,
    console=False,  # 无控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # 如需图标，添加图标文件路径
)

# 如需生成安装包，可使用以下 COLLECT 配置
# coll = COLLECT(
#     exe,
#     a.binaries,
#     a.zipfiles,
#     a.datas,
#     strip=False,
#     upx=True,
#     upx_exclude=[],
#     name='WaterRPA',
# )
