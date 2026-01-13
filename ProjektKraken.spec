# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

import os
import shutil

project_dir = os.getcwd()

# Explicitly clean the dist/ProjektKraken directory to satisfy user request for a clean slate
dist_dir = os.path.join(project_dir, 'dist', 'ProjektKraken')
if os.path.exists(dist_dir):
    print(f"Cleaning build directory: {dist_dir}")
    try:
        shutil.rmtree(dist_dir)
    except OSError as e:
        print(f"WARNING: Could not clean build directory completely: {e}")
        print("Please ensure ProjektKraken is not running.")

from PyInstaller.utils.hooks import collect_data_files

added_files = [
    (os.path.join(project_dir, 'assets'), 'assets'),
    (os.path.join(project_dir, 'themes.json'), '.'),
    (os.path.join(project_dir, 'migrations'), 'migrations'),
    (os.path.join(project_dir, 'src', 'resources'), 'src/resources'),
]
added_files += collect_data_files('pyvis')

a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=[],
    datas=added_files,
    hiddenimports=['PySide6.QtSvg', 'PySide6.QtWebChannel'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ProjektKraken',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ProjektKraken',
)
