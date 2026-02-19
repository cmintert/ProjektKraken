---
**Project:** ProjektKraken  
**Document:** Project Changelog  
**Last Updated:** 2026-02-19
**Commit:** `2995ba7`
---

# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- *(2026-02-19)* **UI**: Implemented actionable empty states across editors (Longform Editor, MapWidget, Timeline, Unified List).
  - Added primary action buttons (e.g., "Create Document", "New Entity") to empty states for improved onboarding.
  - Ensured consistent button styling and states across all empty state views.

### UI
- *(2026-02-19)* **UI**: Implemented MainWindow with dockable panes and layout persistence.
  - Replaced placeholder widgets with real Explorer, Timeline, Relations, and Editor widgets.
  - Enabled dock nesting, resizing, redocking, and robust splitter configuration.

### Fixed
- *(2026-02-19)* **Stability**: Fixed widget resize/collapse stability and dock collapse on startup using size policies and validation delays.

### Testing
- *(2026-02-19)* **Testing**: Standardized variable naming conventions in UI test files to address review feedback.

## [0.13.0]

### Added
- *(2026-02-18)* **Map**: Added "No Fill (Transparent)" and "No Border" options to the marker right-click Visual Styling sub-menu.
  - Markers can now have a fully transparent background or no border, persisted via the undo/redo command stack.
- *(2026-02-17)* **Graph**: Added Border Color, Border Width, and Size Scale columns to Lexicon Editor node rows.
- *(2026-02-17)* **Graph**: Extended `_ColorButton` in Lexicon Editor with a "none" state (right-click to clear); displays ∅ symbol with gradient hatching.
- *(2026-02-17)* **Architecture**: Introduced `src/gui/utils/svg_utils.py` with shared SVG inline-style injection utilities (`apply_svg_inline_styles`, `apply_svg_styling_to_data_uri`, `svg_file_to_string`).
- *(2026-02-17)* **Architecture**: Introduced `VisualResolver` service and `style_constants.py` for centralized, cascading visual property resolution across map markers and graph nodes.
- *(2026-02-17)* **Map**: Map markers now respect `_v_border`, `_v_border_width`, and `_v_size_scale` visual attributes; SVG icons are re-styled on attribute change.
- *(2026-02-17)* **UI**: Added unified `IconPickerDialog` shared between Lexicon Editor and Map Editor with Default Icons, Project Icons, and Import from Disk tabs.
- *(2026-02-17)* **UI**: Added "Clear Icon" button in Lexicon Editor to remove an icon and reset entity-type shape.
- *(2026-02-17)* **Assets**: Added `AssetStore.import_icon()` for importing SVG/PNG/JPG icons while preserving the original file extension.
- *(2026-02-17)* **Graph**: Implemented immediate visual feedback in Lexicon Editor; changes to colors, shapes, and icons now update the graph in real-time.
- *(2026-02-17)* **Graph**: Implemented "Cancel" logic for Lexicon Editor to revert changes if the dialog is rejected.
- *(2026-02-17)* **Graph**: Implemented flicker-free incremental graph updates for smoother visualization changes.
- *(2026-02-17)* **Graph**: Implemented view state preservation (zoom/pan) across data reloads.
- *(2026-02-17)* **UI**: Implemented `ProjectIconCard` widget for a modern, card-based interface in the Project Icons tab.
- *(2026-02-17)* **UI**: Added theme-aware icon management with support for removing project icons and clearing lexicon icons.

### Changed
- *(2026-02-18)* **Map**: Removed redundant top-level "Change Color..." marker context menu item (superseded by "Set Fill Color..." in Visual Styling sub-menu).
- *(2026-02-17)* **Graph**: Renamed "Save" button to "OK" in Lexicon Editor to better reflect the immediate nature of the changes.
- *(2026-02-16)* **Map**: Added visual keyframe indicator (8px dot) to markers with trajectories to improve discoverability of temporal data.
- *(2026-02-16)* **UI**: Extended theme-aware `StandardCheckbox` styling to Map Hierarchy (QTreeView).
- *(2026-02-16)* **Assets**: Updated polyline icon to Phosphor 'bezier-curve' variant for better "Path" visualization.
- *(2026-02-16)* **UI**: Implemented `StandardCheckbox` widget for consistent, theme-aware checkbox styling across the application.
- *(2026-02-15)* **Import**: Implemented Markdown import defaults.
  - Automatically uses filename (without extension) as title if YAML title is missing.
  - Defaults type to `generic` (Entity) for valid Markdown files without a specified type.
  - Populates entity description with the body of the Markdown file.

