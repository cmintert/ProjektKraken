# Testing

## Test levels

- Unit tests cover domain logic, commands, services, and focused widgets.
- Integration tests cover coordinators, worker delivery, and persistence.
- GUI tests exercise PySide6 behaviour with an application fixture.
- Regression tests preserve previously fixed workflows.

## CI suites

- `smoke` is the short critical-path gate for every pull request.
- `ci_fast` is the required pull-request regression suite. It covers CLI,
  security, packaging, core/services/repositories, and selected command and
  persistence tests. Keep it deterministic and within the 12-minute CI budget.
- The full suite, including coverage, runs nightly, on beta tags, and when
  manually dispatched. Run it before approving a release.

Do not use `not slow` as a CI suite selector. It means every test that has not
been explicitly marked slow, not a bounded fast suite.

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

Mypy is a required repository-wide CI check. `python -m mypy src` must pass
with zero diagnostics; no error baseline or changed-files exception is used.
`pyrightconfig.json` remains available for IDE diagnostics, but Pyright is not
a separate CI gate.
