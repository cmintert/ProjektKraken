"""Tag Pill Widget Module.

Provides a rounded rectangular component for displaying a tag with a delete button.
"""

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QStyle,
    QStyleOption,
    QToolButton,
    QWidget,
)

from src.gui.utils.style_helper import StyleHelper


class TagPill(QFrame):
    """A rounded rectangular widget representing a tag.

    Displays the tag text and a small 'x' button to remove it.

    Signals:
        deleted(str): Emitted when the delete button is clicked, with the tag text.
    """

    deleted = Signal(str)

    def __init__(
        self,
        text: str,
        base_color: Optional[str] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initializes the TagPill.

        Args:
            text: The text to display on the pill.
            base_color: Optional hex color string for the pill's theme.
                        If None, uses accent_secondary from current theme.
            parent: The parent widget.
        """
        super().__init__(parent)
        self.text = text
        self.base_color = base_color

        # Enforce fixed height for consistent pill shape
        self.setFixedHeight(26)

        # Enable QSS background support
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("TagPill")

        self._setup_ui()
        self._apply_style()

    def _setup_ui(self) -> None:
        """Sets up the layout and sub-widgets."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 4, 2)
        layout.setSpacing(4)

        self.label = QLabel(self.text)
        layout.addWidget(self.label)

        self.btn_delete = QToolButton()
        self.btn_delete.setObjectName("TagPillDeleteButton")
        self.btn_delete.setText("✕")
        self.btn_delete.setCursor(Qt.PointingHandCursor)
        self.btn_delete.setToolTip(f"Remove tag: {self.text}")
        self.btn_delete.clicked.connect(self._on_delete_clicked)
        # Note: Styling is now handled in StyleHelper via get_tag_pill_style
        layout.addWidget(self.btn_delete)

    def _apply_style(self) -> None:
        """Applies the pill styling using StyleHelper."""
        style = StyleHelper.get_pill_style(
            object_name="TagPill",
            base_color=self.base_color,
            has_delete=True,
            height=26,
        )
        self.setStyleSheet(style)

    def _on_delete_clicked(self) -> None:
        """Handles the delete button click."""
        self.deleted.emit(self.text)

    def paintEvent(self, event) -> None:
        """Ensure QSS styling (background, border-radius) is rendered correctly."""
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, p, self)


# Add Qt namespace import at the top
