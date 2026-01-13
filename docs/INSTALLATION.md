# Installation Guide

This guide covers different ways to install ProjektKraken, from minimal core dependencies to full development setup.

## Quick Start (Windows)

Download the latest release from GitHub Releases. The application is portable - simply extract and run `ProjektKraken.exe`. No Python installation required.

## From Source

### Core Installation (Minimal)

For the basic application with timeline, entities, and basic editing:

```bash
# Clone the repository
git clone https://github.com/cmintert/ProjektKraken.git
cd ProjektKraken

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# Install core dependencies only
pip install -r requirements-core.txt
```

**Core dependencies include:**
- PySide6 (Qt GUI framework)
- Pillow (image processing)
- python-dotenv (environment configuration)

### Optional Features

#### Semantic Search (AI Search Panel)

Enables natural language search using local embeddings:

```bash
pip install -r requirements-optional.txt
# or specifically:
pip install -e .[search]
```

**Requires:**
- numpy (vector operations)
- requests (API communication)
- LM Studio or compatible embedding server

See [Semantic Search Documentation](SEMANTIC_SEARCH.md) for setup.

#### Web Server (Longform Editor)

Enables the embedded web server for advanced longform editing:

```bash
pip install -e .[webserver]
```

**Requires:**
- fastapi (web framework)
- uvicorn (ASGI server)
- python-multipart (file uploads)

#### Graph Visualization

Enables the interactive network graph view:

```bash
pip install -e .[graph]
```

**Requires:**
- pyvis (network graph library)

### All Optional Features

To install all optional features at once:

```bash
pip install -r requirements-optional.txt
# or:
pip install -e .[all]
```

### Development Setup

For contributing to ProjektKraken (includes testing, linting, documentation):

```bash
# Install everything (core + optional + dev tools)
pip install -r requirements.txt
# or:
pip install -e .[dev,all]
```

**Development dependencies include:**
- pytest, pytest-qt, pytest-cov (testing)
- ruff, mypy (code quality)
- Sphinx, myst-parser, furo (documentation)
- pyinstaller (building executables)

## Dependency Summary

### Core Dependencies (Required)
| Package | Purpose | Size Impact |
|---------|---------|-------------|
| PySide6 | GUI framework | ~200 MB |
| Pillow | Image processing | ~3 MB |
| python-dotenv | Config management | <1 MB |

### Optional Dependencies
| Feature | Packages | Size Impact |
|---------|----------|-------------|
| Semantic Search | numpy, requests | ~50 MB |
| Web Server | fastapi, uvicorn, python-multipart | ~10 MB |
| Graph View | pyvis | ~5 MB |

### Development Dependencies (Not for deployment)
| Category | Packages | Size Impact |
|----------|----------|-------------|
| Testing | pytest, pytest-qt, pytest-cov | ~15 MB |
| Linting | ruff, mypy | ~20 MB |
| Docs | Sphinx, myst-parser, furo | ~30 MB |

## Building from Source

### Development Run

```bash
python -m src.app.main
```

### Building Executable (Windows)

```bash
# Install build dependencies
pip install pyinstaller

# Build
pyinstaller ProjektKraken.spec

# Output will be in dist/ProjektKraken/
```

**Note:** The build process automatically excludes development and testing dependencies to minimize deployment size.

## Verifying Installation

Check which features are available:

```python
# Run in Python
from src.services.web_service_manager import WEBSERVER_AVAILABLE
from src.gui.widgets.graph_view.graph_builder import PYVIS_AVAILABLE

print(f"Web Server: {WEBSERVER_AVAILABLE}")
print(f"Graph View: {PYVIS_AVAILABLE}")

try:
    from src.services.search_service import create_search_service
    print("Semantic Search: True")
except ImportError:
    print("Semantic Search: False")
```

Or run the application - unavailable features will display helpful error messages.

## Troubleshooting

### Missing Dependencies

If you see errors like "module not found", you may need to install optional dependencies:

```bash
# For semantic search errors
pip install -e .[search]

# For web server errors
pip install -e .[webserver]

# For graph visualization errors
pip install -e .[graph]
```

### Import Errors

If you get import errors even after installing dependencies, try:

```bash
# Reinstall in development mode
pip install -e .
```

### Build Size Issues

If your PyInstaller build is too large:

1. Ensure you're not installing dev dependencies: `pip install requirements-core.txt requirements-optional.txt`
2. The spec file already excludes test frameworks and dev tools
3. Consider excluding unused optional features (edit `ProjektKraken.spec`)

## Next Steps

- **Basic Usage**: See [README.md](../README.md)
- **CLI Tools**: See [CLI Documentation](../src/cli/README.md)
- **Semantic Search**: See [Semantic Search Guide](SEMANTIC_SEARCH.md)
- **Development**: See [DEVELOPMENT.md](DEVELOPMENT.md)
