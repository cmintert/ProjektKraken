---
**Project:** ProjektKraken  
**Document:** Project Changelog  
**Last Updated:** 2026-01-01  
**Commit:** `373459f4`  
---

# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- **CLI**: Added `--reset-settings` flag to `launcher.py` to clear persistent application settings (window state, active DB) for troubleshooting specific crashes.
- **Architecture**: Introduced `TimelineDataProvider` protocol for decoupling `TimelineView` from `DatasetService`.
- **Architecture**: Added `DataHandler` signals for all data events to remove direct `MainWindow` dependencies.
- **Testing**: Added integration tests for signal wiring and timeline provider.

### Fixed
- **Stability**: Resolved startup crash caused by corrupted `QSettings` (window geometry/state) persisting across versions.

### Changed
- **Refactor**: `TimelineView` no longer accepts `DatabaseService` directly. Use `set_data_provider` instead.
- **Refactor**: `TimelineWidget.set_db_service` removed.
- **Refactor**: UI components now receive data via `DataHandler` signals instead of direct callbacks where possible.

### Deprecated
- Direct access to `mainwindow.data_handler` from child widgets (use signals).
- Direct access to `mainwindow.timeline` from other widgets (use signals/ConnectionManager).
