# Architecture Documentation

**Version:** 0.14.1 (Beta)  
**Last Updated:** July 2026

Technical architecture and design patterns in ProjektKraken.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Layer Architecture](#layer-architecture)
3. [Design Patterns](#design-patterns)
4. [Threading Model](#threading-model)
5. [Database Architecture](#database-architecture)
6. [Data Flow](#data-flow)
7. [Key Services](#key-services)
8. [Command System](#command-system)
9. [Communication Patterns](#communication-patterns)
10. [Extension Points](#extension-points)

---

## Architecture Overview

### Philosophy

ProjektKraken follows **Service-Oriented Architecture (SOA)** with strict separation of concerns to prevent the "God Class" anti-pattern.

**Core Principles:**

1. **"Dumb UI" Principle**: Views contain zero business logic, only display and emit signals
2. **Command Pattern**: All user actions are reversible, encapsulated commands
3. **Loose Coupling**: Signal/slot communication between components
4. **Testability**: Each layer independently testable
5. **Thread Safety**: Strict isolation between UI and database threads

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Application Layer                    │
│  (MainWindow, Coordinators, Entry Point)               │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────┴────────────────────────────────┐
│                     GUI Layer                           │
│  (Widgets, Dialogs, Editors) - Pure Presentation       │
└────────────────────────┬────────────────────────────────┘
                         │ Signals
┌────────────────────────┴────────────────────────────────┐
│                   Commands Layer                        │
│  (BaseCommand, Specific Commands) - Undo/Redo Logic    │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────┴────────────────────────────────┐
│                   Services Layer                        │
│  (DB, Repositories, Workers) - Business Logic          │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────┴────────────────────────────────┐
│                     Core Layer                          │
│  (Data Models, Utilities) - Domain Objects             │
└─────────────────────────────────────────────────────────┘
```

---

## Layer Architecture

### 1. Application Layer (`src/app/`)

**Purpose**: Application entry point and component orchestration.

**Key Components:**

- **`main.py`**: Entry point, initializes Qt application
- **`main_window.py`**: Central UI coordinator, manages panels and menus
- **`command_coordinator.py`**: Manages undo/redo stacks, coordinates command execution
- **`worker_manager.py`**: Manages DatabaseWorker lifecycle
- **Coordinators**:
  - `BackupCoordinator`: Automated backup scheduling
  - `NavigationCoordinator`: Panel navigation and routing
  - `TimeCoordinator`: Timeline playhead management

**Responsibilities:**
- Initialize application
- Wire up signals between components
- Coordinate high-level workflows
- Manage application state

---

### 2. Commands Layer (`src/commands/`)

**Purpose**: Encapsulate all user actions as reversible commands.

**Base Command:**

```python
class BaseCommand(ABC):
    """Abstract base for all commands."""
    
    def __init__(self, service: DatabaseService):
        self.service = service
    
    @abstractmethod
    def execute(self) -> None:
        """Execute the command."""
        pass
    
    @abstractmethod
    def undo(self) -> None:
        """Undo the command."""
        pass
    
    def to_dict(self) -> dict:
        """Serialize for persistence."""
        pass
    
    @classmethod
    def from_dict(cls, data: dict, service: DatabaseService):
        """Deserialize from persistence."""
        pass
```

**Command Types:**

| Module | Commands |
|--------|----------|
| `event_commands.py` | CreateEvent, UpdateEvent, DeleteEvent |
| `entity_commands.py` | CreateEntity, UpdateEntity, DeleteEntity |
| `relation_commands.py` | AddRelation, UpdateRelation, RemoveRelation |
| `wiki_commands.py` | CreateWikiLink, ResolveLink |
| `map_commands.py` | AddMarker, UpdateMarker, RemoveMarker |
| `calendar_commands.py` | UpdateCalendar, ConvertDate |

**Benefits:**
- Full undo/redo support
- Serializable for persistent history
- Testable in isolation
- Reusable between GUI and CLI

---

### 3. Services Layer (`src/services/`)

**Purpose**: Business logic, data access, and background processing.

**Key Services:**

#### DatabaseService (`db_service.py`)
- Raw SQL interface with parameterized queries
- Schema initialization and migrations
- Connection management
- Transaction support

#### Repositories (`repositories/`)
- **EventRepository**: Event CRUD operations
- **EntityRepository**: Entity CRUD operations
- **RelationRepository**: Relation management
- **MapRepository**: Map and marker operations
- **CalendarRepository**: Calendar configuration

#### HistoryService (`history_service.py`)
- Persists command history to `command_history` table
- Session tracking across app restarts
- Command serialization/deserialization

#### Map aggregate and raster storage

- `MapAggregateService` loads and validates the layer tree, markers,
  trajectories, and raster metadata as one logical state.
- `RasterAssetService` validates world-relative paths and atomically replaces
  raster files.
- `CommandArtifactStore` holds reversible files under
  `assets/.history/<command-id>/` and is pruned with command history.
- Raster grids, mappings, serializable patches, calibration, and map constants
  live below the GUI layer. Qt image conversion remains presentation-only.

The database layer tree and raster metadata are canonical. Widgets may preview
an interaction, but they send one intent and reconcile from a successful worker
result. Destructive subtree and map commands stage files, perform their database
changes in one transaction, and restore staged files on failure.

#### BackupService (`backup_service.py`)
- Automated backup scheduling
- Manual backup creation
- Retention policy management
- Integrity verification

#### AssetStore (`asset_store.py`)
- Image import (WebP conversion for photos)
- Icon import (`import_icon`) — preserves SVG/PNG/JPG extension
- Trash / restore for undo/redo support
- UUID-based collision-free filenames

#### RAGService (`rag_service.py`)
- Retrieval-Augmented Generation
- Hybrid search (lexical + semantic)
- Embedding management
- Context retrieval for LLMs

#### Workers (`workers/`)
- **DatabaseWorker**: Executes commands in background thread
- **TextParser**: Wiki link parsing and resolution

**Design Pattern: Repository Pattern**

```python
class EventRepository:
    """Handles Event database operations."""
    
    def __init__(self, db_service: DatabaseService):
        self.db = db_service
    
    def create(self, event: Event) -> Event:
        """Create event in database."""
        # SQL INSERT
        return event
    
    def get(self, event_id: str) -> Optional[Event]:
        """Retrieve event by ID."""
        # SQL SELECT
        return event or None
    
    def update(self, event: Event) -> Event:
        """Update existing event."""
        # SQL UPDATE
        return event
    
    def delete(self, event_id: str) -> bool:
        """Delete event."""
        # SQL DELETE
        return success
```

---

### 4. Core Layer (`src/core/`)

**Purpose**: Domain models, business logic, and utilities.

**Data Models:**

```python
@dataclass
class Event:
    """Event domain model."""
    id: str
    name: str
    lore_date: float  # 1.0 = 1 day
    type: str
    description: str
    tags: List[str]
    attributes: Dict[str, Any]  # JSON storage
    created_at: float
    modified_at: float
    
    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        pass
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Event':
        """Deserialize from dictionary."""
        pass
```

**Key Classes:**
- **Event**: Timestamped lore entry
- **Entity**: Persistent world element
- **Relation**: Typed connection between items
- **Calendar**: Custom calendar configuration
- **Map**: Geographic map with markers
- **World**: Project/world container

**Utilities:**
- **ThemeManager**: UI theme management
- **CalendarConverter**: Date conversion (float ↔ calendar)
- **LinkResolver**: Wiki link resolution

---

### 5. GUI Layer (`src/gui/`)

**Purpose**: Presentation and user interaction.

**Structure:**

```
src/gui/
├── widgets/
│   ├── timeline/         # Timeline visualization
│   │   ├── timeline_widget.py
│   │   ├── ruler_widget.py
│   │   └── lane_packer.py
│   ├── map/              # Map and markers
│   │   ├── map_graphics_view.py
│   │   └── map_marker.py
│   ├── entity_editor.py  # Entity editing
│   ├── event_editor.py   # Event editing
│   ├── unified_list.py   # Project explorer
│   └── history_panel.py  # Undo/redo visualization
├── dialogs/              # Modal dialogs
│   ├── create_world_dialog.py
│   └── import_dialog.py
├── workers/              # Background Qt workers
│   └── database_worker.py
└── utils/
    └── style_helper.py   # Theme utilities
```

**Widget Pattern:**

```python
class EntityEditor(QWidget):
    """Entity editing widget."""
    
    # Signals (output)
    entity_updated = pyqtSignal(dict)
    relation_requested = pyqtSignal(str, str, str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._connect_signals()
    
    def set_entity(self, entity: dict):
        """Display entity (input from controller)."""
        self._entity = entity
        self._update_ui()
    
    def _on_save_clicked(self):
        """User clicked save button."""
        data = self._collect_form_data()
        self.entity_updated.emit(data)  # Emit signal
```

**Key Principles:**
- Widgets **display** data, don't modify it
- All mutations via **signals**
- Controllers listen to signals and invoke commands
- No direct database access from GUI

---

## Design Patterns

### Command Pattern

**Problem**: How to implement undo/redo for all user actions?

**Solution**: Encapsulate each action as a command object.

```python
class UpdateEntityCommand(BaseCommand):
    """Update an entity's properties."""
    
    def __init__(self, service, entity_id, new_data):
        super().__init__(service)
        self.entity_id = entity_id
        self.new_data = new_data
        self.old_data = None  # Stored during execute
    
    def execute(self):
        """Apply update."""
        repo = EntityRepository(self.service)
        entity = repo.get(self.entity_id)
        self.old_data = entity.to_dict()  # Save for undo
        entity.name = self.new_data['name']
        repo.update(entity)
    
    def undo(self):
        """Revert update."""
        repo = EntityRepository(self.service)
        entity = Entity.from_dict(self.old_data)
        repo.update(entity)
```

**Benefits:**
- Undo/redo "for free"
- Command history is audit log
- Commands serializable for persistence
- Testable in isolation

---

### Repository Pattern

**Problem**: Keep database logic out of business logic.

**Solution**: Repositories provide data access abstraction.

```python
# Bad: Business logic mixed with SQL
def update_event(event_id, name):
    conn = sqlite3.connect('db.sqlite')
    cursor = conn.cursor()
    cursor.execute("UPDATE events SET name=? WHERE id=?", (name, event_id))
    conn.commit()
    conn.close()

# Good: Repository abstracts database
class EventRepository:
    def update(self, event: Event) -> Event:
        # SQL implementation hidden
        pass

def update_event(event_id, name):
    repo = EventRepository(db_service)
    event = repo.get(event_id)
    event.name = name
    repo.update(event)
```

---

### Signal/Slot Pattern (Qt)

**Problem**: Loose coupling between components.

**Solution**: Qt signals and slots for event-driven communication.

```python
# Widget emits signal
class EntityEditor(QWidget):
    entity_updated = pyqtSignal(dict)
    
    def _on_save(self):
        self.entity_updated.emit(self._get_data())

# Controller connects and responds
class MainWindow(QMainWindow):
    def __init__(self):
        self.entity_editor.entity_updated.connect(
            self._on_entity_updated
        )
    
    def _on_entity_updated(self, data):
        cmd = UpdateEntityCommand(self.service, data)
        self.command_coordinator.execute(cmd)
```

**Benefits:**
- Widgets don't know about controllers
- Easy to swap implementations
- Testable with mock slots

---

### Coordinator Pattern

**Problem**: MainWindow becomes too complex.

**Solution**: Extract coordination logic to specialized coordinators.

```python
class BackupCoordinator:
    """Manages automated backups."""
    
    def __init__(self, backup_service):
        self.backup_service = backup_service
        self.timer = QTimer()
        self.timer.timeout.connect(self._perform_backup)
    
    def start(self, interval_minutes=15):
        """Start automated backups."""
        self.timer.start(interval_minutes * 60 * 1000)
    
    def _perform_backup(self):
        """Perform backup."""
        self.backup_service.create_backup()
```

---

## Threading Model

### Two-Thread Architecture

**Design**: Strict separation between UI and database operations.

```
┌────────────────────────────────┐
│       Main Thread (GUI)        │
│  - Qt event loop               │
│  - Widget rendering            │
│  - User interactions           │
│  - Signal emissions            │
└────────────┬───────────────────┘
             │ QueuedConnection
             │ (thread-safe signals)
             ↓
┌────────────────────────────────┐
│     Worker Thread (Database)   │
│  - DatabaseService             │
│  - Command execution           │
│  - Long-running operations     │
│  - File I/O                    │
└────────────────────────────────┘
```

### DatabaseWorker

```python
class DatabaseWorker(QThread):
    """Background thread for database operations."""
    
    # Signals (output to main thread)
    command_finished = pyqtSignal(str, bool, object)
    progress_updated = pyqtSignal(int, str)
    
    def __init__(self, db_path):
        super().__init__()
        self.db_service = None
        self.command_queue = Queue()
    
    def run(self):
        """Thread main loop."""
        self.db_service = DatabaseService(db_path)
        
        while self.running:
            cmd = self.command_queue.get()
            try:
                cmd.execute()
                self.command_finished.emit(cmd.id, True, None)
            except Exception as e:
                self.command_finished.emit(cmd.id, False, e)
```

### Thread Safety Rules

1. **DatabaseService owned by worker thread**
   - Never access from main thread

2. **Data marshaled via signals**
   - Signals use `Qt.QueuedConnection` for cross-thread safety
   - Pass immutable data or copies

3. **No shared mutable state**
   - Each thread has its own data structures

4. **GUI updates only on main thread**
   - Worker emits signal → main thread slot updates UI

---

## Database Architecture

### SQLite Configuration

```python
# WAL mode for concurrency
PRAGMA journal_mode = WAL;

# Foreign key enforcement
PRAGMA foreign_keys = ON;

# Optimize performance
PRAGMA synchronous = NORMAL;
PRAGMA temp_store = MEMORY;
PRAGMA mmap_size = 268435456;  # 256MB
```

### Hybrid Schema

**Strict Columns** (searchable, sortable):
```sql
CREATE TABLE events (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    lore_date REAL NOT NULL,
    type TEXT,
    created_at REAL,
    modified_at REAL
);
```

**JSON Attributes** (flexible):
```sql
CREATE TABLE event_attributes (
    event_id TEXT PRIMARY KEY,
    attributes TEXT NOT NULL,  -- JSON
    FOREIGN KEY (event_id) REFERENCES events(id)
);
```

### Schema Structure

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   events    │────→│  relations  │←────│  entities   │
└─────────────┘     └─────────────┘     └─────────────┘
       │                   │                     │
       ↓                   ↓                     ↓
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   event_    │     │  relation_  │     │   entity_   │
│ attributes  │     │ attributes  │     │ attributes  │
└─────────────┘     └─────────────┘     └─────────────┘
```

**Additional Tables:**
- `maps`, `map_markers`: Geographic data
- `calendars`: Custom calendar configurations
- `command_history`: Undo/redo persistence
- `edit_sessions`: Session tracking
- `backups`: Backup metadata

---

## Data Flow

### User Action Flow

```
1. User clicks "Create Event"
         ↓
2. CreateEventDialog shows, user fills form
         ↓
3. Dialog emits event_created(data) signal
         ↓
4. MainWindow._on_event_created(data) slot
         ↓
5. Create CreateEventCommand(service, data)
         ↓
6. CommandCoordinator.execute(cmd)
         ↓
7. Add to undo stack, submit to DatabaseWorker
         ↓
8. Worker thread: cmd.execute()
         ↓
9. EventRepository.create(event)
         ↓
10. SQL INSERT into database
         ↓
11. HistoryService.record(cmd)
         ↓
12. Worker emits command_finished signal
         ↓
13. MainWindow updates UI
```

---

## Key Services

### DatabaseService

**Purpose**: Low-level database access.

```python
class DatabaseService:
    """SQLite database interface."""
    
    def __init__(self, db_path: str):
        self.connection = sqlite3.connect(db_path)
        self._configure()
    
    def execute(self, sql: str, params: tuple = ()) -> List[dict]:
        """Execute SQL query."""
        cursor = self.connection.cursor()
        cursor.execute(sql, params)
        return cursor.fetchall()
    
    def transaction(self) -> ContextManager:
        """Transaction context manager."""
        return self.connection
```

---

### HistoryService

**Purpose**: Persistent undo/redo.

```python
class HistoryService:
    """Manages command history persistence."""
    
    def record(self, cmd: BaseCommand, session_id: str):
        """Save command to database."""
        data = cmd.to_dict()
        self.db.execute(
            "INSERT INTO command_history VALUES (?, ?, ?)",
            (cmd.id, session_id, json.dumps(data))
        )
    
    def restore_session(self, session_id: str) -> List[BaseCommand]:
        """Load commands from previous session."""
        rows = self.db.execute(
            "SELECT data FROM command_history WHERE session_id = ?",
            (session_id,)
        )
        return [self._deserialize(row) for row in rows]
```

---

## Command System

Commands expose two separate history policies:

- `is_undoable` controls the current in-memory undo stack.
- `persist_to_history` controls whether the command survives restart.
- `has_history` remains a compatibility alias during migration.

Every command has a stable `command_id`. Worker results may contain serializable
effects, which are applied only on the Qt main thread. `CommandCoordinator`
moves undo and redo stack entries only after the worker reports success, so a
failed execute, undo, or redo retains the prior stack state.

### CommandCoordinator

**Purpose**: Manage undo/redo stacks.

```python
class CommandCoordinator:
    """Coordinates command execution and history."""
    
    def __init__(self, worker: DatabaseWorker):
        self.worker = worker
        self.undo_stack = []
        self.redo_stack = []
    
    def execute(self, cmd: BaseCommand):
        """Execute command and add to undo stack."""
        self.worker.submit(cmd)
        self.undo_stack.append(cmd)
        self.redo_stack.clear()  # Can't redo after new action
    
    def undo(self):
        """Undo last command."""
        if not self.undo_stack:
            return
        cmd = self.undo_stack.pop()
        cmd.undo()
        self.redo_stack.append(cmd)
    
    def redo(self):
        """Redo last undone command."""
        if not self.redo_stack:
            return
        cmd = self.redo_stack.pop()
        cmd.execute()
        self.undo_stack.append(cmd)
```

---

## Communication Patterns

### Signal Types

**1. Widget → Controller**
```python
# Widget
entity_updated = pyqtSignal(dict)

# Controller
self.entity_editor.entity_updated.connect(self._on_update)
```

**2. Worker → Main Thread**
```python
# Worker
command_finished = pyqtSignal(str, bool, object)

# Main Thread
self.worker.command_finished.connect(self._on_cmd_done)
```

**3. Service → Application**
```python
# Service
backup_created = pyqtSignal(str)

# Application
self.backup_service.backup_created.connect(self._show_notification)
```

---

## Extension Points

### Adding New Commands

1. Create subclass of `BaseCommand`
2. Implement `execute()` and `undo()`
3. Implement `to_dict()` and `from_dict()`
4. Register in `WorkerManager.on_db_initialized()`

### Adding New Repositories

1. Create repository class in `services/repositories/`
2. Inject `DatabaseService` via constructor
3. Implement CRUD methods
4. Use in commands

### Adding New Widgets

1. Create widget in `gui/widgets/`
2. Define signals for outputs
3. Implement data display methods
4. Wire up in `MainWindow`

---

## Next Steps

- **[Development Guide](DEVELOPMENT.md)** - Setup and coding standards
- **[Database Schema](DATABASE.md)** - Detailed schema documentation
- **[API Reference](API_REFERENCE.md)** - Key classes and methods

---

**Navigation:**  
[← FAQ](FAQ.md) • [Back to Index](INDEX.md) • [Development →](DEVELOPMENT.md)
