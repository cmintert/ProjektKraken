# Architecture Guide

This document describes the technical architecture of ProjektKraken, including design patterns, threading model, and best practices for developers.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Layered Architecture](#layered-architecture)
3. [Threading Model](#threading-model)
4. [Command Pattern](#command-pattern)
5. [Signal/Slot Communication](#signalslot-communication)
6. [Data Flow](#data-flow)
7. [Key Components](#key-components)
8. [Design Principles](#design-principles)

---

## Architecture Overview

ProjektKraken uses a **layered Service-Oriented Architecture (SOA)** with strict separation of concerns and the Command Pattern for undo/redo support.

### High-Level Architecture

```
┌─────────────────────────────────────────────────┐
│              Application Layer                   │
│         (app/main_window.py + managers)         │
│  - UI orchestration                             │
│  - Signal/slot wiring                           │
│  - Dock layout management                       │
└───────────────┬─────────────────────────────────┘
                │ signals/commands
┌───────────────▼─────────────────────────────────┐
│           Commands Layer                         │
│         (commands/*.py)                         │
│  - Command pattern for undo/redo               │
│  - Input validation                            │
│  - Transactional operations                    │
└───────────────┬─────────────────────────────────┘
                │ execute()
┌───────────────▼─────────────────────────────────┐
│           Services Layer                         │
│         (services/*.py)                         │
│  - DatabaseService + Repositories              │
│  - Background worker (DatabaseWorker)          │
│  - Business logic services                     │
└───────────────┬─────────────────────────────────┘
                │ CRUD operations
┌───────────────▼─────────────────────────────────┐
│            Core Layer                           │
│         (core/*.py)                             │
│  - Domain models (Event, Entity, etc.)         │
│  - Utilities (calendar, theme)                 │
│  - No external dependencies                    │
└─────────────────────────────────────────────────┘
```

### Design Principles

1. **Separation of Concerns**: Each layer has a single, well-defined responsibility
2. **Dependency Flow**: Top → Down (app depends on services, services depend on core)
3. **Communication**: Signals for loose coupling between components
4. **Thread Safety**: Worker thread for all database operations
5. **Command Pattern**: All user actions encapsulated as reversible commands
6. **Dumb UI**: GUI components contain zero business logic

---

## Layered Architecture

### Core Layer (`src/core/`)

**Responsibility**: Domain models and pure business logic

**Contains:**
- Data models (Event, Entity, Relation, etc.)
- Calendar system (CalendarConfig, CalendarConverter)
- Theme management (ThemeManager)
- Pure utility functions
- No external dependencies (no Qt, no database)

**Key Files:**
- `events.py` - Event dataclass
- `entities.py` - Entity dataclass
- `relations.py` - Relation dataclass
- `calendar.py` - Calendar system
- `temporal_manager.py` - Timeline state management
- `theme_manager.py` - Theme system

### Services Layer (`src/services/`)

**Responsibility**: Data access and business services

**Contains:**
- DatabaseService (SQL interface)
- Repositories (CRUD operations)
- Background worker (DatabaseWorker)
- Import/export services
- Search services
- Backup services

**Key Files:**
- `db_service.py` - SQLite database interface
- `repositories/` - Entity, Event, Relation repositories
- `backup_service.py` - Backup/restore
- `import_service.py` - JSON import with two-pass resolution
- `search_service.py` - Full-text and semantic search
- `embedding_service.py` - Vector embeddings
- `rag_service.py` - Retrieval-Augmented Generation

### Commands Layer (`src/commands/`)

**Responsibility**: Encapsulate user actions as reversible commands

**Contains:**
- BaseCommand abstract class
- Event commands (CreateEvent, UpdateEvent, DeleteEvent)
- Entity commands
- Relation commands
- Map commands
- Composite commands

**Key Files:**
- `base_command.py` - Abstract command base
- `event_commands.py` - Event CRUD commands
- `entity_commands.py` - Entity CRUD commands
- `relation_commands.py` - Relation commands

**Command Pattern:**
```python
class MyCommand(BaseCommand):
    def __init__(self, service, param1, param2):
        super().__init__(service)
        self.param1 = param1
        self.param2 = param2
        self._backup_data = None
    
    def execute(self) -> None:
        """Execute the command."""
        # Store state for undo
        self._backup_data = ...
        # Perform action
        result = self.service.do_something(self.param1, self.param2)
        return result
    
    def undo(self) -> None:
        """Undo the command."""
        # Restore from backup
        self.service.restore_something(self._backup_data)
```

### GUI Layer (`src/gui/`)

**Responsibility**: User interface (Qt widgets)

**Contains:**
- Editor widgets (Event, Entity, Relation editors)
- List widgets (Event list, Entity list)
- Visualization widgets (Timeline, Graph, Map)
- Input widgets (Date pickers, duration inputs)
- Utility widgets (Gallery, filter, search)

**Key Principles:**
- **Dumb UI**: No business logic in widgets
- **Signal-Based**: Emit signals for user actions
- **Display Only**: Only display data and handle user input

**Example Widget:**
```python
class MyWidget(QWidget):
    # Define signals
    save_clicked = Signal(dict)  # Emit data, don't process it
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
    
    def setup_ui(self):
        # Create UI elements
        self.name_edit = QLineEdit()
        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.on_save)
    
    def on_save(self):
        # Emit signal with data - don't save directly
        data = {"name": self.name_edit.text()}
        self.save_clicked.emit(data)
    
    def display_data(self, data):
        # Display data - no processing
        self.name_edit.setText(data.get("name", ""))
```

### Application Layer (`src/app/`)

**Responsibility**: Application entry point and orchestration

**Contains:**
- MainWindow (main application window)
- UI managers (dock layout, toolbar, menu)
- Coordinators (command coordinator, temporal coordinator)
- Data handlers (cache, signal routing)

**Key Files:**
- `main.py` - Application entry point
- `main_window.py` - Main window and UI setup
- `command_coordinator.py` - Undo/redo stack management
- `ui_manager.py` - Dock layout management
- `data_handler.py` - Data caching and routing

---

## Threading Model

### Two-Thread Architecture

ProjektKraken uses **two threads** with strict isolation:

```
┌───────────────────────────────────────────┐
│          MAIN THREAD (GUI)                │
│                                           │
│  ┌─────────────────────────────────────┐ │
│  │ MainWindow                          │ │
│  │  - UI components                    │ │
│  │  - Event handling                   │ │
│  └──────────┬──────────────────────────┘ │
│             │                             │
│  ┌──────────▼──────────────────────────┐ │
│  │ DataHandler                         │ │
│  │  - Data caching                     │ │
│  │  - Signal routing                   │ │
│  └──────────┬──────────────────────────┘ │
│             │ QueuedConnection            │
└─────────────┼───────────────────────────┘
              │
┌─────────────▼───────────────────────────┐
│       WORKER THREAD (Database)          │
│                                         │
│  ┌──────────────────────────────────┐  │
│  │ DatabaseWorker                   │  │
│  │  - Database operations           │  │
│  │  - Command execution             │  │
│  │  - Heavy processing              │  │
│  └──────────┬───────────────────────┘  │
│             │                           │
│  ┌──────────▼───────────────────────┐  │
│  │ DatabaseService                  │  │
│  │  - SQLite connection (WAL mode)  │  │
│  │  - Repository pattern            │  │
│  └──────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

### Thread Affinity Rules

**MAIN THREAD:**
- ✅ All QWidget subclasses
- ✅ MainWindow and UI components
- ✅ DataHandler (caches UI data)
- ✅ UI event handlers
- ❌ NO direct database calls

**WORKER THREAD:**
- ✅ DatabaseWorker (moved via moveToThread)
- ✅ DatabaseService (thread affinity via worker)
- ✅ All database operations
- ✅ Command execution
- ❌ NO UI operations

### Thread Safety Mechanisms

1. **Signal/Slot with QueuedConnection**
   - All cross-thread connections use `Qt.ConnectionType.QueuedConnection`
   - Ensures slots run in receiver's thread
   - Thread-safe event queue mechanism

2. **SQLite WAL Mode**
   - Write-Ahead Logging for concurrent access
   - Allows concurrent reads while writing
   - Crash-safe transactions

3. **No Shared Mutable State**
   - Worker and Main threads share no variables
   - All data passed via immutable signals or deep copies
   - Cache updates happen atomically in slots

---

## Command Pattern

### Command Lifecycle

1. **Creation**: User action creates command object
2. **Validation**: Command validates input
3. **Execution**: Command.execute() performs action
4. **Registration**: Command added to undo stack
5. **Undo/Redo**: Command.undo()/execute() called as needed

### Command Coordinator

The CommandCoordinator manages undo/redo stacks:

```python
class CommandCoordinator:
    def __init__(self):
        self.undo_stack = []
        self.redo_stack = []
        self.max_stack_size = 100
    
    def execute(self, command):
        """Execute command and add to undo stack."""
        result = command.execute()
        self.undo_stack.append(command)
        self.redo_stack.clear()
        self._trim_stack()
        return result
    
    def undo(self):
        """Undo last command."""
        if self.undo_stack:
            command = self.undo_stack.pop()
            command.undo()
            self.redo_stack.append(command)
    
    def redo(self):
        """Redo last undone command."""
        if self.redo_stack:
            command = self.redo_stack.pop()
            command.execute()
            self.undo_stack.append(command)
```

### Persistent History

Commands are serialized and persisted to database:

```python
class BaseCommand:
    def to_dict(self) -> dict:
        """Serialize command to dict."""
        return {
            "type": self.__class__.__name__,
            "params": {...}
        }
    
    @classmethod
    def from_dict(cls, service, data: dict):
        """Deserialize command from dict."""
        return cls(service, **data["params"])
```

---

## Signal/Slot Communication

### Common Patterns

#### Pattern 1: Data Loading

```python
# MainWindow
@Slot()
def on_refresh_clicked(self):
    self.worker.load_events()  # Trigger worker slot

# DatabaseWorker
@Slot()
def load_events(self):
    events = self.db_service.get_events()
    self.events_loaded.emit(events)  # Emit result

# DataHandler
@Slot(list)
def on_events_loaded(self, events):
    self.cached_events = events
    self.data_changed.emit()  # Notify UI
```

#### Pattern 2: Command Execution

```python
# Widget
def on_save_clicked(self):
    data = self.get_form_data()
    command = CreateEventCommand(None, data)
    self.execute_command.emit(command)

# CommandCoordinator
@Slot(BaseCommand)
def execute_command(self, command):
    self.worker.execute_command(command)

# DatabaseWorker
@Slot(BaseCommand)
def execute_command(self, command):
    command.service = self.db_service
    result = command.execute()
    self.command_executed.emit(command, result)
```

---

## Data Flow

### Create Event Flow

```
User Input → EventEditor.save_clicked
           → MainWindow.on_event_save
           → CreateEventCommand created
           → CommandCoordinator.execute
           → Signal to Worker thread
           → Command.execute() (in worker)
           → DatabaseService.create_event()
           → SQLite INSERT
           → Signal back to Main thread
           → DataHandler updates cache
           → UI refreshes
```

### Undo Flow

```
User presses Ctrl+Z → CommandCoordinator.undo()
                    → Get last command from stack
                    → Signal to Worker thread
                    → Command.undo() (in worker)
                    → DatabaseService.delete_event()
                    → SQLite DELETE
                    → Signal back to Main thread
                    → DataHandler updates cache
                    → UI refreshes
```

---

## Key Components

### DatabaseService

- Single SQLite connection per world
- WAL mode enabled
- Repository pattern for CRUD operations
- Thread-safe (runs in worker thread)

### TemporalManager

- Manages timeline state
- Resolves entity states at specific times
- Caches computed states
- Emits signals on state changes

### ThemeManager

- Centralized theme management
- JSON-based theme definitions
- Dynamic theme switching
- Style inheritance

### CalendarConverter

- Float ↔ Calendar date conversion
- Custom calendar support
- Leap year handling
- Sub-day precision

---

## Design Principles

### 1. Separation of Concerns

Each layer has a single responsibility:
- Core: Domain models
- Services: Data access
- Commands: User actions
- GUI: Display and input
- App: Orchestration

### 2. Dependency Inversion

Higher layers depend on abstractions, not implementations:
- Commands depend on service interfaces
- GUI emits signals, doesn't call services directly
- Services implement repository pattern

### 3. Open/Closed Principle

Open for extension, closed for modification:
- New command types can be added without modifying coordinator
- New entity types use same repository
- New themes added via JSON

### 4. Single Responsibility

Each class has one reason to change:
- EventEditor only handles UI
- EventRepository only handles event CRUD
- CreateEventCommand only handles event creation

### 5. DRY (Don't Repeat Yourself)

Shared logic extracted to utilities:
- ThemeManager for all styling
- CalendarConverter for all date conversion
- BaseCommand for command infrastructure

---

## Best Practices

### For GUI Development

1. **No Business Logic**: Widgets only display and emit signals
2. **Signal-Based**: Use signals for all user actions
3. **Theme-Aware**: Use ThemeManager for all styling
4. **Responsive**: Never block UI thread with long operations

### For Service Development

1. **Repository Pattern**: Use repositories for data access
2. **Transaction Safety**: Use context managers for database operations
3. **Error Handling**: Catch and log exceptions, emit error signals
4. **Thread Safety**: Ensure services are thread-safe

### For Command Development

1. **Reversibility**: All commands must be undoable
2. **Validation**: Validate input before execution
3. **State Backup**: Store necessary state for undo
4. **Serialization**: Implement to_dict/from_dict for persistence

---

## Further Reading

- [Development Guide](DEVELOPMENT.md) - Developer setup and workflow
- [Database Schema](DATABASE.md) - Database structure
- [Testing Guide](TESTING.md) - Testing practices
- [API Reference](API.md) - Code documentation

---

For more details on specific components, see the source code and inline documentation.
