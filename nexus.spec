# nexus.spec — PyInstaller build spec
# Run: pyinstaller nexus.spec

import os
from pathlib import Path

block_cipher = None
root = Path(SPECPATH)

a = Analysis(
    [str(root / 'backend' / 'app.py')],
    pathex=[str(root)],
    binaries=[],
    datas=[
        # Include the entire frontend folder inside the bundle
        (str(root / 'frontend'), 'frontend'),
    ],
    hiddenimports=[
        'flask',
        'flask_cors',
        'werkzeug',
        'werkzeug.serving',
        'werkzeug.exceptions',
        'jinja2',
        'jinja2.ext',
        'itsdangerous',
        'click',
        'sqlite3',
        'threading',
        'subprocess',
        'shutil',
        'webbrowser',
        'webview',
        're',
        'hashlib',
        'pathlib',
        'datetime',
        'json',
        'os',
        'sys',
        'requests',
        'openai',
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'PIL', 'cv2'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='NexusNotes',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # No console window — runs silently
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(root / 'frontend' / 'static' / 'icon.ico'),
)