### Fixed
- *(2026-02-17)* **Graph**: Fixed "Image file not found" warnings in Relationship Graph by supporting bundled default icon resolution.
- *(2026-02-17)* **Graph**: Fixed shape revert bug in Lexicon Editor where user-selected shapes were overridden by images.
- *(2026-02-17)* **Graph**: Fixed `AttributeError` in `DataCoordinator` occurring during graph lexicon handling.
- *(2026-02-17)* **Graph**: Fixed regression where edges disappeared during incremental updates by enforcing stable relationship IDs.
- *(2026-02-17)* **Graph**: Fixed entity renames not updating in the graph view by mapping internal properties to presentation layer.
- *(2026-02-16)* **UI**: Removed background color from checked checkbox indicators for cleaner look.
- *(2026-02-16)* **UI**: Fixed checkbox icon visibility issue on Windows by using robust absolute resource paths (`get_resource_path`).
- *(2026-02-15)* **Bug**: Fixed `TypeError` in Markdown import refresh caused by missing `doc_id` in `load_longform_sequence`.

### Refactor
- *(2026-02-18)* **Map**: Removed dead code from `MarkerItem` (`_render_svg_to_pixmap`, `_tint_pixmap`) and cleaned up unused imports.
- *(2026-02-17)* **Graph**: `GraphBuilder.apply_svg_styling` now delegates to shared `svg_utils` module (DRY).
- *(2026-02-16)* **Docs**: Updated `MarkerItem` docstrings to Google style guide.
- *(2026-02-16)* **UI**: Refactored `OnboardingDialog` to use `StyleHelper` and fully support application themes.
- *(2026-02-16)* **UI**: Refactored `EventEditor` and `EntityEditor` to use `StandardCheckbox`, removing redundant manual stylesheet updates.

### Changed
- *(2026-02-16)* **GUI**: Implemented "click empty space to deselect" in Project Explorer, matching behavior of Entity/Event Editor relation lists.

### Deprecated

### Cleanup

## [0.12.0]

### Added
- *(2026-02-14)* **AI**: Added "Summary Temperature" setting (0.0 - 1.0) to control generation determinism.
  - Defaults to `0.3` for consistent, factual summaries.
  - Lower values produce more deterministic output; higher values allow for more creativity.
- *(2026-02-14)* **AI**: Implemented robust settings refresh system; changes to models, providers, and prompt templates now apply immediately without requiring an application restart.
  - `SummaryService` and `LLMGenerationWidget` now listen for `ai_settings_changed` signal.
  - Automatically re-initializes provider connections when API keys or URLs change.

### Fixed
- *(2026-02-14)* **AI**: Fixed "Prompt Editor" autosave not triggering correctly in Settings Dialog.
  - Ensures custom prompt templates are persisted reliably when switching tabs or closing the dialog.
- *(2026-02-14)* **Bug**: Fixed AI summaries not loading on restart by removing `summary_service` guard in `EventEditor`.
- *(2026-02-13)* **Docs**: Corrected opacity slider docstring.

### Cleanup
- *(2026-02-14)* **Architecture**: Removed deprecated `_perform_rag_search` method and unused AI constants from `AISearchManager` to simplify codebase.

### Architecture
- *(2026-02-14)* **Refactor**: Removed backward compatibility hacks in coordinators and standardized usage of `DataCoordinator`.
- *(2026-02-14)* **Architecture**: Continued `MainWindow` decomposition (Phase 1 & 2) by removing passthrough methods and rewiring `ConnectionManager` to access `LongformManager` directly.
- *(2026-02-13)* **Architecture**: Split `map_commands.py` (1,648 lines) into focused functional modules and decomposed `MapGraphicsView` into 5 sub-components for better maintainability.
- *(2026-02-13)* **Architecture**: Decoupled `MapHandler` from dialog management and implemented service locator pattern for `MainWindow` access.
- *(2026-02-11)* **Architecture**: Completed core Hierarchical Layer System (HLS) including themed layer management panel and database persistence.

