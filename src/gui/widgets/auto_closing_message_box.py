"""Auto-Closing Message Box Module.

Provides a QMessageBox that automatically closes after a specified timeout.
Used for transient notifications like toast messages.
"""

from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QMessageBox, QWidget


class AutoClosingMessageBox(QMessageBox):
    """A QMessageBox that closes itself after a specified timeout."""

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

        # QMessageBox often requires at least one button to display correctly as a
        # modal dialog. We add OK and hide it to maintain the "toast" look.
        self.setStandardButtons(QMessageBox.StandardButton.Ok)
        ok_button = self.button(QMessageBox.StandardButton.Ok)
        if ok_button:
            ok_button.hide()

        # Center on parent if available
        if parent:
            self.setWindowModality(Qt.WindowModality.WindowModal)

    def showEvent(self, event) -> None:
        """Starts the auto-close timer when the dialog is shown."""
        super().showEvent(event)
        # Use an explicit timer object as a child of the dialog for maximum
        # reliability in modal loops on Windows.
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.accept)
        self.timer.start(self._timeout_ms)
