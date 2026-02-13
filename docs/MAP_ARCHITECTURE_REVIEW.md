# Map Feature — Architecture & Design Review

**Date:** 2026-02-13
**Scope:** Map feature and all touched application layers
**Standard:** PySide6 production-grade, multi-developer codebase

---

## 8️⃣ Overall Assessment

| Criterion | Score |
|-----------|-------|
| **Architectural Quality** | **5 / 10** |
| Encapsulation | 4 / 10 |
| Single Responsibility | 3 / 10 |
| Separation of Concerns | 5 / 10 |
| Consistency | 6 / 10 |
| Scalability Risk | High |

**Biggest Risks:**
1. `MapGraphicsView` is a 2,757-line God class with 82 methods and 13+ responsibilities
2. `MapHandler` reaches through `self.window` to access private attributes across 3 layers of nesting
3. `MainWindow` is a 2,228-line orchestrator holding every subsystem reference, creating tight coupling for all handlers

**Highest Priority Refactor:** Extract `MapGraphicsView` into focused sub-components (see §4).

---

## 1️⃣ Encapsulation

### Violations Found

| Location | Code | Severity |
|----------|------|----------|
| `map_widget.py:551` | `self.view._finish_vertex_editing()` | 🔴 Critical |
| `map_widget.py:691` | `self.view._finish_vertex_editing()` | 🔴 Critical |
| `map_widget.py:956` | `self.view._find_graphics_item(node_id)` | 🔴 Critical |
| `map_widget.py:994` | `self.layer_panel._selected_node_id` | 🔴 Critical |
| `map_handler.py:77` | `self.window.map_widget._maps_data` | 🔴 Critical |
| `map_handler.py:89` | `self.window.map_widget.view.current_image_path` | 🟡 High |
| `map_handler.py:222` | `self.window._cached_entities` | 🔴 Critical |
| `map_handler.py:224` | `self.window._cached_events` | 🔴 Critical |
| `map_handler.py:614` | `self.window.map_widget.layer_panel._selected_node_id` | 🔴 Critical |
| `map_handler.py:655` | `view._find_graphics_item()` | 🔴 Critical |

**Impact:** Any internal refactoring of `MapGraphicsView`, `MapWidget`, or `MainWindow` will cascade into breakages across the handler layer. This creates a hidden coupling web that makes refactoring dangerous.

### Recommended Fix

Expose needed functionality through **public APIs**:

```python
# MapGraphicsView — add public methods
class MapGraphicsView(QGraphicsView):
    def finish_editing(self) -> None:
        """Public API: completes any active editing session."""
        if self.is_editing_vertices:
            self._finish_vertex_editing()

    def find_item_by_id(self, object_id: str) -> Optional[QGraphicsItem]:
        """Public API: finds a graphics item by object ID."""
        return self._find_graphics_item(object_id)

# MapLayerPanel — add public property
class MapLayerPanel(QWidget):
    @property
    def selected_node_id(self) -> Optional[str]:
        """Currently selected layer node ID."""
        return self._selected_node_id

# MapWidget — add public accessor
class MapWidget(QWidget):
    @property
    def maps_data(self) -> List[Map]:
        """The currently loaded map data list."""
        return self._maps_data
```

---

## 2️⃣ Single Responsibility Principle

### Violations

#### `MapGraphicsView` — 13 Responsibilities