### Stability
- *(2026-02-14)* **Stability**: Forced full map marker reload on undo/redo operations to ensure visual consistency.
- *(2026-02-14)* **Testing**: Added integration tests verifying undo/redo triggers proper reload signals.
- *(2026-02-13)* **Stability**: Resolved "Layer node not found" race condition via signal-based UI snapshots in database commands.
- *(2026-02-12)* **Stability**: Fixed map visibility overwrite issues by suppressing reloads for background sync and implementing selection persistence.
- *(2026-02-12)* **Stability**: Resolved opacity slider flicker and ensured correct persistence of slider-triggered changes.
- *(2026-02-11)* **Stability**: Integrated global undo/redo support for all layer operations with automatic persistence.

### Map
- *(2026-02-12)* **Map**: Implemented "Triple-Sync" rename logic ensuring bidirectional synchronization between Map Hierarchy and Unified List.
- *(2026-02-10)* **Map**: Constrained map hovertips to a 150px maximum width for improved readability of long descriptions.

### UX
- *(2026-02-12)* **UX**: Improved map interaction by preserving viewport transform across marker and layer reload cycles.


### Added
- *(2026-02-10)* **Map**: Implemented `SnappingManager` for robust map editing.
  - Supports "Vertex Snapping" (nearest point) and "Edge Snapping" (nearest segment) using efficient BSP spatial indexing.
  - Added visual indicators for snap targets (yellow circle for vertices, blue cross for edges).
  - Added toolbar toggle button for snapping.
- *(2026-02-10)* **Map**: Implemented In-Place Entity/Event Creation from Map Selection Dialog.
  - Added `<New Entity...>` and `<New Event...>` options to `UnifiedList` dialogs.
  - Allows creating and linking new items entirely within the map workflow without leaving the context.
- *(2026-02-09)* **Map**: Implemented Line (Path) and Polygon (Region) Features.
  - Added drawing tools for creating multi-point paths (roads, rivers) and closed regions (territories).
  - Features support custom colors, hover tooltips showing area/length, and vertex editing.
  - Integrated with `MapGraphicsView` for seamless creation and manipulation.

### Fixed
- *(2026-02-10)* **UI**: Fixed visual state of toolbar toggle buttons (Snap, Draw Path).
  - Updated `StyleHelper` to correctly target `QPushButton` in toolbar styles.
  - Added specific `:checked` pseudo-state styling to clearly indicate active tools.

### Documentation
- *(2026-02-10)* **Docs**: Added comprehensive research and design notes for mapping enhancements (`docs/design_notes/mapping_enhancements/`).
  - Covered Road Network Strategy, Network Analysis (NetworkX vs QGIS), and Snapping implementation.
- *(2026-02-10)* **Docs**: Added detailed `SNAPPING_MANAGER.md` documentation explaining the spatial indexing and math.



### Added
- *(2026-02-08)* **UI**: Updated `ShortcutManager` and "Keyboard Shortcuts" dialog with new hotkeys (Navigate Link, Choose Relation Type, Deselect) and improved categorization.

### Fixed
- *(2026-02-08)* **Bug**: Fixed duplicate End Date field appearing in the Event Inspector.

### Documentation
- *(2026-02-08)* **Docs**: Completed major documentation overhaul, consolidating 62 legacy files into structured User and Technical guides (API Reference, Testing, Contributing, Architecture).

### Cleanup
- *(2026-02-08)* **Cleanup**: Removed temporary test output files and development-only documentation.

## [0.11.0]

### Added
- *(2026-02-07)* **UI**: Implemented "Drag-and-Drop Relations" from Project Explorer to Editors with visual "Drag Pill" cursor and "Relation Type Picker".
- *(2026-02-07)* **UI**: Added generic "Toast Notification" system using themed Auto-Closing Message Box for non-intrusive feedback.
- *(2026-02-07)* **Map**: Implemented "Drag Overlay" on Map Widget for improved visual feedback during drop operations.
- *(2026-02-05)* **Core**: Implemented comprehensive Global Undo/Redo System with persistence across restarts and specialized "History Panel" dock.
- *(2026-02-05)* **UI**: Added Global Keyboard Shortcuts handler via application event filter for consistent hotkey behavior.
- *(2026-02-03)* **UI**: Implemented "Virtualized List Model" (`QAbstractListModel`) for Unified List, significantly improving performance with large datasets.
- *(2026-02-03)* **UI**: Implemented Async Gallery Loading and Smart Attribute Editing for better responsiveness.

