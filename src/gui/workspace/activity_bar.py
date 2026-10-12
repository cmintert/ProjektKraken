"""Content-sized, uniform navigation buttons for the workspace activity rail."""

from PySide6.QtCore import QEvent, QSize, QTimer
from PySide6.QtWidgets import QToolBar, QToolButton, QWidget

from src.gui.utils.action_label_metrics import intrinsic_action_size


class ActivityBar(QToolBar):
    """Give every activity one shared size derived from the largest label."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        """Retain native actions and keyboard behavior while sizing consistently."""
        super().__init__(title, parent)
        self._size_timer = QTimer(self)
        self._size_timer.setSingleShot(True)
        self._size_timer.timeout.connect(self._size_buttons)

    def event(self, event: QEvent) -> bool:
        """Recompute after label, font, style or action-list changes."""
        result = super().event(event)
        if hasattr(self, "_size_timer") and event.type() in (
            QEvent.Type.ActionAdded,
            QEvent.Type.ActionRemoved,
            QEvent.Type.ActionChanged,
            QEvent.Type.FontChange,
            QEvent.Type.StyleChange,
            QEvent.Type.LayoutRequest,
        ):
            self._size_timer.start(0)
        return result

    def _size_buttons(self) -> None:
        buttons = [
            button
            for action in self.actions()
            if action.isVisible()
            and isinstance(button := self.widgetForAction(action), QToolButton)
        ]
        size = QSize()
        for button in buttons:
            size = size.expandedTo(intrinsic_action_size(button))
        for button in buttons:
            if button.size() != size or button.minimumSize() != size:
                button.setFixedSize(size)
