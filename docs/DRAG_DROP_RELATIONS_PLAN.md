# RFC: Drag-and-Drop Relations Feature for ProjektKraken

**Status:** Draft  
**Author:** ProjektKraken Development Team  
**Created:** 2024  
**Target Version:** 2.0.0  

---

## 1. Executive Summary

This RFC proposes a comprehensive drag-and-drop interaction system for creating entity-to-entity relations in ProjektKraken. The feature enables worldbuilders to establish connections between entities and events through natural, intuitive gestures across all major UI surfaces: the Project Explorer (UnifiedList), Timeline cards, Graph nodes, and Map markers. By leveraging the existing command pattern infrastructure, undo/redo support, and Qt's drag-and-drop framework, this enhancement transforms relation creation from a multi-step dialog workflow into a single fluid motion. The implementation introduces visual feedback systems (drag pills, preview lines, drop hints, and confirmation toasts), coordinates with the existing DatabaseWorker for async persistence, and maintains the application's strict separation of concerns across GUI, commands, services, and core layers. This feature represents a major UX advancement that aligns with ProjektKraken's timeline-first, context-aware design philosophy.

---

## 2. Grounding in Current Repository

### 2.1 Existing Architecture

**Commands Layer** (`src/commands/`):
- `base_command.py`: Defines `BaseCommand` abstract class with `execute()` and `undo()` methods
- `relation_commands.py`: Contains `AddRelationCommand`, `RemoveRelationCommand`, and `UpdateRelationCommand`
- Command pattern already supports undo/redo through `CommandStack`

**Services Layer** (`src/services/`):
- `db_service.py`: `DatabaseService` class with repository pattern for entity, event, and relation access
- `worker.py`: `DatabaseWorker` class extends `QThread` for async database operations
  - Emits signals: `entity_created`, `entity_updated`, `relation_added`, `relation_removed`
- `search_service.py`: Contains `index_entity()` and `index_event()` functions for full-text search

**GUI Layer** (`src/gui/widgets/`):
- `unified_list.py`: Already implements `DraggableListView` with MIME type `"application/x-kraken-item"`
  - Uses custom `UnifiedListModel` for entities and events
  - Supports drag operations with item metadata
- `entity_editor.py`: `EntityEditor` widget displays entity details with relation chips
- `event_editor.py`: `EventEditor` widget for event editing
- `graph_view/`: Graph visualization with nodes and edges
  - `graph_widget.py`: Main graph canvas
  - `graph_node.py`: Node representations
- `map/`: Geographic map interface
  - `map_widget.py`: Map canvas with markers
  - `map_marker.py`: Entity location markers
- `timeline_view.py`: Timeline visualization with event cards

**Core Layer** (`src/core/`):
- `events.py`: `Event` dataclass with `to_dict()` and `from_dict()`
- `entities.py`: `Entity` dataclass with relations support
- `relations.py`: `Relation` dataclass defining entity-to-entity connections
- `theme_manager.py`: `ThemeManager` class uses `themes.json` for styling
- `constants.py`: Defines `AUTOSAVE_DELAY_MS = 2000`

**App Layer** (`src/app/`):
- `main.py`: Application entry point
- `main_window.py`: `MainWindow` orchestrates all components via signal/slot connections

### 2.2 Current Relation Workflow

Today, users create relations through:
1. Right-click context menu on entity → "Add Relation"
2. Dialog popup with dropdowns for target entity and relation type
3. OK button to confirm → `AddRelationCommand` executed
4. Relation appears as chip in EntityEditor's relation section

This workflow requires 4+ clicks and breaks the user's flow when rapidly connecting entities.

### 2.3 Existing Drag Infrastructure

The `DraggableListView` in `unified_list.py` already:
- Implements `QAbstractItemView` drag/drop
- Serializes item data to MIME type with JSON payload: `{"type": "entity|event", "id": "uuid", "name": "..."}`
- Handles `dragEnterEvent()`, `dragMoveEvent()`, `dropEvent()`
- Currently used for reordering items within the list

**Gap:** No drop acceptance logic exists for cross-widget drops or relation creation.

---

## 3. Detailed UX Flows

### 3.1 Flow A: Project Explorer → Entity Editor

**Scenario:** User drags "Aragorn" entity from UnifiedList onto "Fellowship" entity in EntityEditor.

**Steps:**
1. User clicks and holds on "Aragorn" item in UnifiedList (left panel)
2. **Drag Start:** Mouse moves 5px → `startDrag()` called
   - Semi-transparent "drag pill" appears under cursor showing "Aragorn" with entity icon
   - Original item in list dims to 50% opacity
3. **Drag Move:** User drags over EntityEditor (center panel) showing "Fellowship"
   - Drop zone highlight appears: 2px dashed border around entity name header
   - Tooltip appears: "Add relation: Aragorn → Fellowship"
4. **Drop:** User releases mouse over EntityEditor
   - Drop zone flashes green (200ms)
   - Confirmation toast appears bottom-right: "Added relation: Aragorn → Fellowship (member_of)"
   - Relation chip appears instantly in Fellowship's relation section
   - `AddRelationCommand` executes async via DatabaseWorker
5. **Undo:** Ctrl+Z reverses the action
   - Relation chip disappears
   - Toast: "Removed relation: Aragorn → Fellowship"

**Edge Cases:**
- **Drag over self:** No drop zone highlight, cursor shows "not-allowed" icon
- **Existing relation:** Drop hint shows "⚠ Relation already exists" in yellow
- **Drop outside valid zones:** No action, drag pill fades away

### 3.2 Flow B: Graph Node → Graph Node

**Scenario:** User connects two nodes in the graph visualization.

**Steps:**
1. User clicks "Aragorn" node in graph and drags
2. **Visual Feedback:**
   - Drag pill shows "Aragorn" with mini avatar
   - Dotted preview line follows cursor from source node center
   - Line color: theme's `primary_accent` color