| # | Responsibility | Methods |
|---|---------------|---------|
| 1 | Map rendering & zooming | `load_map`, `fit_to_view`, `wheelEvent`, `drawForeground` |
| 2 | Marker CRUD | `add_marker`, `update_marker_position`, `remove_marker`, `clear_markers` |
| 3 | Path/region drawing | `start_drawing`, `finish_drawing`, `cancel_drawing`, `_add_drawing_vertex`, `_update_drawing_preview` |
| 4 | Vertex editing | `_start_vertex_editing`, `_on_vertex_moved`, `_on_vertex_deleted`, `_finish_vertex_editing`, `_rebuild_vertex_handles`, `_rebuild_midpoint_handles` |
| 5 | Trajectory visualization | `show_trajectory`, `clear_trajectory`, `_update_trajectory_path`, `_create_trajectory_item` |
| 6 | Keyframe management | `_show_edit_keyframe_dialog`, `_on_keyframe_dropped`, `set_keyframe_pinned`, `update_keyframe_label` |
| 7 | Calibration mode | `start_calibration`, `cancel_calibration` |
| 8 | Snapping | `_show_snap_indicator`, `_hide_snap_indicator`, `_snap_to_nearby_vertex` |
| 9 | Layer model integration | `set_layer_model`, `_on_layer_visibility_changed`, `_on_layer_opacity_changed`, `_on_layer_order_changed` |
| 10 | Drag-and-drop | `dragEnterEvent`, `dragMoveEvent`, `dropEvent`, `_handle_drop_data` |
| 11 | Context menus | `contextMenuEvent`, `_show_marker_context_menu`, `_show_feature_context_menu`, `_show_map_background_context_menu` |
| 12 | Style dialogs | `_show_feature_style_dialog`, `_show_icon_picker`, `_show_color_picker` |
| 13 | Animation | `_pulse_item`, `_update_label_scales` |

**This is the most critical SRP violation in the codebase.** A single class should not own rendering, editing, dialog management, and data interaction simultaneously.

#### `MapHandler` — 5 Responsibilities

| # | Responsibility | Example |
|---|---------------|---------|
| 1 | Map lifecycle (create/delete/load) | `create_map`, `delete_map`, `load_maps` |
| 2 | Marker CRUD | `create_marker`, `delete_marker`, `on_marker_position_changed` |
| 3 | UI dialog management | `QFileDialog`, `QInputDialog`, `QMessageBox` calls |
| 4 | Command creation & emission | 11 different Command classes instantiated |
| 5 | Layer tree persistence | `on_layer_tree_changed`, `on_layer_opacity_changed`, `on_layer_renamed` |

#### `MainWindow` — 9+ Domains

Acts as a service locator for every subsystem in the application. Every handler accesses it to reach other subsystems, creating a coupling hub.

---

## 3️⃣ Separation of Concerns

### Current Architecture

```
┌─────────────────────────────────────────────────┐
│                  MainWindow                      │
│  (God Object / Service Locator)                  │
│                                                  │
│  ┌──────────┐  ┌───────────┐  ┌──────────────┐  │
│  │MapHandler│  │DataHandler│  │   Worker      │  │
│  │          │  │           │  │               │  │
│  │ Reaches  │  │           │  │               │  │
│  │ through  │──│           │  │               │  │
│  │ window.* │  │           │  │               │  │
│  └──────────┘  └───────────┘  └──────────────┘  │
│                                                  │
│  ┌──────────────────────────────────────┐        │
│  │            MapWidget                  │        │
│  │  ┌────────────────────┐  ┌────────┐  │        │
│  │  │  MapGraphicsView   │  │ Layer  │  │        │
│  │  │  (God Class)       │  │ Panel  │  │        │
│  │  │  2757 lines        │  │        │  │        │
│  │  └────────────────────┘  └────────┘  │        │
│  └──────────────────────────────────────┘        │
└─────────────────────────────────────────────────┘
```

### Issues

1. **MapHandler shows UI dialogs directly** (`QFileDialog`, `QInputDialog`, `QMessageBox`). This makes it untestable without a running GUI and violates the principle that handlers should be UI-agnostic coordinators.

2. **MapHandler accesses private caches on MainWindow** (`_cached_entities`, `_cached_events`) to build dialog item lists. This should be injected or accessed through a public API.

3. **MapWidget contains coordinate transformation logic** (`_on_mouse_coordinates_changed` at line 740 computes KM from normalized coords). This is domain logic that belongs in `MapCoordinateSystem` or a domain service.

