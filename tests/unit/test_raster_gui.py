"""GUI (pytest-qt) tests for raster editing tools.

Tests that the RasterEditTool correctly interacts with the scene via
mouse events and that RasterLayerItem / MapGraphicsView respond as expected.

Requires QT_QPA_PLATFORM=offscreen.
"""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QGraphicsPixmapItem

from src.gui.widgets.map.map_data_buffer import ColorEntry, ColorMap, MapDataBuffer
from src.gui.widgets.map.map_graphics_view import MapGraphicsView
from src.gui.widgets.map.raster_edit_tool import RasterEditMode
from src.gui.widgets.map.raster_layer_item import RasterLayerItem

# ── Helpers ────────────────────────────────────────────────────────────


def _make_view(qtbot, width: int = 200, height: int = 200) -> MapGraphicsView:
    """Create a MapGraphicsView with a synthetic pixmap loaded."""
    view = MapGraphicsView()
    qtbot.addWidget(view)

    img = QImage(width, height, QImage.Format.Format_RGB32)
    img.fill(Qt.GlobalColor.white)
    pixmap = QPixmap.fromImage(img)

    view.pixmap_item = QGraphicsPixmapItem(pixmap)
    view.scene.addItem(view.pixmap_item)
    view.coord_system.set_scene_rect(QRectF(0, 0, width, height))
    return view


def _make_raster_item(
    view: MapGraphicsView,
    node_id: str = "n1",
    buf_w: int = 64,
    buf_h: int = 64,
) -> tuple[RasterLayerItem, MapDataBuffer]:
    """Create a RasterLayerItem in the view's scene and register it."""
    buf = MapDataBuffer(width=buf_w, height=buf_h, default_value=0)
    cmap = ColorMap(
        type="gradient",
        gradient_start="#00000000",
        gradient_end="#FF000080",
    )
    scene_rect = QRectF(0, 0, 200, 200)
    item = RasterLayerItem(buffer=buf, color_map=cmap, scene_rect=scene_rect, node_id=node_id)
    view.scene.addItem(item)
    view._raster_items[node_id] = item
    return item, buf


# ── Edit mode activation ────────────────────────────────────────────────


class TestRasterEditModeActivation:
    """start_raster_editing / stop_raster_editing must update tool state."""

    def test_start_editing_activates_tool(self, qtbot) -> None:
        view = _make_view(qtbot)
        _make_raster_item(view, node_id="n1")

        view.start_raster_editing("n1")

        assert view._raster_edit_tool.is_active
        assert view._raster_edit_tool.active_node_id == "n1"

    def test_stop_editing_deactivates_tool(self, qtbot) -> None:
        view = _make_view(qtbot)
        _make_raster_item(view, node_id="n1")

        view.start_raster_editing("n1")
        view.stop_raster_editing()

        assert not view._raster_edit_tool.is_active
        assert view._raster_edit_tool.active_node_id is None

    def test_drag_mode_is_no_drag_during_editing(self, qtbot) -> None:
        view = _make_view(qtbot)
        _make_raster_item(view, node_id="n1")

        view.start_raster_editing("n1")

        from PySide6.QtWidgets import QGraphicsView
        assert view.dragMode() == QGraphicsView.DragMode.NoDrag

    def test_stop_restores_scroll_drag(self, qtbot) -> None:
        view = _make_view(qtbot)
        _make_raster_item(view, node_id="n1")

        view.start_raster_editing("n1")
        view.stop_raster_editing()

        from PySide6.QtWidgets import QGraphicsView
        assert view.dragMode() == QGraphicsView.DragMode.ScrollHandDrag


# ── Brush stroke changes buffer ─────────────────────────────────────────


class TestBrushStrokeUpdatesBuffer:
    """A mouse press+release in brush mode must modify the buffer."""

    def test_brush_press_paints_center(self, qtbot) -> None:
        view = _make_view(qtbot)
        item, buf = _make_raster_item(view, node_id="n2")

        tool = view._raster_edit_tool
        tool.mode = RasterEditMode.BRUSH
        tool.brush_size = 10
        tool.paint_value = 99

        view.start_raster_editing("n2")

        # Simulate mouse press at scene center (100,100)
        center = QPointF(100.0, 100.0)
        tool.handle_mouse_press(center)
        tool.handle_mouse_release(center)

        # Center pixel (0.5, 0.5) should be painted
        val = buf.get_value_at(0.5, 0.5)
        assert val == 99

    def test_brush_drag_accumulates_dirty_region(self, qtbot) -> None:
        view = _make_view(qtbot)
        item, buf = _make_raster_item(view, node_id="n3")

        tool = view._raster_edit_tool
        tool.mode = RasterEditMode.BRUSH
        tool.brush_size = 4
        tool.paint_value = 7

        view.start_raster_editing("n3")

        # Drag from (20,100) to (180,100)
        tool.handle_mouse_press(QPointF(20.0, 100.0))
        tool.handle_mouse_move(QPointF(100.0, 100.0))
        tool.handle_mouse_move(QPointF(180.0, 100.0))
        tool.handle_mouse_release(QPointF(180.0, 100.0))

        # Left pixel should be painted
        assert buf.get_value_at(0.1, 0.5) == 7
        # Right pixel should be painted
        assert buf.get_value_at(0.9, 0.5) == 7


