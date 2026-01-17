---
**Project:** ProjektKraken  
**Document:** Testing Guide  
**Last Updated:** 2026-01-17  
---

# Testing Guide

This document explains how to run tests for ProjektKraken, including setup requirements for different platforms.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=term-missing
```

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures and configuration
├── unit/                    # Fast unit tests
└── integration/             # Integration tests
    ├── test_main_window_initialization.py
    ├── test_main_window_wiring.py
    └── ...
```

## Dependencies

### Python Dependencies

All Python dependencies are in `requirements.txt`:

- **Testing Framework**: pytest, pytest-qt, pytest-cov
- **GUI Framework**: PySide6 (Qt 6)
- **Web Server**: fastapi, uvicorn (for longform editor live preview)
- **Graph Visualization**: pyvis, networkx
- **Environment Config**: python-dotenv
- And more...

### System Dependencies (Linux/CI)

For headless testing (CI, Linux without display), you need Qt platform libraries:

```bash
# Ubuntu/Debian
sudo apt-get install -y \
    libegl1 \
    libxkbcommon-x11-0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render-util0 \
    libxcb-xinerama0 \
    libxcb-xfixes0
```

These libraries are required for Qt to run in offscreen mode without a display.

## Headless Testing

### Automatic Configuration

The test suite automatically configures Qt to run in offscreen mode via `tests/conftest.py`:

```python
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
```

This allows tests to run without a display server (X11, Wayland, etc.).

### Manual Override

If you need to run tests with a different Qt platform:

```bash
# Linux with display
export QT_QPA_PLATFORM=xcb
pytest

# Force offscreen mode
export QT_QPA_PLATFORM=offscreen
pytest

# Windows (no override needed)
pytest
```

## Platform-Specific Notes

### Windows

- Qt automatically uses the Windows native platform
- No special configuration needed
- System dependencies are included with PySide6

### Linux with Display

- Tests will use offscreen mode by default
- To use the X11 display, set `QT_QPA_PLATFORM=xcb`
- Useful for debugging GUI issues visually

### macOS

- Qt automatically uses the macOS native platform
- No special configuration needed

### CI/CD (GitHub Actions, etc.)

The test suite is designed to work in headless CI environments:

1. Install system dependencies (Linux only)
2. Install Python dependencies from `requirements.txt`
3. Run tests with `pytest`

Example GitHub Actions workflow:

```yaml
- name: Install system dependencies
  if: runner.os == 'Linux'
  run: |
    sudo apt-get update
    sudo apt-get install -y libegl1 libxkbcommon-x11-0 \
      libxcb-icccm4 libxcb-image0 libxcb-keysyms1 \
      libxcb-randr0 libxcb-render-util0 libxcb-xinerama0 \
      libxcb-xfixes0

- name: Install Python dependencies
  run: pip install -r requirements.txt

- name: Run tests
  run: pytest --cov=src --cov-report=term-missing
```

## Test Markers

Tests can be filtered using pytest markers:

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Skip slow tests
pytest -m "not slow"
```

Available markers (defined in `pytest.ini`):
- `unit` - Fast unit tests
- `integration` - Integration tests
- `slow` - Tests that take >1 second

## Known Issues

### Segmentation Fault on Exit

You may see a segmentation fault after all tests pass:

```
12 passed in 1.32s
Release of profile requested but WebEnginePage still not deleted. Expect troubles !
Segmentation fault (core dumped)
```

This is a known issue with Qt WebEngine cleanup in headless mode. The tests themselves pass successfully; the crash occurs during cleanup. This does not affect test results.

## Troubleshooting

### Import Errors

If you see `ModuleNotFoundError` for any package:

```bash
# Reinstall all dependencies
pip install -r requirements.txt
```

### Qt Platform Plugin Errors

If you see errors like "cannot open shared object file: No such file or directory":

1. **Linux**: Install the system dependencies listed above
2. **Windows**: Ensure PySide6 is properly installed
3. **macOS**: Ensure PySide6 is properly installed

### QApplication Instance Errors

If you see errors about QApplication being instantiated multiple times:

- This is handled by the `qapp` fixture in `conftest.py`
- Use the `qtbot` fixture from pytest-qt for GUI tests
- Don't create QApplication instances directly in tests

## Writing Tests

### Unit Tests

Unit tests should:
- Be fast (< 100ms)
- Test a single function or class
- Use mocks for external dependencies
- Be marked with `@pytest.mark.unit`

Example:

```python
import pytest
from src.core.events import Event

@pytest.mark.unit
def test_event_creation():
    """Test that Event instances are created correctly."""
    event = Event(name="Test", lore_date=100.0)
    assert event.name == "Test"
    assert event.lore_date == 100.0
```

### Integration Tests

Integration tests should:
- Test multiple components together
- Use real database (in-memory SQLite)
- Use the `db_service` fixture
- Be marked with `@pytest.mark.integration`

Example:

```python
import pytest
from src.services.db_service import DatabaseService

@pytest.mark.integration
def test_event_persistence(db_service):
    """Test that events are persisted to database."""
    event_id = db_service.create_event("Test", 100.0)
    event = db_service.get_event(event_id)
    assert event.name == "Test"
```

### GUI Tests

GUI tests should:
- Use the `qtbot` fixture from pytest-qt
- Use the `qapp` fixture for QApplication
- Patch menu creation to avoid segfaults (see existing tests)

Example:

```python
from unittest.mock import patch

def test_main_window_creation(qtbot):
    """Test that MainWindow can be created."""
    with patch("src.app.ui_manager.UIManager.create_file_menu"):
        from src.app.main_window import MainWindow
        window = MainWindow()
        qtbot.addWidget(window)
        assert window is not None
```

## Coverage Requirements

- **Minimum**: 95% code coverage
- **Focus**: Core business logic should be 100% covered
- **Exceptions**: GUI glue code, entry points

Run coverage report:

```bash
pytest --cov=src --cov-report=html
# Open htmlcov/index.html in browser
```
