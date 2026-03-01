"""Table of Contents Widget Module.

Provides a widget to display a generated table of contents
and emit signals when an item is clicked to navigate to it.
"""

import logging
from typing import List, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.theme_manager import ThemeManager

logger = logging.getLogger(__name__)


class TOCWidget(QWidget):
    """Table of Contents widget displaying a list of headers.

    Emits a `header_clicked` signal with the block position
    when an item in the list is clicked.
    """

    header_clicked = Signal(int)  # Emits block position

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initializes the TOCWidget."""
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.list_widget = QListWidget()
        self.list_widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.list_widget.setCursor(Qt.CursorShape.PointingHandCursor)
        self.list_widget.itemClicked.connect(self._on_item_clicked)

        layout.addWidget(self.list_widget)

        self._apply_style()
        ThemeManager().theme_changed.connect(self._on_theme_changed)

    def _apply_style(self) -> None:
        """Applies theme styling to the list widget."""
        theme = ThemeManager().get_theme()
        surface = theme.get("surface", "#2B2B2B")
        text = theme.get("text_main", "#E0E0E0")
        border = theme.get("border", "#454545")
        primary = theme.get("primary", "#FF9900")

        self.list_widget.setStyleSheet(
            f"""
            QListWidget {{
                background-color: {surface};
                color: {text};
                border: 1px solid {border};
                border-radius: 4px;
                padding: 4px;
            }}
            QListWidget::item {{
                padding: 4px;
                border-radius: 3px;
            }}
            QListWidget::item:hover {{
                background-color: {border};
            }}
            QListWidget::item:selected {{
                background-color: {primary};
                color: {surface};
            }}
        """
        )

    def _on_theme_changed(self, theme_data: dict) -> None:
        """Handles theme changes."""
        self._apply_style()

    def update_headings(self, headings: List[Tuple[int, str, int]]) -> None:
        """Updates the table of contents with new headings.

        Args:
            headings: List of tuples (level, text, block_position).
                     level is 1, 2, or 3.
        """
        self.list_widget.clear()

        for level, text, pos in headings:
            # Create indentation based on heading level (h1=0, h2=2, h3=4 spaces)
            indent = "  " * max(0, level - 1)
            display_text = f"{indent}{text}"

            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, pos)

            # Optionally format H1 to be slightly bolder
            if level == 1:
                font = item.font()
                font.setBold(True)
                item.setFont(font)

            self.list_widget.addItem(item)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        """Handles item clicks and emits the block position."""
        pos = item.data(Qt.ItemDataRole.UserRole)
        # Type check to ensure it's an int in case it's somehow None
        if isinstance(pos, int):
            self.header_clicked.emit(pos)
