# 🛡️ Technical Audit Report: ProjektKraken

> **Date:** 2026-02-21  
> **Scope:** Full codebase — `src/` (234 files, ~77,400 LOC) and `tests/` (265 files, ~49,800 LOC)  
> **Methodology:** Static analysis, dependency mapping, clean-code review, documentation audit

---

## 1. Executive Summary

ProjektKraken is a substantial desktop worldbuilding application (~127K LOC total) built on PySide6/SQLite with a layered architecture. The codebase demonstrates **strong architectural intent** — a proper Command pattern for undo/redo, a Repository pattern for data access, Protocol-based contracts for loose coupling, and clear layer separation (Core → Services → Commands → App → GUI).

However, organic growth has introduced measurable **technical debt** that, if left unaddressed, will impede velocity and onboarding.

### Maintainability Score: **6.5 / 10**

| Dimension              | Score | Notes |
|------------------------|-------|-------|
| Architectural Intent   | 8/10  | Well-defined layers, Command + Repository patterns |
| Coupling               | 5/10  | MainWindow imports 22+ modules; ConnectionManager has 101 `_connect_signal_safe` calls |
| Single Responsibility  | 5/10  | Multiple God Objects (1,500–2,500 LOC files); methods up to 290 lines |
| DRY                    | 6/10  | `style_helper.py` has 29 identical lazy imports; editor duplication |
| Documentation          | 7/10  | Core/Services well-documented; GUI layer has noise and gaps |
| Testability            | 7/10  | Good test coverage infrastructure; in-memory DB pattern |
| Extensibility          | 6/10  | LLM providers use Strategy pattern; but DI is manual in Services layer |

### Critical Risks

1. **God Objects** — `DatabaseService` (2,509 LOC / 86 methods), `map_widget.py` (1,937 LOC), `timeline_view.py` (1,809 LOC) are maintenance bottlenecks.
2. **Hardcoded Dependencies** — `DatabaseService` directly instantiates 7 repository classes with no injection point.
3. **Monolithic Signal Wiring** — `ConnectionManager` has 101 individual signal-safe connections, making it fragile to UI changes.

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
| `main_window.py` | 1,143 | Low (entry point) | **22+ src/ imports** | 🔴 Hub bottleneck |
| `connection_manager.py` | 1,061 | 1 (type-only) | **101 signal connections** | 🟡 Fragile wiring |
| `db_service.py` | 2,509 | Many consumers | **7 repo + 4 entity imports** | 🔴 God Object |
| `worker.py` | 1,152 | App layer | **11 src/ imports** | 🟡 Mediator coupling |
| `data_handler.py` | 448 | App layer | 3 src/ imports | ✅ Well-isolated |
| `style_helper.py` | 874 | GUI widgets | **29 lazy ThemeManager imports** | 🟡 DRY violation |

### 2.3 Decoupling Strategies

1. **DatabaseService → Dependency Injection.** Accept repositories via constructor parameters instead of hardcoding instantiation. This enables mock repositories in tests without monkey-patching.

2. **ConnectionManager → Declarative Configuration.** Replace 101 individual `_connect_signal_safe()` calls with a data-driven connection registry (list of tuples/dicts). This reduces Shotgun Surgery when adding new signals.

3. **MainWindow → Coordinator Facade.** Group the 8 coordinators behind a single `AppCoordinator` facade that MainWindow references, reducing its import count from 22+ to ~5.

4. **style_helper.py → Module-Level Import.** Move the single `from src.core.theme_manager import ThemeManager` to the top of the file instead of repeating it 29 times inside individual methods.

---

## 3. Core Findings & Technical Debt

