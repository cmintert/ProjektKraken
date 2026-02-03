# Qt Threading Quick Reference

**For:** ProjektKraken Developers  
**Purpose:** Quick lookup for signal/slot connection types

---

## 🚦 Connection Type Quick Decision

### Is your signal crossing threads?

```
┌─────────────────────────────────────────────────────────┐
│ Does signal cross from one thread to another?          │
│                                                         │
│ Examples:                                               │
│ • Main thread widget → Worker thread method?           │
│ • Worker thread signal → Main thread UI update?        │
└────────────┬───────────────────────────────────────┬───┘
             │                                       │
          YES│                                       │NO
             │                                       │
             ▼                                       ▼
┌────────────────────────────┐    ┌─────────────────────────────┐
│ Use QueuedConnection       │    │ Use AutoConnection          │
│                            │    │                             │
│ Qt.ConnectionType.         │    │ Qt.ConnectionType.          │
│   QueuedConnection         │    │   AutoConnection            │
│                            │    │                             │
│ ✅ Thread-safe             │    │ ✅ Fast (direct call)       │
│ ✅ Async (non-blocking)    │    │ ✅ Simple                   │
│ ❌ Small overhead          │    │ ❌ Not for cross-thread     │
└────────────────────────────┘    └─────────────────────────────┘
```

---

## 📋 Common Scenarios

### ✅ Scenario 1: Widget Internal Connection

```python
# Button in widget connects to method in same widget
# Both in main thread
self.btn_save.clicked.connect(
    self._on_save,
    Qt.ConnectionType.AutoConnection  # Same thread, direct call
)
```

### ✅ Scenario 2: Main Thread → Worker Thread

```python
# MainWindow signal to DatabaseWorker slot
# Cross-thread: main → worker
connection_type = Qt.ConnectionType.QueuedConnection
main_window.command_requested.connect(
    worker.run_command,
    connection_type  # REQUIRED for thread safety
)
```

### ✅ Scenario 3: Worker Thread → Main Thread

```python
# DatabaseWorker signal to DataHandler slot
# Cross-thread: worker → main
connection_type = Qt.ConnectionType.QueuedConnection
worker.events_loaded.connect(
    data_handler.on_events_loaded,
    connection_type  # REQUIRED for thread safety
)
```

### ✅ Scenario 4: Widget → MainWindow Slot

```python
# Editor widget to MainWindow method
# Same thread (both in main thread)
editor.save_requested.connect(
    main_window.update_event,
    Qt.ConnectionType.AutoConnection
)
```

---

## 🎯 Thread Affinity Reference

### Main Thread (GUI)
- All QWidget subclasses
- MainWindow
- DataHandler
- All GUI editors, lists, widgets
- All coordinators

### Worker Thread (Database)
- DatabaseWorker
- DatabaseService (owned by worker)
- All command execution
- All database operations

---

## ⚠️ Red Flags - Never Do This

### ❌ Don't: Omit Connection Type for Cross-Thread

```python
# BAD - Implicit connection type
worker.events_loaded.connect(handler.on_events_loaded)
```

### ❌ Don't: Use processEvents()

```python
# BAD - Can cause re-entrancy issues
QApplication.processEvents()
```

### ❌ Don't: Call UI Methods from Worker

```python
# BAD - Will crash
class DatabaseWorker(QObject):
    def load_events(self):
        events = self.db.get_events()
        self.main_window.update_list(events)  # CRASH!
```

### ❌ Don't: Call Database from Main Thread

```python
# BAD - Blocks UI
class EventEditor(QWidget):
    def load_event(self):
        event = self.db.get_event(id)  # BLOCKS!
```

---

## ✅ Best Practices

### 1. Always Specify Connection Type

```python
# GOOD - Explicit is better
signal.connect(slot, Qt.ConnectionType.AutoConnection)
```

### 2. Add Comment for Cross-Thread

```python
# BEST - Document why
# Cross-thread: main → worker, requires QueuedConnection
signal.connect(slot, Qt.ConnectionType.QueuedConnection)
```

### 3. Group Cross-Thread Connections

```python
# BEST - Make it obvious
connection_type = Qt.ConnectionType.QueuedConnection

# All worker→main connections
worker.signal1.connect(handler.slot1, connection_type)
worker.signal2.connect(handler.slot2, connection_type)
worker.signal3.connect(handler.slot3, connection_type)
```

---

## 🔍 How to Check Thread Affinity

### At Runtime

```python
from PySide6.QtCore import QThread
from PySide6.QtWidgets import QApplication

# Get current thread
current = QThread.currentThread()

# Get main thread
main = QApplication.instance().thread()

# Check if in main thread
if current == main:
    print("Running in main thread ✅")
else:
    print("Running in worker thread ⚡")
```

### Add Assertions

```python
class DataHandler(QObject):
    def __init__(self):
        super().__init__()
        
        # Assert we're in main thread
        assert QThread.currentThread() == QApplication.instance().thread()
```

---

## 📚 Full Documentation

- **Detailed Guide:** `docs/THREAD_SAFETY_GUIDE.md`
- **Architecture:** `ARCHITECTURE.md` (Thread Safety Model section)
- **Examples:** `src/app/worker_manager.py` (lines 122-196)

---

## 🚨 When in Doubt

**If you're not 100% sure, use QueuedConnection.**

It's always safe, just slightly slower (~microseconds).

---

**Quick Ref Version:** 1.0  
**Last Updated:** 2024-02-03
