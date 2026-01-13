# -*- mode: python ; coding: utf-8 -*-

"""
PyInstaller spec for ProjektKraken - MINIMAL BUILD (core features only).

This configuration excludes ALL optional dependencies to create the
smallest possible build. Optional features (semantic search, web server,
graph visualization) will show error messages when accessed.

To build: pyinstaller ProjektKraken-minimal.spec

Estimated size: 30-50% smaller than full build
Features excluded:
- Semantic search (numpy, requests)
- Web server (fastapi, uvicorn)
- Graph visualization (pyvis)
"""

block_cipher = None

# Minimal data files (core only)
added_files = [
    ('default_assets', 'default_assets'),
    ('themes.json', '.'),
    ('src/resources', 'src/resources'),
    # Exclude lib/ since it's only needed for graph visualization
]

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
        # Optional dependencies (excluded for minimal build)
        'numpy',
        'requests',
        'urllib3',
        'charset_normalizer',
        'certifi',
        'idna',
        'fastapi',
        'uvicorn',
        'starlette',
        'pydantic',
        'anyio',
        'sniffio',
        'pyvis',
        'jinja2',
        'networkx',
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
        'setuptools',
        'pip',
        'wheel',
        'pkg_resources',
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
        'email',
        'xmlrpc',
        'xml.dom',
        'xml.sax',
        'distutils',
        'lib2to3',
        'multiprocessing',
        'concurrent',
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
        'PySide6.QtQml',
        'PySide6.QtQuick',
        'PySide6.QtQuickWidgets',
        'PySide6.QtRemoteObjects',
        'PySide6.QtScxml',
        'PySide6.QtSensors',
        'PySide6.QtSerialPort',
        'PySide6.QtSql',
        'PySide6.QtStateMachine',
        'PySide6.QtTest',
        'PySide6.QtTextToSpeech',
        'PySide6.QtUiTools',
        'PySide6.QtWebChannel',
        'PySide6.QtWebEngineCore',
        'PySide6.QtWebEngineWidgets',
        'PySide6.QtWebSockets',
        'PySide6.QtXml',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Aggressive binary filtering for minimal build
a.binaries = [x for x in a.binaries if not (
    # Qt modules we don't use
    x[0].startswith('Qt6Bluetooth') or
    x[0].startswith('Qt6Charts') or
    x[0].startswith('Qt6DataVisualization') or
    x[0].startswith('Qt6Designer') or
    x[0].startswith('Qt6Help') or
    x[0].startswith('Qt6Multimedia') or
    x[0].startswith('Qt6Nfc') or
    x[0].startswith('Qt6Positioning') or
    x[0].startswith('Qt6PrintSupport') or
    x[0].startswith('Qt6Qml') or
    x[0].startswith('Qt6Quick') or
    x[0].startswith('Qt6Sensors') or
    x[0].startswith('Qt6SerialPort') or
    x[0].startswith('Qt6Sql') or
    x[0].startswith('Qt6Test') or
    x[0].startswith('Qt6WebChannel') or
    x[0].startswith('Qt6WebEngine') or
    x[0].startswith('Qt6WebSockets') or
    x[0].startswith('Qt63D') or
    # Optional dependencies
    'numpy' in x[0].lower() or
    'mkl' in x[0].lower() or
    'openblas' in x[0].lower()
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
