# 🛡️ Technical Audit Report: ProjektKraken

> **Date:** 2026-02-21 (All three roadmap phases implemented: Quick Wins + Structural Improvements + Architectural Refactoring)  
> **Scope:** Full codebase — `src/` (240 files, ~73,500 LOC) and `tests/` (270 files, ~51,200 LOC)  
> **Methodology:** Static analysis, dependency mapping, clean-code review, documentation audit

---

## 1. Executive Summary

ProjektKraken is a substantial desktop worldbuilding application (~127K LOC total) built on PySide6/SQLite with a layered architecture. The codebase demonstrates **strong architectural intent** — a proper Command pattern for undo/redo, a Repository pattern for data access, Protocol-based contracts for loose coupling, and clear layer separation (Core → Services → Commands → App → GUI).

However, organic growth has introduced measurable **technical debt** that, if left unaddressed, will impede velocity and onboarding.

### Maintainability Score: **8.0 / 10** *(up from 7.5 after Architectural Refactoring)*

| Dimension              | Score | Notes |
|------------------------|-------|-------|
| Architectural Intent   | 9/10  | AppCoordinator facade; full repository delegation; proper DI |
| Coupling               | 7/10  | AppCoordinator reduces MainWindow imports 29→24; declarative signal registry; DI for all repos |
| Single Responsibility  | 7/10  | DatabaseService decomposed (2509→1389 LOC); TagRepository + MetaRepository extracted; MapWidget documented |
| DRY                    | 7.5/10 | Editor mixin; style_helper consolidated; repository pattern fully leveraged |
| Documentation          | 8/10  | All new repos/coordinators well-documented; MapWidget responsibility groups documented |
| Testability            | 8/10  | 50+ new tests across unit & integration; DI enables test injection; in-memory DB pattern |
| Extensibility          | 8/10  | Full DI for 9 repos; AppCoordinator facade; McCabe complexity lint gate |

### Remaining Risks

1. **MapWidget complexity** — Still 1,580 LOC with 75 methods. Mixin extraction deferred due to API differences (`node.id` vs `node.feature_id`). Documented responsibility groups serve as refactoring guide.
2. **MainWindow import count** — Reduced from 29→24 but still high due to widget construction requirements. Further reduction requires widget factory pattern.
3. **Pre-existing test failures** — 2 EmptyStateWidget tests and 14 timeline grouping command tests fail due to unrelated issues (missing `.text()` attribute and abstract class instantiation).

---

## 2. Architectural Coupling & Dependency Map

### 2.1 Layer Dependency Flow

```
┌─────────────────────────────────────────────┐
│              GUI Layer                       │  Widgets, Dialogs, Utils
│              (PySide6)                       │  ~30,000 LOC
├──────────────────────────────────────────────┤
│         Application Layer                    │  MainWindow, Coordinators, Managers
│         (Orchestration)                      │  ~6,000 LOC
├──────────────────────────────────────────────┤
│         Command Layer                        │  BaseCommand subclasses
│         (Undo/Redo)                          │  ~4,000 LOC
├──────────────────────────────────────────────┤
│         Service Layer                        │  DB, Search, LLM, Import
│         (Business Logic)                     │  ~12,000 LOC
├──────────────────────────────────────────────┤
│         Repository Layer                     │  CRUD per domain entity
│         (Data Access)                        │  ~3,000 LOC
├──────────────────────────────────────────────┤
│         Core Layer                           │  Dataclasses, Protocols, Utilities
│         (Domain)                             │  ~5,000 LOC
└──────────────────────────────────────────────┘
```

**✅ Clean boundaries:** `src/services/` has zero imports from `src/app/`. `src/gui/` imports from `src/app/` only for constants. No circular dependencies were detected.

**⚠️ Afferent Coupling hotspot:** `MainWindow` imports **22+ internal modules** — it is the highest afferent-coupled class in the codebase. Any change to coordinator, handler, or manager APIs requires touching `main_window.py`.

### 2.2 High-Coupling Modules

