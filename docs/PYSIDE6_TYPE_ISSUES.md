# PySide6 Type Checking Known Issues

This document tracks known type checking false positives in the codebase due to incomplete PySide6 type stubs.

## Summary

- **Affected Files**: `src/app/main.py`, `src/app/ui_manager.py`
- **Total False Positives**: ~212 errors
- **Status**: Accepted as known limitations (not fixable without upstream PySide6-stubs updates)

## Issue Categories

### 1. Qt Enum Access (~150 errors)

**Problem**: Pyright cannot resolve Qt enum attributes like `Qt.BottomDockWidgetArea`, `Qt.QueuedConnection`, etc.

**Example**:
```python
self.main_window.setCorner(Qt.TopLeftCorner, Qt.LeftDockWidgetArea)
# Error: Cannot access attribute "TopLeftCorner" for class "type[Qt]"
```

**Root Cause**: PySide6-stubs don't properly expose Qt namespace enums.

**Runtime Behavior**: ✅ Works correctly - these enums exist and are accessible.

**Workaround**: None needed - code works as intended.

---

### 2. QMetaObject.invokeMethod (~50 errors)

**Problem**: Pyright expects specific types for method names, but PySide6 accepts string literals.

**Example**:
```python
QMetaObject.invokeMethod(
    self.worker, "load_current_time", Qt.QueuedConnection
)
# Error: Argument of type "Literal['load_current_time']" cannot be assigned
```

**Root Cause**: PySide6-stubs type signature doesn't match actual implementation.

**Runtime Behavior**: ✅ Works correctly - string method names are the standard PySide6 pattern.

**Workaround**: None needed - this is the correct PySide6 API usage.

---

### 3. Signal.emit() on Protocol (~12 errors)

**Problem**: `MainWindowProtocol` types `command_requested` as `object`, which doesn't have `.emit()`.

**Example**:
```python
self.main_window.command_requested.emit(cmd)
# Error: Cannot access attribute "emit" for class "object"
```

**Root Cause**: Protocol can't properly type PySide6 Signals without circular imports.

**Runtime Behavior**: ✅ Works correctly - actual MainWindow has properly typed Signal.

**Workaround**: Could use `cast()` but adds noise. Accepted as-is.

---

## Decision

We **accept these 212 errors** as known PySide6-stubs limitations rather than:
1. Adding hundreds of `# type: ignore` comments (obscures real issues)
2. Creating custom stub overrides (high maintenance burden)
3. Waiting for upstream fixes (blocks progress)

## Tracking

- **PySide6-stubs Issues**: https://github.com/python-qt-tools/PySide6-stubs/issues
- **Last Checked**: 2026-01-01
- **PySide6 Version**: 6.x
- **Pyright Version**: 1.1.407

## Future Action

When PySide6-stubs are updated:
1. Remove this document
2. Remove inline comments in `main.py` and `ui_manager.py`
3. Re-run `pyright src/app` to verify fixes

## Official Recommendation for Remaining Errors

As of late 2024 (PySide6 6.8+), the official Qt for Python stance on missing type stubs is:

1.  **Wait for Upstream Fixes**: The Qt Company is actively improving `shiboken6` (the generator), but coverage gaps remain for nested enums and complex variable arguments.
2.  **Use `# type: ignore`**: For attributes that definitely exist at runtime but are missing in stubs (e.g., `Qt.WidgetAttribute.WA_StyledBackground`), this is the cleanest, most "correct" approach.
3.  **Use `typing.cast` or `Any`**: For complex missing methods, casting the object to `Any` temporarily or using a Protocol with `Any` (as we did for `MainWindowProtocol`) is recommended over suppressing entire blocks of code.

### Specific Pitfall: Recursive Enum Replacement
**Do NOT** blindly replace all `Qt.\w+` patterns. This can lead to invalid paths like `Qt.WindowType.WidgetAttribute`. Always verify the parent class structure. `WidgetAttribute` is a direct child of `Qt`, not `WindowType`.