| Severity | Category | File(s) | Description | Recommended Action |
|----------|----------|---------|-------------|-------------------|
| 🔴 Critical | God Object | `db_service.py` (2,509 LOC, 86 methods) | Single class owns all DB operations across 7 domains — events, entities, relations, maps, calendars, attachments, trajectories. | Delegate domain-specific queries entirely to repositories; reduce `DatabaseService` to connection management + transaction coordination. |
| 🔴 Critical | God Object | `map_widget.py` (1,937 LOC, 68 methods) | Manages layers, events, markers, drawing, interactions, and view state in one class. | Extract `MapLayerController`, `MapEventController`, and `MapViewState` into separate classes. |
| 🔴 Critical | Long Method | `graph_builder.py::_generate_html` (291 LOC) | Single method handles file I/O, 5 regex substitutions, CSS injection, and JS injection. | Extract `_replace_cdn_assets()`, `_inject_css()`, `_inject_javascript()`. |
| 🟠 High | Long Method | `event_editor.py::load_event` (156 LOC) | Loads fields, attributes, tags, gallery, and relations in one method. | Extract `_load_fields()`, `_load_attributes()`, `_load_relations()`. |
| 🟠 High | Long Method | `timeline_view.py::_repack_grouped_events` (183 LOC) | Manages band positioning, event partitioning, and scene rect updates. | Extract `_position_bands()`, `_position_group_events()`. |
| 🟠 High | Hardcoded DI | `db_service.py:56-63` | 7 repository classes directly instantiated in `__init__`; no injection. | Accept repositories via constructor or factory method. |
| 🟠 High | Shotgun Surgery | `connection_manager.py` (101 signal wires) | Adding any new signal requires modifying this file and its caller. | Use declarative signal registration. |
| 🟡 Medium | DRY Violation | `style_helper.py` | `from src.core.theme_manager import ThemeManager` repeated **29 times** inside methods. | Move to module-level import. |
| 🟡 Medium | DRY Violation | `event_editor.py` / `entity_editor.py` | Near-identical `__init__`, drag-drop, signal-blocking, and dirty-tracking logic across both editors. | Extract shared behavior into `BaseEditorWidget` mixin or abstract base class. |
| 🟡 Medium | Duplicate Comment | `event_editor.py:1001-1002` | `# Block signals to prevent dirty trigger during load` duplicated on consecutive lines. | Remove duplicate line. |
| 🟡 Medium | Commentary Noise | `db_service.py:72` | `# Enable Foreign Keys` restates `PRAGMA foreign_keys = ON;`. | Remove comment — the code is self-documenting. |
| 🟡 Medium | Commentary Noise | `db_service.py:79` | `# Return rows as Row objects for name access` restates `row_factory = sqlite3.Row`. | **Rewrite** to explain the benefit (e.g., "Enable dict-like column access"). |
| 🟢 Low | Missing Docs | `event_editor.py:58-80` | Signal definitions (`save_requested`, `delete_requested`, etc.) lack docstrings. | Add brief docstring to each signal explaining payload type and emission trigger. |
| 🟢 Low | Missing Docs | `main_window.py:242-246` | Phase-based initialization (`_init_core_services`) lacks explanation of *why* deferred init is needed. | Add docstring explaining Qt event loop timing requirements. |
| 🟢 Low | Verbose Block Comment | `main_window.py:9-23` | ~15-line comment block explaining PySide6 enum paths. Already documented in `PYSIDE6_ENUM_SOLUTION.md`. | Replace with single-line reference to the design doc. |

---

## 4. Clean Coding & Refactoring Examples

### 4.1 Extract Method — `DatabaseService.__init__`

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

**After** (Dependency Injection + Factory):
```python
def __init__(
    self,
    db_path: str = ":memory:",
    repositories: dict[str, "BaseRepository"] | None = None,
) -> None:
    self.db_path = db_path
    self._connection: Optional[sqlite3.Connection] = None
    self._backup_service = None
    self.attachment_service: Optional["AttachmentService"] = None
    self._repos = repositories or self._create_default_repositories()

@staticmethod
def _create_default_repositories() -> dict[str, "BaseRepository"]:
    return {
        "event": EventRepository(),
        "entity": EntityRepository(),
        "relation": RelationRepository(),
        "map": MapRepository(),
        "calendar": CalendarRepository(),
        "attachment": AttachmentRepository(),
        "trajectory": TrajectoryRepository(),
    }
```

### 4.2 Extract Method — `_generate_html`

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
    raw_html = self._render_network_to_html(network)
    html = self._replace_cdn_with_local_assets(raw_html)
    html = self._inject_theme_css(html, theme)
    html = self._inject_interaction_js(html, theme, focus_node_id, view_state)
    return html
```

### 4.3 Remove Commentary Noise

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

### 4.4 Remove Duplicate Comment

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

### 4.5 Eliminate Repeated Lazy Imports

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
| `src/services/db_service.py` | 72 | `# Enable Foreign Keys` | **Remove** — `PRAGMA foreign_keys = ON` is self-evident. |
| `src/services/db_service.py` | 79 | `# Return rows as Row objects for name access` | **Rewrite** — explain the benefit: "Enable dict-like column access instead of positional indexing". |
| `src/gui/widgets/event_editor.py` | 1001-1002 | Duplicate `# Block signals to prevent dirty trigger during load` | **Remove duplicate** — line appears twice consecutively. |
| `src/gui/widgets/event_editor.py` | 1013-1015 | `# Date/Time widgets have set_value which triggers internal updates / Ideally we check value equality first.` | **Rewrite** — convert to a brief inline `# Avoid redundant updates`. |
| `src/gui/widgets/event_editor.py` | 1019-1021 | `# Initialize duration widgets / Duration widget logic is complex...` | **Remove** — the code already shows `set_start_date` + conditional `set_value`. |
| `src/gui/widgets/event_editor.py` | 1026-1029 | 4-line comment block speculating about end date derivation | **Remove** — the if-guard on line 1031 is self-documenting. |
| `src/app/main_window.py` | 9-23 | 15-line block explaining PySide6 enum resolution | **Move** to `PYSIDE6_ENUM_SOLUTION.md` and replace with a 1-line reference. |