4. **MapGraphicsView manages its own dialogs** (`_show_feature_style_dialog`, `_show_icon_picker`, `_show_color_picker`). Dialogs should be handled by the widget or handler layer, not the view.

### Recommended Layering

```
┌───────────────────────────────────────────┐
│  App Layer (Orchestration)                │
│  ┌──────────────┐  ┌──────────────────┐   │
│  │ MapHandler   │  │ ConnectionManager│   │
│  │ (no dialogs) │  │ (signal wiring)  │   │
│  └──────────────┘  └──────────────────┘   │
├───────────────────────────────────────────┤
│  GUI Layer (Presentation)                 │
│  ┌──────────────────────────────────────┐ │
│  │ MapWidget (thin orchestrator)        │ │
│  │  ┌─────────────┐ ┌───────────────┐  │ │
│  │  │ MapRenderer  │ │ LayerPanel    │  │ │
│  │  │ (zoom, pan)  │ │ (tree view)   │  │ │
│  │  ├─────────────┤ └───────────────┘  │ │
│  │  │DrawingTool  │                    │ │
│  │  │EditingTool  │                    │ │
│  │  │DragHandler  │                    │ │
│  │  └─────────────┘                    │ │
│  └──────────────────────────────────────┘ │
├───────────────────────────────────────────┤
│  Domain Layer (Business Logic)            │
│  ┌──────────────┐  ┌──────────────────┐   │
│  │ Map, Marker  │  │ MapLayerNode     │   │
│  │ (dataclasses)│  │ (tree structure) │   │
│  └──────────────┘  └──────────────────┘   │
├───────────────────────────────────────────┤
│  Service Layer (Persistence)              │
│  ┌──────────────┐  ┌──────────────────┐   │
│  │MapRepository │  │ Worker           │   │
│  └──────────────┘  └──────────────────┘   │
└───────────────────────────────────────────┘
```

---

## 4️⃣ God Classes

### `MapGraphicsView` — **2,757 lines, 82 methods, 26 state variables**

This is the most severe God class. It should be decomposed into:

| Extracted Class | Responsibility | Approx. Lines |
|----------------|---------------|---------------|
| `MapRenderer` | Zoom, pan, fit, foreground drawing, scale bar | ~300 |
| `DrawingTool` | Path/region drawing, preview, vertices | ~300 |
| `VertexEditor` | Handle creation, movement, deletion, midpoints | ~400 |
| `MarkerManager` | Add/remove/update markers, temporal state | ~200 |
| `TrajectoryRenderer` | Show/clear/update trajectory paths | ~250 |
| `InteractionHandler` | Mouse events, drag-drop, context menus | ~300 |
| `MapGraphicsView` | Composition root, delegates to above | ~200 |

### `MainWindow` — **2,228 lines, 119 methods**

Acts as a **Service Locator anti-pattern**. Every handler reaches through it to access services, widgets, and caches. This creates hidden dependencies:

```python
# Current (anti-pattern): handler reaches through window
self.window.map_widget._maps_data
self.window._cached_entities
self.window.map_widget.view._find_graphics_item()

# Better: inject only what's needed
class MapHandler:
    def __init__(self, map_widget: MapWidget, command_emitter: Signal,
                 entity_provider: Callable[[], List[Entity]]):
        ...
```

### `map_commands.py` — **1,334 lines, 14 commands**

While each command is individually well-structured, the file is too large. Consider splitting into:
- `map_crud_commands.py` (Create/Update/Delete Map)
- `marker_commands.py` (Create/Update/Delete Marker, Icon, Color)
- `layer_commands.py` (Visibility, Move, Save, Opacity, Rename)
- `keyframe_commands.py` (DeleteKeyframe)

---

## 5️⃣ Anti-Patterns

### 1. Service Locator via MainWindow

