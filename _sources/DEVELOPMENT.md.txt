# Development Guide

**Version:** 0.18.6 (Beta)
**Last Updated:** February 2026

Guide for developers contributing to or extending ProjektKraken.

---

## Table of Contents

1. [Development Setup](#development-setup)
2. [Project Structure](#project-structure)
3. [Coding Standards](#coding-standards)
4. [Development Workflow](#development-workflow)
5. [Building and Testing](#building-and-testing)
6. [Debugging](#debugging)
7. [Common Tasks](#common-tasks)
8. [Best Practices](#best-practices)

---

## Development Setup

### Prerequisites

- **Python 3.13+** (minimum required)
- **Git** for version control
- **pip** package manager
- **virtualenv** or **venv** (recommended)

### Initial Setup

1. **Clone Repository**

   ```bash
   git clone https://github.com/cmintert/ProjektKraken.git
   cd ProjektKraken
   ```

2. **Create Virtual Environment**

   ```bash
   python -m venv .venv
   ```

3. **Activate Virtual Environment**

   **Windows:**
   ```bash
   .venv\Scripts\activate
   ```

   **macOS/Linux:**
   ```bash
   source .venv/bin/activate
   ```

4. **Install Dependencies**

   ```bash
   pip install -r requirements.txt
   ```

5. **Install Development Tools**

   ```bash
   pip install -r requirements.txt
   ```

   This installs:
   - **pytest**: Testing framework
   - **pytest-qt**: Qt testing support
   - **pytest-cov**: Code coverage
   - **ruff**: Fast Python linter and formatter
   - **mypy**: Static type checking
   - **black**: Code formatter (backup)

6. **Verify Installation**

   ```powershell
   .\start-kraken.cmd
   ```

   The launcher should report a healthy Python 3.13 environment and start the
   application successfully.

---

## Project Structure

```
ProjektKraken/
├── src/                      # Source code
│   ├── app/                  # Application layer
│   │   ├── main.py          # Entry point
│   │   ├── main_window.py   # Main UI coordinator
│   │   ├── command_coordinator.py
│   │   └── worker_manager.py
│   ├── commands/             # Command pattern implementation
│   │   ├── base_command.py  # Abstract base class
│   │   ├── event_commands.py
│   │   ├── entity_commands.py
│   │   └── relation_commands.py
│   ├── core/                 # Domain models and utilities
│   │   ├── events.py        # Event dataclass
│   │   ├── entities.py      # Entity dataclass
│   │   ├── relations.py     # Relation dataclass
│   │   ├── calendar.py      # Calendar model
│   │   └── theme_manager.py # UI theming
│   ├── services/             # Business logic layer
│   │   ├── db_service.py    # Database interface
│   │   ├── repositories/    # Data access
│   │   │   ├── event_repository.py
│   │   │   ├── entity_repository.py
│   │   │   └── relation_repository.py
│   │   ├── history_service.py
│   │   ├── backup_service.py
│   │   └── rag_service.py
│   ├── gui/                  # GUI layer
│   │   ├── widgets/         # Custom widgets
│   │   │   ├── timeline/
│   │   │   ├── map/
│   │   │   ├── entity_editor.py
│   │   │   ├── event_editor.py
│   │   │   └── unified_list.py
│   │   ├── dialogs/         # Modal dialogs
│   │   └── utils/           # GUI utilities
│   ├── cli/                  # Command-line interface
│   │   ├── event.py
│   │   ├── entity.py
│   │   └── import.py
│   └── resources/            # Static resources
│       ├── icons/
│       └── images/
├── tests/                    # Test suite
│   ├── unit/                # Unit tests
│   │   ├── test_events.py
│   │   ├── test_entities.py
│   │   └── test_commands.py
│   └── integration/         # Integration tests
│       ├── test_db_service.py
│       └── test_workflows.py
├── docs/                     # Documentation
├── default_assets/           # Default assets
├── themes.json               # UI themes
├── requirements.txt          # Runtime dependencies
├── requirements.txt          # Runtime and development dependencies
├── pyproject.toml           # Project configuration
├── pytest.ini               # Pytest configuration
├── .flake8                  # Flake8 configuration
├── launcher.py              # Development launcher
└── README.md                # Project README
```

---

## Coding Standards

### Python Style

ProjektKraken follows **PEP 8** with some modifications:

- **Line Length**: 88 characters (Black default)
- **Indentation**: 4 spaces
- **Quotes**: Double quotes for strings
- **Imports**: Organized by stdlib → third-party → local

### Type Hints

**Required** for all function signatures:

```python
def create_event(name: str, lore_date: float) -> Event:
    """Create a new event."""
    pass

# Bad - no type hints
def create_event(name, lore_date):
    pass
```

### Docstrings

**Google Style** docstrings required for all public classes and methods:

```python
def update_entity(entity_id: str, **kwargs: Any) -> Entity:
    """
    Update an existing entity with new properties.

    Args:
        entity_id: The unique identifier of the entity.
        **kwargs: Key-value pairs of properties to update.

    Returns:
        Entity: The updated entity object.

    Raises:
        ValueError: If entity_id is invalid.
        DatabaseError: If update fails.
    """
    pass
```

**Required Sections:**
- Brief description (one line)
- **Args**: All parameters with types and descriptions
- **Returns**: Return type and description
- **Raises**: Exceptions that may be raised

### Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| **Classes** | PascalCase | `EventRepository`, `CommandCoordinator` |
| **Functions** | snake_case | `create_event`, `get_entities` |
| **Variables** | snake_case | `event_id`, `lore_date` |
| **Constants** | UPPER_SNAKE_CASE | `DEFAULT_CALENDAR`, `MAX_EVENTS` |
| **Private** | _leading_underscore | `_internal_method`, `_cache` |
| **Protected** | _leading_underscore | `_widget`, `_service` |

### Code Organization

**Imports Order:**

```python
# 1. Standard library
import os
import sys
from typing import List, Optional

# 2. Third-party
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QWidget

# 3. Local application
from src.core.events import Event
from src.services.db_service import DatabaseService
```

**No wildcard imports:**

```python
# Bad
from PySide6.QtWidgets import *

# Good
from PySide6.QtWidgets import QWidget, QPushButton, QVBoxLayout
```

---

## Development Workflow

### 1. Creating a Feature Branch

```bash
git checkout -b feature/my-new-feature
```

### 2. Making Changes

Follow the coding standards and write tests for new code.

### 3. Running Linters

**Ruff (recommended):**

```bash
# Check code
ruff check src/

# Auto-fix issues
ruff check src/ --fix

# Format code
ruff format src/
```

**Flake8 (fallback):**

```bash
flake8 src/ tests/
```

**MyPy (type checking):**

```bash
mypy src/
```

### 4. Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=src --cov-report=term-missing

# Specific test file
pytest tests/unit/test_events.py

# Specific test function
pytest tests/unit/test_events.py::test_event_creation
```

### 5. Committing Changes

```bash
git add .
git commit -m "feat: Add new feature description"
```

**Commit Message Format:**

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `refactor:` Code refactoring
- `test:` Adding or updating tests
- `chore:` Maintenance tasks

### 6. Pushing and Pull Request

```bash
git push origin feature/my-new-feature
```

Then create a Pull Request on GitHub.

---

## Building and Testing

### Running the Application

**Windows (recommended, with environment preflight):**

```powershell
.\start-kraken.cmd
```

**Cross-platform module entry point:**

```bash
python -m src.app.main
```

Run `python launcher.py --check` to verify Python and the required runtime modules
without opening the GUI. In VS Code, use **Run and Debug → ProjektKraken: Launch**;
the checked-in launch configuration uses the same launcher and working directory.

**With Debugging:**

```bash
python -m pdb -m src.app.main
```

### Running Tests

**All Tests:**

```bash
pytest
```

**Unit Tests Only:**

```bash
pytest tests/unit/
```

**Integration Tests Only:**

```bash
pytest tests/integration/
```

**With Coverage Report:**

```bash
pytest --cov=src --cov-report=html
# Opens htmlcov/index.html
```

**With Markers:**

```bash
# Run only fast tests
pytest -m "not slow"

# Run only unit tests
pytest -m unit
```

### Building Executable

**Using PyInstaller:**

```bash
pyinstaller ProjektKraken.spec
```

Output in `dist/ProjektKraken/`.

**Testing Build:**

```bash
cd dist/ProjektKraken
./ProjektKraken  # or ProjektKraken.exe on Windows
```

---

## Debugging

### Debug Mode

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Or via environment variable:

```bash
export KRAKEN_DEBUG=1
python -m src.app.main
```

### PDB Debugger

```python
import pdb

def my_function():
    x = calculate_something()
    pdb.set_trace()  # Breakpoint here
    y = process(x)
```

**PDB Commands:**
- `n` - Next line
- `s` - Step into function
- `c` - Continue execution
- `p variable` - Print variable
- `l` - List code around current line
- `q` - Quit debugger

### Qt Debugging

**Print signal connections:**

```python
from PySide6.QtCore import QMetaObject

obj = my_widget
for i in range(obj.metaObject().methodCount()):
    method = obj.metaObject().method(i)
    if method.methodType() == QMetaObject.Signal:
        print(f"Signal: {method.name().data().decode()}")
```

**Check if slot is connected:**

```python
if self.my_signal.receivers(self.my_signal) > 0:
    print("Signal is connected")
```

### Database Debugging

**Enable SQL logging:**

```python
# In DatabaseService
self.connection.set_trace_callback(print)
```

**Inspect database directly:**

```bash
sqlite3 worlds/MyWorld/MyWorld.kraken
sqlite> .tables
sqlite> .schema events
sqlite> SELECT * FROM events LIMIT 10;
```

### Performance Profiling

**Profile code execution:**

```bash
python -m cProfile -o profile.stats -m src.app.main
```

**Analyze results:**

```python
import pstats
p = pstats.Stats('profile.stats')
p.sort_stats('cumulative').print_stats(20)
```

---

## Common Tasks

### Adding a New Command

1. **Create Command Class**

   ```python
   # src/commands/my_command.py
   from src.commands.base_command import BaseCommand
   from src.services.db_service import DatabaseService

   class MyCommand(BaseCommand):
       """Brief description."""

       def __init__(self, service: DatabaseService, param: str):
           super().__init__(service)
           self.param = param
           self.old_state = None

       def execute(self) -> None:
           """Execute the command."""
           # Store old state for undo
           self.old_state = get_current_state()
           # Perform action
           perform_action(self.param)

       def undo(self) -> None:
           """Undo the command."""
           restore_state(self.old_state)

       def to_dict(self) -> dict:
           """Serialize for persistence."""
           return {
               "type": "MyCommand",
               "param": self.param,
               "old_state": self.old_state
           }

       @classmethod
       def from_dict(cls, data: dict, service: DatabaseService):
           """Deserialize from persistence."""
           cmd = cls(service, data["param"])
           cmd.old_state = data["old_state"]
           return cmd
   ```

2. **Register Command**

   ```python
   # In src/app/worker_manager.py
   def on_db_initialized(self):
       self.command_registry["MyCommand"] = MyCommand
   ```

3. **Write Tests**

   ```python
   # tests/unit/test_my_command.py
   def test_my_command_execute(db_service):
       cmd = MyCommand(db_service, "test_param")
       cmd.execute()
       # Assert expected changes

   def test_my_command_undo(db_service):
       cmd = MyCommand(db_service, "test_param")
       cmd.execute()
       cmd.undo()
       # Assert state restored
   ```

### Adding a New Repository

1. **Create Repository**

   ```python
   # src/services/repositories/my_repository.py
   from typing import List, Optional
   from src.services.db_service import DatabaseService
   from src.core.my_model import MyModel

   class MyRepository:
       """Repository for MyModel data access."""

       def __init__(self, db_service: DatabaseService):
           self.db = db_service

       def create(self, model: MyModel) -> MyModel:
           """Create new record."""
           sql = "INSERT INTO my_table VALUES (?, ?)"
           self.db.execute(sql, (model.id, model.name))
           return model

       def get(self, model_id: str) -> Optional[MyModel]:
           """Retrieve by ID."""
           sql = "SELECT * FROM my_table WHERE id = ?"
           rows = self.db.execute(sql, (model_id,))
           if rows:
               return MyModel.from_dict(rows[0])
           return None

       def update(self, model: MyModel) -> MyModel:
           """Update existing record."""
           sql = "UPDATE my_table SET name = ? WHERE id = ?"
           self.db.execute(sql, (model.name, model.id))
           return model

       def delete(self, model_id: str) -> bool:
           """Delete record."""
           sql = "DELETE FROM my_table WHERE id = ?"
           self.db.execute(sql, (model_id,))
           return True

       def list_all(self) -> List[MyModel]:
           """List all records."""
           sql = "SELECT * FROM my_table"
           rows = self.db.execute(sql)
           return [MyModel.from_dict(row) for row in rows]
   ```

2. **Write Tests**

   ```python
   # tests/unit/test_my_repository.py
   def test_create(db_service):
       repo = MyRepository(db_service)
       model = MyModel(id="123", name="Test")
       result = repo.create(model)
       assert result.id == "123"

   def test_get(db_service):
       repo = MyRepository(db_service)
       # Create first
       model = MyModel(id="123", name="Test")
       repo.create(model)
       # Then get
       result = repo.get("123")
       assert result is not None
       assert result.name == "Test"
   ```

### Adding a New Widget

1. **Create Widget**

   ```python
   # src/gui/widgets/my_widget.py
   from PySide6.QtCore import Signal
   from PySide6.QtWidgets import QWidget, QVBoxLayout

   class MyWidget(QWidget):
       """Custom widget description."""

       # Signals (output)
       data_changed = Signal(dict)
       action_requested = Signal(str)

       def __init__(self, parent=None):
           super().__init__(parent)
           self._data = {}
           self._setup_ui()
           self._connect_signals()

       def _setup_ui(self) -> None:
           """Set up user interface."""
           layout = QVBoxLayout(self)
           # Add widgets

       def _connect_signals(self) -> None:
           """Connect internal signals."""
           pass

       def set_data(self, data: dict) -> None:
           """Set widget data (input)."""
           self._data = data
           self._update_display()

       def _update_display(self) -> None:
           """Update UI with current data."""
           pass
   ```

2. **Integrate in MainWindow**

   ```python
   # In src/app/main_window.py
   def _create_my_widget(self):
       self.my_widget = MyWidget()
       self.my_widget.data_changed.connect(self._on_data_changed)

   def _on_data_changed(self, data: dict):
       # Handle data change
       pass
   ```

---

## Best Practices

### General Guidelines

1. **Write Tests First (TDD)**
   - Write failing test
   - Implement minimum code to pass
   - Refactor

2. **Keep Functions Small**
   - Single Responsibility Principle
   - Max 50 lines per function (guideline)

3. **Avoid God Classes**
   - Break large classes into smaller, focused ones
   - Use composition over inheritance

4. **Document Public APIs**
   - All public methods need docstrings
   - Private methods optional but encouraged

### Command Pattern Guidelines

1. **Store Minimal State**
   - Only store what's needed for undo
   - Don't duplicate large data structures

2. **Make Commands Atomic**
   - One command = one action
   - Use composite commands for multi-step operations

3. **Test Undo/Redo**
   - Every command must have undo test
   - Test multiple undo/redo cycles

### Database Guidelines

1. **Use Repositories**
   - Never write SQL directly in commands
   - Always go through repository layer

2. **Parameterized Queries**
   - Always use parameter binding
   - Never string concatenation for SQL

   ```python
   # Bad
   sql = f"SELECT * FROM events WHERE id = '{event_id}'"

   # Good
   sql = "SELECT * FROM events WHERE id = ?"
   params = (event_id,)
   ```

3. **Transaction Management**
   - Use context managers for transactions
   - Keep transactions short

### Qt/PySide6 Guidelines

1. **Signals and Slots**
   - Prefer signals over direct method calls
   - Use `QueuedConnection` for cross-thread

2. **Thread Safety**
   - Never access UI from worker threads
   - Use signals to communicate with UI

3. **Memory Management**
   - Set parent for widgets (prevents leaks)
   - Disconnect signals when done

### Testing Guidelines

1. **Test Coverage**
   - Aim for 95%+ coverage
   - Core business logic must be 100%

2. **Test Naming**
   - `test_<method>_<scenario>_<expected_result>`
   - Example: `test_create_event_with_invalid_date_raises_error`

3. **Use Fixtures**
   - Define reusable fixtures in `conftest.py`
   - Don't repeat setup code

4. **Mock External Dependencies**
   - Mock file I/O, network, time
   - Keep tests fast and deterministic

---

## Next Steps

- **[Testing Guide](TESTING.md)** - Comprehensive testing documentation
- **[API Reference](API_REFERENCE.md)** - Detailed API documentation
- **[Contributing](CONTRIBUTING.md)** - How to contribute to the project

---

**Navigation:**  
[← Architecture](ARCHITECTURE.md) • [Back to Index](INDEX.md) • [Database →](DATABASE.md)
