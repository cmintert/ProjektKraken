# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# Find PyVis templates directory (only if pyvis is installed)
added_files = [
    ('default_assets', 'default_assets'),
    ('themes.json', '.'),
    ('src/resources', 'src/resources'),
    ('lib', 'lib'),  # vis-network for offline graph rendering
]

# Add PyVis templates if available (optional dependency)
try:
    import pyvis
    import os
    pyvis_templates = os.path.join(os.path.dirname(pyvis.__file__), 'templates')
    added_files.append((pyvis_templates, 'pyvis/templates'))
except ImportError:
    print("PyVis not installed - graph features will be unavailable")

a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=[],
    datas=added_files,
    hiddenimports=['PySide6.QtSvg'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Testing frameworks
        'pytest',
        'pytest_qt',
        'pytest_cov',
        '_pytest',
        'py.test',
        # Documentation
        'sphinx',
        'docutils',
        'alabaster',
        'babel',
        'myst_parser',
        'furo',
        'sphinxcontrib',
        # Development tools
        'ruff',
        'mypy',
        'black',
        'flake8',
        'pylint',
        'coverage',
        # Unused standard library modules
        'tkinter',
        'tcl',
        'tk',
        '_tkinter',
        'turtle',
        'test',
        'unittest',
        'doctest',
        'pdb',
        'pydoc',
        'pydoc_data',
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