```python
# map_handler.py:77 — reaches through 2 layers of nesting
maps = self.window.map_widget._maps_data
```

**Why it's problematic:** Any change to `MapWidget._maps_data` (renaming, restructuring) breaks `MapHandler`. The handler doesn't declare its dependencies explicitly.

### 2. Business Logic in Event Handlers

```python
# map_widget.py:740 — coordinate math in a mouse-move handler
km_x = normalized_x * map_width_km
km_y = normalized_y * map_width_km / aspect
```

**Why it's problematic:** This calculation is untestable without a running widget. It should be in `MapCoordinateSystem`.

### 3. Dialog Creation in Handler Layer

```python
# map_handler.py:149 — UI dialog in a "handler"
file_name, _ = QFileDialog.getOpenFileName(
    self.window, "Select Map Image", "", "Images (*.png *.jpg ...)"
)
```

**Why it's problematic:** Makes `MapHandler` impossible to unit test. Handlers should receive user decisions via signals, not create dialogs.

### 4. Global State via Singleton

```python
# map_graphics_view.py:758
ThemeManager()  # Singleton access
```

**Why it's problematic:** Hidden dependency. Should be injected or accessed through a signal.

### 5. String-Based Type Checking

```python
# marker_item.py:375
if view.__class__.__name__ == "MapGraphicsView"
```

**Why it's problematic:** Fragile — breaks if the class is renamed. Use `isinstance()` with `TYPE_CHECKING` imports instead.

### 6. Layer Violation: GUI → App

```python
# map_widget.py imports from src.app.constants
# map_graphics_view.py imports from src.app.constants
from src.app.constants import MAP_LAYER_TYPE_GROUP, ...
```

**Why it's problematic:** GUI layer should not depend on the application layer. Constants should live in `src.core` or `src.gui`.

---

## 6️⃣ Architectural Structure

### Current Pattern: **Ad-hoc MVC with Service Locator**

The codebase *resembles* MVC but lacks consistent boundaries:
- **Model:** `Map`, `MapFeature`, `MapLayerNode` (clean dataclasses ✅)
- **View:** `MapGraphicsView`, `MapLayerPanel` (mixed with business logic ❌)
- **Controller:** `MapHandler` (mixed with dialog management ❌)
- **Service Locator:** `MainWindow` (everything accessed through it ❌)

### Consistency: **Inconsistent**

- `ConnectionManager` is excellent — pure wiring, no logic ✅
- `MapLayerPanel` is clean — thin UI that emits signals ✅
- `MapHandler` is a mixed bag — good signal routing, bad dialog coupling ❌
- `MapGraphicsView` is the worst offender — monolithic ❌

### Recommended Pattern: **Model-View-Presenter (MVP) with Dependency Injection**

For PySide6, MVP is more natural than MVVM:
- **Model:** Domain objects + `MapLayerModel` (Qt adapter)
- **View:** Widgets that only render and emit signals
- **Presenter:** Handlers that coordinate between views and commands, with injected dependencies instead of reaching through MainWindow

---

## 7️⃣ Concrete Refactoring Suggestions

### Priority 1: Expose Public APIs (Quick Win, High Impact)

**Problem:** 10+ private attribute accesses across module boundaries.
**Impact:** Any refactoring breaks callers silently.
**Fix:** Add public properties/methods to `MapGraphicsView`, `MapLayerPanel`, `MapWidget`.

```python
# MapGraphicsView — expose 2 methods
def finish_editing(self) -> None: ...
def find_item_by_id(self, object_id: str) -> Optional[QGraphicsItem]: ...

# MapLayerPanel — expose 1 property
@property
def selected_node_id(self) -> Optional[str]: ...

# MapWidget — expose 1 property
@property
def maps_data(self) -> List[Map]: ...
```

### Priority 2: Extract Dialogs from MapHandler