### Fixed
- *(2026-02-07)* **UI**: multiple drag-and-drop regression fixes covering selection state preservation and delayed inspection logic.
- *(2026-02-05)* **UI**: Fixed Project Explorer multi-select checkboxes not persisting correct state during filtering.
- *(2026-02-04)* **Timeline**: Prevented playhead from accidentally moving selected events during scrub operations.
- *(2026-02-03)* **Testing**: Resolved test failures by introducing compatibility layers and ensuring proper Qt library installation.

### Refactor
- *(2026-02-07)* **Refactor**: Refactored UI "Magic Numbers" into constants and fixed duplicate relation creation logic.
- *(2026-02-05)* **Architecture**: Major refactor of Command System to support serialization, timestamps, and composite commands.
- *(2026-02-03)* **Architecture**: Completed comprehensive "UX Audit" refactor including Model/View separation and async timeline layout.

### Documentation
- *(2026-02-07)* **Docs**: Added comprehensive documentation for Drag & Drop and Toast Notifications.
- *(2026-02-05)* **Docs**: Added extensive documentation and research for Undo/Redo system and Code Review reports.


## [0.10.3]

### Added
- *(2026-02-03)* **UI**: Added "Help" menu with "Keyboard Shortcuts" dialog showing all available application shortcuts.
- *(2026-02-03)* **UI**: Implemented progress dialog for JSON import operations providing real-time status feedback.
- *(2026-02-03)* **Scripts**: Added `setup_env.sh` and `validate_env.sh` for automated test environment creation and verification.

