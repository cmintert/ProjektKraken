# Thread Safety & Signal Connection Guide

**Status:** Production Guidelines  
**Last Updated:** 2024-02-03  
**Audience:** Developers working on ProjektKraken

---

## Table of Contents
1. [Overview](#overview)
2. [Connection Type Decision Matrix](#connection-type-decision-matrix)
3. [Best Practices](#best-practices)
4. [Common Patterns](#common-patterns)
5. [Anti-Patterns to Avoid](#anti-patterns-to-avoid)
6. [Debugging Guide](#debugging-guide)

---

## Overview

ProjektKraken uses a **two-thread architecture**:
- **Main Thread (GUI):** All UI components, MainWindow, DataHandler
- **Worker Thread (Database):** DatabaseWorker, DatabaseService, all database operations

**Critical Rule:** All cross-thread signal connections MUST use `Qt.ConnectionType.QueuedConnection`.

---

## Connection Type Decision Matrix

| Source Thread | Target Thread | Connection Type | Required? | Why |
|--------------|--------------|-----------------|-----------|-----|
| Main (Widget) | Main (Widget) | `AutoConnection` | Recommended | Explicit is better than implicit |
| Main (Widget) | Main (Slot) | `AutoConnection` | Recommended | Same thread, direct call is safe |
| Main | Worker | `QueuedConnection` | **REQUIRED** | Cross-thread, prevents race conditions |
| Worker | Main | `QueuedConnection` | **REQUIRED** | Cross-thread, UI updates must be queued |
| Worker | Worker | `AutoConnection` | Recommended | Same thread, but be explicit |

### Connection Type Explanations

**`Qt.ConnectionType.AutoConnection` (Default)**
- Qt automatically chooses Direct or Queued based on thread affinity
- Safe for same-thread connections
- **Best Practice:** Still specify explicitly for code clarity

**`Qt.ConnectionType.DirectConnection`**
- Slot called immediately (synchronous)
- Only safe when sender and receiver are in same thread
- **Use Case:** Performance-critical same-thread signals
- **Warning:** Never use for cross-thread connections

**`Qt.ConnectionType.QueuedConnection`**
- Slot called via event queue (asynchronous)
- Thread-safe for cross-thread communication
- **Use Case:** All worker ↔ main thread signals
- **Performance:** Small overhead (~microseconds) from event queue

**`Qt.ConnectionType.BlockingQueuedConnection`**
- Queued but blocks sender until slot completes
- **Warning:** Can cause deadlocks, avoid unless absolutely necessary
- **Use Case:** Rare situations where return value is needed across threads

---

## Best Practices

### 1. Always Specify Connection Type

❌ **Bad (Implicit):**
```python
self.btn_save.clicked.connect(self._on_save)
```

✅ **Good (Explicit):**
```python
# Same-thread connection (widget to widget in main thread)
self.btn_save.clicked.connect(
    self._on_save,
    Qt.ConnectionType.AutoConnection
)
```

✅ **Best (With Comment):**
```python
# Same-thread connection: Save button to slot
self.btn_save.clicked.connect(
    self._on_save,
    Qt.ConnectionType.AutoConnection
)
```

### 2. Document Cross-Thread Connections

✅ **Required for Cross-Thread:**
```python
# CROSS-THREAD: Main → Worker
# Use QueuedConnection for thread safety
connection_type = Qt.ConnectionType.QueuedConnection

self.window.command_requested.connect(
    self.window.worker.run_command,
    connection_type
)

self.window.worker.events_loaded.connect(
    self.window.data_handler.on_events_loaded,
    connection_type
)
```

### 3. Group Cross-Thread Connections

✅ **Pattern from worker_manager.py:**
```python
# Connect Worker Signals (explicit QueuedConnection for cross-thread safety)
# All connections use QueuedConnection because worker is on a different thread
connection_type = Qt.ConnectionType.QueuedConnection

self.window.worker.initialized.connect(
    self.on_db_initialized, connection_type
)
self.window.worker.events_loaded.connect(
    self.window.data_handler.on_events_loaded, connection_type
)
self.window.worker.entities_loaded.connect(
    self.window.data_handler.on_entities_loaded, connection_type
)
```

### 4. Use Helper Methods for Consistency

✅ **Connection Manager Pattern:**
```python
def _connect_signal_safe(
    self,
    obj: object,
    signal_name: str,
    slot: callable,
    obj_description: str = "",
    connection_type: Qt.ConnectionType = Qt.ConnectionType.AutoConnection,
) -> bool:
    """Safely connect with explicit connection type."""
    signal = getattr(obj, signal_name)
    signal.connect(slot, connection_type)
    return True
```

### 5. Add Thread Safety Checks to Services

✅ **DataHandler Pattern (Main Thread Only):**
```python
from PySide6.QtCore import QThread
from PySide6.QtWidgets import QApplication

app = QApplication.instance()
if app is not None:
    main_thread = app.thread()
    current_thread = QThread.currentThread()
    if current_thread != main_thread:
        raise RuntimeError(
            f"DataHandler must be created in the main thread. "
            f"Current thread: {current_thread}, Main thread: {main_thread}"
        )
```

---

## Common Patterns

### Pattern 1: Data Loading (Worker → Main)

```python
# In MainWindow (main thread)
@Slot()
def load_events(self) -> None:
    """Request event loading from worker thread."""
    # Emit signal to worker - cross-thread
    QMetaObject.invokeMethod(
        self.worker,
        "load_events",
        Qt.ConnectionType.QueuedConnection
    )

# In DatabaseWorker (worker thread)
@Slot()
def load_events(self) -> None:
    """Load events from database."""
    events = self.db_service.get_events()
    # Emit signal back to main thread - cross-thread
    self.events_loaded.emit(events)

# In DataHandler (main thread)
@Slot(list)
def on_events_loaded(self, events: List[Event]) -> None:
    """Handle loaded events."""
    self._cached_events = events
    self.events_ready.emit(events)
```

**Connection Setup:**
```python
# Cross-thread: Worker → DataHandler
connection_type = Qt.ConnectionType.QueuedConnection
worker.events_loaded.connect(
    data_handler.on_events_loaded,
    connection_type
)
```

### Pattern 2: Command Execution (Main → Worker → Main)

```python
# In MainWindow (main thread)
def update_event(self, event: Event) -> None:
    """Update an event via command pattern."""
    cmd = UpdateEventCommand(event.id, event.to_dict())
    # Emit to worker - cross-thread
    self.command_requested.emit(cmd)

# In DatabaseWorker (worker thread)
@Slot(BaseCommand)
def run_command(self, command: BaseCommand) -> None:
    """Execute command on worker thread."""
    result = command.execute(self.db_service)
    # Emit result back to main - cross-thread
    self.command_finished.emit(result)

# In DataHandler (main thread)
@Slot(CommandResult)
def on_command_finished(self, result: CommandResult) -> None:
    """Handle command completion."""
    if result.success:
        self.reload_events.emit()
```

**Connection Setup:**
```python
connection_type = Qt.ConnectionType.QueuedConnection

# Main → Worker
main_window.command_requested.connect(
    worker.run_command,
    connection_type
)

# Worker → Main
worker.command_finished.connect(
    data_handler.on_command_finished,
    connection_type
)
```

### Pattern 3: Widget Internal Connections (Same Thread)

```python
# All in EventEditorWidget (main thread)
class EventEditorWidget(QWidget):
    def __init__(self):
        super().__init__()
        
        # Same-thread connections within widget
        # Use AutoConnection or omit for clarity
        self.name_edit.textChanged.connect(
            self._on_field_changed,
            Qt.ConnectionType.AutoConnection
        )
        
        self.btn_save.clicked.connect(
            self._on_save,
            Qt.ConnectionType.AutoConnection
        )
        
        self.btn_discard.clicked.connect(
            self._on_discard,
            Qt.ConnectionType.AutoConnection
        )
```

---

## Anti-Patterns to Avoid

### ❌ Anti-Pattern 1: Missing Connection Type for Cross-Thread

**Problem:**
```python
# BAD - Implicit connection type for cross-thread
self.worker.events_loaded.connect(self.data_handler.on_events_loaded)
```

**Why It's Bad:**
- Defaults to `AutoConnection`, which becomes `DirectConnection` in certain cases
- Can cause race conditions or crashes
- Hard to debug

**Fix:**
```python
# GOOD - Explicit QueuedConnection
connection_type = Qt.ConnectionType.QueuedConnection
self.worker.events_loaded.connect(
    self.data_handler.on_events_loaded,
    connection_type
)
```

### ❌ Anti-Pattern 2: Using processEvents()

**Problem:**
```python
# BAD - Blocks event loop, causes re-entrancy
self.status_bar.showMessage("Processing...")
QApplication.processEvents()  # Don't do this!
self.do_long_operation()
```

**Why It's Bad:**
- Causes re-entrant event processing
- Can trigger nested event handlers
- Leads to unpredictable behavior
- UI freezes possible

**Fix:**
```python
# GOOD - Use QTimer for deferred execution
self.status_bar.showMessage("Processing...")
QTimer.singleShot(0, lambda: self._execute_operation())

def _execute_operation(self) -> None:
    """Execute operation after event loop processes updates."""
    self.do_long_operation()
```

### ❌ Anti-Pattern 3: Direct Database Calls from GUI

**Problem:**
```python
# BAD - Blocking database call in main thread
class EventEditorWidget(QWidget):
    def load_event(self, event_id: str):
        event = self.db_service.get_event(event_id)  # Blocks UI!
        self.populate_form(event)
```

**Why It's Bad:**
- Blocks main thread, freezing UI
- No separation of concerns
- Can't be undone
- Error handling is harder

**Fix:**
```python
# GOOD - Request via signal, worker handles it
class EventEditorWidget(QWidget):
    load_requested = Signal(str)
    
    def load_event(self, event_id: str):
        self.load_requested.emit(event_id)  # Non-blocking
    
    @Slot(Event)
    def on_event_loaded(self, event: Event):
        """Handle event loaded by worker."""
        self.populate_form(event)
```

### ❌ Anti-Pattern 4: Accessing UI from Worker Thread

**Problem:**
```python
# BAD - Direct UI manipulation from worker thread
class DatabaseWorker(QObject):
    def load_events(self):
        events = self.db_service.get_events()
        # CRASH! UI access from wrong thread
        self.main_window.event_list.populate(events)
```

**Why It's Bad:**
- Qt widgets are not thread-safe
- Will crash or cause undefined behavior
- Violates Qt's threading model

**Fix:**
```python
# GOOD - Use signals to communicate
class DatabaseWorker(QObject):
    events_loaded = Signal(list)
    
    def load_events(self):
        events = self.db_service.get_events()
        # Safe - signal will be queued to main thread
        self.events_loaded.emit(events)
```

---

## Debugging Guide

### Symptom 1: Application Crashes with Thread Error

**Error Message:**
```
QObject: Cannot create children for a parent in a different thread
```

**Diagnosis:**
- UI object created in wrong thread
- Check where QWidget instances are created

**Fix:**
```python
# Ensure all widgets created in main thread
assert QThread.currentThread() == QApplication.instance().thread()
```

### Symptom 2: UI Freezes During Operations

**Diagnosis:**
- Long-running operation in main thread
- Check for blocking calls (database, network, file I/O)

**Fix:**
- Move operation to worker thread
- Use signals for communication

### Symptom 3: Data Not Updating

**Diagnosis:**
- Signal not connected
- Wrong connection type
- Slot not being called

**Debug Steps:**
```python
# Add debug logging to slots
@Slot(list)
def on_events_loaded(self, events: List[Event]) -> None:
    logger.debug(f"on_events_loaded called with {len(events)} events")
    logger.debug(f"Current thread: {QThread.currentThread()}")
    logger.debug(f"Main thread: {QApplication.instance().thread()}")
```

### Symptom 4: Race Conditions

**Diagnosis:**
- AutoConnection used for cross-thread
- Direct database access from multiple threads

**Fix:**
- Use `QueuedConnection` for all cross-thread
- Enable SQLite WAL mode (already done in ProjektKraken)

### Enable Qt Debug Logging

```python
import os
os.environ["QT_LOGGING_RULES"] = "qt.qpa.*=true;*.debug=true"
```

---

## Code Review Checklist

When reviewing code, check:

- [ ] All cross-thread connections use `Qt.ConnectionType.QueuedConnection`
- [ ] Same-thread connections explicitly documented (even if using `AutoConnection`)
- [ ] No `QApplication.processEvents()` calls
- [ ] No direct database calls from GUI layer
- [ ] No UI manipulation from worker thread
- [ ] Thread safety checks in service `__init__` methods
- [ ] Signals used instead of direct method calls for cross-component communication
- [ ] Long-running operations moved to worker thread

---

## References

- **Qt Documentation:** [Threads and QObjects](https://doc.qt.io/qt-6/threads-qobject.html)
- **Qt Documentation:** [Signals & Slots](https://doc.qt.io/qt-6/signalsandslots.html)
- **ProjektKraken:** `ARCHITECTURE.md` - Thread Safety Model section
- **Example:** `src/app/worker_manager.py` - Exemplary cross-thread connections
- **Example:** `src/app/data_handler.py` - Thread safety checks

---

**Document Version:** 1.0  
**Author:** Production-Readiness Code Review  
**Next Review:** After addressing all 172+ signal connection audit items
