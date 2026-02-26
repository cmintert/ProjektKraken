# Undo Cross-Thread Crash (Access Violation)

## The Problem
A persistent C++ access violation (segfault) occurred during rapid (and sometimes slow) undo/redo operations. The crash had no Python traceback until `faulthandler` was enabled.

The root cause was a **cross-thread access violation** between the main (UI) thread and the background worker thread:
1. **Worker Thread**: `CommandCoordinator.undo()` delegates the actual database work to a background `QThread` (`DatabaseWorker`). This thread calls `command.undo(...)`, which modifies the command object (e.g., accessing `_previous_event`, setting `_is_executed = False`).
2. **Main Thread**: Simultaneously, `CommandCoordinator.undo()` emits `history_changed`, triggering the `HistoryPanel` to `_refresh_display()`. The UI iterates over the `undo_stack` and `redo_stack` lists across the main thread, accessing properties on the same `Command` objects. It then calls `QListWidget.clear()`, destroying list items that hold raw Python object references to those commands.

This concurrent access to the same command objects while they are dynamically modified by the worker thread (and while Qt is deleting their references) caused the segfault.

## The Solution
1. **Lightweight Snapshots (Decoupling UI from Worker)**
   Instead of passing lists of raw `BaseCommand` objects to the `HistoryPanel`, the main thread now creates lightweight dictionary snapshots (containing just `description` and `timestamp`) inside `_update_history_panel()`. The UI only reads these immutable dicts.
   
2. **Signal Reordering**
   In `CommandCoordinator.undo()` and `redo()`, `history_changed.emit()` is called *before* `undo_requested.emit()`. This ensures the UI history panel finishes generating its snapshots *before* the worker thread is instructed to start modifying the command.

3. **Reentrancy Guard**
   Added an `_undo_redo_in_progress` boolean guard in `CommandCoordinator` to prevent a second undo/redo operation from being incorrectly dispatched while the first one is still processing.

4. **Double Reload Fix**
   Fixed an issue where `CommandCoordinator.on_command_result` was triggering a full `data_coordinator.load_data()` for undo/redo commands, which was completely redundant and overwhelmed the Qt event loop, because `DataHandler.on_command_finished` already handles those reloads globally.

## Future Considerations
- Whenever passing state from a worker thread to a UI panel (or vice-versa), always use **deep copies** or **lightweight dictionaries (snapshots)** to prevent cross-thread violations. 
- `QListWidgetItem.setData(Qt.UserRole, obj)` stores a direct reference to `obj`. If `obj` is mutated or destroyed on another thread, clearing the widget list can crash Qt.
- Make sure to use `faulthandler.enable()` at startup for complex Qt applications to catch these native C++ segfaults.
