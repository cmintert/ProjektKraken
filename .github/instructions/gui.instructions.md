---
description: "Use when editing PySide6 GUI files under src/gui, including widgets, dialogs, models, mixins, and view helpers. Covers dumb-UI boundaries, theme-safe styling, signal-based interactions, and safe deferred access with shiboken6.isValid(...)."
name: "ProjektKraken GUI Guidelines"
applyTo: "src/gui/**/*.py"
---

# GUI Guidelines

- Treat `src/gui/` as dumb UI. Widgets and dialogs may format display state, validate direct user input, and emit signals, but they must not own business logic, persistence rules, or direct `DatabaseService` access.
- Route user mutations through the app layer. Prefer signal -> `MainWindow` or coordinator -> command -> worker execution rather than calling services from the widget.
- Keep cross-thread payloads immutable. Send plain snapshots such as `dict`, `list`, `str`, or dataclass dictionaries across signals instead of live Qt objects, repository instances, or command objects.

## Styling

- Never hardcode widget colors, border colors, or theme-specific values in GUI code.
- Reuse or extend `src/gui/utils/style_helper.py` for QSS so styles resolve colors through `ThemeManager().get_theme()`.
- Use reusable spacing and sizing constants from `src/app/ui_constants.py` or `src/app/constants.py` when values are shared.
- Use runtime-recolored icons from `src/gui/utils/icon_loader.py` instead of shipping one-off tinted assets.

## Qt Safety

- When code runs later than the current event handler, guard Qt-owned objects before touching them. This applies to `QTimer` callbacks, debounce handlers, queued signal handlers, deferred lambdas, and teardown-sensitive editor/document work.
- Use `shiboken6.isValid(...)` before accessing `QObject`, `QWidget`, or `QTextDocument` instances that may already be deleted, and handle `RuntimeError` where partial teardown is still possible.
- If focus-sensitive logic targets a `QTextEdit`, check both the editor and `editor.viewport()` because `QApplication.focusWidget()` may return the viewport.

## Preferred Patterns

- Follow existing examples in `src/gui/widgets/`, `src/gui/mixins/`, and `src/gui/utils/style_helper.py` before introducing new widget structure.
- Prefer small widget methods that update UI state, wire signals, and translate between Qt events and app-layer requests.
- Keep GUI-only helpers in `src/gui/`; move reusable domain or persistence behavior to `src/app/`, `src/commands/`, `src/services/`, or `src/core/`.