3. **Hover Target:** User drags over "Gondor" node
   - Target node border glows (3px solid, pulsing animation)
   - Arrow head appears on preview line pointing to target
   - Tooltip: "Create relation: Aragorn → Gondor"
4. **Drop:** User releases on "Gondor"
   - Preview line morphs into solid edge (300ms animation)
   - Edge labeled with default relation type ("related_to")
   - Confirmation toast with undo button
   - Double-click edge to edit relation type
5. **Modifier Keys:**
   - **Shift+Drag:** Bidirectional relation (two arrows)
   - **Ctrl+Drag:** Opens mini relation-type picker under cursor before drop

**Edge Cases:**
- **Drop on empty canvas:** No action, line fades
- **Circular dependencies:** Allowed (worldbuilding permits time loops, paradoxes)
- **Multiple simultaneous drags:** Not supported (Qt limitation)

### 3.3 Flow C: Timeline Card Drag

**Scenario:** Link event to entity by dragging timeline card.

**Steps:**
1. User drags "Battle of Helm's Deep" event card from timeline
2. **Drag Representation:**
   - Drag pill shows event name + date + icon
   - Drag pill follows cursor with slight trailing animation
3. **Drop on Entity:**
   - User drops on "Rohan" entity in UnifiedList
   - Creates relation: Event → Entity with type "involves"
   - Entity card in list gains small event badge counter (e.g., "3 events")
4. **Drop on Graph Node:**
   - Event node appears in graph at drop location
   - Automatic layout algorithm runs to position nearby
   - Edge connects event to entity
5. **Visual Feedback:**
   - Timeline card temporarily "flashes" to indicate successful link
   - Entity/node shows brief highlight pulse

**Notes:**
- Events can relate to entities but not to other events (per data model)
- Dropping event on another event shows "not-allowed" cursor

### 3.4 Flow D: Map Marker to Marker

**Scenario:** Connect two locations on the world map.

**Steps:**
1. User drags "Rivendell" marker on map
2. **Drag Visuals:**
   - Marker lifts up (z-index increase, shadow grows)
   - Drag pill shows location name + coordinates
   - Dotted line trail from original position to cursor
3. **Hover Target:** Drag over "Lothlórien" marker
   - Target marker scales to 120% and pulses
   - Preview arc line appears between locations (geodesic curve)
   - Distance shown on line: "234 km"
4. **Drop:**
   - Arc line becomes solid edge with arrow
   - Default relation: "connected_to"
   - Both markers briefly flash
   - Relation appears in both entities' editor views
5. **Map-Specific Features:**
   - **Alt+Drag:** Create waypoint mid-drag (route planning)
   - **Right-drag:** Move marker without creating relation

**Edge Cases:**
- **Ocean-to-ocean:** Allowed (sea routes)
- **Cross-layer drops:** Map supports multiple layers (underground, sky) — drop hint shows layer mismatch warning

---

## 4. Visual Indicators Specification

### 4.1 Drag Pill

**Appearance:**
- Semi-transparent rounded rectangle (8px border-radius)
- Background: `rgba(theme.surface, 0.9)` with 4px blur backdrop
- Border: 1px solid `theme.border`
- Icon (16x16) + Text (14pt, `theme.text`) + Type label (10pt, `theme.text_dim`)
- Shadow: `0 4px 12px rgba(0, 0, 0, 0.3)`
- Size: Auto-width (max 200px) × 40px height

**Implementation:**
- `QLabel` with `Qt.WA_TransparentForMouseEvents`
- Positioned at `QCursor.pos() + QPoint(10, 10)`
- Updates position in `dragMoveEvent()` (60 FPS)

**Code Location:** `src/gui/widgets/drag_pill.py` (new file)

### 4.2 Preview Line

**Graph/Map Context:**
- SVG path drawn on overlay layer
- Style: 2px dashed line, dash pattern `[8, 4]`
- Color: `theme.primary_accent` with 80% opacity
- Arrow head: 12px equilateral triangle at cursor end
- Animation: Dash offset animates to create "marching ants" effect (10px/sec)

**Implementation:**
- `QPainterPath` drawn in `paintEvent()`
- Recalculated in `dragMoveEvent()`
- Uses `QPen(Qt.DashLine)` with custom dash pattern

**Code Location:**
- `src/gui/widgets/graph_view/drag_overlay.py` (new file)
- `src/gui/widgets/map/drag_overlay.py` (new file)

### 4.3 Node/Entity Highlight

**On Hover (Valid Drop Target):**
- Border: 3px solid `theme.primary_accent`
- Glow: Box-shadow `0 0 12px rgba(theme.primary_accent, 0.6)`
- Animation: Pulse (1.5s duration, infinite loop, opacity 60%-100%)
- Background: Tint with `rgba(theme.primary_accent, 0.1)`

**On Invalid Hover:**
- Border: 2px solid `theme.error`
- No glow
- Cursor: `Qt.ForbiddenCursor`

**Implementation:**
- QSS dynamic property `dropTarget: true/false`
- Applied via `setProperty("dropTarget", True)` + `style().polish()`
- Stylesheet in `themes.json`:
  ```css
  QWidget[dropTarget="true"] {
      border: 3px solid $primary_accent;
      background-color: rgba($primary_accent, 0.1);
  }
  ```

### 4.4 Drop Hint Tooltip

**Appearance:**
- Floating tooltip near cursor (offset 20px below)
- Background: `theme.surface_raised` with 6px border-radius
- Text: 12pt, `theme.text`
- Prefix icon: ✓ (valid) or ⚠ (warning) or ✗ (invalid)
- Auto-hide after 1.5s if no movement

**Content:**
- Valid: "Add relation: {source} → {target} ({relation_type})"
- Existing: "⚠ Relation already exists"
- Invalid: "✗ Cannot relate {type_a} to {type_b}"
- Self-drop: "✗ Cannot relate entity to itself"

