# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- **Architecture**: Introduced `TimelineDataProvider` protocol for decoupling `TimelineView` from `DatasetService`.
- **Architecture**: Added `DataHandler` signals for all data events to remove direct `MainWindow` dependencies.
- **Testing**: Added integration tests for signal wiring and timeline provider.

### Changed
- **Refactor**: `TimelineView` no longer accepts `DatabaseService` directly. Use `set_data_provider` instead.
- **Refactor**: `TimelineWidget.set_db_service` removed.
- **Refactor**: UI components now receive data via `DataHandler` signals instead of direct callbacks where possible.

### Deprecated
- Direct access to `mainwindow.data_handler` from child widgets (use signals).
- Direct access to `mainwindow.timeline` from other widgets (use signals/ConnectionManager).
