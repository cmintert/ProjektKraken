---
**Project:** ProjektKraken  
**Document:** Project Changelog  
**Last Updated:** 2026-02-06
**Commit:** `899cbd9`
---

# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Fixed
- *(2026-02-06)* **GUI**: Resolved drag and drop conflict in Unified List where dragging triggered box selection.
  - Switched `UnifiedListWidget` to `SingleSelection` mode.
  - Enforced `ItemIsDragEnabled` flag in `ExplorerModel`.

### Added
- *(2026-02-05)* **Feature**: Implemented complete persistent undo/redo system with visual history panel.
  - Added `CommandCoordinator` for centralized command execution and history management.
  - Implemented `HistoryService` for SQLite-based command persistence across sessions.
  - Added `HistoryPanelWidget` with real-time command history display and theme support.
  - Composite commands support for grouping related operations (e.g., wiki link processing).
  - Execution timestamps on all commands with YYYY-MM-DD HH:MM:SS display format.
  - Global Ctrl+Z/Ctrl+Y keyboard shortcuts with application-wide capture.
  - "Clear All History" functionality with confirmation dialog.
  - Auto-migration for existing databases to add timestamp column.
- *(2026-02-05)* **UI**: Enhanced `StyleHelper` with dynamic contrast calculation for improved accessibility.
- *(2026-02-06)* **UI**: Added global ESC key deselection for unified list with click-to-toggle behavior.
- *(2026-02-06)* **UI**: Implemented themed checkbox tick marks replacing filled color boxes.
- *(2026-02-06)* **UI**: Added persistent header to inspector panels showing entity/event name.

### Fixed
- *(2026-02-06)* **Bug**: Fixed Qt6 API error in `KeyframeGizmoOverlay` where `event.position()` was incorrectly used on `QGraphicsSceneMouseEvent` (should be `event.pos()`). Resolves runtime crash when clicking clock/delete icons on trajectory keyframe gizmos.
- *(2026-02-06)* **Bug**: Fixed Project Explorer multi-select checkboxes by persisting check state in `ExplorerModel` and resolving CSS visibility issues.
- *(2026-02-06)* **Bug**: Fixed startup "dirty state" issue where editors were marked as modified immediately upon opening.
- *(2026-02-05)* **Bug**: Fixed persistent undo by adding missing `id` property to `World` class.
- *(2026-02-05)* **Bug**: Fixed undo/redo wiring with deferred initialization to prevent crashes.
- *(2026-02-05)* **Stability**: Implemented serialization for all entity and relation commands to prevent undo/redo crashes.

### Changed
- *(2026-02-06)* **Refactor**: Improved code quality in inspector editor widgets with Sourcery suggestions.
- *(2026-02-05)* **UX**: Optimized deletion workflow with high-speed unblocking auto-closing message box.

### Documentation
- *(2026-02-05)* **Docs**: Added comprehensive technical documentation (DEVELOPMENT.md, DATABASE.md, TESTING.md, API.md, CONTRIBUTING.md).
- *(2026-02-05)* **Docs**: Created WORKFLOWS.md, FAQ.md, and ARCHITECTURE.md for project guidance.
- *(2026-02-05)* **Docs**: Updated root README with consolidated installation and user guide.


## [0.10.3]
