# Map Feature — Architecture & Design Review

**Date:** 2026-02-13
**Updated:** 2026-02-13 (post Priority 2 & 4 fixes)
**Scope:** Map feature and all touched application layers
**Standard:** PySide6 production-grade, multi-developer codebase

---

## 8️⃣ Overall Assessment

| Criterion | Initial | Post-Decomp | Current | Notes |
|-----------|---------|-------------|---------|-------|
| **Architectural Quality** | **5 / 10** | **8 / 10** | **9 / 10** | Dialog coupling + service locator fixed |
| Encapsulation | 4 / 10 | 8 / 10 | 9 / 10 | All handler access via injected deps |
| Single Responsibility | 3 / 10 | 8 / 10 | 9 / 10 | Handler is pure logic, widget owns UI |
| Separation of Concerns | 5 / 10 | 7 / 10 | 9 / 10 | Dialogs in widget layer, no service locator |
| Consistency | 6 / 10 | 8 / 10 | 9 / 10 | DI pattern established for handlers |
| Scalability Risk | High | Low-Medium | Low | Handler is unit-testable without GUI |

### What Changed

#### Phase 1: MapGraphicsView Decomposition

The 2,757-line `MapGraphicsView` God class was decomposed into **5 focused sub-components**:

| Component | File | Lines | Responsibility |
|-----------|------|-------|---------------|
| `DrawingTool` | `drawing_tool.py` | 288 | Path/region drawing mode, vertex placement, rubber-band preview |
| `VertexEditor` | `vertex_editor.py` | 587 | Vertex handles, midpoints, snapping, geometry mutation |
| `MarkerManager` | `marker_manager.py` | 221 | Marker/feature CRUD, temporal state, factory routing |
| `TrajectoryRenderer` | `trajectory_renderer.py` | 317 | Trajectory path, keyframes, labels, calendar, animations |
| `InteractionHandler` | `interaction_handler.py` | 506 | Context menus, drag-drop, icon/color/style dialogs |
| `MapGraphicsView` | `map_graphics_view.py` | ~960 | Thin coordinator with Qt event dispatch + layer integration |

#### Phase 2: Dialog Extraction & Dependency Injection

| Before | After |
|--------|-------|
| `MapHandler` imported `QFileDialog`, `QInputDialog`, `QMessageBox` | Zero Qt dialog imports in `MapHandler` |
| `MapHandler.__init__(self, main_window: MainWindow)` | `MapHandler.__init__(self, map_widget, worker, db_path_accessor, nav_fn)` |
| `self.window.map_widget`, `self.window.worker`, etc. | `self._map_widget`, `self._worker` (injected) |
| 13 delegate methods in MainWindow | Removed entirely |
| Dialogs created in handler layer (untestable) | Dialogs in `MapWidget` (UI layer), results emitted via signals |

### Remaining Risks

1. `map_commands.py` is still a large file (1,334 lines) — could be split (Priority 5)
2. `MainWindow` is still large (now ~1,700 lines after removing delegates)

---

## 1️⃣ Encapsulation

### ✅ Fixed: Cross-module private attribute access

All critical violations have been resolved:

| Before (private) | After (public API) | Status |
|---|---|---|
| `view._finish_vertex_editing()` | `view.finish_editing()` | ✅ Fixed |
| `view._find_graphics_item(id)` | `view.find_item_by_id(id)` | ✅ Fixed |
| `panel._selected_node_id` | `panel.selected_node_id` | ✅ Fixed |
| `widget._maps_data` | `widget.maps_data` | ✅ Fixed |
| `self.window.map_widget` | `self._map_widget` (injected) | ✅ Fixed |
| `self.window._cached_entities` | `MapWidget.set_cached_items()` | ✅ Fixed |
| `self.window.command_requested` | `self.command_requested` (own Signal) | ✅ Fixed |

---

## 2️⃣ Single Responsibility Principle

### ✅ Fixed: MapGraphicsView decomposition + MapHandler cleanup

**MapGraphicsView:** 6 classes, each with 1-2 responsibilities.

**MapHandler now has exactly one responsibility:** Translate UI signals into
commands.  It no longer:
- Creates dialogs (moved to MapWidget)
- Accesses MainWindow internals (uses injected deps)
- Manages entity/event caches (owned by MapWidget)

| Component | Single Responsibility |
|-----------|----------------------|
| `DrawingTool` | Drawing mode lifecycle (start → add vertices → finish/cancel) |
| `VertexEditor` | Vertex manipulation (create/move/delete handles, snapping) |
| `MarkerManager` | Marker lifecycle (add/remove/update/query) |
| `TrajectoryRenderer` | Trajectory visualization (path, keyframes, labels) |
| `InteractionHandler` | User interaction (context menus, drag-drop, dialogs) |
| `MapGraphicsView` | Qt event dispatch + layer integration |
| `MapHandler` | Signal → Command translation |
| `MapWidget` | UI orchestration + dialog ownership |

---

## 3️⃣ Separation of Concerns

### ✅ Improved: Clear three-layer architecture

