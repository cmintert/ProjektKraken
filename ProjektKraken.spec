# -*- mode: python ; coding: utf-8 -*-

"""
PyInstaller spec for ProjektKraken with optimized size.

This configuration excludes optional dependencies and unused Qt modules
to minimize the build size. For a full build with all features, use
ProjektKraken-full.spec instead.

Estimated size reduction: 30-50% compared to unoptimized build.
"""

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
    hiddenimports=[
        'PySide6.QtSvg',
    ],
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
        'xmlrpc',
        'xml.dom',
        'xml.sax',
        'lib2to3',
        # Unused PySide6/Qt modules (significant size reduction)
        'PySide6.Qt3DAnimation',
        'PySide6.Qt3DCore',
        'PySide6.Qt3DExtras',
        'PySide6.Qt3DInput',
        'PySide6.Qt3DLogic',
        'PySide6.Qt3DRender',
        'PySide6.QtBluetooth',
        'PySide6.QtCharts',
        'PySide6.QtDataVisualization',
        'PySide6.QtDesigner',
        'PySide6.QtHelp',
        'PySide6.QtMultimedia',
        'PySide6.QtMultimediaWidgets',
        'PySide6.QtNetworkAuth',
        'PySide6.QtNfc',
        'PySide6.QtPositioning',
        'PySide6.QtPrintSupport',
        'PySide6.QtRemoteObjects',
        'PySide6.QtScxml',
        'PySide6.QtSensors',
        'PySide6.QtSerialPort',
        'PySide6.QtSql',
        'PySide6.QtStateMachine',
        'PySide6.QtTest',
        'PySide6.QtTextToSpeech',
        'PySide6.QtUiTools',
        'PySide6.QtWebSockets',
        'PySide6.QtXml',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Remove duplicate and unwanted binaries to reduce size
# Filter out debug symbols and unnecessary Qt plugins
a.binaries = [x for x in a.binaries if not (
    x[0].startswith('Qt6Bluetooth') or
    x[0].startswith('Qt6Charts') or
    x[0].startswith('Qt6DataVisualization') or
    x[0].startswith('Qt6Nfc') or
    x[0].startswith('Qt6Positioning') or
    x[0].startswith('Qt6Sensors') or
    x[0].startswith('Qt6SerialPort') or
    x[0].startswith('Qt6Sql') or
    x[0].startswith('Qt6Test') or
    x[0].startswith('Qt6WebSockets') or
    x[0].startswith('Qt63D')
)]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ProjektKraken',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,  # Windows: strip has limited effect, use UPX instead
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
