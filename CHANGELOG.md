---
**Project:** ProjektKraken  
**Document:** Project Changelog  
**Last Updated:** 2026-01-21
**Commit:** `0.9.0`
---

# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [0.9.0]

### Added
- *(2026-01-21)* **UI**: Implemented multi-selection with checkboxes in `UnifiedListWidget`.
  - Enabled ExtendedSelection mode for Ctrl+Click and Shift+Click support.
  - Checkboxes sync bidirectionally with selection state.
  - Added `items_selected` signal emitting list of `(type, id)` tuples.
  - Confirmation dialog now adapts for bulk deletion (e.g., "Delete 5 items?").
- *(2026-01-21)* **UI**: Added compact date formatting (dd.mm.yyyy - hh:mm) and sorting options to `UnifiedListWidget`.
  - Added `set_calendar_converter()` method for project-aware date display.
  - Entities sort to end when using "Lore Date" sorting (since they have no date).
- *(2026-01-20)* **Core**: Integrated fully functional `DateParser` into `src.core` (migrated from standalone module).
  - Supports natural language dates (e.g., "1st of January"), ISO formats, and relative terms.
  - Implemented `calculate_timestamp` for precise float conversions using the active `CalendarConfig`.
  - Added support for 12-hour AM/PM time parsing (e.g., "12:30 PM") and natural language backtracking.
- *(2026-01-20)* **Import**: Implemented automatic fallback to default Gregorian calendar if no active calendar config exists in DB.
- *(2026-01-20)* **Import**: Added Import Configuration UI with Source Name, Import Mode (Update, Overwrite, Skip), and Dry Run options.
- *(2026-01-20)* **Import**: Implemented robust deduplication logic using `external_id` and `source_name` metadata to prevent ambiguity.

### Fixed
- *(2026-01-21)* **UI**: Fixed stale/ghost selections persisting in `UnifiedListWidget` when items are filtered out or list is repopulated.
- *(2026-01-20)* **Import**: Prevented duplicate relations from being created on JSON re-import by checking for existing relations before creation.
- *(2026-01-20)* **Import**: Resolved "Ambiguous Entity" errors by ensuring import logic checks source metadata before name matching.

### Changed
- *(2026-01-20)* **Cleanup**: Removed temporary debug scripts (`debug_duplicates.py`, `fix_duplicates.py`).
- *(2026-01-20)* **Cleanup**: Removed legacy `src/date_parser_module` in favor of integrated `src.core.date_parser`.

### Refactor
- *(2026-01-20)* **Linting**: Fixed 31+ Ruff linting errors (type hints, unused variables) across 10 files.
- *(2026-01-20)* **Import**: Implemented Two-Pass Import Strategy (Creation -> Linking) to resolve cyclic dependencies and forward references in JSON imports.

### Documentation
- *(2026-01-20)* **Import**: Updated `docs/imports.md` with explicit instructions for LLMs to include time in date strings.

### Testing
- *(2026-01-21)* **UI**: Added `test_unified_list_features.py` with 14 tests covering multi-selection, sorting, and date formatting.
- *(2026-01-20)* **Import**: Added `test_import_forward_refs.py` and `test_import_feedback.py` covering cyclic deps and parsing warnings.

## [0.8.3]

### Added
- *(2026-01-19)* **Import**: Implemented comprehensive JSON import system with GUI and CLI support.
  - `ImportService` for parsing and persisting entities, events, and relations with transaction support.
  - `ImportPreviewDialog` for reviewing import data before committing.
  - "Import Item..." menu action in File menu.
  - CLI import command: `python -m src.app.main import --file <path>`.
  - Comprehensive documentation with JSON schemas (`docs/imports.md`).
  - Unit and integration tests for import functionality.

