# Testing

## Test levels

- Unit tests cover domain logic, commands, services, and focused widgets.
- Integration tests cover coordinators, worker delivery, and persistence.
- GUI tests exercise PySide6 behaviour with an application fixture.
- Regression tests preserve previously fixed workflows.

Use fixtures from `tests/conftest.py`, including `qapp`, `db_service`, and
`init_theme_manager`.

## Windows GUI tests

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
pytest -m smoke -q
```

## Common hazards

- `MockQSettings._storage` is shared; clear keys touched by a test.
- Debounce timers may fire during teardown.
- A text editor's viewport may be the focused widget.
- Check Qt object validity before delayed access.
- Database work must remain on the worker thread in integration tests as it
  does in production.

## Type checking

Mypy follows a no-new-errors ratchet. Changed code must not introduce errors.
Modules with a small existing baseline should be left clean; larger baselines
require related fixes and bounded cleanup.