### Changed
- *(2026-02-03)* **UI**: Implemented theme-aware styling for timeline elements and "Return to Present" button.
  - Timeline active event borders now use `theme['primary']` instead of hardcoded green (#4CAF50).
  - PLAYHEAD separator uses `theme['primary']`, NOW line uses `theme['accent_secondary']`.
  - "Return to Present" button uses `theme['accent_secondary']` instead of hardcoded blue (#2196F3).
  - Timeline display automatically refreshes when theme changes.

### Fixed
- *(2026-02-03)* **Bug**: Fixed `GenerationContextProvider` reference error in `LLMGenerationWidget`.
- *(2026-02-03)* **Testing**: Resolved theme-related test failures by ensuring complete theme dictionaries in mocks.

### Documentation
- *(2026-02-03)* **Testing**: Added comprehensive test environment setup guide (`docs/TESTING_SETUP.md`) and summary (`docs/TEST_ENVIRONMENT_SUMMARY.md`).
- *(2026-02-03)* **Maintenance**: Created `docs/TODO_TRACKING.md` for technical debt management and tracking.

### Refactor
- *(2026-02-03)* **Code Quality**: Replaced magic numbers with named constants throughout the codebase.
- *(2026-02-03)* **Code Quality**: Completed extensive docstring and type hint improvements (Phase 2).
- *(2026-02-03)* **Cleanup**: Resolved pending TODO comments in `main_window.py` and `unified_list.py`.

## [0.10.2]

### Changed
- *(2026-02-02)* **Core**: Added application version number (v0.10.1) to startup log message.
- *(2026-02-02)* **GUI**: Improved relation list behavior - clicking empty space or an already-selected item now deselects it.
- *(2026-02-02)* **UI**: Added Edit and Remove buttons to Event Editor relation sections (Participants, Locations, Custom Relations) for consistency with Entity Editor.
- *(2026-02-02)* **UI**: Unified destructive button behavior across all editors - Remove buttons now disable when nothing is selected and show warning color when enabled.

### Fixed
- *(2026-02-02)* **Core**: Fixed triplicate startup logging by centralized logging initialization.
- *(2026-02-02)* **GUI**: Fixed relation reselection bug where items could not be reselected after deselection.

### Refactor
- *(2026-02-02)* **UI**: Added explicit `:disabled` state styling for destructive buttons with greyed-out appearance.
- *(2026-02-02)* **UI**: Updated `PrimaryButton` and `DestructiveButton` to dynamically update styles on theme changes.
- *(2026-02-02)* **Refactor**: Applied Sourcery suggestions to widget code - simplified conditionals, used walrus operator, and improved error handling.

## [0.10.1]

### Added
- *(2026-01-29)* **UI**: Implemented global selection sync between Timeline, List, and Inspectors.
- *(2026-01-27)* **UI**: Added "Save as Default Layout" menu action for easier workspace configuration.

### Fixed
- *(2026-02-02)* **UI**: Fixed infinite resize loop and separator rendering issues in Map Dock to prevent layout instability.
- *(2026-01-29)* **Timeline**: Fixed duration bars scaling correctly with zoom level.
- *(2026-01-29)* **Timeline**: Fixed Fit View to include full event durations and respect actual viewport size.
- *(2026-01-29)* **Timeline**: Lowered MIN_ZOOM from 0.0001 to 0.000001 to support massive timelines (up to 40M lore days).
- *(2026-01-29)* **Timeline**: Enforced single event selection (disabled Ctrl+Click multi-select).
- *(2026-01-28)* **UI**: Fixed spinbox up/down arrow visibility in Event Inspector.
- *(2026-01-27)* **Performance**: Optimized calendar calculations with year caching for >50x speedup.
- *(2026-01-27)* **Build**: Fixed gallery image path resolution in portable builds.
- *(2026-01-27)* **Build**: Resolved missing calendar icon in frozen build.

### Changed
- *(2026-01-29)* **UI**: Moved "Reset Layouts" option from "Views" menu to "Layouts" menu for better logical organization.
- *(2026-01-27)* **UI**: Renamed "Imperial Mode" theme and improved theme color control across widgets.

### Refactor
- *(2026-02-02)* **Editor**: Applied Sourcery refactoring suggestions to `LongformEditor`, including walrus operator usage and conditional logic simplifications.
- *(2026-02-02)* **Testing**: Cleaned up code review findings and fixed unit tests to ensure stability after refactoring.

## [0.10.0]

### Added
- *(2026-01-27)* **UI**: Added "Cyberpunk Mode" theme with high-contrast tech-noir neon palette.
- *(2026-01-27)* **UI**: Added "Imperial Mode" with a Grimdark crimson aesthetic.
- *(2026-01-27)* **UI**: Centralized event and entity color control in `themes.json` for all themes.
- *(2026-01-26)* **UI**: Overhauled Longform Search with Ctrl+F support, results highlighting, and dedicated search buttons.

### Changed
- *(2026-01-27)* **UI**: Refined theme-aware color retrieval logic in `StyleHelper`, `EventItem`, and `GraphWidget` to ensure 100% theme adherence.
- *(2026-01-26)* **UI**: Improved consistency of `CompactDateWidget` and `DescriptionEditor` across all themes.
- *(2026-01-26)* **Refactor**: Moved `sqlite3` import to `DatabaseWorker` to ensure proper thread affinity for SQLite objects.

### Fixed
- *(2026-01-26)* **Bug**: Fixed regression where Longform Search bar failed to toggle visibility correctly on Escape or Ctrl+F.
- *(2026-01-26)* **Stability**: Fixed theme compliance for `CompactDateWidget`, `CompactDurationWidget`, and `DescriptionEditor`.
- *(2026-01-26)* **Testing**: Mocked `QMessageBox` in `UnifiedListWidget` tests to prevent hanging in headless environments.

- *(2026-01-24)* **AI**: Implemented `RAGService` with Hybrid Search (Lexical + Semantic) for robust context retrieval.
- *(2026-01-24)* **AI**: Overhauled `LLMGenerationWidget` with RAG context preview and detailed logging.
- *(2026-01-24)* **AI**: Refactored prompt generation to 'Trinity' architecture (Persona-Task-Data).
  - Enforced strict separation and standardized ordering (System Persona + User Task + Data).
  - Renamed 'Templates' to 'Task Templates' and 'Basic Assistant Prompt' to 'Persona'.
  - Added 'Free Text / Custom' and 'Basic Assistant' options for flexible prompt construction.

### Changed
- *(2026-01-23)* **AI**: Standardized template selection logic; all templates are now globally visible across widgets.

### Refactor
- *(2026-01-25)* **Refactor**: Optimized `AISearchManager` and `LLMGenerationWidget` code quality.
  - Applied Sourcery suggestions (walrus operator, optimized if-expressions).
  - Cleaned up unused imports and variables (`rag_content`, `sqlite3`).
- *(2026-01-25)* **Refactor**: Fixed 88-char line length violations and updated docstrings in `AISearchManager`.

### Testing
- *(2026-01-24)* **Testing**: Added verification tests for RAG preview and LLM generation architectures.

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
