# PyInstaller Build Size Optimization Guide

This document details the optimizations made to reduce the PyInstaller build output (the .exe + _internal folder).

## Build Configurations

ProjektKraken now provides two PyInstaller spec files with different size/feature tradeoffs:

### 1. ProjektKraken.spec (Standard Build)

**Target:** General users who want all features with size optimization

**Size:** ~150-180 MB (30-40% reduction from unoptimized)

**Features:**
- ✅ All core features (timeline, events, entities, maps)
- ✅ Optional features if dependencies installed (search, webserver, graph)
- ✅ Unused Qt modules excluded for size savings

**Use when:**
- Building for general distribution
- Users may want optional features
- Reasonable size while keeping flexibility

### 2. ProjektKraken-minimal.spec (Minimal Build)

**Target:** Users who only need core features and want smallest size

**Size:** ~80-120 MB (50-60% reduction from unoptimized)

**Features:**
- ✅ All core features (timeline, events, entities, maps)
- ❌ Semantic search excluded
- ❌ Web server excluded
- ❌ Graph visualization excluded

**Use when:**
- Distributing to users who don't need optional features
- Minimizing download/install size is critical
- Storage space is constrained

## Size Comparison

| Configuration | Approximate Size | vs Unoptimized | vs Standard |
|--------------|------------------|----------------|-------------|
| Unoptimized (old) | ~250-300 MB | baseline | +40-60% |
| Standard (ProjektKraken.spec) | ~150-180 MB | **↓30-40%** | baseline |
| Minimal (ProjektKraken-minimal.spec) | ~80-120 MB | **↓50-60%** | **↓30-40%** |

## Optimization Techniques

Both spec files implement the following optimizations:

### 1. Unused Qt Module Exclusion (~50-80 MB savings)

Excludes Qt modules that ProjektKraken doesn't use:

**Excluded:**
- Qt3D* (3D graphics)
- QtBluetooth, QtNfc, QtPositioning (mobile/location)
- QtCharts, QtDataVisualization (data viz - we use custom)
- QtMultimedia, QtMultimediaWidgets (audio/video)
- QtPrintSupport (printing)
- QtQml, QtQuick* (QML - minimal build only)
- QtSensors, QtSerialPort (hardware)
- QtSql (database UI - not used)
- QtTest (testing)
- QtWebChannel, QtWebEngine* (web - minimal build only)
- QtWebSockets (websockets)

**Used (Kept):**
- QtCore, QtGui, QtWidgets (essential)
- QtSvg (SVG icon support)
- QtWebEngine* (longform editor - standard build)
- QtQuick* (future features - standard build)

### 2. Development Tool Exclusion (~20-30 MB savings)

Excludes packages only needed for development:
- pytest, pytest-qt, pytest-cov
- sphinx, docutils, myst-parser, furo
- ruff, mypy, black, flake8, pylint
- coverage, setuptools, pip, wheel

### 3. Unused Standard Library Exclusion (~10-20 MB savings)

Excludes stdlib modules not used by ProjektKraken:
- tkinter (GUI toolkit - we use Qt)
- email, xmlrpc (protocols not used)
- distutils, lib2to3 (build tools)
- multiprocessing, concurrent (not used)
- test, unittest, doctest, pdb (testing/debugging)

### 4. Optional Dependency Exclusion (Minimal build only, ~50-70 MB savings)

Minimal build excludes optional features:
- numpy (~50 MB) - semantic search
- fastapi/uvicorn (~10 MB) - web server
- pyvis (~5 MB) - graph visualization
- requests (~3 MB) - HTTP client

### 5. Binary Filtering

Post-analysis filtering removes Qt DLLs for excluded modules:
- Qt6Bluetooth.dll, Qt6Charts.dll, Qt6Nfc.dll, etc.
- Prevents PyInstaller from including them even if referenced

### 6. UPX Compression

Enabled for both .exe and DLLs (already in original spec):
- Compresses binaries to reduce size
- Slight startup time increase (negligible)
- 20-30% compression ratio typical

## Building Different Configurations

### Standard Build

```bash
# Install all dependencies
pip install -r requirements.txt

# Build
pyinstaller ProjektKraken.spec

# Output: dist/ProjektKraken/ (~150-180 MB)
```

### Minimal Build

```bash
# Install core only
pip install -r requirements-core.txt
pip install pyinstaller

# Build
pyinstaller ProjektKraken-minimal.spec

# Output: dist/ProjektKraken/ (~80-120 MB)
```

## Verification

After building, verify the optimization worked:

```bash
# Check output size
du -sh dist/ProjektKraken/

# Check for unexpected large files
du -h dist/ProjektKraken/_internal/ | sort -rh | head -20

# Verify excluded Qt modules are not present
ls dist/ProjektKraken/_internal/ | grep -E "Qt6(Bluetooth|Charts|Multimedia)"
# Should return nothing
```

## Distribution

Both builds produce a `dist/ProjektKraken/` folder containing:
- `ProjektKraken.exe` - The main executable (~10-15 MB)
- `_internal/` - Dependencies and data files

**Distribute the entire folder** - users run `ProjektKraken.exe` from within.

For maximum compression, create a ZIP or installer:

```bash
# Create ZIP
cd dist
zip -r ProjektKraken-v0.6.0.zip ProjektKraken/

# Typical compression: 30-40% additional savings
# Standard build: 150 MB → ~100 MB ZIP
# Minimal build: 100 MB → ~60 MB ZIP
```

## Troubleshooting

### Build is still too large

1. Verify you're using the correct dependencies:
   ```bash
   pip list | grep -E "numpy|fastapi|pyvis"
   ```
   If these show in minimal build, uninstall them first.

2. Check for unexpected packages:
   ```bash
   pip list
   ```
   Uninstall any dev tools before building.

3. Use minimal spec:
   ```bash
   pyinstaller ProjektKraken-minimal.spec
   ```

### Missing features in minimal build

This is expected behavior. Minimal build excludes:
- Semantic search → Shows "dependencies not installed" error
- Web server → Shows "dependencies not installed" error  
- Graph visualization → Shows "PyVis not available" message

To include these features, use the standard build (`ProjektKraken.spec`).

### Qt module errors

If you get errors about missing Qt modules:
1. The module is truly needed - remove it from excludes
2. Re-run: `pyinstaller ProjektKraken.spec --clean`

### Binary size doesn't match

Sizes vary by platform and Qt version:
- Windows typically larger than Linux
- Qt version affects size (6.10.x vs 6.8.x)
- Python version affects size (3.13 vs 3.11)

Expected range is provided as guidance, not exact numbers.

## Future Optimizations

Potential further improvements:
1. **Plugin architecture** - Load optional features as DLLs
2. **Lazy loading** - Import heavy modules only when needed
3. **Custom Qt build** - Compile Qt with only needed modules
4. **Asset optimization** - Compress default_assets, resources
5. **Alternative packaging** - Consider alternatives to PyInstaller

## Summary

The optimized spec files reduce PyInstaller build size by **30-60%** through:
- Excluding unused Qt modules (largest impact)
- Excluding development tools
- Excluding unused stdlib modules
- Optional: Excluding optional dependencies (minimal build)
- Binary filtering and UPX compression

**Recommended:** Use `ProjektKraken.spec` (standard build) for general distribution, `ProjektKraken-minimal.spec` when size is critical.
