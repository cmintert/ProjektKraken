"""Keyframe Label Item Module.

Provides the KeyframeLabelItem class for high-contrast labels on trajectory keyframes.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPen
from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsSimpleTextItem

from src.app import constants


class KeyframeLabelItem(QGraphicsRectItem):
    """A high-contrast label for a keyframe (date/time).

    Wraps a text item in a semi-transparent background rect (pill) for readability.
    Ignores transformations to remain a constant size on screen.
    """

    def __init__(self, text: str, marker_id: str = "", parent=None):
        super().__init__(parent)

        # Store the marker ID that owns this keyframe label
        self.marker_id = marker_id

        # Style the background (self)
        self.setPen(QPen(Qt.PenStyle.NoPen))

        # Initial colors (will be updated by theme)
        bg_color = QColor(constants.MAP_LABEL_BG_COLOR)
        bg_color.setAlpha(constants.MAP_LABEL_BG_OPACITY)
        self.setBrush(QBrush(bg_color))

        # Text Item
        self._text_item = QGraphicsSimpleTextItem(text, self)

        font = QFont(
            constants.MAP_LABEL_FONT_FAMILY,
            constants.MAP_KEYFRAME_LABEL_MIN_SIZE_PT,  # Start small
        )
        self._text_item.setFont(font)
        self._text_item.setBrush(QBrush(QColor(constants.MAP_LABEL_TEXT_COLOR)))

        # Flags
        # Important: The label itself ignores transformations to stay readable
        self.setFlag(
            QGraphicsRectItem.GraphicsItemFlag.ItemIgnoresTransformations, True
        )

        self._update_layout()

    def set_text(self, text: str) -> None:
        """Update the label text."""
        self._text_item.setText(text)
        self._update_layout()

    def _update_layout(self) -> None:
        """Recalculate background rect based on text size."""
        rect = self._text_item.boundingRect()
        padding_x = constants.MAP_LABEL_PADDING_X
        padding_y = constants.MAP_LABEL_PADDING_Y

        width = rect.width() + (padding_x * 2)
        height = rect.height() + (padding_y * 2)

        # Center text inside rect
        self._text_item.setPos(padding_x, padding_y)

        # Set rect geometry
        # Center the whole group on its position (0,0) geometry-wise if we want anchors
        # But usually keyframe labels are offset.
        # Let's keep the rect starting at 0,0 locally, and the caller offsets it.
        self.setRect(0, 0, width, height)

    def update_theme(self, theme: dict) -> None:
        """Updates the label styling based on the current theme."""
        # Background
        bg_color = QColor(theme.get("surface", constants.MAP_LABEL_BG_COLOR))
        bg_color.setAlpha(constants.MAP_LABEL_BG_OPACITY + 40)  # Ensure contrast
        self.setBrush(QBrush(bg_color))

        # Text
        text_color = QColor(theme.get("text_main", constants.MAP_LABEL_TEXT_COLOR))
        self._text_item.setBrush(QBrush(text_color))
