"""Non-interactive map geometry preview overlay."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsPathItem, QGraphicsScene

from src.core.theme_manager import ThemeManager
from src.gui.constants import MAP_LAYER_Z_UI_OVERLAY


class RegionPreview(QGraphicsPathItem):
    """Show a preview without intercepting map interaction."""

    def __init__(self, scene: QGraphicsScene) -> None:
        """Add the overlay above the feature and editing handles."""
        super().__init__()
        self.setZValue(MAP_LAYER_Z_UI_OVERLAY + 3)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self._filled = False
        scene.addItem(self)

    def show_path(self, path: QPainterPath, *, filled: bool = False) -> None:
        """Show the geometry with the current theme's selection color."""
        self._filled = filled
        self.restyle()
        self.setPath(path)

    def restyle(self) -> None:
        """Use the current theme for an already visible preview."""
        color = QColor(ThemeManager().get_theme()["selection_bg"])
        pen = QPen(color, 3)
        self.setBrush(
            QBrush(color, Qt.BrushStyle.Dense6Pattern) if self._filled else QBrush()
        )
        pen.setCosmetic(True)
        pen.setStyle(Qt.PenStyle.DashLine)
        self.setPen(pen)

    def clear(self) -> None:
        """Remove this preview from the scene."""
        scene = self.scene()
        if scene is not None:
            scene.removeItem(self)
