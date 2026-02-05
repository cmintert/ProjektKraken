# Testing Guide

This document covers testing practices, patterns, and guidelines for ProjektKraken.

## Table of Contents

1. [Overview](#overview)
2. [Test Organization](#test-organization)
3. [Running Tests](#running-tests)
4. [Writing Tests](#writing-tests)
5. [Test Coverage](#test-coverage)
6. [Testing Patterns](#testing-patterns)
7. [Testing Qt Components](#testing-qt-components)
8. [Mocking and Test Doubles](#mocking-and-test-doubles)
9. [CI/CD Integration](#cicd-integration)
10. [Troubleshooting](#troubleshooting)

---

## Overview

ProjektKraken uses **pytest** as its testing framework with **pytest-qt** for GUI testing.

### Testing Philosophy

- **Test-Driven Development (TDD):** Write tests before implementation
- **High Coverage:** Target 95%+ code coverage
- **Fast Feedback:** Unit tests should run in milliseconds
- **Isolation:** Each test is independent and can run in any order
- **Clarity:** Tests are documentation - make them readable

### Test Types

| Type | Speed | Scope | Examples |
|------|-------|-------|----------|
| **Unit** | Fast (ms) | Single function/class | Event creation, date parsing |
| **Integration** | Medium (100ms) | Multiple components | Command execution, database operations |
| **E2E** | Slow (1s+) | Full application | UI workflows, signal chains |

---

## Test Organization

### Directory Structure

```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures
├── unit/                    # Fast unit tests
│   ├── core/               # Tests for src/core/
│   ├── services/           # Tests for src/services/
│   └── commands/           # Tests for src/commands/
├── integration/             # Integration tests
│   ├── test_commands.py
│   ├── test_main_window_wiring.py
│   └── test_db_isolation.py
├── gui/                     # GUI widget tests
│   ├── test_event_editor.py
│   └── test_timeline_widget.py
└── cli/                     # CLI tool tests
    └── test_cli_commands.py
```

### Test File Naming

- **Pattern:** `test_*.py`
- **Match source:** `src/core/events.py` → `tests/unit/core/test_events.py`
- **Descriptive:** `test_timeline_grouping.py` (feature-based)

### Test Function Naming

```python
def test_event_creation():
    """Test basic event creation."""
    pass

def test_event_creation_with_duration():
    """Test event creation with duration specified."""
    pass

def test_event_creation_invalid_date():
    """Test event creation with invalid date raises ValueError."""
    pass
```

**Pattern:** `test_<what>_<conditions>_<expected_outcome>`

---

## Running Tests

### All Tests

```bash
pytest
```

### With Coverage

```bash
pytest --cov=src --cov-report=term-missing
```

### Only Unit Tests

```bash
pytest tests/unit/ -m unit
```

### Only Integration Tests

```bash
pytest tests/integration/ -m integration
```

### Specific Test File

```bash
pytest tests/unit/core/test_events.py
```

### Specific Test Function

```bash
pytest tests/unit/core/test_events.py::test_event_creation
```

### Skip Slow Tests

```bash
pytest -m "not slow"
```

### Verbose Output

```bash
pytest -v
```

### Stop on First Failure

```bash
pytest -x
```

### Show Local Variables on Failure

```bash
pytest -l
```

### Run Tests in Parallel (faster)

```bash
pip install pytest-xdist
pytest -n auto
```

---

## Writing Tests

### Basic Test Structure

```python
import pytest
from src.core.events import Event

def test_event_creation():
    """Test that Event instances are created correctly."""
    # Arrange
    name = "Test Event"
    lore_date = 100.0
    
    # Act
    event = Event(name=name, lore_date=lore_date)
    
    # Assert
    assert event.name == name
    assert event.lore_date == lore_date
    assert event.id is not None
    assert event.type == "generic"
```

**AAA Pattern:** Arrange, Act, Assert

### Using Fixtures

Fixtures provide reusable test setup:

```python
@pytest.fixture
def sample_event():
    """Provides a sample event for testing."""
    return Event(
        name="Sample Event",
        lore_date=100.0,
        type="generic"
    )

def test_event_to_dict(sample_event):
    """Test event serialization to dict."""
    data = sample_event.to_dict()
    
    assert data["name"] == "Sample Event"
    assert data["lore_date"] == 100.0
    assert "id" in data
```

### Parametrized Tests

Test multiple inputs with one test function:

```python
@pytest.mark.parametrize("input_date,expected", [
    (0.0, "Day 0"),
    (1.0, "Day 1"),
    (365.0, "Year 1, Day 1"),
    (-1.0, "Day -1"),
])
def test_date_formatting(input_date, expected):
    """Test date formatting with various inputs."""
    result = format_lore_date(input_date)
    assert result == expected
```

### Testing Exceptions

```python
def test_event_creation_invalid_duration():
    """Test that negative duration raises ValueError."""
    with pytest.raises(ValueError, match="Duration cannot be negative"):
        Event(name="Test", lore_date=0.0, lore_duration=-10.0)
```

### Testing Warnings

```python
def test_deprecated_function():
    """Test that deprecated function warns."""
    with pytest.warns(DeprecationWarning):
        old_function()
```

---

## Test Coverage

### Coverage Requirements

- **Minimum:** 95% overall coverage
- **Core modules:** 100% coverage required
- **GUI widgets:** 80%+ coverage (UI code harder to test)
- **Tests themselves:** No coverage required

### Running Coverage Report

```bash
pytest --cov=src --cov-report=term-missing
```

**Output:**

```
Name                          Stmts   Miss  Cover   Missing
-----------------------------------------------------------
src/core/events.py               45      2    96%   67-68
src/core/entities.py             40      0   100%
src/services/db_service.py      150      8    95%   234-241
-----------------------------------------------------------
TOTAL                          1234     45    96%
```

### HTML Coverage Report

```bash
pytest --cov=src --cov-report=html
open htmlcov/index.html
```

### Coverage Configuration

In `pyproject.toml`:

```toml
[tool.coverage.run]
source = ["src"]
omit = [
    "tests/*",
    "src/__init__.py",
    "*/__pycache__/*"
]

[tool.coverage.report]
precision = 2
show_missing = true
skip_covered = false
```

### Measuring Coverage for Specific Module

```bash
pytest --cov=src.core.events --cov-report=term-missing tests/unit/core/test_events.py
```

---

## Testing Patterns

### Testing Dataclasses

```python
from src.core.events import Event

def test_event_defaults():
    """Test that Event has correct default values."""
    event = Event(name="Test", lore_date=0.0)
    
    assert event.description == ""
    assert event.type == "generic"
    assert event.lore_duration == 0.0
    assert event.attributes == {}
    assert event.id is not None

def test_event_serialization():
    """Test Event to_dict and from_dict."""
    original = Event(
        name="Test",
        lore_date=100.0,
        description="Test event"
    )
    
    # Serialize
    data = original.to_dict()
    
    # Deserialize
    loaded = Event.from_dict(data)
    
    assert loaded.name == original.name
    assert loaded.lore_date == original.lore_date
    assert loaded.id == original.id
```

### Testing Database Operations

```python
def test_event_crud(db_service):
    """Test event CRUD operations."""
    from src.core.events import Event
    
    # Create
    event = Event(name="Test", lore_date=100.0)
    db_service.event_repo.insert(event)
    
    # Read
    loaded = db_service.event_repo.get_by_id(event.id)
    assert loaded is not None
    assert loaded.name == "Test"
    
    # Update
    loaded.name = "Updated"
    db_service.event_repo.update(loaded)
    updated = db_service.event_repo.get_by_id(event.id)
    assert updated.name == "Updated"
    
    # Delete
    db_service.event_repo.delete(event.id)
    deleted = db_service.event_repo.get_by_id(event.id)
    assert deleted is None
```

### Testing Commands

```python
def test_create_event_command(db_service):
    """Test CreateEventCommand execution and undo."""
    from src.commands.event_commands import CreateEventCommand
    
    # Execute command
    cmd = CreateEventCommand(name="Test", lore_date=100.0)
    result = cmd.execute(db_service)
    
    assert result.success is True
    assert "event_id" in result.data
    
    # Verify event exists
    event_id = result.data["event_id"]
    event = db_service.event_repo.get_by_id(event_id)
    assert event is not None
    
    # Undo command
    cmd.undo(db_service)
    
    # Verify event removed
    event = db_service.event_repo.get_by_id(event_id)
    assert event is None
```

### Testing Services

```python
def test_search_service(db_service):
    """Test search service finds events by name."""
    from src.core.events import Event
    from src.services.search_service import SearchService
    
    # Setup: Create test events
    events = [
        Event(name="Battle of Helm's Deep", lore_date=100.0),
        Event(name="Council of Elrond", lore_date=50.0),
        Event(name="Battle of Pelennor Fields", lore_date=120.0),
    ]
    for event in events:
        db_service.event_repo.insert(event)
    
    # Test: Search for "battle"
    search_service = SearchService(db_service)
    results = search_service.search_events("battle")
    
    assert len(results) == 2
    assert all("battle" in r.name.lower() for r in results)
```

---

## Testing Qt Components

### Using pytest-qt

The `qtbot` fixture provides tools for testing Qt widgets:

```python
def test_event_editor_init(qtbot):
    """Test EventEditor initialization."""
    from src.gui.widgets.event_editor import EventEditorWidget
    
    widget = EventEditorWidget()
    qtbot.addWidget(widget)  # Ensure proper cleanup
    
    assert widget.name_edit is not None
    assert not widget.isEnabled()  # Disabled until loaded
```

### Testing Signals

```python
def test_event_editor_emits_save_signal(qtbot, sample_event):
    """Test that EventEditor emits save_requested signal."""
    from src.gui.widgets.event_editor import EventEditorWidget
    
    widget = EventEditorWidget()
    qtbot.addWidget(widget)
    widget.load_event(sample_event)
    
    # Change data
    widget.name_edit.setText("New Name")
    
    # Wait for signal
    with qtbot.waitSignal(widget.save_requested, timeout=1000) as blocker:
        widget.btn_save.click()
    
    # Verify signal data
    saved_data = blocker.args[0]
    assert saved_data["name"] == "New Name"
```

### Testing User Interactions

```python
def test_button_click(qtbot):
    """Test button click interaction."""
    from PySide6.QtWidgets import QPushButton
    
    button = QPushButton("Click Me")
    qtbot.addWidget(button)
    
    clicked = False
    def on_click():
        nonlocal clicked
        clicked = True
    
    button.clicked.connect(on_click)
    qtbot.mouseClick(button, Qt.LeftButton)
    
    assert clicked is True
```

### Testing Keyboard Input

```python
def test_text_input(qtbot):
    """Test text input in QLineEdit."""
    from PySide6.QtWidgets import QLineEdit
    from PySide6.QtCore import Qt
    
    line_edit = QLineEdit()
    qtbot.addWidget(line_edit)
    
    qtbot.keyClicks(line_edit, "Test Text")
    assert line_edit.text() == "Test Text"
    
    qtbot.keyClick(line_edit, Qt.Key_Backspace)
    assert line_edit.text() == "Test Tex"
```

### Waiting for Async Operations

```python
def test_async_loading(qtbot, db_service):
    """Test async data loading."""
    from src.gui.widgets.event_list import EventListWidget
    
    widget = EventListWidget(db_service)
    qtbot.addWidget(widget)
    
    # Trigger load
    widget.load_events()
    
    # Wait for loading to complete
    qtbot.waitUntil(lambda: widget.is_loaded, timeout=5000)
    
    assert widget.model().rowCount() > 0
```

### Testing Dialogs

```python
def test_dialog_accept(qtbot, monkeypatch):
    """Test dialog acceptance flow."""
    from src.gui.dialogs.event_dialog import EventEditDialog
    from PySide6.QtWidgets import QDialogButtonBox
    
    dialog = EventEditDialog()
    qtbot.addWidget(dialog)
    
    # Mock exec to avoid blocking
    monkeypatch.setattr(dialog, "exec", lambda: True)
    
    # Fill form
    dialog.name_edit.setText("New Event")
    dialog.date_edit.setValue(100.0)
    
    # Accept dialog
    result = dialog.exec()
    assert result is True
    
    # Check data
    data = dialog.get_data()
    assert data["name"] == "New Event"
```

---

## Mocking and Test Doubles

### Using unittest.mock

```python
from unittest.mock import Mock, MagicMock, patch

def test_with_mock_service():
    """Test using a mock service."""
    mock_service = Mock()
    mock_service.get_event.return_value = Event(name="Test", lore_date=0.0)
    
    result = some_function(mock_service)
    
    mock_service.get_event.assert_called_once()
```

### Mocking Database

```python
def test_with_mock_database(monkeypatch):
    """Test with mocked database."""
    from src.services.db_service import DatabaseService
    
    mock_db = Mock(spec=DatabaseService)
    mock_db.event_repo.get_all.return_value = []
    
    # Use in test
    result = load_timeline(mock_db)
    assert result == []
```

### Patching

```python
@patch("src.services.backup_service.shutil.copy")
def test_backup_file(mock_copy, db_service):
    """Test file backup with mocked file operations."""
    from src.services.backup_service import BackupService
    
    backup_service = BackupService()
    backup_service.backup_database(db_service)
    
    mock_copy.assert_called_once()
```

### Fixture-Based Mocks

```python
@pytest.fixture
def mock_worker():
    """Provides a mock Worker for testing."""
    worker = Mock()
    worker.submit_task = Mock()
    return worker

def test_with_mock_worker(mock_worker):
    """Test using mock worker fixture."""
    from src.app.main_window import MainWindow
    
    window = MainWindow(worker=mock_worker)
    window.load_events()
    
    mock_worker.submit_task.assert_called_once()
```

---

## CI/CD Integration

### GitHub Actions Workflow

`.github/workflows/test.yml`:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.13'
      
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      
      - name: Run tests
        run: |
          pytest --cov=src --cov-report=xml --cov-report=term
        env:
          QT_QPA_PLATFORM: offscreen
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
```

### Pre-commit Hooks

`.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: pytest
        name: pytest
        entry: pytest
        language: system
        pass_filenames: false
        always_run: true
```

Install hooks:

```bash
pip install pre-commit
pre-commit install
```

---

## Shared Fixtures

Located in `tests/conftest.py`:

### Database Fixture

```python
@pytest.fixture
def db_service():
    """Provides a fresh in-memory database for each test."""
    from src.services.db_service import DatabaseService
    
    service = DatabaseService(":memory:")
    service.connect()
    yield service
    service.close()
```

### QApplication Fixture

```python
@pytest.fixture(scope="session")
def qapp():
    """Ensure QApplication is instantiated only once."""
    from PySide6.QtWidgets import QApplication
    
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
```

### Theme Manager Fixture

```python
@pytest.fixture(autouse=True, scope="session")
def init_theme_manager():
    """Ensures ThemeManager is initialized for all tests."""
    from src.core.theme_manager import ThemeManager
    
    tm = ThemeManager("themes.json")
    theme = tm.get_theme()
    assert "surface" in theme
```

### Sample Data Fixtures

```python
@pytest.fixture
def sample_event():
    """Provides a sample event."""
    return Event(name="Test Event", lore_date=100.0)

@pytest.fixture
def sample_entity():
    """Provides a sample entity."""
    return Entity(name="Test Entity", type="person")

@pytest.fixture
def sample_events(db_service):
    """Provides a list of events in the database."""
    events = [
        Event(name="Event 1", lore_date=10.0),
        Event(name="Event 2", lore_date=20.0),
        Event(name="Event 3", lore_date=30.0),
    ]
    for event in events:
        db_service.event_repo.insert(event)
    return events
```

---

## Troubleshooting

### Qt Platform Plugin Error

If you see `qt.qpa.plugin: Could not find the Qt platform plugin`:

```bash
export QT_QPA_PLATFORM=offscreen
pytest
```

Or set in `pytest.ini`:

```ini
[pytest]
qt_api = pyside6
```

### Tests Pass Locally but Fail in CI

Common causes:
- **Missing environment variables:** Set in CI config
- **Display required:** Use `QT_QPA_PLATFORM=offscreen`
- **Timing issues:** Increase timeouts for slower CI machines
- **File paths:** Use `pathlib` for cross-platform paths

### Flaky Tests

Tests that sometimes pass and sometimes fail:

**Solutions:**
- Increase timeouts: `qtbot.waitSignal(signal, timeout=5000)`
- Add explicit waits: `qtbot.waitUntil(lambda: condition, timeout=1000)`
- Use fixtures instead of global state
- Ensure proper cleanup with `qtbot.addWidget(widget)`

### Memory Leaks in Tests

Use in-memory database and proper cleanup:

```python
@pytest.fixture
def db_service():
    service = DatabaseService(":memory:")
    service.connect()
    yield service
    service.close()  # Important!
```

### Slow Tests

Optimize slow tests:
- Mark as `@pytest.mark.slow`
- Use mocks instead of real services
- Reduce sleep/wait times
- Run in parallel with `pytest-xdist`

---

## Best Practices

1. **Keep tests focused:** One assertion per test when possible
2. **Use descriptive names:** Test names should describe behavior
3. **Avoid test interdependence:** Each test should run independently
4. **Clean up resources:** Use fixtures and context managers
5. **Test edge cases:** Empty inputs, None values, boundary conditions
6. **Test error handling:** Verify exceptions are raised correctly
7. **Mock external dependencies:** Don't depend on network, file system, etc.
8. **Keep tests fast:** Unit tests should run in milliseconds
9. **Document complex tests:** Add docstrings explaining what's being tested
10. **Run tests frequently:** Before commits, during development

---

## Additional Resources

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-qt Documentation](https://pytest-qt.readthedocs.io/)
- [unittest.mock Documentation](https://docs.python.org/3/library/unittest.mock.html)
- [Coverage.py Documentation](https://coverage.readthedocs.io/)

---

## Questions?

- **Issues:** https://github.com/yourusername/ProjektKraken/issues
- **Discussions:** https://github.com/yourusername/ProjektKraken/discussions
