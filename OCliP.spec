# -*- mode: python ; coding: utf-8 -*-
import platform

from PyInstaller.utils.hooks import collect_submodules

if platform.system() == "Windows":
    app_icon = "./icons/icon.ico"

else:
    app_icon = "./icons/icon.png"

datas = [
    ("./icons/icon.ico", "./icons/"),
    ("./icons/icon.png", "./icons/"),
    ("./sounds/notify.mp3", "./sounds/"),
    ("./images/loading.gif", "./images/"),
]

hiddenimports = collect_submodules('plyer.platforms.win')

a = Analysis(
    ['./impclip.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=2,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='OCliP',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[app_icon],
)
