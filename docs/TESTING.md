# Testing Guide

**Version:** 0.15.0 (Beta)  
**Last Updated:** April 2026

Comprehensive guide to testing in ProjektKraken.

---

## Table of Contents

1. [Testing Overview](#testing-overview)
2. [Test Structure](#test-structure)
3. [Running Tests](#running-tests)
4. [Writing Tests](#writing-tests)
5. [Test Fixtures](#test-fixtures)
6. [Testing Patterns](#testing-patterns)
7. [Coverage](#coverage)
8. [Continuous Integration](#continuous-integration)

---

## Testing Overview

### Testing Framework

ProjektKraken uses **pytest** as the primary testing framework with additional plugins:

- **pytest**: Core testing framework
- **pytest-qt**: Qt/PySide6 testing support
- **pytest-cov**: Code coverage measurement
- **pytest-mock**: Mocking support

### Test Philosophy

**Goals:**

1. **Confidence**: Tests should give confidence that code works correctly
2. **Speed**: Tests should run quickly for fast feedback
3. **Isolation**: Tests should not depend on each other
4. **Clarity**: Tests should be easy to read and understand

**Coverage Target**: 95%+ overall, 100% for core business logic.

### Current Findings And Recent Changes

The test suite is large and already provides broad behavioral coverage, but a recent audit
highlighted several maintainability and execution issues that were worth addressing.

**Current findings:**

- The suite is healthy when run from the repository `.venv`; using a global Python
    interpreter can produce misleading import failures.
- The repository currently collects about `3,800+` tests quickly, so collection itself is
    not a bottleneck.
- Some tests had drifted behind the source of truth, especially around `MainWindow` /
    `ConnectionManager` wiring, which caused integration failures when mocks no longer
    reflected real dependencies.
- Several tests define local `qapp` fixtures even though `tests/conftest.py` already
    provides a shared session-scoped `qapp` fixture.
- Several tests create in-memory `DatabaseService` instances in local fixtures instead of
    reusing the shared `db_service` fixture, which increases duplication and can weaken
    cleanup consistency.
- A small number of tests contain placeholder `pass` bodies or outdated comments instead
    of explicit assertions for current behavior.
- The testing documentation had drifted behind the current command architecture and test
    workflow.

**Changes implemented in April 2026:**

- Added a dedicated CI workflow at `.github/workflows/tests.yml` with a `smoke`
    job for critical-path feedback, a parallel `fast-regression` job for `not slow`
    coverage, JUnit XML artifacts, coverage XML artifacts, and offscreen Qt
    environment settings for CI stability.
- Added `smoke`, `req(id)`, and `bug(id)` markers to `pytest.ini`.
- Marked a small, critical path subset of tests as `smoke` to enable fast feedback.
- Fixed integration test drift in `tests/integration/test_main_window_initialization.py`
    so the mocked window matches current `ConnectionManager` dependencies.
- Removed a redundant local `qapp` fixture from that integration test so it now uses the
    shared fixture from `tests/conftest.py`.
- Simplified `tests/unit/repositories/test_entity_repository.py` to reuse the shared
    `db_service` fixture and replaced a placeholder `pass` test with an assertion that
    documents current exact-match repository behavior.
- Updated this guide so examples match the current codebase more closely.

**Recommended next optimization targets:**

- Continue removing duplicated local `qapp` fixtures in favor of the shared session
    fixture.
- Continue migrating ad-hoc in-memory database fixtures to the shared `db_service`
    fixture where file-backed persistence is not required.
- Replace remaining placeholder tests with explicit assertions or remove them if they no
    longer serve a purpose.
- Expand the `smoke` lane carefully with a few more high-value persistence and timeline
    tests while keeping runtime short.

---

## Test Structure

### Directory Organization

```text
tests/
├── conftest.py              # Shared fixtures
├── unit/                    # Fast unit tests
│   ├── test_events.py
│   ├── test_entities.py
│   ├── test_commands.py
│   └── test_repositories.py
├── integration/             # Integration tests
│   ├── test_db_service.py
│   ├── test_commands.py
│   ├── test_main_window_initialization.py
│   └── test_undo_redo_hotkeys.py
├── gui/                     # GUI widget tests
│   ├── test_entity_editor.py
│   ├── test_event_editor.py
│   └── test_timeline.py
├── cli/                     # CLI command tests
│   ├── test_event_cli.py
│   └── test_entity_cli.py
└── security/                # Security tests
    └── test_sql_injection.py
```

### Test Types

| Type | Purpose | Speed | Dependencies |
| ---- | ------- | ----- | ------------ |
| **Unit** | Test individual functions/classes | Fast (ms) | None |
| **Integration** | Test component interactions | Medium (100ms) | Database |
| **GUI** | Test widget behavior | Medium (100ms) | Qt, qtbot |
| **CLI** | Test command-line interface | Fast (ms) | Minimal |
| **Security** | Test for vulnerabilities | Fast (ms) | None |

---

## Running Tests

### Basic Test Execution

**Run all tests:**

```bash
.venv\Scripts\python -m pytest
```

**Run with output:**

```bash
.venv\Scripts\python -m pytest -v
```

**Run specific test file:**

```bash
.venv\Scripts\python -m pytest tests/unit/test_events.py
```

**Run specific test function:**

```bash
.venv\Scripts\python -m pytest tests/unit/test_events.py::test_event_creation
```

**Run critical smoke tests:**

```bash
.venv\Scripts\python -m pytest -m smoke -q
```

**Run specific test class:**

```bash
.venv\Scripts\python -m pytest tests/unit/test_events.py::TestEventCreation
```

---

### Test Markers

**Run by marker:**

```bash
# Run only unit tests
.venv\Scripts\python -m pytest -m unit

# Run only integration tests
.venv\Scripts\python -m pytest -m integration

# Skip slow tests
.venv\Scripts\python -m pytest -m "not slow"

# Run smoke-only critical path
.venv\Scripts\python -m pytest -m smoke
```

**Available markers** (defined in `pytest.ini`):

- `unit`: Fast unit tests
- `integration`: Integration tests with dependencies
- `slow`: Tests that take >1 second
- `smoke`: Critical-path tests for fast CI feedback

---

### Coverage Reports

**Run with coverage:**

```bash
.venv\Scripts\python -m pytest --cov=src --cov-report=term-missing
```

**Generate HTML coverage report:**

```bash
.venv\Scripts\python -m pytest --cov=src --cov-report=html
# Opens htmlcov/index.html
```

**Coverage for specific module:**

```bash
.venv\Scripts\python -m pytest --cov=src.commands tests/unit/test_commands.py
```

**Show missing lines:**

```bash
.venv\Scripts\python -m pytest --cov=src --cov-report=term-missing
```

---

### Useful Options

| Option | Description |
| ------ | ----------- |
| `-v` | Verbose output |
| `-s` | Show print statements |
| `-x` | Stop on first failure |
| `--lf` | Run last failed tests |
| `--ff` | Run failed tests first |
| `-k EXPRESSION` | Run tests matching expression |
| `--pdb` | Drop into debugger on failure |
| `-n NUM` | Run tests in parallel (requires pytest-xdist) |

**Examples:**

```bash
# Run tests with "entity" in name
.venv\Scripts\python -m pytest -k entity

# Run tests, stop on first failure, show prints
.venv\Scripts\python -m pytest -x -s

# Run last failed tests with debugger
.venv\Scripts\python -m pytest --lf --pdb
```

---

## Writing Tests

### Test Naming

**Convention**: `test_<method>_<scenario>_<expected_result>`

**Examples:**

```python
def test_create_event_with_valid_data_returns_event():
    """Test creating an event with valid input."""
    pass

def test_create_event_with_invalid_date_raises_value_error():
    """Test that invalid date raises ValueError."""
    pass

def test_update_entity_with_new_name_updates_database():
    """Test entity name update persists to database."""
    pass
```

---

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

**AAA Pattern** (Arrange, Act, Assert):

1. **Arrange**: Set up test data and preconditions
2. **Act**: Execute the code being tested
3. **Assert**: Verify the expected outcome

---

### Testing with Database

**Use in-memory database:**

```python
import pytest
from src.services.db_service import DatabaseService

@pytest.fixture
def db_service():
    """Provide an in-memory database."""
    service = DatabaseService(":memory:")
    service.connect()
    yield service
    service.close()

def test_event_repository_create(db_service):
    """Test creating an event in the database."""
    from src.services.repositories.event_repository import EventRepository
    from src.core.events import Event
    
    repo = EventRepository(db_service)
    event = Event(name="Test", lore_date=100.0)
    
    result = repo.create(event)
    
    assert result.id == event.id
    assert result.name == "Test"
```

---

### Testing Commands

**Test execute and undo:**

```python
def test_create_event_command_execute(db_service):
    """Test CreateEventCommand execution."""
    from src.commands.event_commands import CreateEventCommand
    from src.services.repositories.event_repository import EventRepository
    
    cmd = CreateEventCommand({"name": "Test Event", "lore_date": 100.0})
    
    result = cmd.execute(db_service)
    
    # Verify event was created
    repo = EventRepository(db_service)
    event = repo.get(cmd.event.id)
    assert result.success is True
    assert event is not None
    assert event.name == "Test Event"

def test_create_event_command_undo(db_service):
    """Test CreateEventCommand undo."""
    from src.commands.event_commands import CreateEventCommand
    from src.services.repositories.event_repository import EventRepository
    
    cmd = CreateEventCommand({"name": "Test Event", "lore_date": 100.0})
    
    cmd.execute(db_service)
    cmd.undo(db_service)
    
    # Verify event was removed
    repo = EventRepository(db_service)
    event = repo.get(cmd.event.id)
    assert event is None
```

---

### Testing Qt Widgets

**Use qtbot fixture:**

```python
import pytest
from PySide6.QtCore import Qt

def test_entity_editor_displays_entity(qtbot):
    """Test EntityEditor displays entity data."""
    from src.gui.widgets.entity_editor import EntityEditor
    
    # Create widget
    editor = EntityEditor()
    qtbot.addWidget(editor)
    
    # Set entity data
    entity_data = {
        "id": "ent_123",
        "name": "Test Entity",
        "type": "character"
    }
    editor.set_entity(entity_data)
    
    # Verify display
    assert editor.name_field.text() == "Test Entity"
    assert editor.type_combo.currentText() == "character"

def test_button_click_emits_signal(qtbot):
    """Test button click emits expected signal."""
    from src.gui.widgets.my_widget import MyWidget
    
    widget = MyWidget()
    qtbot.addWidget(widget)
    
    # Set up signal spy
    with qtbot.waitSignal(widget.button_clicked, timeout=1000):
        qtbot.mouseClick(widget.button, Qt.LeftButton)
```

---

### Mocking

**Use pytest-mock:**

```python
def test_backup_service_calls_database(mocker):
    """Test BackupService calls database methods."""
    from src.services.backup_service import BackupService
    
    # Mock database service
    mock_db = mocker.Mock()
    mock_db.get_connection.return_value = mocker.Mock()
    
    service = BackupService(mock_db)
    service.create_backup("test.db")
    
    # Verify database was called
    mock_db.get_connection.assert_called_once()
```

**Mock file operations:**

```python
def test_save_file(mocker):
    """Test file saving."""
    mock_open = mocker.patch("builtins.open", mocker.mock_open())
    
    save_data("test.txt", "content")
    
    mock_open.assert_called_once_with("test.txt", "w")
```

---

## Test Fixtures

### Common Fixtures

Defined in `tests/conftest.py`:

```python
import pytest
from src.services.db_service import DatabaseService

@pytest.fixture
def db_service():
    """Provide in-memory database service."""
    service = DatabaseService(":memory:")
    service.connect()
    yield service
    service.close()

@pytest.fixture
def sample_event():
    """Provide a sample event."""
    from src.core.events import Event
    return Event(
        id="evt_test",
        name="Test Event",
        lore_date=100.0,
        type="generic"
    )

@pytest.fixture
def sample_entity():
    """Provide a sample entity."""
    from src.core.entities import Entity
    return Entity(
        id="ent_test",
        name="Test Entity",
        type="character"
    )
```

### Fixture Scopes

- **function** (default): New fixture per test function
- **class**: One fixture per test class
- **module**: One fixture per module
- **session**: One fixture per test session

```python
@pytest.fixture(scope="module")
def expensive_resource():
    """Expensive resource shared across module."""
    resource = create_expensive_resource()
    yield resource
    resource.cleanup()
```

---

## Testing Patterns

### Testing Exceptions

```python
def test_invalid_input_raises_value_error():
    """Test that invalid input raises ValueError."""
    from src.core.events import Event
    
    with pytest.raises(ValueError, match="Invalid date"):
        Event(name="Test", lore_date=-1.0)
```

### Parametrized Tests

```python
@pytest.mark.parametrize("input_date,expected", [
    (0.0, "Year 0, Day 0"),
    (1.0, "Year 0, Day 1"),
    (365.0, "Year 1, Day 0"),
])
def test_date_formatting(input_date, expected):
    """Test date formatting with various inputs."""
    result = format_date(input_date)
    assert result == expected
```

### Testing Async Code

```python
import pytest

@pytest.mark.asyncio
async def test_async_function():
    """Test async function."""
    result = await async_operation()
    assert result == expected_value
```

---

## Coverage

### Coverage Goals

| Component | Target Coverage |
| --------- | --------------- |
| **Core Logic** | 100% |
| **Commands** | 100% |
| **Repositories** | 95%+ |
| **Services** | 95%+ |
| **GUI Widgets** | 80%+ |
| **Overall** | 95%+ |

### Measuring Coverage

**Basic coverage:**

```bash
.venv\Scripts\python -m pytest --cov=src
```

**Detailed coverage with missing lines:**

```bash
.venv\Scripts\python -m pytest --cov=src --cov-report=term-missing
```

**HTML coverage report:**

```bash
.venv\Scripts\python -m pytest --cov=src --cov-report=html
open htmlcov/index.html
```

### Coverage Configuration

In `pyproject.toml` or `.coveragerc`:

```ini
[coverage:run]
source = src
omit = 
    */tests/*
    */venv/*
    */__pycache__/*

[coverage:report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
```

---

## Continuous Integration

### GitHub Actions

Current repository workflow:

- `.github/workflows/tests.yml` runs `smoke` tests for rapid feedback.
- `.github/workflows/tests.yml` runs `not slow` regression tests in parallel with
    `pytest-xdist`.
- `.github/workflows/tests.yml` exports JUnit XML reports.
- `.github/workflows/tests.yml` exports coverage artifacts.

Key CI behaviors:

- Set `QT_QPA_PLATFORM=offscreen` for headless Qt runs.
- Set `QT_OPENGL=software` for better graphics stability in CI environments.
- Prefer `.venv` locally and `python -m pytest` in CI to avoid interpreter drift.

Minimal example:

```yaml
name: Tests

on: [push, pull_request]

jobs:
    smoke:
    runs-on: ubuntu-latest
        env:
            QT_QPA_PLATFORM: offscreen
            QT_OPENGL: software

    steps:
            - uses: actions/checkout@v4

            - name: Set up Python
                uses: actions/setup-python@v5
                with:
                    python-version: '3.13'

            - name: Install dependencies
                run: |
                    python -m pip install --upgrade pip
                    pip install -r requirements.txt
                    pip install pytest pytest-qt pytest-cov pytest-xdist

            - name: Run smoke tests
                run: |
                    python -m pytest -m smoke -q --maxfail=1 --junitxml=test-results.xml
```

### Pre-commit Hooks

Install pre-commit hooks to run tests before committing:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: pytest-check
        name: pytest-check
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

## Best Practices

### Do's

✅ **Write tests first (TDD)**

- Clarifies requirements
- Ensures testability
- Prevents over-engineering

✅ **Use descriptive test names**

- Name should describe what's being tested
- Include expected behavior

✅ **One assertion concept per test**

- Test one thing at a time
- Multiple asserts OK if testing same concept

✅ **Use fixtures for setup**

- Reduces code duplication
- Improves test clarity

✅ **Mock external dependencies**

- File I/O, network, time
- Keeps tests fast and deterministic

✅ **Test edge cases**

- Empty inputs, null values
- Boundary conditions
- Error conditions

### Don'ts

❌ **Don't test implementation details**

- Test behavior, not internals
- Tests should survive refactoring

❌ **Don't use production database**

- Always use in-memory database for tests
- Never connect to production

❌ **Don't write flaky tests**

- No random values without seeds
- No time dependencies without mocking
- No network dependencies

❌ **Don't skip test cleanup**

- Always clean up resources
- Use fixtures with yield

❌ **Don't test external libraries**

- Trust that PySide6, SQLite work correctly
- Test your code, not theirs

---

## Troubleshooting

### Common Issues

**Tests fail with "database is locked":**

```python
# Solution: Use in-memory database
@pytest.fixture
def db_service():
    service = DatabaseService(":memory:")
    yield service
    service.close()
```

**Qt tests hang:**

```python
# Solution: Use qtbot properly
def test_widget(qtbot):
    widget = MyWidget()
    qtbot.addWidget(widget)  # Important!
    # Test widget
```

**Import errors:**

```bash
# Solution: Install package in development mode
.venv\Scripts\python -m pip install -e .
```

**Coverage not tracking all files:**

```bash
# Solution: Specify source in pytest command
.venv\Scripts\python -m pytest --cov=src --cov-report=term-missing
```

---

## Example Test Suite

### Complete Example

```python
"""
tests/unit/test_event_repository.py

Tests for EventRepository.
"""

import pytest
from src.services.repositories.event_repository import EventRepository
from src.core.events import Event

@pytest.fixture
def db_service():
    """Provide in-memory database."""
    from src.services.db_service import DatabaseService
    service = DatabaseService(":memory:")
    service.connect()
    yield service
    service.close()

@pytest.fixture
def event_repo(db_service):
    """Provide EventRepository instance."""
    return EventRepository(db_service)

@pytest.fixture
def sample_event():
    """Provide sample event."""
    return Event(
        name="Test Event",
        lore_date=100.0,
        type="battle"
    )

class TestEventRepository:
    """Tests for EventRepository."""
    
    def test_create_event_returns_event(self, event_repo, sample_event):
        """Test creating an event returns the event."""
        result = event_repo.create(sample_event)
        
        assert result.id == sample_event.id
        assert result.name == sample_event.name
    
    def test_get_existing_event_returns_event(self, event_repo, sample_event):
        """Test getting an existing event."""
        event_repo.create(sample_event)
        
        result = event_repo.get(sample_event.id)
        
        assert result is not None
        assert result.id == sample_event.id
    
    def test_get_nonexistent_event_returns_none(self, event_repo):
        """Test getting a nonexistent event returns None."""
        result = event_repo.get("nonexistent_id")
        
        assert result is None
    
    def test_update_event_persists_changes(self, event_repo, sample_event):
        """Test updating an event persists changes."""
        event_repo.create(sample_event)
        
        sample_event.name = "Updated Name"
        event_repo.update(sample_event)
        
        result = event_repo.get(sample_event.id)
        assert result.name == "Updated Name"
    
    def test_delete_event_removes_from_database(self, event_repo, sample_event):
        """Test deleting an event removes it."""
        event_repo.create(sample_event)
        
        success = event_repo.delete(sample_event.id)
        
        assert success is True
        assert event_repo.get(sample_event.id) is None
    
    def test_list_all_returns_all_events(self, event_repo):
        """Test listing all events."""
        event1 = Event(name="Event 1", lore_date=100.0)
        event2 = Event(name="Event 2", lore_date=200.0)
        
        event_repo.create(event1)
        event_repo.create(event2)
        
        results = event_repo.list_all()
        
        assert len(results) == 2
        assert any(e.id == event1.id for e in results)
        assert any(e.id == event2.id for e in results)
```

---

## Next Steps

- **[Development Guide](DEVELOPMENT.md)** - Learn about development workflow
- **[Contributing Guide](CONTRIBUTING.md)** - Contribute to the project
- **[API Reference](API_REFERENCE.md)** - Understand the codebase

---

**Navigation:**  
[← Database](DATABASE.md) • [Back to Index](INDEX.md) • [API Reference →](API_REFERENCE.md)