**Implementation:**
- `QToolTip.showText(QCursor.pos() + QPoint(0, 20), hint_text)`
- Updated in `dragMoveEvent()` with 100ms debounce

### 4.5 Relation Chips

**Existing Design (Enhanced):**
- Pill-shaped buttons in EntityEditor's relation section
- Click to navigate, right-click to edit/remove
- **New:** Drag-initiated chips have 300ms "spawn" animation:
  - Fade in from 0% to 100% opacity
  - Scale from 80% to 100%
  - Slide in from drop location

**Code Location:** `src/gui/widgets/entity_editor.py` (modify existing)

### 4.6 Confirmation Toast

**Appearance:**
- Bottom-right corner, 16px margin
- 320px wide × auto height
- Background: `theme.surface_raised`
- Border-left: 4px solid `theme.success` (or `theme.error` for failures)
- Text: 13pt, `theme.text`
- Icon + Message + Undo button
- Auto-dismiss after 4 seconds (configurable)

**Behavior:**
- Slides in from right (200ms ease-out)
- Stacks vertically if multiple toasts
- Undo button executes `command_stack.undo()`
- Clicking toast dismisses it

**Implementation:**
- `ToastManager` singleton in `src/gui/widgets/toast_manager.py` (new)
- Uses `QPropertyAnimation` for slide
- Connected to `DatabaseWorker` signals for feedback

---

## 5. Data & Command Flow

### 5.1 Drag Initiation Flow

```
┌─────────────────┐
│ User MousePress │
│   on ListItem   │
└────────┬────────┘
         │ QMouseEvent
         ▼
┌─────────────────────┐
│ mouseMoveEvent()    │ (5px threshold)
│ in DraggableList    │
└────────┬────────────┘
         │
         ▼
┌──────────────────────────┐
│ startDrag()              │
│ - Create QDrag object    │
│ - Set MIME data (JSON)   │
│ - Set drag pixmap        │
│ - Show DragPill widget   │
└────────┬─────────────────┘
         │
         ▼
┌───────────────────────────┐
│ Qt Event Loop             │
│ - Propagate to drop zones│
│ - dragEnterEvent()        │
│ - dragMoveEvent()         │
└────────┬──────────────────┘
         │
         ▼
    Drop or Cancel
```

### 5.2 Drop & Command Execution Flow

```
┌──────────────────┐
│ dropEvent()      │
│ in EntityEditor  │
└────────┬─────────┘
         │ Extract MIME data
         ▼
┌────────────────────────────────┐
│ _handle_drop()                 │
│ - Parse JSON                   │
│ - Validate relation            │
│ - Determine relation type      │
└────────┬───────────────────────┘
         │
         ▼
┌──────────────────────────────────┐
│ MainWindow.create_relation()     │
│ (slot connected to widget signal)│
└────────┬─────────────────────────┘
         │ emit relation_requested(source_id, target_id, rel_type)
         ▼
┌────────────────────────────────┐
│ AddRelationCommand.__init__()  │
│ - Store source_id, target_id   │
│ - Store relation_type          │
│ - Store old_state (for undo)   │
└────────┬───────────────────────┘
         │
         ▼
┌──────────────────────────┐
│ CommandStack.execute()   │
│ - Call cmd.execute()     │
│ - Push to undo stack     │
└────────┬─────────────────┘
         │
         ▼
┌────────────────────────────────┐
│ AddRelationCommand.execute()   │
│ - Create Relation object       │
│ - Call db_service.add_relation()│
└────────┬───────────────────────┘
         │
         ▼
┌──────────────────────────────────┐
│ DatabaseService.add_relation()   │
│ - relation_repo.add(relation)    │
│ - Enqueue worker task            │
└────────┬─────────────────────────┘
         │ QMetaObject.invokeMethod()
         ▼
┌─────────────────────────────┐
│ DatabaseWorker.run()        │ (Background thread)
│ - SQL INSERT                │
│ - Commit transaction        │
└────────┬────────────────────┘
         │ emit relation_added(relation)
         ▼
┌───────────────────────────────────┐
│ MainWindow._on_relation_added()   │ (Main thread)
│ - Update EntityEditor UI          │
│ - Add relation chip               │
│ - Update graph edge               │
│ - Show success toast              │
└───────────────────────────────────┘
```

### 5.3 Signal Definitions

**New Signals in EntityEditor:**
```python
# src/gui/widgets/entity_editor.py
relation_drop_requested = pyqtSignal(str, str, str)  # (source_id, target_id, relation_type)
invalid_drop_attempted = pyqtSignal(str)  # (reason)
```

**New Signals in GraphWidget:**
```python
# src/gui/widgets/graph_view/graph_widget.py
node_drop_completed = pyqtSignal(str, str)  # (source_node_id, target_node_id)
preview_line_update = pyqtSignal(QPointF, QPointF)  # (start_pos, end_pos)
```

**New Signals in MapWidget:**
```python
# src/gui/widgets/map/map_widget.py
marker_drop_completed = pyqtSignal(str, str, float)  # (source_id, target_id, distance_km)
```

**Existing DatabaseWorker Signals (reused):**
```python
# src/services/worker.py
relation_added = pyqtSignal(dict)  # Relation as dict
relation_removed = pyqtSignal(str)  # Relation ID
operation_failed = pyqtSignal(str, str)  # (operation_name, error_message)
```

### 5.4 Undo Flow