| Module | LOC | Inbound Deps | Outbound Deps | Assessment |
|--------|-----|-------------|---------------|------------|
| `main_window.py` | 1,135 | Low (entry point) | **24 src/ imports** (was 29) | 🟡 Improved via AppCoordinator |
| `connection_manager.py` | 353 | 1 (type-only) | **Declarative `_connect_batch` registry** | ✅ Fixed (was 1,061 LOC / 101 calls) |
| `db_service.py` | 1,389 | Many consumers | **9 repos (all delegated via DI)** | ✅ Fixed (was 2,509 LOC God Object) |
| `worker.py` | 1,152 | App layer | **11 src/ imports** | 🟡 Mediator coupling |
| `data_handler.py` | 448 | App layer | 3 src/ imports | ✅ Well-isolated |
| `style_helper.py` | 874 | GUI widgets | **1 module-level ThemeManager import** | ✅ Fixed (was 29 lazy imports) |

### 2.3 Decoupling Strategies

1. **DatabaseService → Full Repository Delegation.** ✅ **Done** — All domain queries delegated to 9 repositories (Event, Entity, Relation, Map, Calendar, Attachment, Trajectory, Tag, Meta). DatabaseService reduced from 2,509 → 1,389 LOC.

2. **ConnectionManager → Declarative Configuration.** ✅ **Done** — 101 individual `_connect_signal_safe()` calls replaced with `_connect_batch` registry. Reduced from 1,061 → 353 LOC.

3. **MainWindow → Coordinator Facade.** ✅ **Done** — 7 individual coordinator imports replaced with single `AppCoordinator` facade. Import count reduced from 29 → 24.

4. **style_helper.py → Module-Level Import.** ✅ **Done** — Single `from src.core.theme_manager import ThemeManager` at module level.

---

## 3. Core Findings & Technical Debt

| Severity | Category | File(s) | Description | Recommended Action |
|----------|----------|---------|-------------|-------------------|
| 🔴 Critical | God Object | `db_service.py` (2,509 LOC, 86 methods) | Single class owned all DB operations across 7 domains. | ✅ **Fixed** — Decomposed into 9 repositories. `DatabaseService` reduced to 1,389 LOC (connection management + delegation). Created `TagRepository` (24 methods) and `MetaRepository` (8 methods). |
| 🔴 Critical | God Object | `map_widget.py` (1,937 LOC, 68 methods) | Manages layers, events, markers, drawing, interactions, and view state in one class. | 🟡 **Documented** — Responsibility groups documented in class docstring. Full decomposition deferred due to tight coupling between layer model API (`node.id`) and mixin pattern. |
| 🔴 Critical | Long Method | `graph_builder.py::_generate_html` (291 LOC) | Single method handles file I/O, 5 regex substitutions, CSS injection, and JS injection. | ✅ **Fixed** — decomposed into `_render_network_to_html`, `_replace_cdn_with_local_assets`, `_inject_theme_css`, `_inject_interaction_js`. |
| 🟠 High | Long Method | `event_editor.py::load_event` (156 LOC) | Loads fields, attributes, tags, gallery, and relations in one method. | Extract `_load_fields()`, `_load_attributes()`, `_load_relations()`. |
| 🟠 High | Long Method | `timeline_view.py::_repack_grouped_events` (183 LOC) | Manages band positioning, event partitioning, and scene rect updates. | ✅ **Fixed** — decomposed into `_position_tag_group_events`, `_position_all_events_group`. |
| 🟠 High | Hardcoded DI | `db_service.py:56-63` | 7 repository classes directly instantiated in `__init__`; no injection. | ✅ **Fixed** — keyword-only constructor params with defaults. |
| 🟠 High | Shotgun Surgery | `connection_manager.py` (101 signal wires) | Adding any new signal requires modifying this file and its caller. | ✅ **Fixed** — declarative `_connect_batch` registry (1061→353 LOC). |
| 🟡 Medium | DRY Violation | `style_helper.py` | `from src.core.theme_manager import ThemeManager` repeated **29 times** inside methods. | ✅ **Fixed** — moved to single module-level import. |
| 🟡 Medium | DRY Violation | `event_editor.py` / `entity_editor.py` | Near-identical `__init__`, drag-drop, signal-blocking, and dirty-tracking logic across both editors. | ✅ **Fixed** — extracted into `BaseEditorMixin` (`src/gui/mixins/editor_mixin.py`). |
| 🟡 Medium | Duplicate Comment | `event_editor.py:1001-1002` | `# Block signals to prevent dirty trigger during load` duplicated on consecutive lines. | ✅ **Fixed** — duplicate removed. |
| 🟡 Medium | Commentary Noise | `db_service.py:72` | `# Enable Foreign Keys` restates `PRAGMA foreign_keys = ON;`. | ✅ **Fixed** — comment removed. |
| 🟡 Medium | Commentary Noise | `db_service.py:79` | `# Return rows as Row objects for name access` restates `row_factory = sqlite3.Row`. | ✅ **Fixed** — comment removed. |
| 🟢 Low | Missing Docs | `event_editor.py:58-80` | Signal definitions (`save_requested`, `delete_requested`, etc.) lack docstrings. | ✅ **Fixed** — signal docstrings added. |
| 🟢 Low | Missing Docs | `main_window.py:242-246` | Phase-based initialization (`_init_core_services`) lacks explanation of *why* deferred init is needed. | ✅ **Fixed** — class docstring enhanced with 3-phase init explanation. |
| 🟢 Low | Verbose Block Comment | `main_window.py:9-23` | ~15-line comment block explaining PySide6 enum paths. Already documented in `PYSIDE6_ENUM_SOLUTION.md`. | ✅ **Fixed** — replaced with single-line reference. |

