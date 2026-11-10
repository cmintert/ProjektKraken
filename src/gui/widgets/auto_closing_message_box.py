"""Auto-Closing Message Box Module.

Provides a QMessageBox that automatically closes after a specified timeout.
Used for transient notifications like toast messages.
"""

import logging
from typing import Optional

import shiboken6
from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import QMessageBox, QWidget

from src.gui.ui_constants import COMPLETION_FEEDBACK_TIMEOUT_MS

logger = logging.getLogger(__name__)


class AutoClosingMessageBox(QMessageBox):
    """A QMessageBox that closes itself after a specified timeout."""

    @classmethod
    def notify(cls, parent: QWidget, title: str, text: str) -> "AutoClosingMessageBox":
        """Present routine completion without blocking or activating a window.

        Reuse one parent-owned notification so rapid completions do not stack.
        Errors and decisions use their existing acknowledged dialog paths.
        """
        parent = parent.window()
        popup = parent.findChild(
            cls,
            "completionNotification",
            options=Qt.FindChildOption.FindDirectChildrenOnly,
        )
        if popup is None:
            popup = cls(title, text, COMPLETION_FEEDBACK_TIMEOUT_MS, parent=parent)
            popup.setObjectName("completionNotification")
            popup.setWindowModality(Qt.WindowModality.NonModal)
            popup.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
            popup.setTextFormat(Qt.TextFormat.PlainText)
        popup.setWindowTitle(title)
        popup.setText(text)
        if not popup.isVisible():
            popup.show()
        # Arm explicitly after presentation rather than depending on Qt's
        # platform-specific Show-event delivery. Only a new notice resets it.
        popup.timer.start(COMPLETION_FEEDBACK_TIMEOUT_MS)
        logger.info(
            "Completion notification shown: %s; timeout_ms=%d",
            title,
            COMPLETION_FEEDBACK_TIMEOUT_MS,
        )
        return popup

    def __init__(
        self,
        title: str,
        text: str,
        timeout_ms: int = 1000,
        icon: QMessageBox.Icon = QMessageBox.Icon.Information,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialize the message box.

        Args:
            title: Window title.
            text: Message text.
            timeout_ms: Timeout in milliseconds before closing.
            icon: Icon to display.
            parent: Parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setText(text)
        self.setIcon(icon)
        self._timeout_ms = timeout_ms
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._expire)

        # QMessageBox often requires at least one button to display correctly as a
        # modal dialog. We add OK and hide it to maintain the "toast" look.
        self.setStandardButtons(QMessageBox.StandardButton.Ok)
        ok_button = self.button(QMessageBox.StandardButton.Ok)
        if ok_button:
            ok_button.hide()

        # Center on parent if available
        if parent:
            self.setWindowModality(Qt.WindowModality.WindowModal)

    def showEvent(self, event: QShowEvent) -> None:
        """Starts the auto-close timer when the dialog is shown."""
        super().showEvent(event)
        # Use an explicit timer object as a child of the dialog for maximum
        # reliability in modal loops on Windows.
        # Repeated Show events within one presentation must not postpone expiry.
        if not self.timer.isActive():
            self.timer.start(self._timeout_ms)

    @Slot()
    def _expire(self) -> None:
        """Hide the transient surface before completing its dialog lifecycle."""
        self.timer.stop()
        title = self.windowTitle()
        self.hide()
        if shiboken6.isValid(self):
            self.accept()
        logger.info("Completion notification expired: %s", title)
