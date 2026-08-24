# -*- mode: python ; coding: utf-8 -*-
"""Audited one-directory Windows build for ProjektKraken."""

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

ROOT = Path(SPECPATH)

datas = [
    (str(ROOT / "LICENSE"), "."),
    (str(ROOT / "Kraken.webp"), "."),
    (str(ROOT / "default_assets"), "default_assets"),
    (str(ROOT / "themes.json"), "."),
    (str(ROOT / "src" / "resources"), "src/resources"),
    (str(ROOT / "src" / "assets"), "src/assets"),
    (str(ROOT / "src" / "webserver" / "static"), "src/webserver/static"),
    (str(ROOT / "src" / "webserver" / "templates"), "src/webserver/templates"),
    (str(ROOT / "lib"), "lib"),
    (str(ROOT / "packaging" / "windows" / "package-contract.json"), "."),
]
datas += collect_data_files("pyvis", includes=["templates/**"])
datas += copy_metadata("keyring")

hiddenimports = [
    "PySide6.QtSvg",
    "src.services.providers.anthropic_provider",
    "src.services.providers.google_provider",
    "src.services.providers.lmstudio_provider",
    "src.services.providers.openai_provider",
]
hiddenimports += collect_submodules("keyring.backends")

excluded_modules = [
    "_pytest",
    "docutils",
    "mypy",
    "pytest",
    "ruff",
    "sphinx",
]

icon_path = os.environ.get("PK_WINDOWS_ICON")
version_file = os.environ.get("PK_WINDOWS_VERSION_FILE")

a = Analysis(
    [str(ROOT / "launcher.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excluded_modules,
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ProjektKraken",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=icon_path,
    version=version_file,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="ProjektKraken",
)
