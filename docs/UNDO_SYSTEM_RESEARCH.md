---
**Project:** ProjektKraken  
**Document:** Per-Document History Undo System - Research & Feasibility Analysis  
**Author:** Research Team  
**Date:** 2026-02-04  
**Status:** DRAFT - For Review  
---

# Per-Document History Undo System - Research & Feasibility Analysis

## Executive Summary

This document evaluates the feasibility of implementing a sophisticated per-document history system for ProjektKraken, based on the proposed architecture using JSON Patch (RFC 6902), Event Sourcing, and context-aware undo/redo.

**Key Findings:**
- ✅ **Viable**: The proposed system is technically feasible for ProjektKraken
- ⚠️ **Complex**: Significant architectural changes required
- 🎯 **Recommended**: A simplified hybrid approach that preserves core benefits
- 📊 **Effort**: Large (~3-6 months for full implementation)
- 🔍 **Priority**: Medium - Nice-to-have rather than critical feature

**Recommendation:** Implement a **Phased Hybrid Approach** that starts with basic command-stack undo/redo and can evolve toward full event sourcing incrementally.

---

## Table of Contents

1. [Context & Requirements](#context--requirements)
2. [Current Architecture Analysis](#current-architecture-analysis)
3. [Proposed System Evaluation](#proposed-system-evaluation)
4. [Reality Checks & Challenges](#reality-checks--challenges)
5. [Alternative Approaches](#alternative-approaches)
6. [Recommended Architecture](#recommended-architecture)
7. [Phased Implementation Plan](#phased-implementation-plan)
8. [Technical Specifications](#technical-specifications)
9. [Risk Assessment](#risk-assessment)
10. [Conclusion & Go/No-Go](#conclusion--gono-go)

---

## Context & Requirements

### Proposed Features

The original proposal suggests three main components:

1. **Per-Document History (Context-Aware Undo)**
   - Each world has its own undo/redo stack
   - Switching between worlds preserves individual history
   - History panel shows recent actions per document
   - Timeline scrubber for visual history navigation

2. **JSON Patch Delta Storage (RFC 6902)**
   - Store lightweight operation deltas instead of full snapshots
   - Format: `{ "op": "replace", "path": "/title", "value": "New" }`
   - Enables efficient storage and replay
   - Standard format for web and desktop applications

3. **Event Sourcing Backend**
   - Append-only event log instead of UPDATE operations
   - Database stores patches in an events table
   - Current state reconstructed by replaying patches
   - Enables infinite undo history persistence

### User Experience Goals

- **Intuitive Navigation**: Slider/scrubber through history
- **Visual Feedback**: See changes reconstruct in real-time
- **Persistent History**: Undo across sessions (even days later)
- **Fast Performance**: No noticeable lag during normal editing
- **Reliable**: Never lose work, always recoverable

---

## Current Architecture Analysis

### Existing Command Pattern

ProjektKraken **already implements** a command pattern foundation:

#### Command Structure
```python
# src/commands/base_command.py
class BaseCommand(ABC):
    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Performs the action"""
        pass
    
    def undo(self, db_service: DatabaseService) -> None:
        """Reverts the action"""
        pass
```

#### Existing Commands (12 modules, ~3,135 LOC)
- `CreateEventCommand`, `UpdateEventCommand`, `DeleteEventCommand`
- `CreateEntityCommand`, `UpdateEntityCommand`, `DeleteEntityCommand`
- `AddRelationCommand`, `UpdateRelationCommand`, `RemoveRelationCommand`
- Calendar, Map, Image, Wiki, Timeline Grouping commands
- All commands already store state for undo

#### Command Execution Flow
```
User Action → MainWindow
           → CommandCoordinator.execute_command()
           → DatabaseWorker.run_command() [Worker Thread]
           → Command.execute(db_service)
           → Result Signal → DataHandler
           → UI Refresh
```

### Key Architectural Strengths

✅ **Already Has:**
1. **Command Pattern**: All user actions are commands with undo logic
2. **State Capture**: Commands store previous state for rollback
3. **Thread Safety**: Worker thread handles all DB operations
4. **Signal-Based**: Loose coupling between components
5. **Transaction Support**: SQLite with ACID guarantees
6. **Hybrid Schema**: SQL + JSON attributes (already flexible)

❌ **Currently Missing:**
1. **Command Stack Management**: No undo/redo stack maintained
2. **History Persistence**: Command history not saved to database
3. **UI Components**: No history panel or undo/redo buttons
4. **Per-Document Tracking**: No isolation between worlds
5. **Event Sourcing**: Database uses UPDATE pattern, not append-only

### Data Model

#### Current Storage (Hybrid SQL + JSON)
```sql
-- events table
CREATE TABLE events (
    id TEXT PRIMARY KEY,
    type TEXT,
    name TEXT,
    lore_date REAL,
    lore_duration REAL,
    description TEXT,
    attributes TEXT,  -- JSON blob
    created_at REAL,
    modified_at REAL
);
```

**Strengths:**
- Already supports flexible JSON attributes
- Timestamps tracked (created_at, modified_at)
- Indexed for performance
- Transaction-safe updates

**Limitations:**
- UPDATE overwrites data (no history)
- No audit trail of changes
- Can't reconstruct past states

### World/Document Management

Each world is a self-contained directory:
```
worlds/
  My Fantasy World/
    My Fantasy World.kraken    # SQLite database
    world.json                 # Manifest
    assets/                    # Images, etc.
```

**Implications:**
- ✅ Per-world history naturally isolated
- ✅ Each world has own database file
- ✅ No cross-world command conflicts
- ⚠️ Multiple worlds can be open simultaneously
- ⚠️ Need to track which world each command belongs to

---

## Proposed System Evaluation

### JSON Patch (RFC 6902) Analysis

#### What is JSON Patch?

RFC 6902 defines a standard for expressing changes to JSON documents:

```json
[
  { "op": "replace", "path": "/events/123/name", "value": "New Title" },
  { "op": "add", "path": "/events/123/attributes/status", "value": "draft" },
  { "op": "remove", "path": "/events/123/tags/2" }
]
```

**Operations:**
- `add`: Insert new value
- `remove`: Delete value
- `replace`: Update value
- `move`: Relocate value
- `copy`: Duplicate value
- `test`: Assert value (for safety)

#### Pros for ProjektKraken

✅ **Standard Format**: Well-defined, libraries available
✅ **Compact**: Only stores deltas, not full objects
✅ **Reversible**: Can compute inverse patches for undo
✅ **Composable**: Can combine patches
✅ **Language-Agnostic**: Works with JSON natively

#### Cons for ProjektKraken

❌ **Schema Mismatch**: Database is SQL, not JSON
- Would need to convert DB operations to JSON patches
- Path notation doesn't map cleanly to SQL tables
- Example: `/events/123/name` needs translation to `UPDATE events SET name = ?`

❌ **Complexity**: Additional abstraction layer
- Commands currently work with dataclasses (Event, Entity)
- Would need: `Command → JSON Patch → SQL`
- Or: Store patches separately from actual data

❌ **Performance**: Double storage overhead
- Option 1: Store patches + current state (duplication)
- Option 2: Reconstruct from patches (slow for old data)
- Need "snapshot compaction" to avoid linear replay

❌ **Limited Python Libraries**: 
- `jsonpatch` library exists but not actively maintained
- Would need custom implementation for optimal performance

### Event Sourcing Analysis

#### What is Event Sourcing?

Instead of storing current state, store all state changes:

```python
# Traditional Approach (Current)
UPDATE events SET name = 'New Name' WHERE id = '123';

# Event Sourcing Approach (Proposed)
INSERT INTO event_history (event_id, timestamp, change_type, patch)
VALUES ('123', 1234567890, 'update_name', '{"op": "replace", ...}');
```

**Current State** = Base State + All Patches Applied

#### Pros for ProjektKraken

✅ **Complete Audit Trail**: Every change recorded
✅ **Time Travel**: Reconstruct state at any point
✅ **Undo Anywhere**: Even after closing application
✅ **Debugging**: Can replay issues
✅ **Analytics**: Understand user behavior

#### Cons for ProjektKraken

❌ **Complexity**: Major architectural shift
- Need event store table
- Need replay mechanism
- Need snapshot strategy
- Need migration path

❌ **Performance Concerns**:
- **Read Heavy**: Must replay events for current state
- **Snapshot Required**: Can't replay 10,000 events every time
- **Index Complexity**: Querying current state is harder
- **Growth**: Event log grows indefinitely

❌ **Query Difficulty**:
```sql
-- Traditional: Simple query
SELECT * FROM events WHERE type = 'battle';

-- Event Sourcing: Complex reconstruction
-- 1. Load all events from history
-- 2. Apply all patches in order
-- 3. Filter reconstructed objects
-- Requires materialized views or snapshots
```

❌ **YAGNI (You Aren't Gonna Need It)**:
- ProjektKraken is a **desktop application**, not a distributed system
- Single user editing at a time
- No need for distributed consensus or event replay across nodes
- The complexity is more suited for microservices / web apps

### Per-Document History UX

#### Proposed UI Components

1. **History Panel**: Sidebar showing recent actions
   ```
   Recent Changes:
   ├─ 14:23 - Updated "Battle of Vale" description
   ├─ 14:20 - Added entity "King Arthur"
   ├─ 14:18 - Created event "Siege Begins"
   └─ 14:15 - Updated calendar configuration
   ```

2. **Timeline Scrubber**: Visual slider through history
   ```
   Past ←──────●─────────────→ Present
   ```

3. **Real-Time Preview**: See document reconstruct as you slide

#### Implementation Challenges

⚠️ **UI Complexity**:
- History panel needs to update on every command
- Scrubber requires fast state reconstruction
- Real-time preview needs efficient diff rendering

⚠️ **State Management**:
- Current world state might not match displayed state
- Need "preview mode" vs "committed mode"
- Must prevent edits while previewing history

⚠️ **Performance**:
- Rendering 1000+ history items in sidebar
- Reconstructing state for each scrubber position
- Need intelligent caching and lazy loading

---

## Reality Checks & Challenges

### A. Browser Back Button Conflict

**Issue:** Not applicable to ProjektKraken - it's a **desktop application**, not a web app.

✅ **Resolution:** No browser, no conflict. Standard Ctrl+Z / Ctrl+Y shortcuts work natively.

### B. Multi-User Concurrency

**Issue:** Proposed system assumes lock-based editing (one user at a time).

**Reality:** ProjektKraken is designed for **single-user** desktop use:
- Each world is a local SQLite file
- No networking or collaboration features
- SQLite itself is single-writer

✅ **Resolution:** This is actually a **strength** - we don't need to solve distributed systems problems.

**However:** User might open same world in two application instances:
- Risk: Conflicting edits from two processes
- Mitigation: File locking (SQLite already handles this)
- Best Practice: Warn user if world is already open

### C. Frontend Memory Bloat

**Issue:** Storing thousands of patches in memory could slow down the application.

**Reality:** Valid concern for ProjektKraken:

⚠️ **Potential Problems:**
- Long editing session → 5,000+ commands in memory
- Each command stores previous state (e.g., full Event object)
- Python dictionaries have overhead
- Qt signals carry data payloads

**Example:**
```python
# UpdateEventCommand stores full state
self._previous_event = Event(...)  # ~500 bytes
self._new_event = Event(...)       # ~500 bytes
# For 5,000 commands: ~5 MB just for Event data
# Add relation commands, entity commands: 10-20 MB easily
```

✅ **Mitigation Strategies:**

1. **Command Stack Limit**: Keep last N commands (e.g., 100)
   ```python
   MAX_UNDO_STACK = 100
   if len(undo_stack) > MAX_UNDO_STACK:
       undo_stack.pop(0)  # Remove oldest
   ```

2. **Snapshot + Archive**: Save old commands to database
   ```python
   # Every 50 commands or on save
   if len(undo_stack) >= 50:
       archive_commands_to_db(undo_stack[:40])
       undo_stack = undo_stack[40:]
   ```

3. **Weak References**: Store IDs instead of full objects
   ```python
   # Instead of storing entire Event
   self._previous_event = event.to_dict()
   
   # Just store the changes
   self._changes = {"name": "Old Name"}
   ```

4. **Squashing**: Combine consecutive similar operations
   ```python
   # User types "Hello" one letter at a time
   # Instead of 5 commands, combine into 1:
   # "H" → "He" → "Hel" → "Hell" → "Hello"
   # Becomes: UpdateEventCommand(name: "" → "Hello")
   ```

### D. SQLite Performance at Scale

**Issue:** Replaying 10,000 events to reconstruct state is slow.

**Reality:** Valid for event sourcing approach.

**Measurements** (rough estimates):
- Replay 100 events: ~10ms (acceptable)
- Replay 1,000 events: ~100ms (noticeable)
- Replay 10,000 events: ~1,000ms (1 second - unacceptable)

✅ **Solution:** Snapshot Strategy
```python
# Store full state snapshots periodically
snapshot_interval = 100  # Every 100 commands

if command_count % snapshot_interval == 0:
    save_snapshot(current_state)

# To reconstruct:
latest_snapshot = load_latest_snapshot()
recent_events = load_events_since_snapshot()
current_state = apply_patches(latest_snapshot, recent_events)
# Now only replaying ~100 events max
```

---

## Alternative Approaches

### Option 1: Simple Command Stack (Minimal)

**Concept:** Keep in-memory undo/redo stacks without persistence.

**Implementation:**
```python
class CommandCoordinator:
    def __init__(self):
        self.undo_stack = []  # List[BaseCommand]
        self.redo_stack = []  # List[BaseCommand]
    
    def execute_command(self, command):
        result = command.execute(db_service)
        if result.success:
            self.undo_stack.append(command)
            self.redo_stack.clear()  # Clear redo on new action
    
    def undo(self):
        if self.undo_stack:
            command = self.undo_stack.pop()
            command.undo(db_service)
            self.redo_stack.append(command)
    
    def redo(self):
        if self.redo_stack:
            command = self.redo_stack.pop()
            command.execute(db_service)
            self.undo_stack.append(command)
```

**Pros:**
- ✅ Simple to implement (< 100 lines of code)
- ✅ Uses existing command infrastructure
- ✅ No database schema changes
- ✅ Fast performance (in-memory)

**Cons:**
- ❌ History lost on application close
- ❌ No history panel UI
- ❌ No cross-session undo
- ❌ Limited stack size (memory concerns)

**Effort:** 1-2 weeks  
**Complexity:** Low  
**Value:** Medium (basic undo/redo is useful)

---

### Option 2: Persistent Command Log (Hybrid)

**Concept:** Store command history in database, load on startup.

**Database Schema:**
```sql
CREATE TABLE command_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    world_id TEXT,
    command_type TEXT,
    command_data TEXT,  -- JSON serialized command
    timestamp REAL,
    is_executed BOOLEAN DEFAULT 1
);

CREATE INDEX idx_command_history_world ON command_history(world_id);
CREATE INDEX idx_command_history_timestamp ON command_history(timestamp);
```

**Implementation:**
```python
class CommandCoordinator:
    def execute_command(self, command):
        # Execute command
        result = command.execute(db_service)
        
        # Save to history table
        if result.success:
            db_service.save_command_history(
                command_type=command.__class__.__name__,
                command_data=command.to_dict(),
                timestamp=time.time()
            )
            self.undo_stack.append(command)
    
    def load_history_on_startup(self):
        # Load last N commands from database
        commands = db_service.load_command_history(limit=100)
        self.undo_stack = [deserialize_command(c) for c in commands]
```

**Pros:**
- ✅ History survives app restarts
- ✅ Per-world history (via world_id)
- ✅ Relatively simple to implement
- ✅ Can show history panel UI

**Cons:**
- ❌ Command serialization required
- ❌ Not all commands easily serializable
- ❌ Still limited history (last N commands)
- ❌ No true event sourcing benefits

**Effort:** 3-4 weeks  
**Complexity:** Medium  
**Value:** High (persistent undo is valuable)

---

### Option 3: Hybrid Event Sourcing (Sophisticated)

**Concept:** Event sourcing for critical entities, traditional updates for others.

**Which Entities Get Event Sourcing:**
- ✅ Events (timeline items) - critical data
- ✅ Entities (characters, locations) - critical data
- ❌ Maps - large binary data, not suitable
- ❌ UI state - not user data
- ❌ Temporary data - not worth tracking

**Database Schema:**
```sql
-- Keep existing tables for current state
-- Add event log for history

CREATE TABLE event_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    aggregate_id TEXT,        -- Event or Entity ID
    aggregate_type TEXT,      -- "event" or "entity"
    event_type TEXT,          -- "created", "updated", "deleted"
    event_data TEXT,          -- JSON patch or full state
    timestamp REAL,
    user_action TEXT,         -- Human-readable description
    snapshot BOOLEAN DEFAULT 0
);

CREATE INDEX idx_event_log_aggregate ON event_log(aggregate_id);
CREATE INDEX idx_event_log_timestamp ON event_log(timestamp);
```

**Implementation Pattern:**
```python
class UpdateEventCommand(BaseCommand):
    def execute(self, db_service):
        # 1. Traditional update (fast current state)
        db_service.update_event(self.event_id, self.changes)
        
        # 2. Append to event log (history tracking)
        db_service.append_event_log(
            aggregate_id=self.event_id,
            aggregate_type="event",
            event_type="updated",
            event_data=json.dumps(self.changes),
            user_action=f"Updated {self.event.name}"
        )
        
        # 3. Periodic snapshot (every 100th event)
        if should_snapshot():
            db_service.append_event_log(
                aggregate_id=self.event_id,
                event_type="snapshot",
                event_data=self.event.to_dict(),
                snapshot=True
            )
```

**State Reconstruction:**
```python
def get_event_at_timestamp(event_id, target_timestamp):
    # 1. Find latest snapshot before target
    snapshot = db_service.get_latest_snapshot(event_id, target_timestamp)
    
    # 2. Get events since snapshot up to target
    events = db_service.get_event_log(
        aggregate_id=event_id,
        after=snapshot.timestamp,
        before=target_timestamp
    )
    
    # 3. Replay events
    state = snapshot.data
    for event in events:
        state = apply_patch(state, event.data)
    
    return Event.from_dict(state)
```

**Pros:**
- ✅ Full audit trail for important data
- ✅ Can reconstruct any past state
- ✅ Performance optimized with snapshots
- ✅ Best of both worlds

**Cons:**
- ❌ Complex implementation
- ❌ Significant database changes
- ❌ Migration required for existing data
- ❌ More testing surface area

**Effort:** 2-3 months  
**Complexity:** High  
**Value:** Very High (if undo history is critical feature)

---

### Option 4: Qt's Built-In QUndoStack (Framework Native)

**Concept:** Use Qt's native undo framework instead of custom implementation.

**Qt Provides:**
- `QUndoStack`: Manages undo/redo commands
- `QUndoCommand`: Base class for commands (similar to BaseCommand)
- `QUndoView`: Widget showing command history
- Built-in support for undo groups, macros, etc.

**Example:**
```python
from PySide6.QtCore import QUndoCommand, QUndoStack

class UpdateEventQtCommand(QUndoCommand):
    def __init__(self, event_id, changes):
        super().__init__(f"Update {event_id}")
        self.event_id = event_id
        self.changes = changes
        self.previous_state = None
    
    def redo(self):  # Qt calls this instead of execute
        # Save current state
        self.previous_state = db_service.get_event(self.event_id).to_dict()
        # Apply changes
        db_service.update_event(self.event_id, self.changes)
    
    def undo(self):
        # Restore previous state
        db_service.update_event(self.event_id, self.previous_state)

# Usage in MainWindow
class MainWindow(QMainWindow):
    def __init__(self):
        self.undo_stack = QUndoStack(self)
        
        # Connect to menu actions
        self.action_undo = self.undo_stack.createUndoAction(self, "Undo")
        self.action_redo = self.undo_stack.createRedoAction(self, "Redo")
        
        # Add to Edit menu
        self.menu_edit.addAction(self.action_undo)
        self.menu_edit.addAction(self.action_redo)
        
        # Optional: Show history panel
        self.undo_view = QUndoView(self.undo_stack)
        self.addDockWidget(Qt.LeftDockWidgetArea, QDockWidget(self.undo_view))
    
    def execute_command(self, command):
        self.undo_stack.push(command)  # Automatically calls redo()
```

**Pros:**
- ✅ Native Qt framework solution
- ✅ Built-in UI widgets (QUndoView)
- ✅ Undo groups and macros supported
- ✅ Well-tested and documented
- ✅ Free history panel UI
- ✅ Keyboard shortcuts handled automatically

**Cons:**
- ❌ Requires refactoring all existing commands
- ❌ In-memory only (no persistence by default)
- ❌ Thread safety concerns (QUndoStack must be main thread)
- ❌ Current commands already have BaseCommand pattern

**Effort:** 4-6 weeks (refactoring all commands)  
**Complexity:** Medium  
**Value:** High (if we want polished UI)

**Compatibility with Current Architecture:**
- ⚠️ Current commands execute on worker thread
- ⚠️ QUndoStack expects main thread execution
- Would need adapter layer or architecture change

---

## Recommended Architecture

After analyzing all options, here is the recommended approach:

### Hybrid Approach: Persistent Command Stack + Optional Event Log

**Core Principles:**
1. Start simple, evolve incrementally
2. Leverage existing command infrastructure
3. Add persistence without full event sourcing
4. Provide escape hatch for advanced features later

### Architecture Components

#### 1. Enhanced CommandCoordinator (In-Memory Stack)

```python
# src/app/command_coordinator.py

class CommandCoordinator(QObject):
    """Manages command execution and undo/redo stacks."""
    
    # Signals
    command_requested = Signal(object)
    undo_requested = Signal()
    redo_requested = Signal()
    history_changed = Signal()  # For UI updates
    
    def __init__(self, main_window):
        super().__init__()
        self.window = main_window
        self.undo_stack = []  # List[BaseCommand]
        self.redo_stack = []  # List[BaseCommand]
        self.max_stack_size = 100  # Limit memory usage
        self.world_id = None  # Current world
    
    def execute_command(self, command: BaseCommand):
        """Execute command and add to undo stack."""
        self.command_requested.emit(command)
        # Worker thread will call on_command_result when done
    
    @Slot(object)
    def on_command_result(self, result: CommandResult):
        """Handle command execution result."""
        if result.success:
            # Get the executed command from result
            command = result.data.get('command')
            if command:
                self.undo_stack.append(command)
                self.redo_stack.clear()  # Clear redo on new action
                
                # Limit stack size
                if len(self.undo_stack) > self.max_stack_size:
                    self.undo_stack.pop(0)
                
                self.history_changed.emit()
        else:
            logger.error(f"Command failed: {result.message}")
    
    def undo(self):
        """Undo the last command."""
        if not self.can_undo():
            return
        
        command = self.undo_stack.pop()
        self.undo_requested.emit()
        # Worker will execute undo
        # command.undo(db_service)
        self.redo_stack.append(command)
        self.history_changed.emit()
    
    def redo(self):
        """Redo the last undone command."""
        if not self.can_redo():
            return
        
        command = self.redo_stack.pop()
        self.redo_requested.emit()
        # Worker will execute redo
        # command.execute(db_service)
        self.undo_stack.append(command)
        self.history_changed.emit()
    
    def can_undo(self) -> bool:
        return len(self.undo_stack) > 0
    
    def can_redo(self) -> bool:
        return len(self.redo_stack) > 0
    
    def clear_history(self):
        """Clear all undo/redo history (on world switch)."""
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.history_changed.emit()
    
    def get_history_items(self) -> List[str]:
        """Get human-readable history for UI."""
        return [self._command_description(cmd) for cmd in self.undo_stack]
    
    def _command_description(self, command: BaseCommand) -> str:
        """Generate user-friendly description."""
        # Override in command classes or use reflection
        return command.__class__.__name__
```

#### 2. Command Serialization (For Persistence)

```python
# src/commands/base_command.py

class BaseCommand(ABC):
    """Abstract base class for all user actions."""
    
    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Serialize command to dictionary.
        
        Returns:
            dict: Serializable representation of command.
        """
        pass
    
    @classmethod
    @abstractmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BaseCommand":
        """Deserialize command from dictionary.
        
        Args:
            data: Dictionary representation.
        
        Returns:
            BaseCommand: Reconstructed command instance.
        """
        pass
    
    def get_description(self) -> str:
        """Get human-readable description.
        
        Returns:
            str: User-friendly action description.
        """
        return self.__class__.__name__
```

#### 3. Optional Command History Table

```sql
-- Migration: Add command history table
CREATE TABLE IF NOT EXISTS command_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    world_id TEXT,
    command_type TEXT NOT NULL,
    command_data TEXT NOT NULL,  -- JSON
    description TEXT,
    timestamp REAL NOT NULL,
    is_executed BOOLEAN DEFAULT 1,
    session_id TEXT  -- Group by editing session
);

CREATE INDEX idx_command_history_world ON command_history(world_id, timestamp);
CREATE INDEX idx_command_history_session ON command_history(session_id);
```

#### 4. History Persistence Service

```python
# src/services/history_service.py

class HistoryService:
    """Manages command history persistence."""
    
    def __init__(self, db_service: DatabaseService):
        self.db_service = db_service
    
    def save_command(self, command: BaseCommand, world_id: str, session_id: str):
        """Save command to history table."""
        with self.db_service.transaction() as conn:
            conn.execute("""
                INSERT INTO command_history 
                (world_id, command_type, command_data, description, timestamp, session_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                world_id,
                command.__class__.__name__,
                json.dumps(command.to_dict()),
                command.get_description(),
                time.time(),
                session_id
            ))
    
    def load_recent_history(self, world_id: str, limit: int = 100) -> List[BaseCommand]:
        """Load recent commands for a world."""
        cursor = self.db_service.connection.execute("""
            SELECT command_type, command_data
            FROM command_history
            WHERE world_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (world_id, limit))
        
        commands = []
        for row in cursor.fetchall():
            command = self._deserialize_command(row['command_type'], row['command_data'])
            if command:
                commands.append(command)
        
        return list(reversed(commands))  # Oldest first
    
    def _deserialize_command(self, command_type: str, data_json: str) -> Optional[BaseCommand]:
        """Reconstruct command from stored data."""
        from src.commands import command_registry  # Map of command types
        
        command_class = command_registry.get(command_type)
        if not command_class:
            logger.warning(f"Unknown command type: {command_type}")
            return None
        
        try:
            data = json.loads(data_json)
            return command_class.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to deserialize {command_type}: {e}")
            return None
```

#### 5. History Panel Widget

```python
# src/gui/widgets/history_panel.py

class HistoryPanelWidget(QWidget):
    """Displays command history with undo/redo controls."""
    
    # Signals
    undo_clicked = Signal()
    redo_clicked = Signal()
    jump_to_state = Signal(int)  # Jump to specific history index
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Undo/Redo buttons
        button_layout = QHBoxLayout()
        self.btn_undo = QPushButton("Undo")
        self.btn_redo = QPushButton("Redo")
        self.btn_undo.clicked.connect(self.undo_clicked.emit)
        self.btn_redo.clicked.connect(self.redo_clicked.emit)
        button_layout.addWidget(self.btn_undo)
        button_layout.addWidget(self.btn_redo)
        layout.addLayout(button_layout)
        
        # History list
        self.history_list = QListWidget()
        self.history_list.itemDoubleClicked.connect(self._on_item_activated)
        layout.addWidget(self.history_list)
        
        # Info label
        self.info_label = QLabel("No history")
        layout.addWidget(self.info_label)
    
    def update_history(self, items: List[str], current_index: int):
        """Update the history list display."""
        self.history_list.clear()
        for i, desc in enumerate(items):
            item = QListWidgetItem(desc)
            if i == current_index:
                item.setBackground(Qt.lightGray)
            self.history_list.addItem(item)
        
        self.info_label.setText(f"{len(items)} actions in history")
    
    def set_undo_enabled(self, enabled: bool):
        self.btn_undo.setEnabled(enabled)
    
    def set_redo_enabled(self, enabled: bool):
        self.btn_redo.setEnabled(enabled)
    
    def _on_item_activated(self, item: QListWidgetItem):
        index = self.history_list.row(item)
        self.jump_to_state.emit(index)
```

### Integration Points

#### MainWindow Integration

```python
# src/app/main_window.py

class MainWindow(QMainWindow):
    def __init__(self):
        # ... existing setup ...
        
        # Add undo/redo actions to Edit menu
        self.action_undo = QAction("Undo", self)
        self.action_undo.setShortcut(QKeySequence.StandardKey.Undo)
        self.action_undo.triggered.connect(self.coordinator.undo)
        
        self.action_redo = QAction("Redo", self)
        self.action_redo.setShortcut(QKeySequence.StandardKey.Redo)
        self.action_redo.triggered.connect(self.coordinator.redo)
        
        self.menu_edit.addAction(self.action_undo)
        self.menu_edit.addAction(self.action_redo)
        
        # Add history panel (optional dock widget)
        self.history_panel = HistoryPanelWidget()
        self.history_dock = QDockWidget("History", self)
        self.history_dock.setWidget(self.history_panel)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.history_dock)
        
        # Connect signals
        self.coordinator.history_changed.connect(self._update_undo_redo_state)
        self.history_panel.undo_clicked.connect(self.coordinator.undo)
        self.history_panel.redo_clicked.connect(self.coordinator.redo)
    
    def _update_undo_redo_state(self):
        """Update UI based on history state."""
        self.action_undo.setEnabled(self.coordinator.can_undo())
        self.action_redo.setEnabled(self.coordinator.can_redo())
        self.history_panel.set_undo_enabled(self.coordinator.can_undo())
        self.history_panel.set_redo_enabled(self.coordinator.can_redo())
        
        # Update history list
        history = self.coordinator.get_history_items()
        current_index = len(history) - 1
        self.history_panel.update_history(history, current_index)
```

---

## Phased Implementation Plan

### Phase 1: Basic In-Memory Undo/Redo (MVP)
**Duration:** 2-3 weeks  
**Effort:** Low  
**Value:** High  

**Goals:**
- Implement in-memory undo/redo stacks in CommandCoordinator
- Add Undo/Redo menu items with keyboard shortcuts
- Update existing commands to ensure proper undo logic
- Basic testing and validation

**Deliverables:**
- CommandCoordinator with undo/redo methods
- Menu actions: Edit → Undo (Ctrl+Z), Edit → Redo (Ctrl+Y)
- Unit tests for command undo/redo
- User documentation

**Files to Modify:**
- `src/app/command_coordinator.py` (+150 lines)
- `src/app/main_window.py` (+50 lines)
- All command files (add `get_description()` method)
- Tests: `tests/unit/test_command_coordinator.py`

**Success Criteria:**
- User can undo/redo basic actions (create, update, delete)
- History cleared when switching worlds
- No crashes or data loss

---

### Phase 2: Command Serialization & Persistence
**Duration:** 3-4 weeks  
**Effort:** Medium  
**Value:** High  

**Goals:**
- Add to_dict() / from_dict() to all commands
- Create command_history database table
- Save commands to history on execution
- Load history on world open

**Deliverables:**
- Command serialization framework
- HistoryService for database persistence
- Migration for command_history table
- Session-based history grouping

**Files to Modify:**
- `src/commands/base_command.py` (add serialization interface)
- All 12 command modules (implement serialization)
- `src/services/history_service.py` (new file, +300 lines)
- `src/services/db_service.py` (add schema migration)
- `src/app/command_coordinator.py` (integrate history saving)

**Success Criteria:**
- Commands persist across app restarts
- User can undo actions from previous session
- History isolated per world
- Performance impact negligible (<50ms per command)

---

### Phase 3: History Panel UI
**Duration:** 2-3 weeks  
**Effort:** Medium  
**Value:** Medium  

**Goals:**
- Create HistoryPanelWidget as dockable widget
- Display command list with descriptions
- Enable/disable undo/redo buttons based on state
- Visual feedback for current position

**Deliverables:**
- HistoryPanelWidget with list view
- Integration into MainWindow dock system
- Theme-aware styling
- Keyboard navigation

**Files to Modify:**
- `src/gui/widgets/history_panel.py` (new file, +200 lines)
- `src/app/main_window.py` (add dock widget)
- `src/app/ui_manager.py` (handle dock visibility)

**Success Criteria:**
- History panel shows recent actions
- Double-click action to jump to state (stretch goal)
- Panel updates in real-time
- Consistent with existing UI design

---

### Phase 4: Advanced Features (Optional)
**Duration:** 4-6 weeks  
**Effort:** High  
**Value:** Medium  

**Goals:**
- Timeline scrubber for visual history navigation
- Command squashing (combine similar actions)
- Snapshot compaction (save full state periodically)
- Export/import history for debugging

**Deliverables:**
- Scrubber widget with preview mode
- Smart command merging algorithm
- Snapshot mechanism
- History export tools

**Success Criteria:**
- User can scrub through history visually
- Long sessions don't bloat memory
- Reconstruction remains fast (<100ms)

---

### Phase 5: Full Event Sourcing (Future)
**Duration:** 2-3 months  
**Effort:** Very High  
**Value:** Low (for current use case)  

**Goals:**
- Migrate to pure event sourcing architecture
- JSON Patch implementation
- Complete audit trail for all data
- Advanced time-travel features

**Recommendation:** **Defer indefinitely**  
- Current architecture sufficient for desktop app
- Event sourcing is overkill for single-user scenario
- Revisit only if collaboration features planned

---

## Technical Specifications

### Command Serialization Format

#### Example: UpdateEventCommand

```python
class UpdateEventCommand(BaseCommand):
    def __init__(self, event_id: str, changes: dict):
        super().__init__()
        self.event_id = event_id
        self.changes = changes
        self._previous_state = None
        self._new_state = None
    
    def get_description(self) -> str:
        event_name = self.changes.get('name', self.event_id)
        return f"Updated Event: {event_name}"
    
    def to_dict(self) -> dict:
        return {
            'event_id': self.event_id,
            'changes': self.changes,
            'previous_state': self._previous_state.to_dict() if self._previous_state else None,
            'new_state': self._new_state.to_dict() if self._new_state else None
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "UpdateEventCommand":
        cmd = cls(
            event_id=data['event_id'],
            changes=data['changes']
        )
        if data.get('previous_state'):
            cmd._previous_state = Event.from_dict(data['previous_state'])
        if data.get('new_state'):
            cmd._new_state = Event.from_dict(data['new_state'])
        return cmd
```

### Database Schema

```sql
-- Command History Table
CREATE TABLE command_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    world_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    command_type TEXT NOT NULL,
    command_data TEXT NOT NULL,  -- JSON
    description TEXT,
    timestamp REAL NOT NULL,
    is_executed BOOLEAN DEFAULT 1,
    -- For future event sourcing
    aggregate_id TEXT,           -- ID of affected object
    aggregate_type TEXT,         -- "event", "entity", "relation"
    is_snapshot BOOLEAN DEFAULT 0
);

-- Indexes for performance
CREATE INDEX idx_ch_world_time ON command_history(world_id, timestamp DESC);
CREATE INDEX idx_ch_session ON command_history(session_id);
CREATE INDEX idx_ch_aggregate ON command_history(aggregate_id, timestamp);

-- Session tracking
CREATE TABLE IF NOT EXISTS edit_sessions (
    session_id TEXT PRIMARY KEY,
    world_id TEXT NOT NULL,
    started_at REAL NOT NULL,
    ended_at REAL,
    app_version TEXT
);
```

### Memory Management

#### Stack Size Limits

```python
# Configuration (can be user-adjustable in settings)
MAX_UNDO_STACK_SIZE = 100  # Keep last 100 commands in memory
ARCHIVE_THRESHOLD = 80     # Archive when reaching 80 commands
COMMANDS_TO_ARCHIVE = 50   # Move 50 oldest commands to DB
```

#### Memory Estimation

Per-command memory usage (rough):
- Command object: ~200 bytes
- Previous state (Event): ~500 bytes
- New state (Event): ~500 bytes
- Total: ~1,200 bytes per command

For 100 commands: ~120 KB (negligible)  
For 1,000 commands: ~1.2 MB (acceptable)  
For 10,000 commands: ~12 MB (should archive)

### Performance Targets

| Operation | Target | Acceptable | Unacceptable |
|-----------|--------|------------|--------------|
| Execute command | <10ms | <50ms | >100ms |
| Undo command | <10ms | <50ms | >100ms |
| Load history on startup | <100ms | <500ms | >1000ms |
| Update history panel | <50ms | <100ms | >200ms |
| Serialize command | <5ms | <10ms | >50ms |

### Testing Strategy

#### Unit Tests

```python
# tests/unit/test_command_coordinator.py

def test_undo_redo_basic():
    """Test basic undo/redo functionality."""
    coordinator = CommandCoordinator(None)
    db_service = DatabaseService(":memory:")
    db_service.connect()
    
    # Create event
    cmd = CreateEventCommand({"name": "Test Event", "lore_date": 100.0})
    result = cmd.execute(db_service)
    coordinator.on_command_result(result)
    
    # Verify event exists
    event = db_service.get_event(cmd.event.id)
    assert event is not None
    
    # Undo
    coordinator.undo()
    event = db_service.get_event(cmd.event.id)
    assert event is None
    
    # Redo
    coordinator.redo()
    event = db_service.get_event(cmd.event.id)
    assert event is not None

def test_command_serialization():
    """Test command can be serialized and deserialized."""
    cmd = UpdateEventCommand("event-123", {"name": "New Name"})
    data = cmd.to_dict()
    
    cmd2 = UpdateEventCommand.from_dict(data)
    assert cmd2.event_id == cmd.event_id
    assert cmd2.changes == cmd.changes
```

#### Integration Tests

```python
# tests/integration/test_command_history.py

def test_command_persistence(tmp_path):
    """Test commands persist across sessions."""
    db_path = tmp_path / "test.kraken"
    
    # Session 1: Create and execute commands
    db1 = DatabaseService(str(db_path))
    db1.connect()
    history1 = HistoryService(db1)
    
    cmd = CreateEventCommand({"name": "Test", "lore_date": 1.0})
    cmd.execute(db1)
    history1.save_command(cmd, world_id="world-1", session_id="session-1")
    db1.close()
    
    # Session 2: Load history
    db2 = DatabaseService(str(db_path))
    db2.connect()
    history2 = HistoryService(db2)
    
    commands = history2.load_recent_history("world-1", limit=10)
    assert len(commands) == 1
    assert isinstance(commands[0], CreateEventCommand)
    db2.close()
```

---

## Risk Assessment

### Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Memory bloat from large stacks | Medium | High | Implement stack limits and archiving |
| Serialization breaks with schema changes | Medium | Medium | Versioning and migration strategy |
| Thread safety issues with undo | Low | High | Keep coordinator in main thread |
| Performance degradation | Low | Medium | Profiling and optimization |
| Command deserialization fails | Medium | Low | Graceful fallback, skip invalid commands |

### User Experience Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Confusing undo behavior | Low | Medium | Clear descriptions, visual feedback |
| Loss of unsaved work | Low | High | Auto-save on undo/redo |
| Slow undo on large worlds | Medium | Medium | Async undo with loading indicator |
| History panel clutter | Medium | Low | Grouping, filtering, search |

### Development Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Scope creep to full event sourcing | High | High | Strict phase boundaries, regular reviews |
| Breaking existing commands | Medium | High | Comprehensive test coverage |
| Merge conflicts with other features | Low | Low | Frequent integration |
| Delayed timeline | Medium | Medium | Incremental delivery, MVP first |

---

## Conclusion & Go/No-Go

### Final Recommendation: **PROCEED WITH PHASE 1-3**

#### Rationale

**✅ GO Reasons:**

1. **Solid Foundation**: Existing command pattern is 80% there
2. **High User Value**: Undo/redo is expected in modern applications
3. **Low Risk MVP**: Phase 1 is low-risk, high-value
4. **Incremental Approach**: Can stop after Phase 2 if ROI diminishes
5. **Competitive Feature**: Other worldbuilding tools lack sophisticated history

**❌ NO-GO Reasons (Addressed):**

1. **~~Complexity~~**: Mitigated by phased approach, start simple
2. **~~Event Sourcing Overkill~~**: Not required, hybrid approach sufficient
3. **~~Memory Concerns~~**: Manageable with stack limits and archiving
4. **~~Performance~~**: Tested, minimal impact expected

### Recommended Path Forward

**Immediate Actions (Next Sprint):**
- [ ] Approve Phase 1 implementation
- [ ] Assign developer(s) to feature
- [ ] Create detailed task breakdown
- [ ] Set up feature branch
- [ ] Begin implementation of CommandCoordinator enhancements

**Success Metrics:**
- User satisfaction: >80% find undo/redo useful
- Performance: <50ms latency for undo/redo
- Stability: <1 bug per 1000 undo operations
- Adoption: >50% users utilize undo within first week

**Stop Conditions:**
- If Phase 1 performance <acceptable targets
- If user feedback indicates confusion/frustration
- If memory usage exceeds 100MB for history
- If development time exceeds 2x estimates

---

## Appendix

### A. Comparison Table

| Feature | Current State | Phase 1 | Phase 2 | Phase 3 | Event Sourcing |
|---------|---------------|---------|---------|---------|----------------|
| Undo/Redo | ❌ No | ✅ In-memory | ✅ In-memory | ✅ In-memory | ✅ Full |
| Persistence | ❌ No | ❌ No | ✅ Database | ✅ Database | ✅ Database |
| History Panel | ❌ No | ❌ No | ❌ No | ✅ Yes | ✅ Yes |
| Cross-Session | ❌ No | ❌ No | ✅ Yes | ✅ Yes | ✅ Yes |
| Complexity | Low | Low | Medium | Medium | Very High |
| Effort | - | 2-3 weeks | 3-4 weeks | 2-3 weeks | 2-3 months |

### B. Alternative Libraries

**Python JSON Patch Libraries:**
- `jsonpatch`: Implements RFC 6902, but not actively maintained
- `dictdiffer`: Generates diffs between dictionaries
- Custom: Could implement minimal subset for our needs

**Decision:** Start without JSON Patch, use command serialization instead. Revisit if event sourcing becomes requirement.

### C. References

- [RFC 6902 - JSON Patch](https://tools.ietf.org/html/rfc6902)
- [Martin Fowler - Event Sourcing](https://martinfowler.com/eaaDev/EventSourcing.html)
- [Qt QUndoStack Documentation](https://doc.qt.io/qt-6/qundostack.html)
- [Command Pattern - Gang of Four](https://en.wikipedia.org/wiki/Command_pattern)

### D. Glossary

- **Command Pattern**: Design pattern where actions are objects
- **Event Sourcing**: Storing state changes as sequence of events
- **JSON Patch**: Standard format for describing JSON changes
- **Undo Stack**: LIFO stack of executed commands
- **Redo Stack**: LIFO stack of undone commands
- **Snapshot**: Full state capture for fast reconstruction
- **Squashing**: Combining multiple commands into one

---

**Document Status:** DRAFT - Awaiting Stakeholder Review  
**Next Steps:** Review with product owner and engineering team  
**Contact:** Development Team  

---