**Problem:** `MapHandler` creates `QFileDialog`, `QInputDialog`, `QMessageBox` directly.
**Impact:** Handler is untestable; UI and logic are coupled.
**Fix:** Move dialog creation to `MapWidget` or a dedicated `MapDialogService`, pass results as signal parameters.

```python
# Current (bad):
class MapHandler:
    def create_map(self):
        file_name, _ = QFileDialog.getOpenFileName(self.window, ...)

# Better:
class MapWidget:
    create_map_with_path = Signal(str, str)  # name, image_path

    def _on_create_map(self):
        file_name, _ = QFileDialog.getOpenFileName(self, ...)
        if file_name:
            name, ok = QInputDialog.getText(self, ...)
            if ok:
                self.create_map_with_path.emit(name, file_name)

class MapHandler:
    def on_create_map(self, name: str, image_path: str):
        # Pure logic — no dialogs
        command = CreateMapCommand(...)
        self.window.command_requested.emit(command)
```

### Priority 3: Decompose MapGraphicsView

**Problem:** 2,757 lines, 13 responsibilities.
**Impact:** Any change risks regressions; new developers can't navigate.
**Fix:** Extract into focused composition classes.

Phase 1 (lowest risk): Extract `DrawingTool` and `VertexEditor`:
```python
class DrawingTool:
    """Manages path/region drawing on a QGraphicsScene."""
    def __init__(self, scene: QGraphicsScene, snapping: SnappingManager):
        ...
    def start(self, mode: str) -> None: ...
    def add_vertex(self, pos: QPointF) -> None: ...
    def finish(self) -> Optional[Tuple[str, list]]: ...
    def cancel(self) -> None: ...

class VertexEditor:
    """Manages vertex editing for existing features."""
    def __init__(self, scene: QGraphicsScene, snapping: SnappingManager):
        ...
    def start(self, feature_item) -> None: ...
    def finish(self) -> Optional[Tuple[str, list]]: ...
```

### Priority 4: Inject Dependencies into MapHandler

**Problem:** `MapHandler` reaches through `self.window` for everything.
**Impact:** Hidden dependencies, impossible to test in isolation.
**Fix:** Inject specific interfaces rather than the entire MainWindow.

```python
class MapHandler:
    def __init__(
        self,
        map_widget: MapWidget,
        command_emitter: Signal,
        worker: Worker,
        db_path_provider: Callable[[], str],
        entity_provider: Callable[[], List[Entity]],
        event_provider: Callable[[], List[Event]],
    ):
        ...
```

### Priority 5: Move Constants to Core Layer

**Problem:** `src.app.constants` imported by GUI widgets (layer violation).
**Fix:** Move map-related constants to `src.core.constants` or `src.gui.constants`.

---

## Summary of Findings

| Category | Finding Count | Critical |
|----------|:------------:|:--------:|
| Encapsulation violations | 10 | 7 |
| SRP violations | 3 classes | 1 (MapGraphicsView) |
| Separation of concerns | 6 patterns | 3 |
| God classes | 3 | 2 (MapGraphicsView, MainWindow) |
| Anti-patterns | 6 | 3 |
| Layer violations | 2 files | — |

### What's Working Well ✅

1. **Domain models** (`Map`, `MapFeature`, `MapLayerNode`) are clean dataclasses with proper serialization
2. **Command pattern** is consistently applied with undo/redo support
3. **ConnectionManager** is excellently designed — pure wiring, no logic
4. **MapLayerPanel** is a clean thin-view widget
5. **Signal/slot architecture** is used throughout (correct Qt pattern)
6. **MapRepository** has proper separation from domain objects
7. **`MapLayerModel`** correctly wraps domain data in a Qt model adapter

### What Needs Work ❌

1. **MapGraphicsView** must be decomposed (highest priority)
2. **MapHandler** should not show dialogs
3. **MainWindow** should not be used as a service locator
4. **Private attribute access** must be replaced with public APIs
5. **Constants** should move to the appropriate layer
6. **`map_commands.py`** should be split into focused files
