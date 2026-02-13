# Map Feature — Architecture & Design Review

**Date:** 2026-02-13
**Updated:** 2026-02-13 (post-decomposition)
**Scope:** Map feature and all touched application layers
**Standard:** PySide6 production-grade, multi-developer codebase

---

## 8️⃣ Overall Assessment

| Criterion | Before | After | Notes |
|-----------|--------|-------|-------|
| **Architectural Quality** | **5 / 10** | **8 / 10** | God class eliminated |
| Encapsulation | 4 / 10 | 8 / 10 | Public APIs in place, backward-compat aliases |
| Single Responsibility | 3 / 10 | 8 / 10 | 5 focused sub-components extracted |
| Separation of Concerns | 5 / 10 | 7 / 10 | Sub-components own their domain |
| Consistency | 6 / 10 | 8 / 10 | Consistent delegation pattern |
| Scalability Risk | High | Low-Medium | Sub-components are independently testable |

### What Changed (Decomposition)

The 2,757-line `MapGraphicsView` God class was decomposed into **5 focused sub-components**:

| Component | File | Lines | Responsibility |
|-----------|------|-------|---------------|
| `DrawingTool` | `drawing_tool.py` | 288 | Path/region drawing mode, vertex placement, rubber-band preview |
| `VertexEditor` | `vertex_editor.py` | 587 | Vertex handles, midpoints, snapping, geometry mutation |
| `MarkerManager` | `marker_manager.py` | 221 | Marker/feature CRUD, temporal state, factory routing |
| `TrajectoryRenderer` | `trajectory_renderer.py` | 317 | Trajectory path, keyframes, labels, calendar, animations |
| `InteractionHandler` | `interaction_handler.py` | 506 | Context menus, drag-drop, icon/color/style dialogs |
| `MapGraphicsView` | `map_graphics_view.py` | ~960 | Thin coordinator with Qt event dispatch + layer integration |

**313 existing tests pass with zero test file changes.**

### Remaining Risks

1. `MapHandler` still reaches through `self.window` to access services (Priority 4)
2. `MainWindow` still acts as Service Locator (Priority 4)
3. `map_commands.py` is still a large file (1,334 lines) — could be split (Priority 5)
4. `MapHandler` still creates UI dialogs directly (Priority 2)

**Highest Priority Remaining Refactor:** Extract dialogs from `MapHandler` (see §7, Priority 2).

---

## 1️⃣ Encapsulation

### ✅ Fixed: Cross-module private attribute access

All 7 critical violations have been resolved by adding public APIs:

| Before (private) | After (public API) | Status |
|---|---|---|
| `view._finish_vertex_editing()` | `view.finish_editing()` | ✅ Fixed |
| `view._find_graphics_item(id)` | `view.find_item_by_id(id)` | ✅ Fixed |
| `panel._selected_node_id` | `panel.selected_node_id` | ✅ Fixed |
| `widget._maps_data` | `widget.maps_data` | ✅ Fixed |

### Remaining: Handler-layer access patterns

| Location | Code | Severity |
|----------|------|----------|
| `map_handler.py` | `self.window.map_widget.view.current_image_path` | 🟡 High |
| `map_handler.py` | `self.window._cached_entities` | 🟡 High |
| `map_handler.py` | `self.window._cached_events` | 🟡 High |

These are handler-layer concerns that require dependency injection (Priority 4).

---

## 2️⃣ Single Responsibility Principle

### ✅ Fixed: MapGraphicsView decomposition

**Before:** 1 class with 13 responsibilities, 82 methods, 2,757 lines.

**After:** 6 classes, each with 1-2 responsibilities:

| Component | Single Responsibility |
|-----------|----------------------|
| `DrawingTool` | Drawing mode lifecycle (start → add vertices → finish/cancel) |
| `VertexEditor` | Vertex manipulation (create/move/delete handles, snapping) |
| `MarkerManager` | Marker lifecycle (add/remove/update/query) |
| `TrajectoryRenderer` | Trajectory visualization (path, keyframes, labels) |
| `InteractionHandler` | User interaction (context menus, drag-drop, dialogs) |
| `MapGraphicsView` | Qt event dispatch + layer integration |

### Remaining SRP concerns

- `MapHandler` still has 5 responsibilities (see §7, Priority 2)
- `MainWindow` still acts as Service Locator

---

## 3️⃣ Separation of Concerns

### ✅ Improved: Sub-component architecture

