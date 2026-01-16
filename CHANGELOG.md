---
**Project:** ProjektKraken  
**Document:** Project Changelog  
**Last Updated:** 2026-01-16  
**Commit:** `cbeec64`  
---

# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- *(2026-01-16)* **Architecture**: Implemented versioned prompt template system with YAML metadata and comprehensive validation.
  - Added `PromptLoader` class with support for template discovery, loading, and validation.
  - Implemented YAML frontmatter parsing for template metadata (version, description, variables).
  - Added template inheritance and variable substitution with Jinja2-style syntax.
  - Created comprehensive test suite with 363 unit tests covering edge cases and error handling.
  - Moved templates from `src/assets` to `default_assets/templates` for better organization.
  - Added support for system prompts and custom user prompts with validation.
- *(2026-01-15)* **Stability**: Implemented comprehensive Qt layout hardening with signal connection validation (79/79 connections validated).
  - Added `_connect_signal_safe()` method to `ConnectionManager` with graceful error handling and detailed logging.
  - Updated all 8 `connect_*()` methods to use validated connections with failure tracking.
  - Created 10 unit tests for signal validation (all passing).
- *(2026-01-15)* **Architecture**: Refactored `MainWindow` initialization to three-phase pattern to eliminate race conditions.
  - Phase 1: Core services initialization (DataHandler, WorkerManager).
  - Phase 2: UI skeleton creation (widgets, docks, menus).
  - Phase 3: Deferred completion (signal connections, database init, state restoration).
- *(2026-01-15)* **Architecture**: Implemented deferred layout restoration with three stages for improved startup performance.
  - Stage 1: Immediate geometry restoration for instant visual feedback.
  - Stage 2: Critical docks at 100ms (list, editors, timeline).
  - Stage 3: Optional docks at 500ms (longform, map, AI, graph).
- *(2026-01-15)* **Stability**: Added comprehensive error handling to dock creation with validation and graceful degradation.
- *(2026-01-15)* **Architecture**: Implemented layout version compatibility checking to prevent corrupted state issues.
- *(2026-01-15)* **Architecture**: Created `WidgetRegistry` class for centralized widget lifecycle management.
- *(2026-01-15)* **Testing**: Added 29 unit tests and 9 integration tests for layout hardening (38 tests total, all passing).
- *(2026-01-15)* **Feature**: Implemented AST-based cursor synchronization for `WikiTextEdit` to ensure pixel-perfect cursor preservation when toggling between Rich and Source views.
- *(2026-01-13)* **Feature**: Implemented Autocompletion for Tags, Attribute Keys, Relation Types, and Entity Types.
  - Added `GraphDataService` methods to fetch unique types and keys from the database.
  - Integrated `QCompleter` into `TagEditorWidget`, `AttributeEditorWidget`, and `RelationEditDialog`.
  - Added `update_suggestions` methods to `EntityEditorWidget` and `EventEditorWidget` to propagate data.
  - Added `completer_data_loaded` signal to `DatabaseWorker` for asynchronous data loading.
- *(2026-01-13)* **Feature**: Implemented Robust Autosave system with "Smart Updates" to prevent cursor jumps.
  - Added `AutoSaveManager` with debounced timing (2s).
  - Configured Entity/Event editors to only update UI fields when data actually changes.
- *(2026-01-13)* **UX**: Stabilized Graph View layout by enforcing a deterministic physics seed (`randomSeed: 42`).

### Fixed
- *(2026-01-15)* **Bug**: Fixed `WikiTextEdit` formatting issue where `Ctrl+4` did not reliably revert text to unformatted body text.
- *(2026-01-14)* **Bug**: Fixed cursor jumping to start of document on autosave in `WikiTextEdit`.
- *(2026-01-14)* **Bug**: Fixed persistence of Heading styles (H1-H3) in `WikiTextEdit` during Markdown/HTML conversion.
- *(2026-01-13)* **Bug**: Fixed `AttributeError` in `MainWindow` when opening AI Settings dialog.
- *(2026-01-13)* **Graph**: Fixed offline graph rendering by bundling PyVis templates and local assets.
- *(2026-01-13)* **Build**: Removed missing migrations directory from build configuration to fix PyInstaller builds.

### Documentation
- *(2026-01-16)* **Docs**: Added comprehensive LLM integration review document (`docs/LLM_REVIEW_SUMMARY.md`).
  - Executive summary analyzing current LLM integration strengths and identifying 8 critical gaps.
  - Detailed gap analysis covering prompt management, UI/UX, RAG, semantic search, and context handling.
  - Recommended 12 prioritized PRs with effort/risk/impact estimates (Quick Wins, Medium, Long-term).
  - UI/UX mockups for enhanced LLM panel design with collapsible sections and streaming support.
  - 14-item implementation checklist with examples, JSON schemas, and pseudo-code.
  - Security, performance, and future enhancement considerations.
  - 516 lines of production-ready specification for follow-up work.
- *(2026-01-13)* **Design**: Updated `Design.md` to reflect v0.6.0 changes and portable world model.
- *(2026-01-12)* **Docs**: Updated `README.md` for v0.6.0 features.

### Architecture
- *(2026-01-13)* **Feature**: Implemented portable-only World/Workspace model to decouple user data from application files.
  - Renamed root `assets` directory to `default_assets`.
  - Updated resource loading logic to support the new directory structure.
  - Enforced separation of user data by adding `worlds/` to `.gitignore`.

### Refactor
- *(2026-01-15)* **Cleanup**: Removed unused imports from `test_editor_signals.py`.

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
