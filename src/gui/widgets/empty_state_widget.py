"""Empty State Widget Module.

Provides an actionable empty state widget with title, description, and optional
action buttons to guide users when a view has no data.
"""

from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.gui.utils.style_helper import StyleHelper


class EmptyStateWidget(QWidget):
    """Composite widget for displaying actionable empty state messages.

    Presents a centered title, description, and optional action buttons to cure
    "Blank Page Syndrome" by providing users with immediate, clickable actions
    when a view has no data.

    Hidden by default. Call show() to display when no data is available.
    """

    def __init__(
        self,
        title: str = "No Items",
        description: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initializes the empty state widget.

        Args:
            title: The headline message to display.
            description: A secondary description shown below the title.
            parent: The parent widget, if any.

        """
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        # Main layout centered vertically and horizontally
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(8)

        # Title label
        self._title_label = QLabel(title)
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_label.setWordWrap(True)
        self._apply_title_style()
        main_layout.addWidget(self._title_label)

        # Description label
        self._description_label = QLabel(description)
        self._description_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._description_label.setWordWrap(True)
        self._description_label.setStyleSheet(StyleHelper.get_empty_state_style())
        if not description:
            self._description_label.hide()
        main_layout.addWidget(self._description_label)

        # Button container
        self._button_layout = QHBoxLayout()
        self._button_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._button_layout.setSpacing(8)
        main_layout.addLayout(self._button_layout)

        self.hide()  # Hidden by default

    def _apply_title_style(self) -> None:
        """Applies theme-aware styling to the title label."""
        from src.core.theme_manager import ThemeManager

        theme = ThemeManager().get_theme()
        self._title_label.setStyleSheet(
            f"color: {theme['text_main']}; font-size: 14pt; font-weight: bold;"
        )

    def set_message(self, message: str) -> None:
        """Updates the empty state title message.

        Args:
            message: The new title message to display.

        """
        self._title_label.setText(message)

    def set_description(self, description: str) -> None:
        """Updates the empty state description.

        Args:
            description: The new description to display.

        """
        self._description_label.setText(description)
        self._description_label.setVisible(bool(description))

    def add_action(
        self, text: str, callback: Callable[[], None], primary: bool = False
    ) -> QPushButton:
        """Adds an action button to the empty state.

        Creates a QPushButton with primary (accent) or secondary (ghost) styling,
        connects its clicked signal to the provided callback, and adds it to the
        button layout.

        Args:
            text: The button label text.
            callback: The callable to invoke when the button is clicked.
            primary: If True, applies primary accent styling; otherwise ghost styling.

        Returns:
            QPushButton: The created button instance.

        """
        button = QPushButton(text)
        if primary:
            button.setStyleSheet(StyleHelper.get_primary_button_style())
        else:
            button.setStyleSheet(StyleHelper.get_secondary_button_style())
        button.clicked.connect(callback)
        self._button_layout.addWidget(button)
        return button
