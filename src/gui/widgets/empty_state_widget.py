"""
Empty State Widget Module.

Provides a simple widget for displaying empty state messages.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from src.gui.utils.style_helper import StyleHelper


class EmptyStateWidget(QLabel):
    """
    A QLabel subclass for displaying empty state messages.

    Applies consistent styling from StyleHelper and is hidden by default.
    Use show() to display when no data is available.
    """

    def __init__(self, message: str = "No Items", parent=None) -> None:
        """
        Initializes the empty state widget.

        Args:
            message: The message to display in the empty state.
            parent: The parent widget, if any.
        """
        super().__init__(message, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(StyleHelper.get_empty_state_style())
        self.hide()  # Hidden by default

    def set_message(self, message: str) -> None:
        """
        Updates the empty state message.

        Args:
            message: The new message to display.
        """
        self.setText(message)
