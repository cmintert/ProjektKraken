# Sprint 0 Implementation: Drag-and-Drop Relations Prototype

**Status:** ✅ Complete  
**Date:** 2026-02-07  
**Branch:** `copilot/analyze-drag-and-drop-relations`  
**Commits:** 90d41df (RFC), c48a68e (Implementation)

---

## Overview

Sprint 0 implements the minimal viable prototype for drag-and-drop relation creation between items in ProjektKraken. Users can now drag events or entities from the Project Explorer and drop them onto the Entity Editor or Event Editor to create relations.

## Implementation Summary

### Files Modified

1. **`src/gui/widgets/entity_editor.py`** (+90 lines)
   - Added `setAcceptDrops(True)` in `__init__()`
   - Implemented `dragEnterEvent()` - Accepts MIME type "application/x-kraken-item"
   - Implemented `dragMoveEvent()` - Continues accepting drag
   - Implemented `dropEvent()` - Parses JSON data, emits signal with default "related" type

2. **`src/gui/widgets/event_editor.py`** (+90 lines)
   - Same implementation as entity_editor.py
   - Ensures consistency across both editor types

3. **`src/app/main_window.py`** (+42 lines)
   - Connected `entity_editor.add_relation_requested` signal (line 512-513)
   - Connected `event_editor.add_relation_requested` signal (line 514-515)
   - Implemented `_on_add_relation_via_drag()` handler (line 517-544)
   - Creates `AddRelationCommand` with source=dropped_id, target=editor_id, type="related"

4. **`tests/unit/test_drag_drop_sprint0.py`** (new file, 183 lines)
   - 6 unit tests covering signal emission and rejection logic
   - Tests for both EntityEditor and EventEditor
   - Tests for valid drops, invalid MIME data, and missing entity/event

### Signal Flow

```
Project Explorer (DraggableListView)
  │ drag starts with MIME data: {"id": "...", "type": "...", "name": "..."}
  ▼
EntityEditorWidget / EventEditorWidget
  │ dropEvent() parses MIME data
  │ emits: add_relation_requested(source_id, target_id, "related", {}, False)
  ▼
MainWindow._on_add_relation_via_drag()
  │ creates: AddRelationCommand(source_id, target_id, "related", {}, False)
  │ emits: command_requested signal
  ▼
CommandCoordinator
  │ emits: command_requested signal to worker thread
  ▼
DatabaseWorker (worker thread)
  │ executes: AddRelationCommand.execute(db_service)
  │ calls: db_service.insert_relation()
  │ emits: command_finished signal
  ▼
MainWindow (UI updates)
  │ reloads editor relations
  └── relation appears in UI
```

## What Works

✅ **Drag from Project Explorer**
- Both events and entities can be dragged
- MIME data format: `application/x-kraken-item` with JSON payload

✅ **Drop on Entity Editor**
- Creates relation: dropped_item → current_entity
- Relation type: "related" (default)
- Works only when entity is loaded

✅ **Drop on Event Editor**
- Creates relation: dropped_item → current_event
- Relation type: "related" (default)
- Works only when event is loaded

✅ **Database Persistence**
- Uses existing `AddRelationCommand` infrastructure
- Fully integrated with undo/redo system (Ctrl+Z works)
- Relations stored in `relations` table via `RelationRepository`

✅ **Error Handling**
- Rejects drops when no entity/event loaded
- Rejects invalid MIME data
- Logs warnings for debugging

## What's Not Implemented

❌ **Type Picker** (Sprint 1)
- Currently hard-coded to "related" type
- Future: Show picker on Shift key press

❌ **Visual Feedback** (Sprint 1-2)
- No drag pill (following cursor)
- No drop hint overlay
- No preview lines for graph/map

❌ **Undo Toast** (Sprint 1)
- Undo works via Ctrl+Z, but no toast notification
- No "Undo" button in UI

❌ **Bulk Operations** (Sprint 2)
- Single-item drop only
- No multi-select support
- No confirmation dialog for bulk

