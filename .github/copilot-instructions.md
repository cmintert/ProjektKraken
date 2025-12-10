# GitHub Copilot Instructions for ProjektKraken

## Project Overview

ProjektKraken is a desktop worldbuilding environment designed for the "Architect" persona. It treats history as the primary axis of the world, offering a timeline-first approach to lore creation.

**Key Characteristics:**
- Desktop application for worldbuilding with timeline-first workflow
- Context-aware UI with "Trinity" view system (Editor, Timeline, Relations)
- Hybrid data model: strict SQL schema with flexible JSON attributes
- Modern dark-mode UI with dockable panels

## Technology Stack

- **Language:** Python 3.10+
- **GUI Framework:** PySide6 (Qt for Python)
- **Database:** SQLite 3.35+
- **Testing:** pytest, pytest-qt
- **Documentation:** Sphinx (Google Style docstrings)
- **Linting:** flake8, mypy, black
- **Type Hints:** Mandatory throughout codebase

## Architecture

### Service-Oriented Architecture (SOA)

The project follows strict separation of concerns:

1. **Core Layer** (`src/core/`) - Business logic, data models, utilities
   - Event and Entity dataclasses
   - ThemeManager for UI theming
   - No UI dependencies

2. **Services Layer** (`src/services/`) - Data access and background processing
   - `DatabaseService`: SQLite interactions
   - `Worker`: Background thread operations
   - `TextParser`: Wiki link parsing

3. **Commands Layer** (`src/commands/`) - Command pattern for undo/redo
   - All user actions as standalone classes
   - Inherit from `BaseCommand`
   - Must implement `execute()` and `undo()` methods

4. **GUI Layer** (`src/gui/`) - PySide6 widgets
   - "Dumb UI" principle: zero business logic
   - Only display data and emit signals
   - Timeline, EventEditor, EntityEditor, UnifiedList widgets

5. **App Layer** (`src/app/`) - Application entry point
   - MainWindow orchestrates components
   - Signal/slot communication between layers

### Communication Pattern

```
UI → Signal → Command → Service → Database
                ↓
            Signal → UI Update
```

## Coding Standards

### Python Style

- **Line Length:** 88 characters maximum (Black default)
- **Imports:** No wildcards, organize by stdlib/third-party/local
- **Type Hints:** Required for all function parameters and return types
- **Docstrings:** Google Style, required for all public methods and classes
- **No print():** Use the `logging` module instead
- **Naming Conventions:**
  - Classes: `PascalCase`
  - Functions/methods: `snake_case`
  - Constants: `UPPER_SNAKE_CASE`
  - Private members: `_leading_underscore`

### Documentation Requirements

- **Module-level docstrings:** Required for all Python modules
- **Class docstrings:** Must describe purpose and key responsibilities
- **Method docstrings:** Must include:
  - Brief description
  - Args section with types
  - Returns section with type
  - Raises section if applicable

Example:
```python
def create_event(name: str, lore_date: float) -> Event:
    """
    Creates a new Event instance with the given parameters.

    Args:
        name: The display name of the event.
        lore_date: The timeline date as a float (1.0 = 1 day).

    Returns:
        Event: A new Event instance with generated ID and timestamps.

    Raises:
        ValueError: If name is empty or lore_date is invalid.
    """
```

### Data Models

- Use `@dataclass` for data models (Event, Entity)
- Include `to_dict()` and `from_dict()` class methods for serialization
- Use `field(default_factory=...)` for mutable defaults
- Auto-generate IDs using `uuid.uuid4()`
- Track metadata: `created_at`, `modified_at` timestamps

### Database Conventions

- **Storage Format:** SQLite single-file (`.kraken` extension)
- **Time Storage:** Float values where 1.0 = 1 day
- **Hybrid Schema:** SQL columns for searchable/sortable data, JSON for flexible attributes
- **Testing:** Always use in-memory database (`:memory:`) in tests
- **Transactions:** Use context managers for database operations

### Command Pattern

All user actions must be implemented as commands:

```python
class MyCommand(BaseCommand):
    """Brief description of what this command does."""

    def __init__(self, service: DatabaseService, param1: str):
        super().__init__(service)
        self.param1 = param1
        # Store state needed for undo

    def execute(self) -> None:
        """Execute the command."""
        # Perform the action
        # Store any state needed for undo

    def undo(self) -> None:
        """Undo the command."""
        # Reverse the action using stored state
```

### Qt/PySide6 Guidelines