# ── Fill tool ─────────────────────────────────────────────────────────


class TestFillToolUpdatesBuffer:
    """Fill mode must flood-fill on mouse press."""

    def test_fill_paints_entire_uniform_buffer(self, qtbot) -> None:
        view = _make_view(qtbot)
        item, buf = _make_raster_item(view, node_id="n4")

        tool = view._raster_edit_tool
        tool.mode = RasterEditMode.FILL
        tool.paint_value = 55

        view.start_raster_editing("n4")
        tool.handle_mouse_press(QPointF(100.0, 100.0))

        import numpy as np
        assert np.all(buf.data == 55)


# ── Sample tool ───────────────────────────────────────────────────────


class TestSampleToolProbesValue:
    """Sample tool must emit raster_value_probed with correct value."""

    def test_sample_emits_probed_signal(self, qtbot) -> None:
        view = _make_view(qtbot)
        item, buf = _make_raster_item(view, node_id="n5")

        # Pre-paint a specific value
        buf.set_value_at(0.5, 0.5, 1234)

        tool = view._raster_edit_tool
        tool.mode = RasterEditMode.SAMPLE

        view.start_raster_editing("n5")

        probed_values: list[int] = []
        view.raster_value_probed.connect(
            lambda nid, val, x, y: probed_values.append(val)
        )

        tool.handle_mouse_press(QPointF(100.0, 100.0))

        assert probed_values, "raster_value_probed signal not emitted"
        assert probed_values[0] == 1234


# ── RasterLayerItem display ───────────────────────────────────────────


class TestRasterLayerItemDisplay:
    """RasterLayerItem must render to a valid pixmap."""

    def test_update_display_gradient_not_null(self, qtbot) -> None:
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()

        buf = MapDataBuffer(width=32, height=32, default_value=32768)
        cmap = ColorMap(
            type="gradient",
            gradient_start="#000000FF",
            gradient_end="#FF0000FF",
        )
        scene_rect = QRectF(0, 0, 100, 100)
        item = RasterLayerItem(buffer=buf, color_map=cmap, scene_rect=scene_rect)

        pixmap = item.pixmap()
        assert not pixmap.isNull()
        assert pixmap.width() == 100
        assert pixmap.height() == 100

    def test_update_display_palette_colors_pixels(self, qtbot) -> None:
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()

        buf = MapDataBuffer(width=4, height=4, default_value=1)
        cmap = ColorMap(
            type="palette",
            entries=[ColorEntry(value=1, color="#FF0000")],
        )
        scene_rect = QRectF(0, 0, 4, 4)
        item = RasterLayerItem(buffer=buf, color_map=cmap, scene_rect=scene_rect)

        px = item.pixmap()
        assert not px.isNull()
        # At least one pixel should be red-ish
        img = px.toImage()
        r, g, b, a = img.pixelColor(2, 2).getRgb()
        assert r > 200 and g < 50 and b < 50, f"Expected red pixel, got ({r},{g},{b})"

    def test_scene_rect_property(self) -> None:
        buf = MapDataBuffer(width=8, height=8, default_value=0)
        cmap = ColorMap()
        rect = QRectF(10, 20, 100, 50)
        item = RasterLayerItem(buffer=buf, color_map=cmap, scene_rect=rect)
        assert item.scene_rect == rect

    def test_update_region_does_not_crash(self, qtbot) -> None:
        from PySide6.QtWidgets import QApplication
        buf = MapDataBuffer(width=32, height=32, default_value=0)
        cmap = ColorMap(
            type="gradient",
            gradient_start="#000000FF",
            gradient_end="#FFFFFFFF",
        )
        scene_rect = QRectF(0, 0, 64, 64)
        item = RasterLayerItem(buffer=buf, color_map=cmap, scene_rect=scene_rect)

        # Paint something and do a partial update
        buf.paint_brush(0.5, 0.5, radius_px=5, value=1000, falloff=0.0)
        item.update_region((12, 12, 19, 19))  # should not raise
        QApplication.processEvents()

        assert not item.pixmap().isNull()


# ── Escape key exits editing ───────────────────────────────────────────


class TestEscapeKeyExitsEditing:
    def test_escape_stops_editing(self, qtbot) -> None:
        view = _make_view(qtbot)
        _make_raster_item(view, node_id="n6")

        view.start_raster_editing("n6")
        assert view._raster_edit_tool.is_active

        consumed = view._raster_edit_tool.handle_key_escape()
        assert consumed
        assert not view._raster_edit_tool.is_active

    def test_escape_no_op_when_not_editing(self, qtbot) -> None:
        view = _make_view(qtbot)
        consumed = view._raster_edit_tool.handle_key_escape()
        assert not consumed