❌ **Graph/Map/Timeline** (Sprint 2)
- Only Project Explorer → Editor works
- Graph, Map, Timeline drops not implemented

## Manual Testing

### Prerequisites
1. ProjektKraken application running
2. World database loaded
3. At least one entity and one event in database

### Test Procedure

**Test 1: Drag Event to Entity Editor**
1. Open Entity Editor with an entity (e.g., "John Smith")
2. In Project Explorer, click and hold an event (e.g., "The Great War")
3. Drag event over Entity Editor
4. Release mouse button (drop)
5. ✅ Verify: Relation "The Great War → John Smith" appears in entity's relations tab

**Test 2: Drag Entity to Event Editor**
1. Open Event Editor with an event (e.g., "The Great War")
2. In Project Explorer, click and hold an entity (e.g., "John Smith")
3. Drag entity over Event Editor
4. Release mouse button (drop)
5. ✅ Verify: Relation "John Smith → The Great War" appears in event's relations tab

**Test 3: Undo Relation Creation**
1. After creating a relation via drag-drop
2. Press Ctrl+Z (or Cmd+Z on Mac)
3. ✅ Verify: Relation is removed from editor's relations tab

**Test 4: Redo Relation Creation**
1. After undoing a relation
2. Press Ctrl+Shift+Z (or Cmd+Shift+Z on Mac)
3. ✅ Verify: Relation reappears in editor's relations tab

**Test 5: Drop Without Loaded Item**
1. Open Entity Editor (but don't load any entity - editor should be disabled)
2. Try to drag and drop an event
3. ✅ Verify: Drop is rejected (no relation created, no crash)

## Known Issues

- **No visual feedback during drag** - User doesn't know if drop will be accepted
- **Default "related" type** - All relations use generic "related" type
- **No confirmation** - Relations created immediately on drop
- **Only works with Project Explorer** - Other drag sources not implemented

## Unit Tests

Run tests with:
```bash
pytest tests/unit/test_drag_drop_sprint0.py -v
```

**Test Coverage:**
- `test_entity_editor_accepts_drops` - Verifies setAcceptDrops(True)
- `test_event_editor_accepts_drops` - Verifies setAcceptDrops(True)
- `test_entity_editor_drop_creates_relation_signal` - Signal emission with correct args
- `test_event_editor_drop_creates_relation_signal` - Signal emission with correct args
- `test_entity_editor_rejects_drop_when_no_entity_loaded` - Edge case
- `test_entity_editor_rejects_invalid_mime_data` - Error handling

## Next Steps (Sprint 1)

Sprint 1 will add:
1. **Type Picker Widget** - Show on Shift key press, select relation type
2. **Toast Notification** - "✓ Relation created" with Undo button
3. **Drag Pill** - Visual indicator following cursor
4. **Drop Hint Badge** - "→ related" overlay on editor during drag

See `docs/DRAG_DROP_RELATIONS_PLAN.md` Section 8 for full Sprint 1 plan.

## Technical Notes

### MIME Data Format
```json
{
  "id": "uuid-string",
  "type": "event" | "entity",
  "name": "Display Name"
}
```

### Signal Signature
```python
add_relation_requested = Signal(
    str,   # source_id (dropped item)
    str,   # target_id (current editor item)
    str,   # rel_type (e.g., "related")
    dict,  # attributes (empty for now)
    bool   # bidirectional (False for Sprint 0)
)
```

### Relation Direction
- Source: The dragged item from Project Explorer
- Target: The item currently loaded in the editor
- Example: Dragging "Event A" onto entity editor with "Entity B" loaded creates relation "Event A → Entity B"

## Resources

- **RFC:** `docs/DRAG_DROP_RELATIONS_PLAN.md`
- **Architecture:** `docs/ARCHITECTURE.md`
- **Command Pattern:** `docs/Design.md` Section 2.2
- **Thread Safety:** `docs/QT_THREADING_SAFETY.md`

---

**Sprint 0 Complete** ✅  
**Ready for Sprint 1** → Type Picker & Visual Feedback
