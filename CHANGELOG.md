---
**Project:** ProjektKraken  
**Document:** Project Changelog  
**Last Updated:** 2026-01-04  
**Commit:** `cf2c11a`  
---

# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Fixed
- *(2026-01-04)* **Quality**: Applied PySide6 type annotations to entire `src/gui` module (49 files).
- *(2026-01-04)* **Quality**: Fixed ambiguous variable names and missing annotations in test files.
- *(2026-01-04)* **Bug**: Fixed AI search panel stylesheet selector (hover effects now work).
- *(2026-01-04)* **Accessibility**: Enabled keyboard navigation in AI search panel (arrow keys + Enter).

## [0.5.0]

### Added
- *(2026-01-01)* **CLI**: Added `--reset-settings` flag to `launcher.py` to clear persistent application settings.
- *(2026-01-02)* **CLI**: Added `--set-default-layout` flag to save current layout as default on exit.
- *(2026-01-01)* **Architecture**: Introduced `TimelineDataProvider` protocol for decoupling `TimelineView`.
- *(2026-01-01)* **Architecture**: Added `DataHandler` signals for all data events.
- *(2026-01-02)* **Architecture**: Added `reload_markers_for_current_map` signal for auto-reloading markers.
- *(2026-01-02)* **Testing**: Added integration tests for signal wiring, timeline provider, and map/longform wiring.
- *(2026-01-04)* **Feature**: Implemented "Return to Present" button in Timeline and Entity Editor.
- *(2026-01-04)* **Feature**: Implemented text-based, card-style timeline rendering (`TimelineDisplayWidget`).
- *(2026-01-04)* **Feature**: Added collapsible LLM sections to Event/Entity editors.
- *(2026-01-03)* **Feature**: Implemented "Timeline Logic" for Temporal Relations (Staging and dynamic overrides).
- *(2026-01-03)* **UX**: Added collapsible timeline section to Entity Inspector.
- *(2026-01-04)* **Docs**: Added `docs/TEMPORAL_RELATIONS.md` guide.
- *(2026-01-04)* **Docs**: Established formal release policy and added status checking tools.

### Fixed
- *(2026-01-01)* **Stability**: Resolved startup crash caused by corrupted `QSettings`.
- *(2026-01-02)* **Stability**: Fixed startup crash caused by manager classes not inheriting from `QObject`.
- *(2026-01-02)* **Stability**: Fixed "QThread: Destroyed while thread is still running" warning on exit.
- *(2026-01-02)* **Bug**: Fixed map markers not appearing immediately after creation.
- *(2026-01-04)* **Quality**: Achieved 100% docstring coverage for timeline module.
- *(2026-01-04)* **Quality**: Resolved all ruff linting errors in timeline components.
- *(2026-01-04)* **Bug**: Fixed `check_docstrings.py` crash on single file arguments.
- *(2026-01-04)* **Testing**: Fixed integration test isolation issues (QTimer leak in MainWindow).

### Changed
- *(2026-01-02)* **Refactor**: Split `main.py` into `main_window.py` and `entry.py`.
- *(2026-01-02)* **Refactor**: Extracted `MapHandler` from MainWindow (~226 lines).
- *(2026-01-02)* **Refactor**: Extracted `TimelineGroupingManager` from MainWindow (~60 lines).
- *(2026-01-02)* **Refactor**: Extracted `AISearchManager` from MainWindow (~133 lines).
- *(2026-01-02)* **Refactor**: Extracted `LongformManager` and `WorkerManager` from MainWindow (~159 lines).
- *(2026-01-02)* **Refactor**: All manager classes now inherit from `QObject` for proper thread affinity.
- *(2026-01-01)* **Refactor**: `TimelineView` no longer accepts `DatabaseService` directly.
- *(2026-01-01)* **Refactor**: `TimelineWidget.set_db_service` removed.
- *(2026-01-01)* **Refactor**: UI components now receive data via `DataHandler` signals.
- *(2026-01-02)* **Cleanup**: Removed 20+ unused imports from `main_window.py`.

### Deprecated
- *(2026-01-01)* Direct access to `mainwindow.data_handler` from child widgets (use signals).
- *(2026-01-01)* Direct access to `mainwindow.timeline` from other widgets (use signals/ConnectionManager).
