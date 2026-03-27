"""Scale Bar Painter Module.

Handles the calculation and rendering of a GIS-style scale bar.
"""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetrics, QPainter, QPen


class ScaleBarPainter:
    """Helper class to render a map scale bar."""

    # Geometry constants
    PADDING_PX = 5  # Padding around background rect
    MARGIN_PX = 20  # Distance from viewport edge to scale bar
    MIN_BAR_WIDTH = 60  # Minimum scale bar display width in pixels
    MAX_RECT_WIDTH = 240  # Max width for background rect in 250px overlay (250 - 2*5)

    def __init__(self) -> None:
        """Initialize the scale bar painter."""
        self.font = QFont("Sans Serif", 9)
        self.font.setBold(True)
        self.pen_black = QPen(Qt.GlobalColor.black, 2)
        self.pen_white = QPen(Qt.GlobalColor.white, 2)
        self.brush_white = QBrush(
            QColor(255, 255, 255, 180)
        )  # Semi-transparent background

    def paint(
        self,
        painter: QPainter,
        viewport_rect: QRectF,
        meters_per_pixel: float,
    ) -> None:
        """Draws the scale bar overlay.

        Args:
            painter: The viewport painter.
            viewport_rect: Visible area of the view.
            meters_per_pixel: Current scale resolution.

        """
        if meters_per_pixel <= 0:
            return

        # Target width for the scale bar in pixels (e.g., ~150px)
        target_pixel_width = 150.0
        target_meters = target_pixel_width * meters_per_pixel

        # Find the nearest nice number (1, 2, 5, 10, etc.)
        display_meters = self._round_to_nice_number(target_meters)
        display_pixels = display_meters / meters_per_pixel

        # Format label
        label = self._format_distance(display_meters)

        # Layout
        bar_height = 6
        text_height = 20

        # Position: Bottom Right
        # rect_width includes padding: display_pixels + 10 (5px padding each side in draw call)
        rect_width = max(display_pixels, self.MIN_BAR_WIDTH) + 10
        rect_height = bar_height + text_height + 5

        # Cap rect_width to fit within the overlay bounds.
        # The background rect is drawn at (x-5, …, rect_width+10, …),
        # so with x >= 5, the right edge is at x + rect_width + 5.
        # To stay within viewport_width, we need rect_width <= MAX_RECT_WIDTH.
        rect_width = min(rect_width, self.MAX_RECT_WIDTH)
        display_pixels = min(display_pixels, rect_width - 10)

        x = max(self.PADDING_PX, viewport_rect.width() - rect_width - self.MARGIN_PX)
        y = viewport_rect.height() - rect_height - self.MARGIN_PX

        # Draw background container
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.brush_white)
        painter.drawRoundedRect(
            QRectF(x - 5, y - 5, rect_width + 10, rect_height + 10), 4, 4
        )

        # Draw Bar (Black line with ticks)
        bar_y = y + text_height + bar_height
        bar_x_start = x + (rect_width - display_pixels) / 2
        bar_x_end = bar_x_start + display_pixels

        painter.setPen(self.pen_black)
        # Horizontal line
        painter.drawLine(int(bar_x_start), int(bar_y), int(bar_x_end), int(bar_y))
        # Left tick
        painter.drawLine(
            int(bar_x_start), int(bar_y), int(bar_x_start), int(bar_y - bar_height)
        )
        # Right tick
        painter.drawLine(
            int(bar_x_end), int(bar_y), int(bar_x_end), int(bar_y - bar_height)
        )

        # Draw Text
        painter.setFont(self.font)
        painter.setPen(Qt.GlobalColor.black)
        fm = QFontMetrics(self.font)
        text_width = fm.horizontalAdvance(label)
        text_x = bar_x_start + (display_pixels - text_width) / 2

        painter.drawText(int(text_x), int(y + fm.ascent()), label)

    def _round_to_nice_number(self, num: float) -> float:
        """Rounds a number to the nearest 1, 2, 5 magnitude."""
        import math

        if num == 0:
            return 0

        magnitude = 10 ** math.floor(math.log10(num))
        residual = num / magnitude

        if residual > 5:
            return 10 * magnitude
        elif residual > 2:
            return 5 * magnitude
        elif residual > 1:
            return 2 * magnitude
        else:
            return 1 * magnitude

    def _format_distance(self, meters: float) -> str:
        """Formats meters into m or km string."""
        return f"{meters / 1000:.0f} km" if meters >= 1000 else f"{meters:.0f} m"
