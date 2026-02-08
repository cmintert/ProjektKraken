# Qt Threading Safety Guide

**Document:** Qt Threading Safety and Best Practices  
**Last Updated:** 2026-01-04  
**Status:** Production Guidelines

## Overview

ProjektKraken uses Qt's threading model to keep the UI responsive while performing database operations and other long-running tasks. This document outlines the threading architecture, safety patterns, and best practices used throughout the application.

## Threading Architecture

### Core Principles

1. **UI Thread (Main Thread)**: All UI operations and widget updates must occur on the main thread
2. **Worker Thread**: Database operations and long-running tasks execute on a dedicated worker thread
3. **Signal/Slot Communication**: Thread-safe communication between threads using Qt's signal/slot mechanism

### Thread Affinity

```python
# Main thread owns:
- MainWindow and all QWidget subclasses
- DatabaseWorker (moved to worker thread)
- All UI event handlers

# Worker thread owns:
- DatabaseService instance
- AttachmentService instance
- AssetStore instance
- All database connections
```

## Worker Thread Pattern

### Implementation in WorkerManager

```python
# From src/app/worker_manager.py
class WorkerManager:
    def setup(self):
        # Create worker thread
        self.window.worker_thread = QThread()
        
        # Create worker object
        self.window.worker = DatabaseWorker(self.db_path)
        
        # Move worker to thread (thread affinity transfer)
        self.window.worker.moveToThread(self.window.worker_thread)
        
        # Start thread
        self.window.worker_thread.start()
```

### Key Safety Points

1. **Never access UI from worker thread**: All UI updates must be done via signals
2. **Database connection per thread**: SQLite connections have thread affinity
3. **Worker owns services**: DatabaseService, AttachmentService are created and accessed only on worker thread

## Signal/Slot Connection Types

### QueuedConnection (Cross-Thread)

**Use When**: Connecting signals from worker thread to main thread slots

```python
# Correct: QueuedConnection for cross-thread communication
self.worker.events_loaded.connect(
    self.timeline_widget.set_events,
    Qt.ConnectionType.QueuedConnection
)
```

**Why QueuedConnection?**
- Thread-safe: Signal is queued in the receiver's event loop
- Parameters are copied and passed safely
- Prevents race conditions and crashes

### BlockingQueuedConnection (Synchronous Cross-Thread)

**Use When**: Need to wait for worker thread operation to complete

```python
# Cleanup must complete before shutdown
self.worker.cleanup.connect(
    self.worker, "cleanup",
    Qt.ConnectionType.BlockingQueuedConnection
)
```

**Cautions:**
- Can cause deadlocks if used incorrectly
- Only use when absolutely necessary (e.g., shutdown sequences)
- Never use from worker thread back to UI thread (will deadlock)

### DirectConnection (Same Thread)

**Use When**: Connecting signals/slots on the same thread (rare, usually default)

**Note**: Qt automatically selects appropriate connection type if not specified, but we explicitly specify for clarity and safety.

## Common Patterns

### Pattern 1: Load Data from Database

```python
# 1. UI requests data (main thread)
def load_events(self):
    # Invoke method on worker thread via QMetaObject
    QMetaObject.invokeMethod(
        self.worker,
        "load_events",
        Qt.ConnectionType.QueuedConnection
    )

# 2. Worker loads data (worker thread)
@Slot()
def load_events(self):
    events = self.db_service.get_all_events()
    self.events_loaded.emit(events)  # Thread-safe signal

# 3. UI updates (main thread)
@Slot(list)
def on_events_loaded(self, events):
    self.timeline.set_events(events)  # Safe: on UI thread
```

### Pattern 2: Execute Command

```python
# 1. UI creates command (main thread)
def create_event(self):
    command = CreateEventCommand(event_data)
    QMetaObject.invokeMethod(
        self.worker,
        "execute_command",
        Qt.ConnectionType.QueuedConnection,
        Q_ARG(object, command)
    )

# 2. Worker executes (worker thread)
@Slot(object)
def execute_command(self, command):
    result = command.execute(self.db_service)
    self.command_finished.emit(result)

# 3. UI receives result (main thread)
@Slot(object)
def on_command_finished(self, result):
    if result.success:
        self.refresh_ui()
```

### Pattern 3: Background Processing with Progress

```python
# From src/services/worker.py
class DatabaseWorker(QObject):
    operation_started = Signal(str)
    operation_finished = Signal(str)
    
    @Slot()
    def long_operation(self):
        self.operation_started.emit("Processing...")
        # Do work
        self.operation_finished.emit("Complete")
```

## Race Conditions and Data Safety

### Thread-Safe Data Types

**Safe to pass between threads** (copied by Qt):
- Basic Python types: int, float, str, bool
- Qt value types: QString, QVariant
- Immutable collections: tuple (of safe types)
- Dataclasses marked with `@dataclass(frozen=True)`

**Unsafe without synchronization**:
- Mutable collections: list, dict (unless copied)
- Custom objects with mutable state
- Qt object pointers (QObject*, QWidget*)

### Safe Pattern: Copy Data

```python
# Good: Pass copies
events = self.db_service.get_all_events()
self.events_loaded.emit(list(events))  # Explicit copy

# Good: Immutable data
event = Event(name="Test", lore_date=100.0)  # Dataclass
self.event_created.emit(event)  # Safe if immutable
```

### Unsafe Pattern: Shared Mutable State

```python
# BAD: Shared mutable state
class Worker(QObject):
    def __init__(self):
        self.cache = {}  # Mutable, no lock!
    
    def add_to_cache(self, key, value):
        self.cache[key] = value  # Race condition!

# Better: Use thread-local storage or signals
```