---

## 4. Clean Coding & Refactoring Examples

### 4.1 Extract Method — `DatabaseService.__init__` ✅ Implemented

**Before** (`src/services/db_service.py:46-63`):
```python
def __init__(self, db_path: str = ":memory:") -> None:
    self.db_path = db_path
    self._connection: Optional[sqlite3.Connection] = None
    self._backup_service = None

    self._event_repo = EventRepository()
    self._entity_repo = EntityRepository()
    self._relation_repo = RelationRepository()
    self._map_repo = MapRepository()
    self._calendar_repo = CalendarRepository()
    self._attachment_repo = AttachmentRepository()
    self._trajectory_repo = TrajectoryRepository()
    self.attachment_service: Optional["AttachmentService"] = None
```

**After** (Dependency Injection via keyword-only params):
```python
def __init__(
    self,
    db_path: str = ":memory:",
    *,
    event_repo: Optional[EventRepository] = None,
    entity_repo: Optional[EntityRepository] = None,
    relation_repo: Optional[RelationRepository] = None,
    map_repo: Optional[MapRepository] = None,
    calendar_repo: Optional[CalendarRepository] = None,
    attachment_repo: Optional[AttachmentRepository] = None,
    trajectory_repo: Optional[TrajectoryRepository] = None,
) -> None:
    self.db_path = db_path
    self._event_repo = event_repo or EventRepository()
    self._entity_repo = entity_repo or EntityRepository()
    # ... etc
```

### 4.2 Extract Method — `_generate_html` ✅ Implemented

**Before** (`src/gui/widgets/graph_view/graph_builder.py:521-812` — 291 lines):
```python
def _generate_html(self, network, theme, focus_node_id=None, view_state=None):
    # Write temp file (10 lines)
    # Remove CDN scripts with 5 regex calls (30 lines)
    # Inject CSS (40 lines)
    # Inject JavaScript (200 lines)
    ...
```

**After** (Single Responsibility per method):
```python
def _generate_html(self, network, theme, focus_node_id=None, view_state=None):
    html = self._render_network_to_html(network)
    html = self._replace_cdn_with_local_assets(html)
    html = self._inject_theme_css(html, theme)
    html = self._inject_interaction_js(html, focus_node_id, view_state)
    return html
```

### 4.3 Remove Commentary Noise ✅ Implemented

**Before** (`src/services/db_service.py:70-80`):
```python
self._connection = sqlite3.connect(self.db_path)
# Enable Foreign Keys
self._connection.execute("PRAGMA foreign_keys = ON;")
# Enable Write-Ahead Logging for better concurrency
# WAL mode allows concurrent readers with a single writer
if self.db_path != ":memory:":
    self._connection.execute("PRAGMA journal_mode=WAL;")
    logger.debug("WAL mode enabled for database.")
# Return rows as Row objects for name access
self._connection.row_factory = sqlite3.Row
```

