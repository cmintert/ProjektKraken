# Test Environment Setup Guide

This document describes how to set up and use the testing environment for ProjektKraken.

## Quick Start

```bash
# Run the setup script
./setup_env.sh

# Activate the environment
source .venv/bin/activate

# Run tests
pytest tests/
```

## Manual Setup

If you prefer to set up the environment manually:

### 1. Prerequisites

- Python 3.10 or higher (tested with Python 3.12.3)
- pip (Python package installer)
- Git

### 2. Create Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. System Dependencies (Linux)

For Qt applications to work in headless environments, install these system packages:

```bash
# Ubuntu/Debian
sudo apt-get install -y libegl1 libgl1 libxkbcommon-x11-0 libdbus-1-3

# Fedora/RHEL
sudo dnf install -y mesa-libEGL mesa-libGL libxkbcommon-x11 dbus-libs
```

## Running Tests

### All Tests

```bash
pytest tests/
```

### Unit Tests Only

```bash
pytest tests/unit/
```

### Integration Tests Only

```bash
pytest tests/integration/
```

### With Coverage

```bash
pytest --cov=src --cov-report=html tests/
```

The coverage report will be available at `htmlcov/index.html`.

### Specific Test File

```bash
pytest tests/unit/test_constants.py -v
```

### Run Tests with Different Markers

```bash
# Run only fast unit tests
pytest -m unit tests/

# Run all except slow tests
pytest -m "not slow" tests/

# Run integration tests
pytest -m integration tests/
```

## Test Configuration

Test configuration is defined in `pytest.ini`:

- **Test Discovery**: Files matching `test_*.py`
- **Test Classes**: Classes matching `Test*`
- **Test Functions**: Functions matching `test_*`
- **Markers**:
  - `slow`: Marks tests as slow (can be skipped)
  - `unit`: Fast unit tests
  - `integration`: Integration tests

## Qt Testing

The test environment is configured for headless Qt testing:

- **QT_QPA_PLATFORM**: Set to `offscreen` in `tests/conftest.py`
- **pytest-qt**: Provides `qtbot` fixture for Qt testing
- **QApplication**: Automatically managed via session-scoped fixture

### Example Qt Test

```python
def test_widget_creation(qtbot):
    """Test widget can be created."""
    from PySide6.QtWidgets import QWidget
    
    widget = QWidget()
    qtbot.addWidget(widget)
    
    assert widget is not None
```

## Troubleshooting

### Import Errors

If you get import errors, ensure the virtual environment is activated:

```bash
source .venv/bin/activate
which python  # Should point to .venv/bin/python
```

### Qt Library Errors

If you see errors about missing Qt libraries:

```bash
# Check if Qt libraries are installed
python -c "import PySide6; print(PySide6.__version__)"
```

If this fails, reinstall PySide6:

```bash
pip install --force-reinstall PySide6
```

### Display Errors

If tests fail with display-related errors, ensure `QT_QPA_PLATFORM=offscreen` is set.
This should be automatic via `conftest.py`, but you can set it manually:

```bash
export QT_QPA_PLATFORM=offscreen
pytest tests/
```

### Test Failures

Some test failures may be pre-existing issues in the codebase. To identify environment vs. code issues:

1. Run a simple test: `pytest tests/unit/test_constants.py`
2. If this passes, the environment is working correctly
3. Check specific test failures for actual code issues

## Development Workflow

### 1. Activate Environment

```bash
source .venv/bin/activate
```

### 2. Make Changes

Edit source code in `src/` directory.

### 3. Run Tests

```bash
# Quick check
pytest tests/unit/

# Full test suite
pytest tests/

# With coverage
pytest --cov=src tests/
```

### 4. Code Quality

```bash
# Lint with ruff
ruff check src/ tests/

# Type check with mypy
mypy src/

# Format with ruff
ruff format src/ tests/
```

### 5. Deactivate Environment

```bash
deactivate
```

## CI/CD Integration

For continuous integration, use the following commands:

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests with coverage
pytest --cov=src --cov-report=xml --cov-report=term tests/

# Generate coverage badge
coverage-badge -o coverage.svg
```

## Environment Variables

The following environment variables affect testing:

- **QT_QPA_PLATFORM**: Set to `offscreen` for headless testing (automatic)
- **PYTHONPATH**: Project root is added automatically via `conftest.py`

## Installed Packages

Key packages in the test environment:

### Core Framework
- **PySide6** (6.10.1): Qt for Python GUI framework
- **Python** (3.12.3): Programming language

### Testing
- **pytest** (9.0.2): Test framework
- **pytest-qt** (4.5.0): Qt testing support
- **pytest-cov** (7.0.0): Coverage plugin

### Code Quality
- **ruff** (0.14.10): Fast Python linter
- **mypy** (1.19.0): Static type checker

### Documentation
- **Sphinx** (8.2.3): Documentation generator
- **myst-parser** (4.0.1): Markdown support for Sphinx
- **furo** (2025.9.25): Modern Sphinx theme

### Other Dependencies
- **Pillow** (12.0.0): Image processing
- **numpy** (2.4.2): Numerical computing
- **requests** (2.32.3): HTTP library
- **fastapi** (0.128.0): Web framework
- **networkx** (3.6.1): Graph algorithms

See `requirements.txt` for the complete list.

## References

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-qt Documentation](https://pytest-qt.readthedocs.io/)
- [PySide6 Documentation](https://doc.qt.io/qtforpython/)
- [Project README](README.md)
- [Architecture Documentation](ARCHITECTURE.md)
