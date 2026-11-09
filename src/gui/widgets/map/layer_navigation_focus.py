"""Bounded keyboard-focus handoff from Layers back to map navigation."""

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QApplication, QGraphicsView, QTreeView


class LayerNavigationFocus(QObject):
    """Return Space navigation to the map when leaving the focused Layers tree."""

    def __init__(self, view: QGraphicsView, tree: QTreeView) -> None:
        """Watch the stable view, including when its viewport is replaced."""
        super().__init__(view)
        self._view = view
        self._tree = tree
        view.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Hand off only tree navigation focus; never steal an editor's caret."""
        if (
            watched is self._view
            and event.type() == QEvent.Type.Enter
            and QApplication.mouseButtons() == Qt.MouseButton.NoButton
            and QApplication.focusWidget() in (self._tree, self._tree.viewport())
        ):
            self._view.setFocus(Qt.FocusReason.MouseFocusReason)
        return super().eventFilter(watched, event)
