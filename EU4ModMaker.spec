# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for EU4 모드 제작기.

빌드:
    pyinstaller --clean EU4ModMaker.spec

산출물:
    dist/EU4ModMaker.exe  (단일 파일, 콘솔 창 없음)
"""

import sys
from pathlib import Path

block_cipher = None
project_root = Path(SPECPATH)

a = Analysis(
    ['main.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        # src 패키지를 실행 파일에 포함 (countries.py, event_pictures.py 등)
        ('src/*.py', 'src'),
    ],
    hiddenimports=[
        'PIL._tkinter_finder',
        'PIL.DdsImagePlugin',
        'PIL.TgaImagePlugin',
        'src.countries',
        'src.event_pictures',
        'src.image_processor',
        'src.mod_builder',
        'src.music_builder',
        'src.loading_screens',
        'src.sounds',
        'src.ui_icons',
        'src.ideas',
        'src.localisation',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'numpy', 'scipy', 'pandas', 'pytest',
        'IPython', 'jupyter', 'notebook',
    ],
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
    name='EU4ModMaker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,     # GUI 앱: 콘솔 창 없음
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