### 5.2 Missing Documentation (Add)

| File | Line(s) | What's Missing | Recommendation |
|------|---------|---------------|----------------|
| `src/gui/widgets/event_editor.py` | 58-80 | Signal definitions lack docstrings | Add payload type and trigger context per signal. |
| `src/app/main_window.py` | 200-246 | Phase-based init strategy undocumented | Add class-level docstring explaining 3-phase init and *why* deferred. |
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

| # | Task | Files | Effort | Impact |
|---|------|-------|--------|--------|
| 1 | Remove commentary noise (§5.1 table) | `db_service.py`, `event_editor.py`, `main_window.py` | 1h | Cleaner codebase |
| 2 | Fix duplicate comment on `event_editor.py:1001-1002` | `event_editor.py` | 5m | Bug-proofing |
| 3 | Move lazy `ThemeManager` import to module-level in `style_helper.py` | `style_helper.py` | 30m | DRY; 29 duplicate lines removed |
| 4 | Add missing signal docstrings to `EventEditorWidget` | `event_editor.py` | 1h | Onboarding clarity |
| 5 | Add phase-init docstring to `MainWindow.__init__` | `main_window.py` | 30m | Architecture docs |
| 6 | Extract `_load_fields()`, `_load_attributes()`, `_load_relations()` from `event_editor.py::load_event` | `event_editor.py` | 2h | SRP; testability |
| 7 | Extract `_load_fields()`, `_load_attributes()`, `_load_relations()` from `entity_editor.py::load_entity` | `entity_editor.py` | 2h | Consistency with #6 |

### 🚀 Days 31–60: Structural Improvements (Medium Risk)

| # | Task | Files | Effort | Impact |
|---|------|-------|--------|--------|
| 8 | Extract `_replace_cdn_assets()`, `_inject_css()`, `_inject_javascript()` from `graph_builder.py::_generate_html` | `graph_builder.py` | 3h | SRP; testability |
| 9 | Extract `_position_bands()`, `_position_group_events()` from `timeline_view.py::_repack_grouped_events` | `timeline_view.py` | 3h | SRP; testability |
| 10 | Introduce DI for `DatabaseService` repositories (accept via constructor, default to current behavior) | `db_service.py`, tests | 4h | Testability; decoupling |
| 11 | Extract shared editor logic into `BaseEditorMixin` (signal blocking, dirty tracking, drag-drop) | `event_editor.py`, `entity_editor.py`, new mixin | 6h | DRY; maintainability |
| 12 | Replace `ConnectionManager` individual calls with declarative signal registry | `connection_manager.py` | 8h | Reduced Shotgun Surgery |

### 🏗️ Days 61–90: Architectural Refactoring (Higher Risk)

| # | Task | Files | Effort | Impact |
|---|------|-------|--------|--------|
| 13 | Decompose `DatabaseService` — move domain queries entirely into repositories, keep only connection/transaction management | `db_service.py`, `*_repository.py` | 16h | God Object elimination |
| 14 | Decompose `MapWidget` into `MapLayerController`, `MapEventController`, `MapViewState` | `map_widget.py`, new files | 12h | SRP; testability |
| 15 | Introduce `AppCoordinator` facade to reduce MainWindow import count from 22+ to ~5 | `main_window.py`, new coordinator | 8h | Reduced coupling |
| 16 | Add integration tests for decomposed components | tests/ | 8h | Safety net for refactoring |
| 17 | Establish file-size lint rule (warn >500 LOC, error >1,000 LOC) via ruff custom config | `pyproject.toml` | 1h | Prevent future God Objects |

### Priority Summary

```
               Impact
               ▲
          High │  #1-5 (Quick)   #10,12 (Structural)  #13,14 (Architectural)
               │
        Medium │  #6-7 (Quick)   #8,9,11 (Structural) #15,16 (Architectural)
               │
           Low │                                       #17 (Preventive)
               └──────────────────────────────────────────────────► Risk
                    Low              Medium                 High
```

---

*Report generated by static analysis of the ProjektKraken codebase (commit HEAD on `copilot/conduct-technical-debt-assessment`). Metrics are approximate and based on line-counting heuristics.*
