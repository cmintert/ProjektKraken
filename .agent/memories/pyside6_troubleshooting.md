# PySide6/Qt Troubleshooting Patterns

## Signals on Non-QObject Classes

### Problem
When defining `Signal` attributes on a class that inherits from `QGraphicsPathItem` (or other non-QObject Qt classes), you get:
```
AttributeError: 'PySide6.QtCore.Signal' object has no attribute 'connect'
```

### Cause
PySide6/PyQt Signals **only work on classes that inherit from `QObject`**. Many `QGraphics*` classes like `QGraphicsPathItem`, `QGraphicsRectItem`, etc. do NOT inherit from `QObject`.

### Solution
Use multiple inheritance with `QObject` **first**, and call both `__init__` methods explicitly:

```python
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QGraphicsPathItem

class MyPathItem(QObject, QGraphicsPathItem):  # QObject MUST be first
    my_signal = Signal(str, float)
    
    def __init__(self, parent=None):
        QObject.__init__(self)  # Initialize QObject first
        QGraphicsPathItem.__init__(self, parent)  # Then QGraphicsPathItem
```

### Alternative
Use `QGraphicsObject` instead if you don't need specific `QGraphicsPathItem` features. `QGraphicsObject` already provides a QObject+QGraphicsItem combination.

### Related Files
- `src/gui/widgets/map/motion_path_item.py` - Uses this pattern for `MotionPathItem`
