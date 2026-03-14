---
description: "Use when editing or adding tests under tests, including pytest, pytest-qt, GUI regressions, command tests, and fixture setup. Covers shared fixtures, offscreen Qt handling, and MockQSettings contamination risks."
name: "ProjektKraken Test Guidelines"
applyTo: "tests/**/*.py"
---

# Test Guidelines

- Prefer the shared fixtures in `tests/conftest.py` before creating new setup code.
- Use `db_service` for a fresh in-memory database unless the test specifically needs a file-backed database.
- Use `qapp` and the existing Qt session setup rather than constructing a separate `QApplication` inside tests.
- Assume `ThemeManager` is already initialized by fixtures; avoid custom theme bootstrap unless a test is specifically covering theme startup behavior.

## Qt And Offscreen Behavior

- GUI tests run in offscreen mode. Keep assertions resilient to offscreen rendering differences and shell subprocess requirements.
- If a test launches pytest or Qt code in a subprocess on Windows, ensure `$env:QT_QPA_PLATFORM = "offscreen"` is set for that subprocess path too.
- Prefer widget behavior assertions, emitted signals, and state changes over pixel-perfect rendering checks.

## QSettings And Shared State

- `MockQSettings._storage` in `tests/conftest.py` is class-level shared state across the session.
- If a test writes settings, clear only the touched keys or patch `QSettings` per test so unrelated tests do not inherit state.
- Reset or isolate other singleton-style state when the test mutates it, especially theme or global manager state.

## Scope And Structure

- Keep unit tests focused and direct. Use integration tests only when behavior spans commands, services, and persistence together.
- Follow existing naming patterns such as `test_<behavior>_<scenario>`.
- For command tests, cover execute and undo paths, and add serialization coverage when history persistence matters.
- For Qt teardown-sensitive code, prefer patterns that avoid leaving live widgets, timers, or web engine objects behind after the test.