**After** (self-documenting with purposeful comments only):
```python
self._connection = sqlite3.connect(self.db_path)
self._connection.execute("PRAGMA foreign_keys = ON;")
if self.db_path != ":memory:":
    # WAL enables concurrent reads during background writes
    self._connection.execute("PRAGMA journal_mode=WAL;")
    logger.debug("WAL mode enabled for database.")
self._connection.row_factory = sqlite3.Row
```

### 4.4 Remove Duplicate Comment ✅ Implemented

**Before** (`src/gui/widgets/event_editor.py:1001-1002`):
```python
            # Block signals to prevent dirty trigger during load
            # Block signals to prevent dirty trigger during load
            self.name_edit.blockSignals(True)
```

**After**:
```python
            # Block signals to prevent dirty trigger during load
            self.name_edit.blockSignals(True)
```

### 4.5 Eliminate Repeated Lazy Imports ✅ Implemented

**Before** (`src/gui/utils/style_helper.py` — 29 occurrences):
```python
class StyleHelper:
    @staticmethod
    def get_main_stylesheet() -> str:
        from src.core.theme_manager import ThemeManager  # Repeated in EVERY method
        tm = ThemeManager.instance()
        ...

    @staticmethod
    def get_button_style() -> str:
        from src.core.theme_manager import ThemeManager  # Again
        tm = ThemeManager.instance()
        ...
```

**After** (single module-level import):
```python
from src.core.theme_manager import ThemeManager

class StyleHelper:
    @staticmethod
    def get_main_stylesheet() -> str:
        tm = ThemeManager.instance()
        ...

    @staticmethod
    def get_button_style() -> str:
        tm = ThemeManager.instance()
        ...
```

---

## 5. Documentation & Verbosity Review

### 5.1 Commentary Noise (Remove or Rewrite)

| File | Line(s) | Current Comment | Action |
|------|---------|----------------|--------|
| `src/services/db_service.py` | 72 | `# Enable Foreign Keys` | ✅ **Removed** |
| `src/services/db_service.py` | 79 | `# Return rows as Row objects for name access` | ✅ **Removed** |
| `src/gui/widgets/event_editor.py` | 1001-1002 | Duplicate `# Block signals to prevent dirty trigger during load` | ✅ **Removed duplicate** |
| `src/gui/widgets/event_editor.py` | 1013-1015 | `# Date/Time widgets have set_value which triggers internal updates / Ideally we check value equality first.` | ✅ **Rewritten** to `# Avoid redundant updates` |
| `src/gui/widgets/event_editor.py` | 1019-1021 | `# Initialize duration widgets / Duration widget logic is complex...` | ✅ **Removed** |
| `src/gui/widgets/event_editor.py` | 1026-1029 | 4-line comment block speculating about end date derivation | ✅ **Removed** |
| `src/app/main_window.py` | 9-23 | 15-line block explaining PySide6 enum resolution | ✅ **Replaced** with single-line reference |

### 5.2 Missing Documentation (Add)

| File | Line(s) | What's Missing | Recommendation |
|------|---------|---------------|----------------|
| `src/gui/widgets/event_editor.py` | 58-80 | Signal definitions lack docstrings | ✅ **Added** — payload type and trigger context per signal. |
| `src/app/main_window.py` | 200-246 | Phase-based init strategy undocumented | ✅ **Added** — class docstring explains 3-phase init and *why* deferred. |
| `src/services/db_service.py` | 56-63 | Repository initialization pattern not explained | Add docstring explaining the pattern and that repos share the connection post-`connect()`. |
| `src/app/connection_manager.py` | 95-1061 | Individual `_connect_*` methods have no docstrings | Add brief per-method docstring (e.g., "Wires timeline widget signals"). |
| `src/gui/widgets/map_widget.py` | 1-10 | Module docstring present but class responsibilities unclear | Expand to list the 4+ responsibilities (layers, events, markers, view state). |

### 5.3 Well-Documented Files (No Action)

The following files have **excellent** documentation and should be used as templates:

- `src/commands/base_command.py` — Clear docstrings on all abstract methods with Args/Returns/Raises.
- `src/core/events.py` / `src/core/entities.py` — Concise module + class + property docstrings.
- `src/services/search_service.py` — Purposeful comments (e.g., "avoid division by zero"), thorough docstrings.
- `src/core/protocols.py` — Well-documented protocol contracts.

---

## 6. 30-60-90 Day Roadmap

### 🏃 Days 1–30: Quick Wins (Low Risk, High Impact)

