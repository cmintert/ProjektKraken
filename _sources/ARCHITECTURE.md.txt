# ProjektKraken Architecture & Thread Safety Guide

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Thread Safety Model](#thread-safety-model)
3. [Signal/Slot Patterns](#signalslot-patterns)
4. [Layer Responsibilities](#layer-responsibilities)
5. [Best Practices](#best-practices)

---

## Architecture Overview

ProjektKraken uses a **layered Service-Oriented Architecture (SOA)** with strict separation of concerns:

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

1. **Separation of Concerns:** Each layer has a single, well-defined responsibility
2. **Dependency Flow:** Top → Down (app depends on services, services depend on core)
3. **Communication:** Signals for loose coupling between components
4. **Thread Safety:** Worker thread for all database operations
5. **Command Pattern:** All user actions encapsulated as commands

---

## Thread Safety Model

### Threading Architecture

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
- ✅ MainWindow and coordinators
- ✅ DataHandler (caches UI data)
- ✅ UI event handlers
- ❌ NO direct database calls

**WORKER THREAD:**
- ✅ DatabaseWorker (moved via moveToThread)
- ✅ DatabaseService (thread affinity via worker)
- ✅ All database operations
- ✅ Command execution
- ❌ NO UI operations

### Thread Safety Guarantees

1. **Signal/Slot with QueuedConnection**
   ```python
   # All cross-thread connections use QueuedConnection explicitly
   worker.events_loaded.connect(
       data_handler.on_events_loaded,
       Qt.ConnectionType.QueuedConnection
   )
   ```
   - Ensures slots run in receiver's thread
   - Thread-safe event queue mechanism
   - No manual locking needed

2. **SQLite WAL Mode**
   ```python
   # DatabaseService.connect()
   connection.execute("PRAGMA journal_mode=WAL;")
   ```
   - Allows concurrent reads while writing
   - Writer-reader isolation
   - Crash-safe transactions

3. **No Shared Mutable State**
   - Worker and Main threads share no variables
   - All data passed via immutable signals (or deep copies)
   - Cache updates happen atomically in slots

4. **Runtime Verification**
   ```python
   # DataHandler.__init__()
   if QThread.currentThread() != QApplication.instance().thread():
       raise RuntimeError("DataHandler must be in main thread")
   ```

### Common Pitfalls to Avoid

❌ **DON'T:** Call UI methods from worker thread
```python
# WRONG - will crash or cause undefined behavior
def load_events(self):
    events = db.get_events()
    self.main_window.update_list(events)  # BAD!
```

✅ **DO:** Emit signal instead
```python
# CORRECT - use signal/slot
def load_events(self):
    events = db.get_events()
    self.events_loaded.emit(events)  # Good!
```

❌ **DON'T:** Access database from main thread
```python
# WRONG - blocks UI
def on_button_clicked(self):
    events = self.db_service.get_events()  # BAD!
```

✅ **DO:** Request via signal to worker
```python
# CORRECT - asynchronous
def on_button_clicked(self):
    self.load_events_requested.emit()  # Good!
```

---

## Signal/Slot Patterns

### Pattern 1: Data Loading

**Flow:** User Action → Worker Signal → Load Data → Worker Signal → Update UI

```python
# MainWindow
@Slot()
def on_refresh_clicked(self):
    self.worker.load_events()  # Trigger worker slot

# DatabaseWorker
@Slot()
def load_events(self):
    events = self.db_service.get_events()
    self.events_loaded.emit(events)  # Signal with data

# DataHandler (runs in main thread)
@Slot(list)
def on_events_loaded(self, events: List[Event]):
    self._cached_events = events
    self.events_ready.emit(events)  # Forward to UI

# MainWindow
@Slot(list)
def _on_events_ready(self, events: List[Event]):
    self.event_list.populate(events)  # Update UI
```

**Benefits:**
- Non-blocking UI
- Clear data flow
- Easy to test each component

### Pattern 2: Command Execution

**Flow:** User Action → Command → Worker Executes → Result Signal → UI Update

```python
# MainWindow
def create_event(self, name: str, date: float):
    cmd = CreateEventCommand(name, date)
    self.command_requested.emit(cmd)

# DatabaseWorker
@Slot(BaseCommand)
def run_command(self, command: BaseCommand):
    result = command.execute(self.db_service)
    self.command_finished.emit(result)  # CommandResult

# DataHandler
@Slot(CommandResult)
def on_command_finished(self, result: CommandResult):
    if result.success:
        self.reload_events.emit()  # Trigger refresh
    else:
        self.command_failed.emit(result.message)
```

**Benefits:**
- Undo/redo support (commands are objects)
- Validation before execution
- Consistent error handling

### Pattern 3: Editor Coordination

**Flow:** Select Item → Load Details → Update Editor → User Edits → Save Command

```python
# Timeline widget emits selection
self.event_selected.emit(event_id)

# MainWindow listens and requests details
@Slot(str)
def on_event_selected(self, event_id: str):
    self.worker.load_event_details(event_id)

# Worker loads event + relations
@Slot(str)
def load_event_details(self, event_id: str):
    event = self.db_service.get_event(event_id)
    relations = self.db_service.get_event_relations(event_id)
    self.event_details_loaded.emit(event, relations)

# MainWindow updates editor
@Slot(Event, list)
def on_event_details_loaded(self, event: Event, relations: list):
    self.event_editor.load_event(event, relations)
```

---

## Layer Responsibilities

### 1. App Layer (`src/app/`)

**Purpose:** UI orchestration and coordination

**Key Components:**
- `MainWindow`: Central hub, dock management, menu actions
- `DataHandler`: Loose coupling via signals, caches UI data
- `WorkerManager`: Worker thread lifecycle
- `ConnectionManager`: Signal/slot wiring with validation
- **Coordinators:** Feature-specific orchestration (timeline grouping, backup, navigation)

**Rules:**
- ✅ Emit signals, don't call methods directly
- ✅ Handle UI events
- ✅ Manage dock widget layout
- ❌ NO business logic
- ❌ NO database operations

### 2. Commands Layer (`src/commands/`)

**Purpose:** Encapsulate user actions as objects

**Pattern:**
```python
class CreateEventCommand(BaseCommand):
    def __init__(self, name: str, lore_date: float):
        super().__init__()
        self.name = name
        self.lore_date = lore_date
        self._created_id = None
    
    def execute(self, db_service: DatabaseService) -> CommandResult:
        event = Event(name=self.name, lore_date=self.lore_date)
        self._created_id = db_service.create_event(event)
        return CommandResult(success=True, data={"id": self._created_id})
    
    def undo(self, db_service: DatabaseService) -> bool:
        db_service.delete_event(self._created_id)
        return True
```

**Rules:**
- ✅ Validate input in `__init__`
- ✅ Store state for undo
- ✅ Return `CommandResult` with success/error info
- ❌ NO UI operations
- ❌ NO signals (let caller handle results)

### 3. Services Layer (`src/services/`)

**Purpose:** Business logic and data access

**Key Components:**
- `DatabaseService`: SQLite connection, schema management
- `DatabaseWorker`: Background thread worker (QObject)
- **Repositories:** Modular CRUD (EventRepository, EntityRepository, etc.)
- **Business Services:** ImportService, SearchService, SummaryService

**Rules:**
- ✅ CRUD operations
- ✅ Data transformations
- ✅ External integrations (LLM APIs)
- ❌ NO UI components
- ❌ NO direct user interaction

### 4. Core Layer (`src/core/`)

**Purpose:** Domain models and utilities

**Components:**
- **Data Models:** Event, Entity, Relation, Map, etc. (dataclasses)
- **Utilities:** Calendar, ThemeManager, DateParser
- **Protocols:** Structural typing for interfaces

**Rules:**
- ✅ Pure Python logic
- ✅ Immutable data structures (dataclasses)
- ✅ Self-contained (no dependencies on other layers)
- ❌ NO Qt imports
- ❌ NO database access

### 5. GUI Layer (`src/gui/`)

**Purpose:** Reusable UI components

**Components:**
- **Widgets:** Timeline, EventEditor, EntityEditor, UnifiedList
- **Dialogs:** Settings, Import Preview, Calendar Config
- **Mixins:** AutosaveMixin, LayoutGuard (reusable behaviors)

**Rules:**
- ✅ "Dumb UI" - display data, emit signals
- ✅ Widget-specific logic only
- ❌ NO business logic
- ❌ NO database access

---

## Best Practices

### 1. Adding a New Feature

**Checklist:**
1. ✅ Create command class in `src/commands/`
2. ✅ Add worker slot in `DatabaseWorker`
3. ✅ Add result signal to `DatabaseWorker`
4. ✅ Connect signal in `WorkerManager` with `QueuedConnection`
5. ✅ Handle result in `DataHandler` or `MainWindow`
6. ✅ Update UI in main thread slots

**Example: Add "Duplicate Event" Feature**

1. Create command:
   ```python
   # src/commands/event_commands.py
   class DuplicateEventCommand(BaseCommand):
       def execute(self, db_service):
           original = db_service.get_event(self.event_id)
           duplicate = Event(name=f"{original.name} (Copy)", ...)
           new_id = db_service.create_event(duplicate)
           return CommandResult(success=True, data={"id": new_id})
   ```

2. Add worker method:
   ```python
   # src/services/worker.py
   @Slot(str)
   def duplicate_event(self, event_id: str):
       cmd = DuplicateEventCommand(event_id)
       result = cmd.execute(self.db_service)
       self.command_finished.emit(result)
   ```

3. Connect in WorkerManager:
   ```python
   self.window.duplicate_event_requested.connect(
       self.window.worker.duplicate_event,
       Qt.ConnectionType.QueuedConnection
   )
   ```

4. Handle in MainWindow:
   ```python
   def on_duplicate_event_clicked(self):
       selected_id = self.timeline.get_selected_event_id()
       self.duplicate_event_requested.emit(selected_id)
   ```

### 2. Debugging Cross-Thread Issues

**Symptoms:**
- UI freezes
- Crashes with "QObject: Cannot create children for a parent in a different thread"
- Data not updating

**Debugging Steps:**
1. ✅ Verify connection type: Check all cross-thread signals use `QueuedConnection`
2. ✅ Check thread affinity:
   ```python
   logger.debug(f"Thread: {QThread.currentThread()}")
   logger.debug(f"Main: {QApplication.instance().thread()}")
   ```
3. ✅ Add assertions:
   ```python
   assert QThread.currentThread() == self.thread()
   ```
4. ✅ Enable Qt logging:
   ```python
   os.environ["QT_LOGGING_RULES"] = "qt.qpa.*=true"
   ```

### 3. Testing Patterns

**Unit Tests:**
```python
def test_command_execution():
    db = DatabaseService(":memory:")
    db.connect()
    
    cmd = CreateEventCommand(name="Test", lore_date=1.0)
    result = cmd.execute(db)
    
    assert result.success
    assert result.data["id"] is not None
```

**Integration Tests with Signals:**
```python
def test_worker_signal_emission(qtbot):
    worker = DatabaseWorker(":memory:")
    worker.initialize_db()
    
    with qtbot.waitSignal(worker.events_loaded, timeout=1000):
        worker.load_events()
```

### 4. Performance Guidelines

**Database:**
- ✅ Use transactions for batch operations
- ✅ Add indexes for frequently queried columns
- ✅ Use `LIMIT` for large result sets
- ❌ Avoid N+1 queries (load relations in batch)

**UI:**
- ✅ Lazy load large datasets
- ✅ Use virtual lists for 1000+ items
- ✅ Debounce frequent signals (e.g., text input)
- ❌ Don't load all data upfront

**Memory:**
- ✅ Clear caches when switching worlds
- ✅ Use weak references for parent-child relationships
- ✅ Delete large objects explicitly
- ❌ Don't keep entire database in memory

---

## Appendix: Common Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| "Cannot create children for parent in different thread" | UI created in worker thread | Move object creation to main thread |
| "Database is locked" | Multiple writers without WAL | Enable WAL mode in DatabaseService |
| "Signal already connected" | Duplicate connection in ConnectionManager | Check connection logic, use `disconnect()` first |
| "QThread already running" | Starting thread twice | Check `worker_thread.isRunning()` before start |

---

**Document Version:** 1.0
**Last Updated:** 2026-01-25