```
┌──────────────────┐
│ User presses     │
│ Ctrl+Z           │
└────────┬─────────┘
         │ QKeySequence::Undo
         ▼
┌────────────────────┐
│ CommandStack.undo()│
└────────┬───────────┘
         │
         ▼
┌──────────────────────────────┐
│ AddRelationCommand.undo()    │
│ - Call db_service.remove()   │
│ - Restore old state          │
└────────┬─────────────────────┘
         │
         ▼
┌──────────────────────────────┐
│ DatabaseWorker               │
│ - SQL DELETE                 │
│ - emit relation_removed      │
└────────┬─────────────────────┘
         │
         ▼
┌──────────────────────────────┐
│ MainWindow                   │
│ - Remove relation chip       │
│ - Remove graph edge          │
│ - Show undo toast            │
└──────────────────────────────┘
```

---

## 6. Files to Add and Modify

### 6.1 New Files

**GUI Components:**

1. **`src/gui/widgets/drag_pill.py`**
   - `DragPill(QLabel)`: Floating widget that follows cursor
   - Methods: `update_position(QPoint)`, `set_content(item_dict)`, `show_invalid()`
   - ~100 LOC

2. **`src/gui/widgets/toast_manager.py`**
   - `ToastManager(QObject)`: Singleton for notification management
   - `Toast(QWidget)`: Individual toast notification
   - Methods: `show_success()`, `show_error()`, `show_info()`, `_auto_dismiss()`
   - Supports undo button integration
   - ~200 LOC

3. **`src/gui/widgets/graph_view/drag_overlay.py`**
   - `GraphDragOverlay(QWidget)`: Transparent overlay for preview lines
   - Methods: `update_preview_line(start, end)`, `clear_preview()`, `paintEvent()`
   - ~150 LOC

4. **`src/gui/widgets/map/drag_overlay.py`**
   - `MapDragOverlay(QWidget)`: Similar to graph overlay but for map
   - Draws geodesic curves between markers
   - ~150 LOC

5. **`src/gui/widgets/drop_mixin.py`**
   - `DropTargetMixin`: Reusable logic for widgets accepting drops
   - Methods: `_handle_drop_enter()`, `_handle_drop_move()`, `_parse_mime_data()`, `_validate_drop()`
   - Reduces code duplication across EntityEditor, GraphWidget, MapWidget
   - ~120 LOC

**Commands:**

6. **`src/commands/bulk_relation_command.py`**
   - `BulkAddRelationCommand(BaseCommand)`: For multiple relations at once
   - Optimizes database writes for multi-select drops
   - ~80 LOC

**Tests:**

7. **`tests/unit/test_drag_pill.py`**
   - Unit tests for DragPill widget
   - ~100 LOC

8. **`tests/integration/test_drag_drop_relations.py`**
   - Integration tests for full drag-drop-persist cycle
   - Uses `qtbot` fixture for simulated drags
   - ~300 LOC

### 6.2 Files to Modify

**Core Layer:**

1. **`src/core/constants.py`**
   - Add: `DRAG_THRESHOLD_PX = 5`
   - Add: `TOAST_AUTO_DISMISS_MS = 4000`
   - Add: `BULK_RELATION_THRESHOLD = 5`
   - Add: `DEFAULT_RELATION_TYPE = "related_to"`
   - +10 LOC

**GUI Layer:**

2. **`src/gui/widgets/unified_list.py`**
   - Modify `DraggableListView.startDrag()`: Initialize DragPill widget
   - Add multi-select drag support (Ctrl+Click → drag multiple items)
   - +50 LOC

3. **`src/gui/widgets/entity_editor.py`**
   - Implement `dropEvent()`, `dragEnterEvent()`, `dragMoveEvent()`
   - Add signal: `relation_drop_requested`
   - Integrate drop zone highlight via dynamic QSS properties
   - Add `_spawn_relation_chip_animated()` method
   - +120 LOC

4. **`src/gui/widgets/event_editor.py`**
   - Similar drop handling for event-to-entity relations
   - +80 LOC

5. **`src/gui/widgets/graph_view/graph_widget.py`**
   - Add drag overlay layer (`GraphDragOverlay` instance)
   - Modify `mouseMoveEvent()` for node dragging disambiguation
   - Add `_create_edge_from_drop()` method
   - Connect to `node_drop_completed` signal
   - +150 LOC

6. **`src/gui/widgets/graph_view/graph_node.py`**
   - Add `setDropHighlight(bool)` method for glow effect
   - Modify `paint()` to render highlight border
   - +40 LOC

7. **`src/gui/widgets/map/map_widget.py`**
   - Add `MapDragOverlay` integration
   - Implement geodesic line calculation for preview
   - Add `_calculate_marker_distance()` method
   - +130 LOC

8. **`src/gui/widgets/map/map_marker.py`**
   - Add lift/drop animation (z-index + shadow)
   - Add `setHoverScale(float)` for target highlighting
   - +50 LOC

9. **`src/gui/widgets/timeline_view.py`**
   - Enable drag on timeline cards (currently view-only)
   - Add `TimelineCard.mouseMoveEvent()` to initiate drag
   - +60 LOC

**App Layer:**

10. **`src/app/main_window.py`**
    - Add slot: `_on_relation_drop_requested(source_id, target_id, rel_type)`
    - Connect new signals from all drop-enabled widgets
    - Instantiate `ToastManager` and connect to worker signals
    - Add keyboard shortcut: Ctrl+Shift+Z for redo
    - +80 LOC

**Services Layer:**

11. **`src/services/worker.py`**
    - Add task type: `"bulk_add_relations"` for batch processing
    - Optimize transaction handling for bulk inserts
    - +40 LOC

**Theme Layer:**

12. **`themes.json`**
    - Add QSS rules for `[dropTarget="true"]` pseudo-state
    - Add animation keyframes for pulse effect
    - Add toast notification styles
    - +60 lines JSON

**Documentation:**

13. **`docs/USER_GUIDE.md`**
    - Add "Creating Relations via Drag-and-Drop" section
    - Add animated GIF demos (to be created)
    - +200 LOC (including examples)

**Total Estimated Changes:**
- New files: ~1,100 LOC
- Modified files: ~930 LOC
- **Total: ~2,030 LOC**

