# Deployment Size Reduction Analysis

## Overview

This document summarizes the changes made to reduce ProjektKraken's deployment size by splitting dependencies into core, optional, and development categories.

## Changes Made

### 1. Dependency Split

Created three separate requirements files:

- **requirements-core.txt**: Essential dependencies for basic functionality
- **requirements-optional.txt**: Optional features (semantic search, web server, graph)
- **requirements-dev.txt**: Development tools (testing, linting, documentation)

### 2. PyProject.toml Updates

Added optional dependency groups:
```toml
[project.optional-dependencies]
search = ["numpy", "requests"]
webserver = ["fastapi", "uvicorn[standard]", "python-multipart"]
graph = ["pyvis"]
all = ["ProjektKraken[search,webserver,graph]"]
dev = [pytest, ruff, mypy, sphinx, ...]
```

### 3. Runtime Checks

Added graceful fallbacks for optional dependencies:
- `src/app/ai_search_manager.py`: Handles missing semantic search dependencies
- `src/services/web_service_manager.py`: Checks for webserver availability
- `src/gui/widgets/graph_view/graph_builder.py`: Handles missing PyVis

### 4. PyInstaller Optimization

Updated `ProjektKraken.spec` to exclude:
- Testing frameworks (pytest, pytest-qt, pytest-cov)
- Documentation tools (Sphinx, myst-parser, furo)
- Development tools (ruff, mypy, black)
- Unused stdlib modules (tkinter, unittest, pdb)

## Estimated Size Impact

### Before Changes

| Category | Packages | Est. Size |
|----------|----------|-----------|
| Core | PySide6, Pillow | ~200 MB |
| Optional | numpy, requests, fastapi, uvicorn, pyvis | ~65 MB |
| Development | pytest, Sphinx, ruff, mypy | ~65 MB |
| **Total** | | **~330 MB** |

### After Changes (Core Only)

| Category | Packages | Est. Size |
|----------|----------|-----------|
| Core | PySide6, Pillow, python-dotenv | ~203 MB |
| **Total** | | **~203 MB** |

### After Changes (With Optional Features)

| Category | Packages | Est. Size |
|----------|----------|-----------|
| Core | PySide6, Pillow, python-dotenv | ~203 MB |
| Optional | numpy, requests, fastapi, uvicorn, pyvis | ~65 MB |
| **Total** | | **~268 MB** |

## Size Reduction

- **Development environment**: ~62 MB saved by excluding dev tools from deployment
- **Minimal deployment**: ~127 MB saved by making optional features truly optional
- **PyInstaller build**: Additional savings from excluding test/dev modules

## Installation Options

Users can now choose their installation level:

### Minimal (Core)
```bash
pip install -r requirements-core.txt
```
- Basic timeline, events, entities
- Image attachments
- Local file storage
- ~203 MB installed size

### With Optional Features
```bash
pip install -e .[all]
```
- All core features
- Semantic search (AI)
- Web server (longform)
- Graph visualization
- ~268 MB installed size

### Full Development
```bash
pip install -r requirements.txt
```
- All features
- Testing frameworks
- Linting tools
- Documentation builders
- ~330 MB installed size

## PyInstaller Build Improvements

The updated spec file excludes ~65 MB of development dependencies that were previously included in builds:

- pytest and testing frameworks
- Sphinx and documentation tools
- ruff, mypy, black linters
- tkinter, unittest, pdb (unused stdlib)

Expected PyInstaller build size reduction: **15-25%** (varies by platform)

## Breaking Changes

**None.** All changes are backward compatible:

- `requirements.txt` still installs everything (via includes)
- Existing installations continue to work
- Runtime checks provide clear error messages if optional deps missing
- Documentation updated with clear installation instructions

## User Impact

### Developers
- No change: `pip install -r requirements.txt` installs everything
- Can now use `requirements-core.txt` for faster CI builds

### End Users (Windows Executable)
- Smaller download size (15-25% reduction)
- Faster application startup (fewer modules to load)
- Same functionality if optional features included in build

### Power Users (From Source)
- Can install minimal core for basic usage
- Can selectively install only needed optional features
- Clear documentation on what each feature requires

## Testing

Added `tests/test_optional_dependencies.py` to verify:
- Optional dependency flags exist
- Requirements files are properly structured
- pyproject.toml has correct optional groups
- Modules handle missing dependencies gracefully

## Documentation

Created/updated:
- `docs/INSTALLATION.md`: Comprehensive installation guide
- `README.md`: Updated with minimal and full install options
- Requirements files: Comments explaining each dependency's purpose

## Future Improvements

Potential further optimizations:
1. Split PySide6 into minimal Qt modules (if possible)
2. Lazy-load heavy optional dependencies
3. Consider alternative lighter-weight image processing libraries
4. Profile actual PyInstaller build to identify other bloat

## Conclusion

These changes provide significant deployment size reduction while maintaining full backward compatibility and giving users flexibility in choosing their installation level.
