"""Pre-teardown notification for dialogs that can own the Help companion."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDialog


class HelpAwareDialog(QDialog):
    """Let application orchestration detach Help before dialog completion."""

    preparing_to_close = Signal()

    def done(self, result: int) -> None:
        """Notify before Qt hides or deletes this dialog and its children."""
        self.preparing_to_close.emit()
        super().done(result)