---

## 7. Acceptance Criteria & Tests

### 7.1 Functional Acceptance Criteria

**AC1: Basic Drag-Drop Relation Creation**
- ✅ User can drag entity from UnifiedList and drop on EntityEditor to create relation
- ✅ Relation appears as chip in target entity's relation section
- ✅ Relation persists to database within 2 seconds
- ✅ Confirmation toast appears with undo button

**AC2: Visual Feedback**
- ✅ Drag pill follows cursor during drag
- ✅ Drop target highlights with border/glow when valid
- ✅ Cursor changes to "not-allowed" when hovering invalid drop zone
- ✅ Preview line animates in graph/map views

**AC3: Undo/Redo**
- ✅ Ctrl+Z removes drag-created relation
- ✅ Ctrl+Shift+Z restores undone relation
- ✅ Undo works after relation persisted to database
- ✅ Undo toast notification appears

**AC4: Edge Cases**
- ✅ Dropping entity on itself shows error toast
- ✅ Dropping duplicate relation shows warning (does not create duplicate)
- ✅ Dropping on invalid target type shows error
- ✅ Dragging multiple items (multi-select) creates multiple relations

**AC5: Cross-Widget Support**
- ✅ Drag from UnifiedList → drop on Graph node works
- ✅ Drag from Graph node → drop on Map marker works
- ✅ Drag Timeline card → drop on Entity works
- ✅ Drag Map marker → drop on EntityEditor works

**AC6: Performance**
- ✅ Drag pill updates at 60 FPS (≤16ms frame time)
- ✅ Bulk relation creation (>5 items) uses batch command
- ✅ UI remains responsive during database write
- ✅ No memory leaks after 100 drag-drop cycles

### 7.2 Unit Tests

**Test File: `tests/unit/test_drag_pill.py`**

```python
def test_drag_pill_creation(qtbot):
    """Test DragPill widget initializes correctly."""
    pill = DragPill()
    qtbot.addWidget(pill)
    assert pill.isHidden()
    pill.set_content({"name": "Test", "type": "entity"})
    pill.show()
    assert pill.isVisible()

def test_drag_pill_position_update(qtbot):
    """Test DragPill follows cursor position."""
    pill = DragPill()
    qtbot.addWidget(pill)
    pill.update_position(QPoint(100, 200))
    assert pill.pos() == QPoint(110, 210)  # Offset applied

def test_drag_pill_invalid_state(qtbot):
    """Test DragPill shows error styling for invalid drops."""
    pill = DragPill()
    qtbot.addWidget(pill)
    pill.show_invalid()
    assert "error" in pill.styleSheet()
```

**Test File: `tests/unit/test_drop_mixin.py`**

```python
def test_parse_mime_data_valid():
    """Test MIME data parsing for valid entity."""
    mime = QMimeData()
    mime.setData("application/x-kraken-item", b'{"type":"entity","id":"123"}')
    mixin = DropTargetMixin()
    result = mixin._parse_mime_data(mime)
    assert result["type"] == "entity"
    assert result["id"] == "123"

def test_validate_drop_self_rejection():
    """Test dropping entity on itself is rejected."""
    mixin = DropTargetMixin()
    mixin.entity_id = "123"
    is_valid = mixin._validate_drop({"id": "123"}, "entity")
    assert not is_valid
```

**Test File: `tests/unit/test_bulk_relation_command.py`**

```python
def test_bulk_command_execute(db_service):
    """Test bulk relation command creates multiple relations."""
    cmd = BulkAddRelationCommand(
        db_service,
        source_ids=["1", "2", "3"],
        target_id="target",
        relation_type="related_to"
    )
    cmd.execute()
    relations = db_service.relation_repo.get_by_target("target")
    assert len(relations) == 3

def test_bulk_command_undo(db_service):
    """Test bulk undo removes all relations."""
    cmd = BulkAddRelationCommand(db_service, ["1", "2"], "target", "member_of")
    cmd.execute()
    cmd.undo()
    relations = db_service.relation_repo.get_by_target("target")
    assert len(relations) == 0
```

### 7.3 Integration Tests

**Test File: `tests/integration/test_drag_drop_relations.py`**

```python
def test_drag_entity_to_entity_editor(qtbot, main_window, db_service):
    """Test full drag-drop flow from list to editor."""
    # Setup
    entity1 = Entity(name="Source", type="character")
    entity2 = Entity(name="Target", type="location")
    db_service.entity_repo.add(entity1)
    db_service.entity_repo.add(entity2)
    main_window.refresh_unified_list()
    main_window.load_entity(entity2.id)

    # Simulate drag
    list_view = main_window.unified_list
    editor = main_window.entity_editor
    
    mime = QMimeData()
    mime.setData("application/x-kraken-item", 
                 json.dumps({"type": "entity", "id": entity1.id}).encode())
    
    # Simulate drop
    drop_event = QDropEvent(
        editor.rect().center(),
        Qt.CopyAction,
        mime,
        Qt.LeftButton,
        Qt.NoModifier
    )
    editor.dropEvent(drop_event)
    
    # Wait for async persistence
    qtbot.waitSignal(db_service.worker.relation_added, timeout=5000)
    
    # Verify relation created
    relations = db_service.relation_repo.get_by_source(entity1.id)
    assert len(relations) == 1
    assert relations[0].target_id == entity2.id
    
    # Verify UI updated
    chips = editor.findChildren(RelationChip)
    assert len(chips) == 1

def test_drag_graph_node_to_node(qtbot, main_window, db_service):
    """Test drag-drop between graph nodes."""
    # Setup graph with two nodes
    entity1 = Entity(name="Node1", type="character")
    entity2 = Entity(name="Node2", type="character")
    db_service.entity_repo.add(entity1)
    db_service.entity_repo.add(entity2)
    
    graph = main_window.graph_widget
    graph.load_entities([entity1, entity2])
    
    # Get node widgets
    node1 = graph.get_node_by_entity_id(entity1.id)
    node2 = graph.get_node_by_entity_id(entity2.id)
    
    # Simulate drag
    with qtbot.waitSignal(graph.node_drop_completed) as blocker:
        graph._simulate_node_drag(node1, node2)
    
    assert blocker.args == [entity1.id, entity2.id]
    
    # Verify edge rendered
    edges = graph.get_edges()
    assert len(edges) == 1
    assert edges[0].source_id == entity1.id

def test_undo_drag_created_relation(qtbot, main_window, db_service):
    """Test undo of drag-created relation."""
    # Create relation via drag-drop
    entity1 = Entity(name="Source", type="character")
    entity2 = Entity(name="Target", type="location")
    db_service.entity_repo.add(entity1)
    db_service.entity_repo.add(entity2)
    
    # Simulate drop (reuse helper from previous test)
    main_window.create_relation_via_drop(entity1.id, entity2.id, "related_to")
    qtbot.wait(100)
    
    # Undo
    main_window.command_stack.undo()
    qtbot.waitSignal(db_service.worker.relation_removed, timeout=5000)
    
    # Verify relation removed
    relations = db_service.relation_repo.get_by_source(entity1.id)
    assert len(relations) == 0
```

