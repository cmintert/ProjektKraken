# PySide6 Enum Access - Proven Solution

## Research Summary

**Problem**: Pyright reports ~600 `reportAttributeAccessIssue` errors for Qt enum access.

**Root Cause**: PySide6 6.4+ uses fully qualified enum paths in type stubs, but allows shorthand at runtime for backwards compatibility.

## Official Solution: Fully Qualified Enum Paths

### Examples

```python
# ❌ Old (works at runtime, fails type checking)
Qt.AlignLeft
Qt.RightButton  
Qt.BottomDockWidgetArea
Qt.QueuedConnection

# ✅ New (works everywhere)
Qt.AlignmentFlag.AlignLeft
Qt.MouseButton.RightButton
Qt.DockWidgetArea.BottomDockWidgetArea  
Qt.ConnectionType.QueuedConnection
```

### Common Mappings

| Old Shorthand | Fully Qualified Path |
|---------------|---------------------|
| `Qt.LeftDockWidgetArea` | `Qt.DockWidgetArea.LeftDockWidgetArea` |
| `Qt.RightDockWidgetArea` | `Qt.DockWidgetArea.RightDockWidgetArea` |
| `Qt.TopDockWidgetArea` | `Qt.DockWidgetArea.TopDockWidgetArea` |
| `Qt.BottomDockWidgetArea` | `Qt.DockWidgetArea.BottomDockWidgetArea` |
| `Qt.AllDockWidgetAreas` | `Qt.DockWidgetArea.AllDockWidgetAreas` |
| `Qt.TopLeftCorner` | `Qt.Corner.TopLeftCorner` |
| `Qt.TopRightCorner` | `Qt.Corner.TopRightCorner` |
| `Qt.BottomLeftCorner` | `Qt.Corner.BottomLeftCorner` |
| `Qt.BottomRightCorner` | `Qt.Corner.BottomRightCorner` |
| `Qt.QueuedConnection` | `Qt.ConnectionType.QueuedConnection` |
| `Qt.WaitCursor` | `Qt.CursorShape.WaitCursor` |
| `Qt.ControlModifier` | `Qt.KeyboardModifier.ControlModifier` |

## Implementation Plan

1. Update `src/app/ui_manager.py` - dock widget areas and corners
2. Update `src/app/main.py` - connection types and cursor shapes
3. Update `src/gui/**/*.py` - all Qt enum usage
4. Remove PySide6 limitation documentation (no longer needed)

## Benefits

- ✅ Eliminates ~600 false positive errors
- ✅ Aligns with PySide6 6.4+ best practices
- ✅ Future-proof (official recommendation)
- ✅ No runtime behavior change
