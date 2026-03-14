"""Scale Bar Overlay Widget.

A transparent viewport-space widget that renders the scale bar without
triggering full-scene repaints.  This allows the graphics view to use
``MinimalViewportUpdate`` instead of ``FullViewportUpdate``.
"""

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget

from src.gui.widgets.map.scale_bar_painter import ScaleBarPainter

# Fixed overlay dimensions — generous enough for the scale bar at any zoom.
_OVERLAY_WIDTH = 250
_OVERLAY_HEIGHT = 60
_MARGIN = 20


class ScaleBarOverlay(QWidget):
    """Transparent overlay widget that paints the map scale bar.

    Intended to be parented to the ``QGraphicsView.viewport()`` so it
    floats in device coordinates without participating in the scene's
    dirty-region tracking.

    Args:
        parent: The viewport widget.
    """

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._painter = ScaleBarPainter()
        self._meters_per_pixel: float = 0.0
        self.setFixedSize(_OVERLAY_WIDTH, _OVERLAY_HEIGHT)
        self.reposition(parent.size())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_scale(self, meters_per_pixel: float) -> None:
        """Set the current resolution and trigger a repaint.

        Args:
            meters_per_pixel: Metres per screen pixel at the current zoom.
        """
        if meters_per_pixel != self._meters_per_pixel:
            self._meters_per_pixel = meters_per_pixel
            self.update()

    def reposition(self, parent_size: QSize) -> None:
        """Anchor the overlay to the bottom-right of *parent_size*.

        Args:
            parent_size: The viewport's current size.
        """
        x = parent_size.width() - _OVERLAY_WIDTH - _MARGIN
        y = parent_size.height() - _OVERLAY_HEIGHT - _MARGIN
        self.move(max(0, x), max(0, y))

    # ------------------------------------------------------------------
    # Qt overrides
    # ------------------------------------------------------------------

    def paintEvent(self, event: QPaintEvent) -> None:
        """Delegate painting to :class:`ScaleBarPainter`."""
        if self._meters_per_pixel <= 0:
            return
        painter = QPainter(self)
        self._painter.paint(
            painter,
            QRectF(self.rect()),
            self._meters_per_pixel,
        )
        painter.end()
