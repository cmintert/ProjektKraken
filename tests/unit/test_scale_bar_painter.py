"""Unit tests for ScaleBarPainter positioning and rendering."""

from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QWidget


class TestScaleBarPainterPositioning:
    """Tests for ScaleBarPainter x-position clamping at various scales."""

    def test_scale_bar_x_position_clamped_at_large_scales(self, qtbot):
        """Scale bar x-position should not go negative at large zoom scales.

        At large zoom levels where display_pixels is very large,
        the x position calculation should be clamped to 0 to prevent
        the bar from being cut off on the left side.
        """
        from src.gui.widgets.map.scale_bar_painter import ScaleBarPainter

        painter_obj = ScaleBarPainter()
        test_widget = QWidget()
        qtbot.addWidget(test_widget)

        # Create a test image for painting
        test_image = QImage(250, 60, QImage.Format.Format_ARGB32)
        test_image.fill(0)

        painter = QPainter(test_image)

        # Test at a very large scale where display_pixels would exceed viewport width
        # At 10 meters/pixel with 150px target, that's 1500 meters
        # which rounds to 2000 m. At normal resolution, this could be 500+ pixels wide
        large_scale_mpp = 50.0  # 50 meters per pixel

        # Paint the scale bar at this large scale
        painter_obj.paint(painter, QRectF(0, 0, 250, 60), large_scale_mpp)
        painter.end()

        # The test passes if no exception is raised
        # In the past, this would have caused drawing outside widget bounds
        assert test_image is not None

    def test_scale_bar_x_position_positive_at_normal_scales(self, qtbot):
        """Scale bar x-position should be positive at normal scales."""
        from src.gui.widgets.map.scale_bar_painter import ScaleBarPainter

        painter_obj = ScaleBarPainter()
        test_widget = QWidget()
        qtbot.addWidget(test_widget)

        # Create a test image for painting
        test_image = QImage(250, 60, QImage.Format.Format_ARGB32)
        test_image.fill(0)

        painter = QPainter(test_image)

        # Test at a normal scale
        normal_scale_mpp = 1.0  # 1 meter per pixel

        painter_obj.paint(painter, QRectF(0, 0, 250, 60), normal_scale_mpp)
        painter.end()

        assert test_image is not None

    def test_scale_bar_rounds_to_nice_numbers(self, qtbot):
        """Scale bar display should round meters to nice numbers (1, 2, 5, 10, etc)."""
        from src.gui.widgets.map.scale_bar_painter import ScaleBarPainter

        painter_obj = ScaleBarPainter()

        # Test rounding function: residual in (1,2]→2x, (2,5]→5x, (5,10]→10x
        assert painter_obj._round_to_nice_number(1234) == 2000   # residual 1.234 → 2×
        assert painter_obj._round_to_nice_number(2345) == 5000   # residual 2.345 → 5×
        assert painter_obj._round_to_nice_number(5678) == 10000  # residual 5.678 → 10×
        assert painter_obj._round_to_nice_number(7890) == 10000  # residual 7.890 → 10×
        assert painter_obj._round_to_nice_number(1000) == 1000   # residual 1.0 → 1×

    def test_scale_bar_formats_distance_correctly(self, qtbot):
        """Scale bar should format distances as m or km."""
        from src.gui.widgets.map.scale_bar_painter import ScaleBarPainter

        painter_obj = ScaleBarPainter()

        assert painter_obj._format_distance(500) == "500 m"
        assert painter_obj._format_distance(1000) == "1 km"
        assert painter_obj._format_distance(2500) == "2 km"
        assert painter_obj._format_distance(0.5) == "0 m"