### Architecture
- *(2026-01-19)* **Import**: Refactored import to run entirely on worker thread.
  - Eliminates multi-connection WAL isolation issues.
  - Single DB connection architecture (worker's db_service).
  - JSON serialization for thread-safe cross-thread data transfer.
  - Auto-refresh events/entities after successful import.
- *(2026-01-19)* **Database**: Added `ensure_fresh_view()` method with WAL checkpoint for visibility guarantees.

### Performance
- *(2026-01-19)* **Timeline**: Optimized `CalendarConverter` with year caching for >50x speedup on high-year date conversions (from >5ms to <0.1ms).
- *(2026-01-19)* **Timeline**: Added performance logging to `drawForeground`, `repack_events`, `fit_all`, and `wheelEvent` for diagnostic monitoring.

### Fixed
- *(2026-01-19)* **AI Search**: Fixed entity/event selection from search results by correcting signal emission in click handlers and replacing non-existent method call with proper `UnifiedListWidget.select_item()` access.
- *(2026-01-19)* **Timeline**: Fixed Fit View to include Playhead and Current Time in the visible range.
- *(2026-01-19)* **Timeline**: Fixed panning clipping by updating Scene Rect calculation to include Playhead/Current Time positions.
- *(2026-01-19)* **Timeline**: Restored large Scene Rect buffer (50M px) for smooth infinite-feeling panning after performance bottleneck was resolved.

### Testing
- *(2026-01-19)* **Timeline**: Added `test_timeline_fit.py` with comprehensive tests for Fit View logic across different scenarios.
- *(2026-01-19)* **Import**: Added `test_import_service.py` and `test_db_isolation.py` for import validation.

## [0.8.2]

### Refactor
- *(2026-01-19)* **Coordinators**: Major architectural refactor extracting logic from `MainWindow` into dedicated coordinators: `NavigationCoordinator`, `TimeCoordinator`, and `FastInjectCoordinator`.
  - Reduced `MainWindow` size by ~1000 lines, improving maintainability.
  - Enforced public API surface (properties/methods) for better encapsulation and testability.

## [0.8.1]

### Stability
- *(2026-01-18)* **Review**: Completed extended code review of 162 files, covering Service, App, and Repository layers.
- *(2026-01-18)* **Exceptions**: Resolved 34 bare exception handlers across critical service and GUI modules to improve error visibility.
- *(2026-01-18)* **Signals**: Fixed duplicate signal definitions in `EntityEditorWidget` that could cause connection ambiguity.

### Testing
- *(2026-01-18)* **Coverage**: Increased overall test coverage from 61.2% to 70.5% (+9.3% improvement).
  - Added 9 new test files covering Core, Services, and App modules.
  - Achieved 94.7% coverage for core business logic.
- *(2026-01-18)* **Bug**: Fixed `test_shutdown.py` to properly mock `QSettings` during application termination.

### Refactor
- *(2026-01-18)* **Logging**: Replaced direct `print()` statements in `entry.py` with standard library `logging`.

### Architecture
- *(2026-01-18)* **Audit**: Validated threading (DatabaseWorker), Command patterns, and Repository abstraction layers.

## [0.8.0]

### Added
- *(2026-01-18)* **Fast Inject**: Implemented comprehensive "Fast Inject" system for rapid entity/event creation with template support.
  - Hybrid UI with dynamic sub-rows for mixed-content variables and real-time preview.
  - Core command system for undo/redo support of bulk injections.
  - Support for custom template injection and variable resolution.
- *(2026-01-18)* **Calendar**: Implemented Gregorian defaults and algorithmic leap year rules.
  - Added "Leap Rules" configuration to `CalendarConfigDialog`.
  - Updated `CalendarConverter` with weekday name calculation and 1-based month indexing.

### Refactor
- *(2026-01-18)* **Style**: Standardized docstrings across the entire codebase using `docformatter` (88 char wrap).

### Documentation
- *(2026-01-18)* **Fast Inject**: Added `docs/FAST_INJECT.md` with system architecture and usage guide.

## [0.7.0]

### Added
- *(2026-01-18)* **CLI**: Implemented comprehensive tool suite (`src.cli`) for Backups, Graph management, Obsidian export, and Trajectories.
- *(2026-01-18)* **Feature**: Implemented auto-refresh for Longform Editor to sync with external data changes.
- *(2026-01-16)* **Feature**: Implemented `GenerationReviewDialog` for reviewing and editing LLM output before acceptance.
- *(2026-01-16)* **Feature**: Enhanced `LMStudioProvider` to handle reasoning tags (e.g., `<think>`, `<scratchpad>`) and improve response parsing.
- *(2026-01-16)* **Feature**: Added template-based prompt system with few-shot examples for LLM generation.
- *(2026-01-15)* **Feature**: Implemented AST-based cursor synchronization for `WikiTextEdit` to preserve cursor position between views.
- *(2026-01-13)* **Feature**: Implemented Autocompletion for Tags, Attribute Keys, Relation Types, and Entity Types.
- *(2026-01-13)* **Feature**: Implemented Robust Autosave system with "Smart Updates" to prevent cursor jumps.

### Stability
- *(2026-01-18)* **Layout**: Hardened layout restoration to prevent crashes from off-screen windows and corrupted state.
- *(2026-01-18)* **Logging**: Added diagnostic logging to `UIManager` and `GraphWidget` for visibility troubleshooting.
- *(2026-01-15)* **Qt**: Implemented comprehensive Qt layout hardening with signal connection validation.

### Architecture
- *(2026-01-16)* **Prompts**: Implemented versioned prompt template system with YAML metadata and Jinja2-style syntax.
- *(2026-01-15)* **Initialization**: Refactored `MainWindow` initialization to three-phase pattern to eliminate race conditions.
- *(2026-01-15)* **Layout**: Implemented deferred layout restoration with three stages for improved startup performance.
- *(2026-01-15)* **Management**: Created `WidgetRegistry` class for centralized widget lifecycle management.

### Testing
- *(2026-01-18)* **CI**: Configured offscreen Qt platform for reliable headless CI testing.
- *(2026-01-17)* **Coverage**: Increased test coverage from 61% to 70% with comprehensive unit tests for core modules and services.

### UX
- *(2026-01-13)* **Graph**: Stabilized Graph View layout by enforcing a deterministic physics seed.

### Fixed
- *(2026-01-18)* **Graph**: Restored "Close" capability for Graph Dock and improved widget stability.
- *(2026-01-17)* **Testing**: Fixed Windows platform-specific test failures in `test_backup_config.py`, `test_asset_store.py`, and `test_paths.py`.
- *(2026-01-17)* **Bug**: Fixed asset store entity→entities pluralization and added `img_`/`thumb_` prefixes.
- *(2026-01-16)* **Bug**: Fixed dirty state loop in Entity Editor where editor became marked as modified immediately after loading.
- *(2026-01-15)* **Bug**: Fixed `WikiTextEdit` formatting issue where `Ctrl+4` did not reliably revert text.
- *(2026-01-14)* **Bug**: Fixed cursor jumping to start of document on autosave in `WikiTextEdit`.
- *(2026-01-13)* **Bug**: Fixed `AttributeError` in `MainWindow` when opening AI Settings dialog.
- *(2026-01-13)* **Graph**: Fixed offline graph rendering by bundling PyVis templates and local assets.

### Refactor
- *(2026-01-18)* **Linting**: Resolved project-wide Ruff linting errors and formatting issues.

### Documentation
- *(2026-01-18)* **CLI**: Added `docs/cli.rst` with auto-generated API reference.
- *(2026-01-18)* **Graph**: Added comprehensive Google-style docstrings to `GraphWidget`.
- *(2026-01-16)* **Docs**: Added comprehensive LLM integration review document (`docs/LLM_REVIEW_SUMMARY.md`).
- *(2026-01-13)* **Design**: Updated `Design.md` to reflect v0.7.0 changes and portable world model.
- *(2026-01-12)* **Docs**: Updated `README.md` for latest features.


## [0.6.0]

### Added
- *(2026-01-12)* **Feature**: Implemented complete Backup System with auto-save, retention policies, and integrity verification.
  - Added `BackupSettingsDialog` for runtime configuration of intervals and locations.
  - Integrated "Backup & Restore" menu with options for manual creation and folder access.
  - Implemented `BackupService` with automated background processing and robust error handling.
- *(2026-01-11)* **Docs**: Added comprehensive internal documentation for the Backup system.
- *(2026-01-11)* **Docs**: Standardized schema documentation and fixed missing title in `LICENSE.md`.
- *(2026-01-11)* **Feature**: Introduced Interactive Graph Visualization system.
  - Added `GraphWidget` and `GraphWebView` for PyVis/vis.js integration.
  - Added `GraphDataService` for efficient relationship graph calculation.
  - Features: Fluid zoom/pan, node dragging, and double-click navigation.
  - Integrated filtering via `GraphFilterBar` for Tags and Relationship types.
- *(2026-01-11)* **Feature**: Implemented Graph View Auto-Update. The graph now automatically refreshes relationships and nodes when data changes in the application.
- *(2026-01-11)* **Feature**: Implemented Graph Filtering Logic. The filter panel now correctly populates with available Tags and Relation Types fetched from the database.
- *(2026-01-11)* **Architecture**: Decoupled `DataHandler` from UI focus control to prevent background data refreshes from stealing user focus.
- *(2026-01-11)* **Feature**: Implemented full Theme Integration for Graph View, enabling dynamic color updates and background synchronization with the application theme.
- *(2026-01-10)* **Feature**: Implemented "Dulling Future Markers" for temporal visualization. Markers in the future relative to the playhead are now rendered with reduced opacity (0.7) and desaturated colors (80% saturation), while past/present markers remain vivid.
- *(2026-01-10)* **Architecture**: Migrated trajectory storage to OGC MF-JSON format for geospatial interoperability.
  - Added `geojson>=3.0.0` dependency.
  - Added `keyframes_to_mfjson()` and `mfjson_to_keyframes()` serialization helpers.
  - Added `_migrate_trajectories_to_mfjson()` for automatic one-time data migration on DB connect.
  - Structure: `{"type": "MovingPoint", "coordinates": [[x,y],...], "datetimes": [t,...]}`.
- *(2026-01-10)* **Feature**: Implemented persistent "Clock Mode" indicator with a toolbar status label and an interactive map overlay banner.
  - Added keyboard shortcuts: `Esc` for cancel and `Enter`/`Return` for commit.
  - Added `WaitCursor` feedback when entering Clock Mode.
- *(2026-01-10)* **Feature**: Integrated a comprehensive progressive disclosure system for map UX.
  - Added `OnboardingDialog` for first-time keyframe creation guidance.
  - Added a subtle pulsing animation (1.1x scale, 3 loops) for trajectories on first load to improve discoverability.
  - Added one-time 💡 hover hint tooltips for keyframes.
- *(2026-01-10)* **Feature**: Implemented Playhead Persistence, saving state on drag release, stop, and exit.
- *(2026-01-10)* **Feature**: Implemented "Draft Mode" (Amber) for transient marker states with visual snap-back on selection change or scrubbing.
- *(2026-01-10)* **UX**: Enhanced keyframe interaction with `SizeAllCursor` in spatial mode and optimized gizmo icon spacing for better click precision.
- *(2026-01-09)* **Feature**: Implemented keyframe deletion support and hardened trajectory precision.
  - Added context menu for keyframes with "Edit Keyframe..." and "Delete Keyframe" options.
  - Hardened trajectory calculation by rounding to 4 decimal places to prevent float precision drift.
  - Added description/tooltip support for markers, pulling from cached entity/event data.
- *(2026-01-09)* **Refactor**: Improved TimelineView code quality with 10 helper extractions and 18 new tests.
- *(2026-01-06)* **Feature**: Implemented live mouse coordinate display showing Normalized (0-1) and Real-World (Kilometers) values.
- *(2026-01-06)* **Feature**: Added GIS-style `ScaleBarPainter` with automatic unit selection and configurable map width via settings dialog.
- *(2026-01-06)* **Feature**: Added `moving_features` table for temporal map data with `ON DELETE CASCADE` on marker FK.
- *(2026-01-06)* **Architecture**: Introduced `MapCoordinateSystem` class for bidirectional normalized/scene coordinate handling.
- *(2026-01-06)* **Architecture**: Added OpenGL viewport support (`KRAKEN_NO_OPENGL` env var for software fallback).
- *(2026-01-06)* **Testing**: Added `test_map_graphics_view.py` covering coordinate signal behavior and bounds checking.
- *(2026-01-06)* **Testing**: Added ON DELETE CASCADE test for `moving_features.marker_id` FK.

### Fixed
- *(2026-01-12)* **Bug**: Fixed persistent bug where Project Explorer filter state (tags) was lost upon item save/reload.
- *(2026-01-12)* **Bug**: Fixed Project Explorer selection incorrectly jumping to random items when the selected item becomes filtered out.
- *(2026-01-12)* **Stability**: Fixed Windows-specific AppData path virtualization issues for Microsoft Store Python installations.
- *(2026-01-12)* **Stability**: Implemented `SafeRotatingFileHandler` to resolve "file in use" errors during log rotation on Windows.
- *(2026-01-11)* **Bug**: Fixed editor focus jumping to Entity Inspector when saving an Event.
- *(2026-01-11)* **Bug**: Fixed stale graph selection and camera reset issues on data reload.
- *(2026-01-11)* **Bug**: Improved Graph View focus restoration reliability after stabilization.
- *(2026-01-10)* **Bug**: Fixed onboarding dialog triggering incorrectly during keyframe movement.

### Changed
- *(2026-01-12)* **Refactor**: Encapsulated advanced filtering logic within `UnifiedListWidget`, removing dependency on `MainWindow` logic.
- *(2026-01-11)* **Refactor**: Centralized global selection logic in `MainWindow` to synchronize Project Explorer, Graph, and Editors.
- *(2026-01-10)* **UX**: Removed legacy background circle from map markers for a cleaner aesthetic.
- *(2026-01-10)* **Refactor**: Refactored `MapWidget` mode indicator to support Normal, Clock, and Draft modes.
- *(2026-01-10)* **Refactor**: Refactored `KeyframeItem` to `QGraphicsObject` for `QPropertyAnimation` support.
- *(2026-01-06)* **Refactor**: Refactored `MapWidget` toolbar to use styled `QPushButton`s for theme consistency.
- *(2026-01-06)* **Refactor**: Extracted drop handling and context menu logic in `MapGraphicsView`.
- *(2026-01-04)* **Tooling**: Improved changelog workflow to analyze full commit messages, not just headers.

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