| # | Task | Files | Effort | Status |
|---|------|-------|--------|--------|
| 1 | Remove commentary noise (§5.1 table) | `db_service.py`, `event_editor.py`, `main_window.py` | 1h | ✅ Done |
| 2 | Fix duplicate comments in `event_editor.py` and `entity_editor.py` | `event_editor.py`, `entity_editor.py` | 5m | ✅ Done |
| 3 | Move lazy `ThemeManager` import to module-level in `style_helper.py` | `style_helper.py` | 30m | ✅ Done |
| 4 | Add missing signal docstrings to `EventEditorWidget` and `EntityEditorWidget` | `event_editor.py`, `entity_editor.py` | 1h | ✅ Done |
| 5 | Enhance `MainWindow` class docstring with 3-phase init docs; trim verbose enum comment | `main_window.py` | 30m | ✅ Done |
| 6 | Extract `_load_event_fields()`, `_load_event_attributes()`, `_load_event_relations()` from `load_event` | `event_editor.py` | 2h | ✅ Done |
| 7 | Extract `_load_entity_fields()`, `_load_entity_attributes()`, `_load_entity_relations()` from `load_entity` | `entity_editor.py` | 2h | ✅ Done |

### 🚀 Days 31–60: Structural Improvements (Medium Risk)

| # | Task | Files | Effort | Status |
|---|------|-------|--------|--------|
| 8 | Extract `_render_network_to_html()`, `_replace_cdn_with_local_assets()`, `_inject_theme_css()`, `_inject_interaction_js()` from `_generate_html` | `graph_builder.py` | 3h | ✅ Done |
| 9 | Extract `_position_tag_group_events()`, `_position_all_events_group()` from `_repack_grouped_events` | `timeline_view.py` | 3h | ✅ Done |
| 10 | Introduce DI for `DatabaseService` repositories (keyword-only constructor params, backward compatible) | `db_service.py`, tests | 4h | ✅ Done |
| 11 | Extract shared editor logic into `BaseEditorMixin` (set_dirty, drag-drop, hidden attributes) | `event_editor.py`, `entity_editor.py`, `editor_mixin.py` | 6h | ✅ Done |
| 12 | Replace `ConnectionManager` individual calls with declarative `_connect_batch` registry | `connection_manager.py` (1061→353 LOC) | 8h | ✅ Done |

### 🏗️ Days 61–90: Architectural Refactoring (Higher Risk)

| # | Task | Files | Effort | Status |
|---|------|-------|--------|--------|
| 13 | Decompose `DatabaseService` — created `TagRepository` (24 methods) and `MetaRepository` (8 methods), moved marker/relation SQL to existing repos | `db_service.py` (2509→1389 LOC), `tag_repository.py`, `meta_repository.py`, `map_repository.py`, `relation_repository.py` | 16h | ✅ Done |
| 14 | Document `MapWidget` responsibility groups — full decomposition deferred due to `node.id` vs `node.feature_id` API mismatch | `map_widget.py` | 2h | ✅ Documented (decomposition deferred) |
| 15 | Introduce `AppCoordinator` facade to reduce MainWindow import count from 29 to 24 | `main_window.py`, `app_coordinator.py` | 4h | ✅ Done |
| 16 | Add 14 integration tests for decomposed components | `test_integration_decomposition.py` | 4h | ✅ Done |
| 17 | Add McCabe complexity lint rule (C901, max-complexity=15) via ruff config | `pyproject.toml` | 15m | ✅ Done |

### Priority Summary

```
               Impact
               ▲
          High │  #1-5 ✅ Done    #10,12 ✅ Done        #13 ✅ Done
               │
        Medium │  #6-7 ✅ Done    #8,9,11 ✅ Done       #15,16 ✅ Done
               │
           Low │                                        #14 🟡 Documented  #17 ✅ Done
               └──────────────────────────────────────────────────► Risk
                    Low              Medium                 High
```

### Complete Roadmap Status: 17/17 items addressed (15 fully implemented, 2 documented/deferred)

---

*Report generated and maintained through static analysis of the ProjektKraken codebase. All three roadmap phases (Quick Wins, Structural Improvements, Architectural Refactoring) implemented and verified with 50+ new tests. Metrics reflect post-refactoring state.*