### 7.4 Test Execution

**Run all tests:**
```bash
pytest tests/ --cov=src --cov-report=term-missing -v
```

**Run only drag-drop tests:**
```bash
pytest tests/integration/test_drag_drop_relations.py -v
```

**Run with Qt visual debugging:**
```bash
pytest tests/integration/test_drag_drop_relations.py --qt-debug
```

**Performance benchmarks:**
```bash
pytest tests/integration/test_drag_drop_relations.py::test_drag_performance -v --benchmark
```

**Coverage target:**
- Drag-drop code: 100% (critical UX path)
- Overall project: Maintain ≥95%

---

## 8. Rollout Plan & Milestones

### 8.1 Sprint 1: Foundation (Week 1-2, 40 hours)

**Goals:**
- Implement core drag infrastructure
- Add visual feedback components
- No database persistence yet (in-memory only)

**Tasks:**
1. Create `DragPill` widget with cursor tracking (6h)
2. Create `DropTargetMixin` with validation logic (8h)
3. Modify `DraggableListView` to use `DragPill` (4h)
4. Implement drop handling in `EntityEditor` (UI only) (8h)
5. Add QSS styling for drop highlights in `themes.json` (4h)
6. Write unit tests for `DragPill` and `DropTargetMixin` (6h)
7. Create `ToastManager` widget (4h)

**Deliverables:**
- ✅ Drag pill appears and follows cursor
- ✅ EntityEditor highlights on valid hover
- ✅ Toast notifications appear (mock data)
- ✅ Unit tests pass

**Risks:**
- Qt drag-drop event propagation quirks → Mitigation: Test on multiple platforms early

### 8.2 Sprint 2: Command Integration (Week 3-4, 40 hours)

**Goals:**
- Connect drag-drop to command pattern
- Implement database persistence
- Add undo/redo support

**Tasks:**
1. Integrate `AddRelationCommand` with drop events (6h)
2. Connect `MainWindow` signals to command execution (4h)
3. Add `DatabaseWorker` task for async relation creation (4h)
4. Implement `BulkAddRelationCommand` for multi-select (6h)
5. Wire up toast notifications to `DatabaseWorker` signals (4h)
6. Add undo button to toast widget (3h)
7. Write integration tests for full drop-persist cycle (10h)
8. Bug fixing and polish (3h)

**Deliverables:**
- ✅ Drag-drop creates relations in database
- ✅ Undo/redo works correctly
- ✅ Integration tests pass
- ✅ Bulk drops optimized

**Risks:**
- Race conditions between UI update and DB write → Mitigation: Use signals for synchronization

### 8.3 Sprint 3: Graph & Map Support (Week 5-6, 40 hours)

**Goals:**
- Extend drag-drop to graph and map widgets
- Add preview line animations
- Support cross-widget drops

**Tasks:**
1. Create `GraphDragOverlay` with preview line rendering (8h)
2. Implement drop handling in `GraphWidget` (8h)
3. Add node highlight effects in `GraphNode` (4h)
4. Create `MapDragOverlay` with geodesic curves (8h)
5. Implement drop handling in `MapWidget` (6h)
6. Add marker lift/drop animations (4h)
7. Write integration tests for graph and map drops (8h)
8. Performance optimization (60 FPS target) (4h)

**Deliverables:**
- ✅ Graph node-to-node drag works
- ✅ Map marker-to-marker drag works
- ✅ Preview lines animate smoothly
- ✅ Cross-widget drops functional

**Risks:**
- Performance issues with complex graphs → Mitigation: Implement LOD (level of detail) for preview rendering

### 8.4 Sprint 4: Timeline & Polish (Week 7-8, 40 hours)

**Goals:**
- Add timeline card dragging
- Comprehensive testing
- User documentation
- Bug fixes and UX refinements

**Tasks:**
1. Enable drag on `TimelineCard` widgets (6h)
2. Implement event-to-entity drop logic (6h)
3. Add timeline card "flash" feedback (3h)
4. Create user guide section with GIFs (6h)
5. Accessibility testing (keyboard navigation, screen readers) (4h)
6. Cross-platform testing (Windows, macOS, Linux) (6h)
7. Performance profiling and optimization (4h)
8. Fix bugs from testing phase (5h)

**Deliverables:**
- ✅ Timeline drag-drop works
- ✅ User documentation complete
- ✅ All acceptance criteria met
- ✅ Cross-platform verified
- ✅ 95%+ test coverage

**Risks:**
- Timeline widget complexity → Mitigation: Refactor if needed, keep scope focused

### 8.5 Total Effort Estimate

