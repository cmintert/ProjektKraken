# Development Guide

This guide covers setting up your development environment, coding standards, and workflow for contributing to ProjektKraken.

## Table of Contents

1. [Environment Setup](#environment-setup)
2. [Project Structure](#project-structure)
3. [Coding Standards](#coding-standards)
4. [Running the Application](#running-the-application)
5. [Building for Release](#building-for-release)
6. [Code Quality Tools](#code-quality-tools)
7. [Development Workflow](#development-workflow)

---

## Environment Setup

### Prerequisites

- **Python 3.13+** (required)
- **Git** (for version control)
- **SQLite 3.35+** (usually bundled with Python)
- **Qt 6** (installed via PySide6)

### Initial Setup

1. **Clone the repository:**

```bash
git clone https://github.com/yourusername/ProjektKraken.git
cd ProjektKraken
```

2. **Create a virtual environment:**

```bash
python -m venv .venv
```

3. **Activate the virtual environment:**

```bash
# Linux/macOS
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

4. **Install dependencies:**

```bash
pip install -r requirements.txt
```

5. **Verify installation:**

```bash
python -m pytest --version
python -c "import PySide6; print(PySide6.__version__)"
```

### IDE Setup

#### VS Code

Recommended extensions:
- Python (Microsoft)
- Pylance
- Ruff
- Test Explorer UI

Settings (`.vscode/settings.json`):

```json
{
  "python.defaultInterpreterPath": ".venv/bin/python",
  "python.linting.enabled": true,
  "python.linting.ruffEnabled": true,
  "python.formatting.provider": "ruff",
  "python.testing.pytestEnabled": true,
  "python.testing.unittestEnabled": false,
  "editor.formatOnSave": true,
  "[python]": {
    "editor.rulers": [88],
    "editor.tabSize": 4
  }
}
```

#### PyCharm

1. Set Python interpreter to `.venv/bin/python`
2. Enable pytest as test runner
3. Configure Ruff as external tool
4. Set line length to 88 characters

---

## Project Structure

```
ProjektKraken/
├── src/                    # Source code
│   ├── app/               # Application layer (MainWindow)
│   ├── commands/          # Command pattern implementations
│   ├── core/              # Domain models and business logic
│   ├── gui/               # PySide6 widgets
│   │   ├── dialogs/      # Modal dialogs
│   │   ├── widgets/      # Reusable widgets
│   │   ├── models/       # Qt models (table/list)
│   │   ├── delegates/    # Custom item delegates
│   │   └── mixins/       # Reusable widget mixins
│   ├── services/          # Data access and background services
│   │   └── repositories/ # Repository pattern for CRUD
│   ├── cli/              # Command-line interface tools
│   └── webserver/        # FastAPI server for live preview
├── tests/                 # Test suite
│   ├── unit/             # Fast unit tests
│   ├── integration/      # Integration tests
│   └── conftest.py       # Shared test fixtures
├── docs/                  # Documentation
├── scripts/               # Utility scripts
├── default_assets/        # Default images and resources
├── themes.json           # UI theme definitions
├── requirements.txt      # Python dependencies
├── pyproject.toml        # Project metadata and tool config
├── pytest.ini            # Pytest configuration
└── launcher.py           # Application entry point
```

### Layer Responsibilities

| Layer | Directory | Purpose | Dependencies |
|-------|-----------|---------|--------------|
| **Core** | `src/core/` | Domain models, pure logic | None (no Qt, no DB) |
| **Services** | `src/services/` | Data access, background work | Core only |
| **Commands** | `src/commands/` | Undo/redo actions | Core + Services |
| **GUI** | `src/gui/` | UI widgets (no logic) | Core (for types) |
| **App** | `src/app/` | Orchestration, wiring | All layers |

**Key Principle:** Dependencies flow downward. Core has no dependencies. GUI contains zero business logic.

---

## Coding Standards

### Python Style

Follow **PEP 8** with these specifics:

- **Line length:** 88 characters (Black default)
- **Indentation:** 4 spaces (no tabs)
- **Quotes:** Double quotes for strings
- **Imports:** Absolute imports, organized by stdlib/third-party/local
- **Naming conventions:**
  - Classes: `PascalCase`
  - Functions/methods: `snake_case`
  - Constants: `UPPER_SNAKE_CASE`
  - Private members: `_leading_underscore`

### Type Hints

**Required** for all function signatures:

```python
from typing import Optional, List, Dict, Any

def create_event(
    name: str,
    lore_date: float,
    description: Optional[str] = None,
    attributes: Optional[Dict[str, Any]] = None
) -> Event:
    """Creates a new event with the given parameters."""
    # Implementation
```

**Use modern type syntax (Python 3.10+):**

```python
# Good
def process_items(items: list[str]) -> dict[str, int]:
    pass

# Avoid (unless Python 3.9 compatibility needed)
from typing import List, Dict
def process_items(items: List[str]) -> Dict[str, int]:
    pass
```

### Docstrings

Use **Google Style** docstrings for all public classes and functions:

```python
def calculate_duration(start: float, end: float) -> float:
    """Calculate the duration between two timeline points.

    This function computes the difference between two lore dates,
    accounting for the calendar system's precision requirements.

    Args:
        start: The starting lore date (1.0 = 1 day).
        end: The ending lore date (1.0 = 1 day).

    Returns:
        The duration as a float in timeline units.

    Raises:
        ValueError: If start > end.

    Example:
        >>> calculate_duration(100.0, 150.0)
        50.0
    """
    if start > end:
        raise ValueError("Start must be before end")
    return end - start
```

**Required sections:**
- Brief description (one line)
- Extended description (optional)
- `Args:` - All parameters with types
- `Returns:` - Return type and description
- `Raises:` - Exceptions that may be raised
- `Example:` - Usage examples (optional)

### Dataclasses

Use `@dataclass` for data models:

```python
from dataclasses import dataclass, field
from typing import Any, Dict
import time
import uuid

@dataclass
class Event:
    """Represents a point or span in time."""
    
    name: str
    lore_date: float
    description: str = ""
    type: str = "generic"
    attributes: Dict[str, Any] = field(default_factory=dict)
    
    # Auto-generated fields
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = field(default_factory=time.time)
    modified_at: float = field(default_factory=time.time)
```

**Key rules:**
- Use `field(default_factory=...)` for mutable defaults
- Auto-generate IDs with `uuid.uuid4()`
- Track `created_at` and `modified_at` timestamps
- Provide `to_dict()` and `from_dict()` methods

### Logging

**Never use `print()` in production code.** Use the `logging` module:

```python
import logging

logger = logging.getLogger(__name__)

def risky_operation() -> None:
    """Performs an operation that might fail."""
    try:
        # Do something
        logger.info("Operation completed successfully")
    except Exception as e:
        logger.error(f"Operation failed: {e}", exc_info=True)
```

**Log levels:**
- `DEBUG`: Detailed diagnostic information
- `INFO`: General informational messages
- `WARNING`: Unexpected but recoverable issues
- `ERROR`: Errors that prevent specific operations
- `CRITICAL`: Fatal errors that stop the application

### Error Handling

**Be specific with exceptions:**

```python
# Good
def load_event(event_id: str) -> Event:
    if not event_id:
        raise ValueError("Event ID cannot be empty")
    event = db.get_event(event_id)
    if event is None:
        raise KeyError(f"Event not found: {event_id}")
    return event

# Bad
def load_event(event_id: str) -> Event:
    try:
        return db.get_event(event_id)
    except:  # Too broad!
        raise
```

**Never use bare `except:`** - always specify the exception type.

---

## Running the Application

### Development Mode

Run directly from source:

```bash
python launcher.py
```

Or using the module syntax:

```bash
python -m src.app.main
```

### Debug Mode

Enable verbose logging:

```bash
export LOG_LEVEL=DEBUG
python launcher.py
```

### With Sample Data

Load the Middle Earth demo:

```bash
python tests/populate_middle_earth.py
```

---

## Building for Release

### Using PyInstaller

Build a standalone executable:

```bash
pyinstaller ProjektKraken.spec
```

The executable will be in `dist/ProjektKraken/`.

### Build Configuration

See `ProjektKraken.spec` for build settings. Key options:

- `datas`: Include `themes.json` and `default_assets/`
- `hiddenimports`: Specify implicit dependencies
- `excludes`: Remove unused modules to reduce size
- `onefile`: Create single-file vs directory bundle

### Platform-Specific Builds

**Linux:**
```bash
pyinstaller ProjektKraken.spec
```

**macOS:**
```bash
pyinstaller ProjektKraken.spec --windowed
```

**Windows:**
```bash
pyinstaller ProjektKraken.spec --noconsole --icon=icon.ico
```

---

## Code Quality Tools

### Ruff (Linting + Formatting)

Run linter:

```bash
ruff check src/ tests/
```

Auto-fix issues:

```bash
ruff check --fix src/ tests/
```

Format code:

```bash
ruff format src/ tests/
```

Configuration in `pyproject.toml`:

```toml
[tool.ruff]
line-length = 88
target-version = "py313"

[tool.ruff.lint]
select = ["E4", "E7", "E9", "F", "I", "ANN"]
ignore = ["ANN401"]  # Allow Any type

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["ANN"]  # No type hints in tests
```

### Mypy (Type Checking)

Run type checker:

```bash
mypy src/
```

Configuration in `pyrightconfig.json`:

```json
{
  "typeCheckingMode": "basic",
  "pythonVersion": "3.13",
  "include": ["src"],
  "exclude": ["**/node_modules", "**/__pycache__", ".venv"]
}
```

### Pytest (Testing)

Run all tests:

```bash
pytest
```

Run with coverage:

```bash
pytest --cov=src --cov-report=term-missing
```

Run only unit tests:

```bash
pytest tests/unit/ -m unit
```

Run only integration tests:

```bash
pytest tests/integration/ -m integration
```

Skip slow tests:

```bash
pytest -m "not slow"
```

### Pre-commit Checklist

Before committing code, run:

```bash
# Format code
ruff format src/ tests/

# Check linting
ruff check src/ tests/

# Type check
mypy src/

# Run tests
pytest --cov=src --cov-report=term-missing

# Check docstring coverage
python scripts/check_docstrings.py
```

Or use the validation script:

```bash
./validate_env.sh
```

---

## Development Workflow

### 1. Create a Feature Branch

```bash
git checkout -b feature/my-new-feature
```

Branch naming conventions:
- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation
- `refactor/` - Code refactoring
- `test/` - Adding tests

### 2. Write Tests First (TDD)

Create failing tests before implementing:

```python
# tests/unit/core/test_new_feature.py
def test_new_feature():
    """Test that new feature works correctly."""
    result = my_new_function(input_data)
    assert result == expected_output
```

### 3. Implement the Feature

Follow the coding standards and architecture patterns:

- Keep changes focused and atomic
- Follow the layer responsibilities
- Use the command pattern for user actions
- Maintain separation of concerns

### 4. Run Code Quality Checks

```bash
ruff format src/ tests/
ruff check --fix src/ tests/
mypy src/
pytest --cov=src
```

### 5. Commit Changes

Write clear commit messages:

```bash
git add .
git commit -m "feat: Add timeline grouping by entity type

- Implement TimelineGroupCommand
- Add grouping UI controls to timeline widget
- Update tests for grouping logic
- Add documentation for grouping API
"
```

**Commit message format:**
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `test:` - Adding tests
- `refactor:` - Code refactoring
- `style:` - Formatting changes
- `chore:` - Build/tooling changes

### 6. Push and Create Pull Request

```bash
git push origin feature/my-new-feature
```

Then create a PR on GitHub with:
- Clear title and description
- Reference to related issues
- Screenshots/demos for UI changes
- Test coverage information

---

## Common Patterns

### Command Pattern

All user actions should be commands:

```python
from src.commands.base_command import BaseCommand, CommandResult
from src.services.db_service import DatabaseService

class CreateEventCommand(BaseCommand):
    """Command to create a new event."""

    def __init__(self, name: str, lore_date: float) -> None:
        super().__init__()
        self.name = name
        self.lore_date = lore_date
        self.event_id: Optional[str] = None

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Create the event."""
        from src.core.events import Event
        
        event = Event(name=self.name, lore_date=self.lore_date)
        self.event_id = event.id
        db_service.event_repo.insert(event)
        
        return CommandResult(
            success=True,
            message=f"Event '{self.name}' created",
            data={"event_id": self.event_id}
        )

    def undo(self, db_service: DatabaseService) -> None:
        """Delete the event."""
        if self.event_id:
            db_service.event_repo.delete(self.event_id)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "lore_date": self.lore_date,
            "event_id": self.event_id
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CreateEventCommand":
        cmd = cls(data["name"], data["lore_date"])
        cmd.event_id = data.get("event_id")
        return cmd
```

### Signal/Slot Communication

GUI components emit signals, MainWindow connects them:

```python
# In widget (GUI layer)
class EventEditor(QWidget):
    save_requested = Signal(dict)  # Event data
    
    def on_save_clicked(self) -> None:
        data = self.get_form_data()
        self.save_requested.emit(data)

# In MainWindow (App layer)
class MainWindow(QMainWindow):
    def setup_connections(self) -> None:
        self.event_editor.save_requested.connect(self.on_event_save)
    
    def on_event_save(self, data: dict) -> None:
        cmd = UpdateEventCommand(data["id"], data)
        self.history_service.execute_command(cmd)
```

### Background Operations

Use DatabaseWorker for database operations:

```python
# In MainWindow
self.worker.submit_task(
    task_fn=lambda: self.db_service.event_repo.get_all(),
    on_success=self.on_events_loaded,
    on_error=self.on_load_error
)

def on_events_loaded(self, events: list[Event]) -> None:
    """Handle loaded events on main thread."""
    self.timeline.display_events(events)
```

---

## Troubleshooting

### Qt Platform Plugin Error

```bash
export QT_QPA_PLATFORM=offscreen  # For headless environments
```

### Import Errors

Ensure project root is in PYTHONPATH:

```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### Database Lock Issues

ProjektKraken uses WAL mode for concurrent access. If you encounter locks:

```python
# Enable WAL mode explicitly
db_service.execute_sql("PRAGMA journal_mode=WAL;")
```

### High DPI Display Issues

High DPI support is enabled by default. If scaling is wrong:

```python
# In src/app/main.py
QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
```

---

## Additional Resources

- [Architecture Guide](ARCHITECTURE.md) - System design and patterns
- [Database Schema](DATABASE.md) - Database structure
- [Testing Guide](TESTING.md) - Testing best practices
- [API Reference](API.md) - Code API documentation
- [Contributing Guide](CONTRIBUTING.md) - Contribution guidelines

---

## Questions?

- **Issues:** https://github.com/yourusername/ProjektKraken/issues
- **Discussions:** https://github.com/yourusername/ProjektKraken/discussions
- **Documentation:** https://projektkraken.readthedocs.io