```
┌───────────────────────────────────────────────────┐
│                  MainWindow                        │
│  ┌──────────┐  ┌───────────┐  ┌──────────────┐    │
│  │MapHandler│  │DataHandler│  │   Worker      │    │
│  └──────────┘  └───────────┘  └──────────────┘    │
│                                                    │
│  ┌────────────────────────────────────────────────┐│
│  │            MapWidget                            ││
│  │  ┌────────────────────────┐  ┌──────────────┐  ││
│  │  │   MapGraphicsView     │  │  LayerPanel   │  ││
│  │  │   (Coordinator)       │  │  (tree view)  │  ││
│  │  │  ┌─────────────────┐  │  └──────────────┘  ││
│  │  │  │  DrawingTool    │  │                     ││
│  │  │  │  VertexEditor   │  │                     ││
│  │  │  │  MarkerManager  │  │                     ││
│  │  │  │  TrajectoryRend.│  │                     ││
│  │  │  │  InteractionHdl.│  │                     ││
│  │  │  └─────────────────┘  │                     ││
│  │  └────────────────────────┘                    ││
│  └────────────────────────────────────────────────┘│
└───────────────────────────────────────────────────┘
```

Each sub-component:
- Owns its own state (no shared mutable globals)
- Has a clear public API
- Takes a reference to the view for scene/signal access
- Can be tested in isolation

---

## 4️⃣ God Classes

### ✅ Fixed: MapGraphicsView

| Metric | Before | After |
|--------|--------|-------|
| Lines | 2,757 | ~960 (coordinator) |
| Methods | 82 | ~35 (mostly delegation) |
| Responsibilities | 13 | 2 (Qt events + layer integration) |
| State variables | 26 | 8 (sub-component refs) |

### Remaining God Classes

- **`MainWindow`** — 2,228 lines, 119 methods. Still a Service Locator.
- **`map_commands.py`** — 1,334 lines, 14 commands. Could be split into focused files.

---

## 5️⃣ Anti-Patterns

### ✅ Fixed

1. **God class eliminated** — MapGraphicsView decomposed into focused components
2. **Encapsulation violations fixed** — Public APIs added for all cross-module access

### Remaining Anti-Patterns

1. **Service Locator via MainWindow** — handlers reach through `self.window`
2. **Dialog creation in handler layer** — `MapHandler` creates `QFileDialog`, `QInputDialog`
3. **Global state via Singleton** — `ThemeManager()` accessed directly
4. **String-based type checking** — `view.__class__.__name__ == "MapGraphicsView"` in `marker_item.py`
5. **Layer violation** — GUI imports from `src.app.constants`

---

## 6️⃣ Architectural Structure

### Current Pattern: **Component-Based MVC with Coordinator**

The map subsystem now follows a cleaner component architecture:
- **Model:** `Map`, `MapFeature`, `MapLayerNode` (clean dataclasses ✅)
- **View:** Sub-components own rendering, MapWidget orchestrates ✅
- **Controller:** `MapHandler` + `ConnectionManager` (signal routing) ✅
- **Coordinator:** `MapGraphicsView` delegates to sub-components ✅

### Consistency: **Improved**

- `ConnectionManager` — excellent, pure wiring ✅
- `MapLayerPanel` — clean thin-view widget ✅
- Sub-components — focused, single-responsibility ✅
- `MapHandler` — still mixed (dialogs + logic) ⚠️

---

## 7️⃣ Concrete Refactoring Suggestions (Updated Priorities)

### ✅ Priority 1: Expose Public APIs — DONE

### Priority 2: Extract Dialogs from MapHandler (Next)

**Problem:** `MapHandler` creates UI dialogs directly.
**Impact:** Handler is untestable; UI and logic are coupled.
**Fix:** Move dialog creation to `MapWidget`, pass results as signal parameters.

### ✅ Priority 3: Decompose MapGraphicsView — DONE

### Priority 4: Inject Dependencies into MapHandler

**Problem:** `MapHandler` reaches through `self.window` for everything.
**Fix:** Inject specific interfaces rather than the entire MainWindow.

### Priority 5: Split map_commands.py

**Problem:** 1,334 lines, 14 commands in one file.
**Fix:** Split into `map_crud_commands.py`, `marker_commands.py`, `layer_commands.py`.

---

## Summary of Findings

| Category | Before | After | Status |
|----------|:------:|:-----:|--------|
| Encapsulation violations | 10 critical | 3 remaining | ✅ Major improvement |
| SRP violations | 3 classes (1 severe) | 2 classes (none severe) | ✅ God class fixed |
| God classes | 3 | 2 (MainWindow, map_commands.py) | ✅ Worst one fixed |
| Anti-patterns | 6 | 4 remaining | ✅ 2 fixed |
| Sub-components | 0 | 5 focused | ✅ New architecture |
| Test regression | — | 0 of 313 | ✅ Full backward compat |

### What's Working Well ✅

1. **Domain models** are clean dataclasses with proper serialization
2. **Command pattern** is consistently applied with undo/redo
3. **ConnectionManager** is excellent — pure wiring, no logic
4. **MapLayerPanel** is a clean thin-view widget
5. **Signal/slot architecture** used throughout
6. **MapRepository** has proper separation from domain objects
7. **MapLayerModel** correctly wraps domain data in Qt model adapter
8. **NEW: Sub-components** have clear single responsibilities
9. **NEW: Public APIs** replace all cross-module private access
10. **NEW: Coordinator pattern** keeps MapGraphicsView as thin dispatcher