- **Development:** 120 hours (3 weeks for 1 developer)
- **Testing:** 40 hours
- **Documentation:** 8 hours
- **Code review & polish:** 12 hours
- **Total:** 180 hours (~5 weeks for 1 developer, or 2.5 weeks for 2 developers)

---

## 9. Open Questions & Decisions

### 9.1 Default Relation Type

**Question:** When drag-dropping without specifying a relation type, what should be the default?

**Options:**
1. **Always "related_to"** (generic)
2. **Context-aware heuristics** (e.g., character → location = "lives_in", character → event = "participated_in")
3. **Show quick-picker popup** on drop before creating relation
4. **User-configurable default** in settings

**Current Proposal:** Option 1 (always "related_to") for MVP, with Option 3 (quick-picker) on Ctrl+Drop.

**Decision Needed By:** Sprint 1

**Impacts:**
- User guide content
- Command implementation
- UX flow complexity

---

### 9.2 Bulk Relation Threshold

**Question:** When dragging multiple items, at what count should we switch to bulk command?

**Options:**
1. **Always use individual commands** (simpler undo)
2. **Threshold of 5 items** (current proposal)
3. **Threshold of 10 items**
4. **Always use bulk command** (faster)

**Current Proposal:** Option 2 (threshold of 5) with configurable constant.

**Trade-offs:**
- Individual commands: Granular undo, slower for large batches
- Bulk commands: All-or-nothing undo, faster execution

**Decision Needed By:** Sprint 2

**Impacts:**
- `BulkAddRelationCommand` implementation
- Undo/redo UX
- Performance benchmarks

---

### 9.3 Modifier Key Behavior

**Question:** What should Shift, Ctrl, Alt do during drag?

**Options:**
1. **Shift:** Bidirectional relation (creates two edges)
2. **Ctrl:** Show relation-type picker popup
3. **Alt:** Copy instead of link (duplicate entity at target)
4. **Shift+Ctrl:** Multi-select mode

**Current Proposal:**
- Shift: Bidirectional
- Ctrl: Relation-type picker
- Alt: Reserved for OS drag-copy behavior
- Shift+Ctrl: Not used (too complex)

**Decision Needed By:** Sprint 1

**Impacts:**
- Drag pill visual indicators (show modifier hints)
- Command implementation (bidirectional = 2 commands)
- User documentation

---

### 9.4 Cross-World Dragging

**Question:** Should users be able to drag entities from one world file to another?

**Context:** ProjektKraken supports multiple open world files (tabs).

**Options:**
1. **Disallow:** Show error toast if attempting cross-world drop
2. **Copy entity:** Clone entity to target world with relations
3. **Create reference:** Special "external reference" relation type
4. **Defer to Phase 2:** Not in MVP

**Current Proposal:** Option 1 (disallow) for MVP, Option 3 (references) for future enhancement.

**Decision Needed By:** Sprint 3

**Impacts:**
- Drop validation logic
- Multi-tab architecture
- Data model (external references table)

---

### 9.5 Auto-Suggest Relation Type

**Question:** Should the system suggest relation types based on entity types?

**Example:** Dragging character → location could suggest "lives_in", "visited", "born_in"

**Options:**
1. **No auto-suggest:** User always picks type (or uses default)
2. **Simple heuristics:** Hardcoded rules (character+location = "lives_in")
3. **ML-based:** Learn from user's past relations
4. **Template library:** User defines relation-type templates per world

**Current Proposal:** Option 4 (templates) deferred to Phase 2; Option 1 (no auto-suggest) for MVP.

**Decision Needed By:** Sprint 4

**Impacts:**
- Data model (relation templates table)
- UI (template picker widget)
- User onboarding (template setup wizard)

---

### 9.6 Preview Line Performance

**Question:** How to optimize preview line rendering for large graphs (1000+ nodes)?

**Options:**
1. **Always render:** Simple but potentially slow
2. **Throttle updates:** Only update every 50ms
3. **Simplified rendering:** Use straight line instead of curves for large graphs
4. **GPU acceleration:** Use OpenGL widget for graph rendering

**Current Proposal:** Option 2 (throttle) + Option 3 (simplified) based on node count.

**Decision Needed By:** Sprint 3

**Impacts:**
- `GraphDragOverlay` implementation
- Frame rate benchmarks
- Graph rendering architecture

---

## 10. Follow-up PR Checklist

### PR #1: Foundation Components

**Goal:** Drag pill, toast manager, drop mixin

**Changes:**
- ✅ Add `src/gui/widgets/drag_pill.py`
- ✅ Add `src/gui/widgets/toast_manager.py`
- ✅ Add `src/gui/widgets/drop_mixin.py`
- ✅ Add unit tests
- ✅ Update `themes.json` with drag-drop styles

**Acceptance:**
- All unit tests pass
- Code coverage ≥95%
- No lint warnings
- Docstrings complete (Google Style)

**Estimated Size:** +450 LOC

---

### PR #2: List-to-Editor Drag

**Goal:** Enable drag from UnifiedList to EntityEditor

**Changes:**
- ✅ Modify `src/gui/widgets/unified_list.py` to use DragPill
- ✅ Modify `src/gui/widgets/entity_editor.py` with drop handling
- ✅ Add signals for drop events
- ✅ Add integration test

**Acceptance:**
- Can drag entity from list to editor
- Drop zone highlights correctly
- Toast appears (mock data)
- No database persistence yet

**Estimated Size:** +200 LOC

---

### PR #3: Command Integration

**Goal:** Connect drag-drop to database persistence

**Changes:**
- ✅ Modify `src/app/main_window.py` to handle drop signals
- ✅ Connect to `AddRelationCommand`
- ✅ Wire up `DatabaseWorker` signals to toast
- ✅ Add undo/redo support
- ✅ Add integration tests