- **Signals:** Use `pyqtSignal` for custom signals
- **Slots:** Connect using `signal.connect(slot)`
- **Threading:** Use `QThread` and `Worker` pattern, never block the UI thread
- **Stylesheets:** Apply via `ThemeManager`, use QSS tokens
- **High DPI:** Already enabled, ensure scalable layouts
- **Widgets:** Prefer composition over inheritance

## Testing Standards

### Test Organization

- **Location:** `tests/` directory
- **Structure:**
  - `tests/unit/` - Fast unit tests, no external dependencies
  - `tests/integration/` - Integration tests with database
- **Naming:** `test_*.py` files, `test_*` functions, `Test*` classes

### Test Patterns

- **Fixtures:** Use pytest fixtures in `conftest.py`
- **Database Testing:** Use in-memory SQLite via `db_service` fixture
- **Qt Testing:** Use `qtbot` fixture from pytest-qt
- **Markers:**
  - `@pytest.mark.unit` - Fast unit tests
  - `@pytest.mark.integration` - Integration tests
  - `@pytest.mark.slow` - Tests that take >1 second

### Coverage Requirements

- **Minimum:** 95% code coverage
- **Run tests:** `pytest --cov=src --cov-report=term-missing`
- **Focus:** Core business logic must be 100% covered

Example test:
```python
import pytest
from src.core.events import Event

def test_event_creation():
    """Test that Event instances are created correctly."""
    event = Event(name="Test Event", lore_date=100.0)
    assert event.name == "Test Event"
    assert event.lore_date == 100.0
    assert event.id is not None
    assert event.type == "generic"
```

## Build and Run

### Setup Development Environment

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Run Application

```bash
python -m src.app.main
```

### Run Tests

```bash
# All tests with coverage
pytest --cov=src --cov-report=term-missing

# Unit tests only
pytest tests/unit/

# Specific test file
pytest tests/unit/test_events.py
```

### Code Quality Checks

```bash
# Format code
black src/ tests/

# Lint code
flake8 src/ tests/

# Type checking
mypy src/

# Check docstring coverage
python check_docstrings.py
```

## Common Patterns and Anti-Patterns

### ✅ DO

- Use dataclasses for data models
- Implement undo/redo via command pattern
- Use type hints everywhere
- Write comprehensive docstrings
- Use logging instead of print
- Keep UI logic out of core/services
- Use signals for cross-component communication
- Write tests for new features
- Use in-memory database for tests

### ❌ DON'T

- Don't put business logic in GUI widgets
- Don't use wildcard imports
- Don't use bare `except:` clauses
- Don't use `print()` statements
- Don't bypass the command pattern for user actions
- Don't create "God Objects" - keep classes focused
- Don't skip type hints or docstrings
- Don't commit without running tests
- Don't use magic numbers - define constants

## File Structure

```
ProjektKraken/
├── src/
│   ├── app/           # Application entry point and MainWindow
│   ├── commands/      # Command pattern implementations
│   ├── core/          # Business logic and data models
│   ├── gui/           # PySide6 widgets and UI components
│   ├── services/      # Data access and background workers
│   └── resources/     # UI resources (icons, themes, etc.)
├── tests/
│   ├── unit/          # Unit tests
│   └── integration/   # Integration tests
├── docs/              # Sphinx documentation
├── .flake8           # Flake8 configuration
├── pytest.ini        # Pytest configuration
├── requirements.txt  # Python dependencies
└── themes.json       # UI theme definitions
```

## Development Workflow

1. **Before coding:** Understand the architecture layer you're working in
2. **Write tests first:** TDD approach preferred for core logic
3. **Follow patterns:** Use existing code as a reference
4. **Check quality:** Run linters and tests before committing
5. **Document:** Add/update docstrings and comments as needed
6. **Small commits:** Make focused, atomic commits

## Special Considerations

### Timeline System

- Time is stored as float (1.0 = 1 day)
- Supports cosmic scales (millions of years) to second precision
- Calendar presentation is separate from storage
- Use `lore_date` for event timestamps

### Theme System

- Centralized via `ThemeManager` in `src/core/theme_manager.py`
- Themes defined in `themes.json`
- Use semantic color tokens (primary, surface, border, etc.)
- Apply styles via QSS (Qt Style Sheets)

### Wiki Links

- Format: `[[Entity Name]]`
- Parsed by `TextParser` service
- Clickable in editors
- Auto-linked to entities in database

## Getting Help

- **Design Docs:** See `Design.md` for architecture details
- **Code Quality:** Review `CODE_QUALITY_ASSESSMENT.md` for standards
- **Examples:** Browse existing code in each layer for patterns
- **Tests:** Check test files for usage examples
