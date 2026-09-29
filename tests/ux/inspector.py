"""Test-only Qt control inventory and rendered-widget capture."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QComboBox,
    QDoubleSpinBox,
    QLineEdit,
    QMenu,
    QSlider,
    QSpinBox,
    QWidget,
)


def _interactive(widget: QWidget) -> bool:
    """Count user-level controls once, omitting composite private editors."""
    if isinstance(widget, QLineEdit) and isinstance(widget.parentWidget(), QComboBox):
        return False
    return isinstance(
        widget,
        (
            QAbstractButton,
            QAbstractItemView,
            QComboBox,
            QLineEdit,
            QSlider,
            QSpinBox,
            QDoubleSpinBox,
        ),
    )


def inspect_widget(root: QWidget) -> dict[str, Any]:
    """Record the visible user-level controls and the full widget tree."""
    controls: list[dict[str, Any]] = []

    def visit(widget: QWidget, depth: int) -> dict[str, Any]:
        visible = widget.isVisible()
        enabled = widget.isEnabled()
        label = widget.accessibleName() or widget.objectName()
        if isinstance(widget, QAbstractButton):
            label = widget.text() or label
        elif isinstance(widget, QLineEdit):
            label = widget.placeholderText() or label
        elif isinstance(widget, QComboBox):
            label = widget.currentText() or label
        geometry = widget.geometry()
        entry = {
            "class": type(widget).__name__,
            "object_name": widget.objectName(),
            "label": label,
            "visible": visible,
            "enabled": enabled,
            "interactive": _interactive(widget),
            "geometry": [geometry.x(), geometry.y(), geometry.width(), geometry.height()],
            "depth": depth,
        }
        if visible and enabled and entry["interactive"]:
            controls.append(entry)
        children = widget.findChildren(
            QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly
        )
        entry["children"] = [visit(child, depth + 1) for child in children]
        if isinstance(widget, QMenu) and visible:
            for action in widget.actions():
                if isinstance(action, QAction) and action.isVisible() and action.isEnabled():
                    controls.append({"class": "QAction", "label": action.text(), "depth": depth + 1})
        return entry

    tree = visit(root, 0)
    return {"visible_enabled_controls": len(controls), "controls": controls, "tree": tree}


def capture_widget(root: QWidget, path: Path) -> Path:
    """Save a screenshot of an actually shown Qt widget for review."""
    if not root.isVisible():
        raise ValueError("Show the widget before capturing it")
    path.parent.mkdir(parents=True, exist_ok=True)
    if not root.grab().save(str(path), "PNG"):
        raise OSError(f"Could not capture widget to {path}")
    return path
