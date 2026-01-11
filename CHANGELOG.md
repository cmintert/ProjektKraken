---
**Project:** ProjektKraken  
**Document:** Project Changelog  
**Last Updated:** 2026-01-11  
**Commit:** `0076ace`  
---

# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- *(2026-01-11)* **Architecture**: Decoupled `DataHandler` from UI focus control to prevent background data refreshes from stealing user focus.
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
- *(2026-01-11)* **Bug**: Fixed editor focus jumping to Entity Inspector when saving an Event.
- *(2026-01-11)* **Bug**: Fixed stale graph selection and camera reset issues on data reload.
- *(2026-01-10)* **Bug**: Fixed onboarding dialog triggering incorrectly during keyframe movement.

### Changed
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
