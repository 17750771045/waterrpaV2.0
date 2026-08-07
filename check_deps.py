import sys

libs = [
    ('PySide6', 'PySide6.QtWidgets'),
    ('pyautogui', 'pyautogui'),
    ('pyperclip', 'pyperclip'),
    ('PIL', 'PIL.Image'),
    ('opencv-python', 'cv2'),
    ('numpy', 'numpy'),
    ('pywin32', 'win32gui'),
    ('psutil', 'psutil')
]

print('=' * 60)
print('Check Dependencies...')
print('=' * 60)

missing = []
for name, import_name in libs:
    try:
        __import__(import_name)
        print(f'[OK] {name:20} - Installed')
    except ImportError:
        print(f'[MISS] {name:20} - Missing')
        missing.append(name)

print('=' * 60)
if missing:
    print(f'\nMissing libraries: {missing}')
    sys.exit(1)
else:
    print('\nAll dependencies installed!')
    sys.exit(0)