## Database Connection Safety

### SQLite Threading Constraints

1. **Connection per thread**: Each thread must have its own connection
2. **WAL mode**: Enables concurrent readers with single writer
3. **PRAGMA foreign_keys**: Must be set per connection

```python
# From src/services/db_service.py
def connect(self):
    self._connection = sqlite3.connect(self.db_path)
    self._connection.execute("PRAGMA foreign_keys = ON;")
    
    if self.db_path != ":memory:":
        # WAL allows concurrent readers
        self._connection.execute("PRAGMA journal_mode=WAL;")
```

### Safety Rules

1. **Never share connections**: DatabaseService instance belongs to worker thread
2. **No UI thread database access**: All DB operations via worker
3. **Transaction isolation**: Use context managers for transactions

## Common Mistakes and Solutions

### Mistake 1: Accessing UI from Worker

```python
# BAD: Crashes or undefined behavior
@Slot()
def load_data(self):
    data = self.db_service.get_data()
    self.main_window.label.setText(data)  # WRONG: UI access from worker

# GOOD: Use signals
@Slot()
def load_data(self):
    data = self.db_service.get_data()
    self.data_loaded.emit(data)  # Signal to UI thread
```

### Mistake 2: Wrong Connection Type

```python
# BAD: DirectConnection for cross-thread
self.worker.events_loaded.connect(
    self.timeline.set_events  # Implicit DirectConnection - UNSAFE!
)

# GOOD: Explicit QueuedConnection
self.worker.events_loaded.connect(
    self.timeline.set_events,
    Qt.ConnectionType.QueuedConnection  # Safe cross-thread
)
```

### Mistake 3: Blocking UI Thread

```python
# BAD: Synchronous database call on UI thread
def button_clicked(self):
    events = self.db_service.get_all_events()  # Blocks UI!
    self.display(events)

# GOOD: Async via worker
def button_clicked(self):
    QMetaObject.invokeMethod(
        self.worker, "load_events",
        Qt.ConnectionType.QueuedConnection
    )
```

## Debugging Threading Issues

### Symptoms of Threading Problems

1. **Random crashes**: Usually accessing UI from wrong thread
2. **Deadlocks**: Often from BlockingQueuedConnection misuse
3. **Stale data**: Race conditions with shared mutable state
4. **Database locked errors**: Connection shared across threads

### Debugging Tools

```python
# Check current thread
from PySide6.QtCore import QThread
print(f"Current thread: {QThread.currentThread()}")
print(f"UI thread: {QApplication.instance().thread()}")

# Add thread safety assertions
def update_ui(self):
    assert QThread.currentThread() == QApplication.instance().thread()
    # Safe to update UI here
```

### Enable Qt Warnings

```python
# In main.py or test setup
import os
os.environ['QT_LOGGING_RULES'] = 'qt.qml.connections=true'
```

## Best Practices

### DO

✅ Use QueuedConnection for all cross-thread signals  
✅ Keep worker thread for database operations  
✅ Emit signals with copied/immutable data  
✅ Use QMetaObject.invokeMethod for worker calls  
✅ Test with assertions for thread safety  
✅ Document thread ownership in class docstrings

### DON'T

❌ Access UI widgets from worker thread  
❌ Share database connections between threads  
❌ Use blocking operations on UI thread  
❌ Rely on implicit connection types  
❌ Pass mutable objects without copying  
❌ Use BlockingQueuedConnection from UI to worker

## Testing Thread Safety

### Unit Test Pattern

```python
def test_cross_thread_signal(qtbot):
    """Test that signals work correctly across threads."""
    worker = DatabaseWorker()
    thread = QThread()
    worker.moveToThread(thread)
    thread.start()
    
    # Use qtbot.waitSignal for thread-safe testing
    with qtbot.waitSignal(worker.events_loaded, timeout=1000):
        QMetaObject.invokeMethod(
            worker, "load_events",
            Qt.ConnectionType.QueuedConnection
        )
    
    thread.quit()
    thread.wait()
```

### Integration Test Pattern

```python
@pytest.mark.integration
def test_command_execution_threading(qtbot, main_window):
    """Test command execution through worker thread."""
    command = CreateEventCommand({"name": "Test"})
    
    with qtbot.waitSignal(main_window.worker.command_finished):
        main_window.execute_command(command)
    
    # Verify result on UI thread
    assert main_window.event_created
```

## Performance Considerations

### When to Use Threading

**Good candidates:**
- Database queries (especially complex ones)
- File I/O operations
- Network requests
- Heavy computations
- Batch operations

**Not worth threading:**
- Simple in-memory operations
- UI updates (must be on main thread anyway)
- Operations < 16ms (one frame at 60 FPS)

### Profiling

```python
# Use QElapsedTimer for performance measurement
from PySide6.QtCore import QElapsedTimer

timer = QElapsedTimer()
timer.start()
# ... operation ...
elapsed_ms = timer.elapsed()
logger.debug(f"Operation took {elapsed_ms}ms")
```

## References

- [Qt Threading Basics](https://doc.qt.io/qt-6/thread-basics.html)
- [QThread Documentation](https://doc.qt.io/qt-6/qthread.html)
- [Qt::ConnectionType](https://doc.qt.io/qt-6/qt.html#ConnectionType-enum)
- [Thread-Support in Qt Modules](https://doc.qt.io/qt-6/threads-modules.html)

## Related Documentation

- `Design.md` - Overall architecture
- `src/app/worker_manager.py` - Worker thread setup
- `src/services/worker.py` - DatabaseWorker implementation
- `src/app/connection_manager.py` - Signal/slot wiring