**Acceptance:**
- Relations persist to database
- Undo/redo works
- Toast shows success/error from DB
- Integration tests pass

**Estimated Size:** +180 LOC

---

### PR #4: Bulk Relations

**Goal:** Optimize multi-select drag performance

**Changes:**
- ✅ Add `src/commands/bulk_relation_command.py`
- ✅ Modify `unified_list.py` for multi-select drag
- ✅ Modify `main_window.py` to use bulk command when threshold exceeded
- ✅ Add unit tests

**Acceptance:**
- Can drag 10 entities at once
- Bulk command executes in <1 second
- Undo removes all relations
- Tests verify transaction atomicity

**Estimated Size:** +150 LOC

---

### PR #5: Graph Drag Support

**Goal:** Node-to-node dragging in graph view

**Changes:**
- ✅ Add `src/gui/widgets/graph_view/drag_overlay.py`
- ✅ Modify `src/gui/widgets/graph_view/graph_widget.py`
- ✅ Modify `src/gui/widgets/graph_view/graph_node.py` for highlights
- ✅ Add integration tests

**Acceptance:**
- Can drag node to node
- Preview line animates at 60 FPS
- Edge appears after drop
- Integration tests pass

**Estimated Size:** +340 LOC

---

### PR #6: Map Drag Support

**Goal:** Marker-to-marker dragging on map

**Changes:**
- ✅ Add `src/gui/widgets/map/drag_overlay.py`
- ✅ Modify `src/gui/widgets/map/map_widget.py`
- ✅ Modify `src/gui/widgets/map/map_marker.py` for animations
- ✅ Add geodesic curve calculation
- ✅ Add integration tests

**Acceptance:**
- Can drag marker to marker
- Geodesic curve renders correctly
- Distance displayed on line
- Integration tests pass

**Estimated Size:** +310 LOC

---

### PR #7: Timeline Drag

**Goal:** Event card dragging from timeline

**Changes:**
- ✅ Modify `src/gui/widgets/timeline_view.py`
- ✅ Add `TimelineCard` drag initiation
- ✅ Support event-to-entity drops
- ✅ Add flash animation on success
- ✅ Add integration tests

**Acceptance:**
- Can drag timeline card
- Drop on entity works
- Flash feedback appears
- Integration tests pass

**Estimated Size:** +120 LOC

---

### PR #8: Cross-Widget Drops

**Goal:** Support drops across all widget combinations

**Changes:**
- ✅ Test and fix: List → Graph
- ✅ Test and fix: Graph → Map
- ✅ Test and fix: Map → Editor
- ✅ Test and fix: Timeline → Map
- ✅ Add comprehensive integration tests

**Acceptance:**
- All 12 widget-pair combinations work
- No crashes or data loss
- Performance acceptable (<100ms drop handling)

**Estimated Size:** +80 LOC (mostly fixes)

---

### PR #9: Polish & Performance

**Goal:** Optimize performance and add final polish

**Changes:**
- ✅ Profile drag-drop frame rate
- ✅ Optimize preview line rendering
- ✅ Add keyboard shortcuts (Ctrl+Shift+Z for redo)
- ✅ Add accessibility features (focus indicators)
- ✅ Fix any remaining bugs

**Acceptance:**
- 60 FPS maintained during drag
- No memory leaks after 100 cycles
- Keyboard navigation works
- All acceptance criteria met

**Estimated Size:** +100 LOC

---

### PR #10: Documentation

**Goal:** Complete user and developer documentation

**Changes:**
- ✅ Update `docs/USER_GUIDE.md`
- ✅ Create animated GIF demos
- ✅ Add code examples to docstrings
- ✅ Update architecture diagrams
- ✅ Add troubleshooting section

**Acceptance:**
- User guide section complete
- All public APIs documented
- GIFs demonstrate each flow
- Sphinx docs build without warnings

**Estimated Size:** +300 LOC documentation

---

### Total PR Summary

- **10 PRs**
- **~2,230 LOC** added/modified
- **~40 hours** review time estimated
- **Dependency chain:** PRs 1-2-3 sequential, then PRs 4-7 parallel, then 8-9-10 sequential

---

## Appendix A: Implementation Timeline Gantt Chart

```
Week 1-2 (Sprint 1):
  PR #1 [========]
  PR #2         [====]

Week 3-4 (Sprint 2):
  PR #3              [========]
  PR #4                    [====]

Week 5-6 (Sprint 3):
  PR #5                        [=====]
  PR #6                        [=====]
  PR #7                            [===]

Week 7-8 (Sprint 4):
  PR #8                                 [====]
  PR #9                                     [====]
  PR #10                                        [====]
```

---

## Appendix B: Risk Register

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Qt drag-drop bugs | Medium | High | Early cross-platform testing |
| Performance degradation | Low | Medium | Profile frequently, use throttling |
| Race conditions (UI vs DB) | Medium | High | Use signals, avoid blocking calls |
| Scope creep | High | Medium | Stick to MVP, defer enhancements |
| User confusion (new UX) | Low | Low | Comprehensive user guide + tooltips |
| Undo stack corruption | Low | High | Extensive integration tests |

---

## Appendix C: Glossary

- **Drag Pill:** Floating widget that follows cursor during drag
- **Drop Zone:** Area that accepts drops (e.g., EntityEditor)
- **Preview Line:** Animated line showing potential relation in graph/map
- **Toast:** Temporary notification popup
- **Relation Chip:** Pill-shaped button representing a relation in EntityEditor
- **MIME Type:** Data format identifier for drag-drop (`application/x-kraken-item`)
- **Command Stack:** Undo/redo history manager
- **DatabaseWorker:** Background thread for async DB operations
- **Trinity View:** The three-panel layout (Editor, Timeline, Relations)

---

**End of RFC**

This document is a living specification and will be updated as decisions are made and implementation progresses. All stakeholders are encouraged to provide feedback via issue tracker or team meetings.