```
┌──────────────────────────────────────────────────────────┐
│                     MainWindow                            │
│  (Application bootstrap, NOT a service locator for maps)  │
│                                                           │
│  ┌─────────────┐  ┌───────────┐  ┌──────────────┐        │
│  │ MapHandler  │  │DataHandler│  │   Worker      │        │
│  │(pure logic) │  │ (signals) │  │  (DB thread)  │        │
│  │ DI: widget, │  └───────────┘  └──────────────┘        │
│  │   worker,   │                                          │
│  │   db_path,  │                                          │
│  │   nav_fn    │                                          │
│  └─────────────┘                                          │
│        ↕ signals                                          │
│  ┌────────────────────────────────────────────────────┐   │
│  │            MapWidget (UI layer)                     │   │
│  │  Owns dialogs, entity/event cache, layout          │   │
│  │  ┌────────────────────────┐  ┌──────────────┐      │   │
│  │  │   MapGraphicsView     │  │  LayerPanel   │      │   │
│  │  │   (Coordinator)       │  │  (tree view)  │      │   │
│  │  │  ┌─────────────────┐  │  └──────────────┘      │   │
│  │  │  │  DrawingTool    │  │                         │   │
│  │  │  │  VertexEditor   │  │                         │   │
│  │  │  │  MarkerManager  │  │                         │   │
│  │  │  │  TrajectoryRend.│  │                         │   │
│  │  │  │  InteractionHdl.│  │                         │   │
│  │  │  └─────────────────┘  │                         │   │
│  │  └────────────────────────┘                        │   │
│  └────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────┘
```

---

## 4️⃣ God Classes

### ✅ Fixed: MapGraphicsView

| Metric | Before | After |
|--------|--------|-------|
| Lines | 2,757 | ~960 (coordinator) |
| Methods | 82 | ~35 (mostly delegation) |
| Responsibilities | 13 | 2 (Qt events + layer integration) |

### Remaining Large Classes

- **`MainWindow`** — ~1,700 lines (reduced from 2,228 by removing 13 map delegates)
- **`map_commands.py`** — 1,334 lines, 14 commands. Could be split.

---

## 5️⃣ Anti-Patterns

### ✅ Fixed

1. **God class eliminated** — MapGraphicsView decomposed
2. **Encapsulation violations fixed** — Public APIs added
3. **Service Locator eliminated** — MapHandler uses DI
4. **Dialog creation in handler layer eliminated** — Dialogs in MapWidget

### Remaining Anti-Patterns

1. **Global state via Singleton** — `ThemeManager()` accessed directly
2. **String-based type checking** — `view.__class__.__name__` in `marker_item.py`
3. **Layer violation** — GUI imports from `src.app.constants` (shared constants)

---

## 6️⃣ Architectural Structure

### Current Pattern: **Component-Based MVC with DI**

- **Model:** `Map`, `MapFeature`, `MapLayerNode` (clean dataclasses ✅)
- **View:** Sub-components own rendering, MapWidget orchestrates + owns dialogs ✅
- **Controller:** `MapHandler` (pure logic, injected deps, no UI) ✅
- **Coordinator:** `MapGraphicsView` delegates to sub-components ✅
- **Wiring:** `ConnectionManager` (pure signal routing, no logic) ✅

---

## 7️⃣ Refactoring Suggestions (Updated Priorities)

### ✅ Priority 1: Expose Public APIs — DONE
### ✅ Priority 2: Extract Dialogs from MapHandler — DONE
### ✅ Priority 3: Decompose MapGraphicsView — DONE
### ✅ Priority 4: Inject Dependencies into MapHandler — DONE

### Priority 5: Split map_commands.py

**Problem:** 1,334 lines, 14 commands in one file.
**Fix:** Split into `map_crud_commands.py`, `marker_commands.py`, `layer_commands.py`.

---

## Summary of Findings

| Category | Initial | Current | Status |
|----------|:-------:|:-------:|--------|
| Encapsulation violations | 10 critical | 0 | ✅ All fixed |
| SRP violations | 3 classes (1 severe) | 0 severe | ✅ Fixed |
| God classes | 3 | 1 (MainWindow, reduced) | ✅ 2 fixed |
| Anti-patterns | 6 | 3 remaining | ✅ 3 fixed |
| Sub-components | 0 | 5 focused | ✅ New architecture |
| Service locator | MapHandler → MainWindow | DI constructor | ✅ Fixed |
| Dialog coupling | 10 dialog calls in handler | 0 in handler | ✅ Fixed |
| Test regression | — | 0 of 349 | ✅ Full backward compat |

### What's Working Well ✅

1. **Domain models** are clean dataclasses with proper serialization
2. **Command pattern** is consistently applied with undo/redo
3. **ConnectionManager** is excellent — pure wiring, no logic
4. **MapLayerPanel** is a clean thin-view widget
5. **Signal/slot architecture** used throughout
6. **MapRepository** has proper separation from domain objects
7. **MapLayerModel** correctly wraps domain data in Qt model adapter
8. **Sub-components** have clear single responsibilities
9. **Public APIs** replace all cross-module private access
10. **Coordinator pattern** keeps MapGraphicsView as thin dispatcher
11. **Dependency injection** makes MapHandler fully unit-testable
12. **Dialog ownership** properly in the widget layer
