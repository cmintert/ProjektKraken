---
description: Build the ProjektKraken desktop application
---

This workflow describes how to package ProjektKraken into a standalone Windows executable with optimized size.

## Build Configurations

ProjektKraken now offers two build configurations:

### 1. Standard Build (Recommended)
Includes all features but excludes unused Qt modules for size optimization.

**Features:**
- ✅ Timeline, events, entities (core)
- ✅ Semantic search (if numpy/requests installed)
- ✅ Web server (if fastapi/uvicorn installed)
- ✅ Graph visualization (if pyvis installed)

**Estimated size:** 150-180 MB

### 2. Minimal Build
Smallest possible build with core features only. Optional features will show error messages.

**Features:**
- ✅ Timeline, events, entities (core)
- ❌ Semantic search (not included)
- ❌ Web server (not included)
- ❌ Graph visualization (not included)

**Estimated size:** 80-120 MB (30-50% smaller)

## Prerequisites

1. Ensure you are in the project root
2. Activate your virtual environment

### For Standard Build:
```pwsh
# Install core + optional dependencies
pip install -r requirements.txt
```

### For Minimal Build:
```pwsh
# Install core dependencies only
pip install -r requirements-core.txt
pip install pyinstaller
```

## Build Steps

### Standard Build (with optional features)

```pwsh
pyinstaller ProjektKraken.spec
```

### Minimal Build (core only)

```pwsh
pyinstaller ProjektKraken-minimal.spec
```

## Post-Build

1. The executable and its dependencies will be in the `dist/ProjektKraken/` folder
2. Run `dist/ProjektKraken/ProjektKraken.exe` to start the application
3. Distribute the entire `dist/ProjektKraken/` folder (contains .exe + _internal/)

## Size Optimization

Both spec files include:
- ✅ Excluded unused Qt modules (Qt3D, QtBluetooth, QtMultimedia, etc.)
- ✅ Excluded development tools (pytest, sphinx, ruff, mypy)
- ✅ Excluded unused stdlib modules (tkinter, email, xmlrpc)
- ✅ UPX compression enabled
- ✅ Binary filtering for Qt libraries

**Expected size reduction:** 30-50% compared to unoptimized build

## Troubleshooting

### Build is too large
- Use `ProjektKraken-minimal.spec` for smallest build
- Ensure you install only core dependencies: `pip install -r requirements-core.txt`
- Run `pip list` to verify no unnecessary packages are installed

### Missing features in minimal build
- This is expected - minimal build excludes optional features
- Use `ProjektKraken.spec` (standard build) to include all features
- Or install optional dependencies before building: `pip install -e .[all]`

## Updating the Build

If you add new assets or source folders:
1. Update `added_files` in the appropriate `.spec` file
2. Rerun the build command
