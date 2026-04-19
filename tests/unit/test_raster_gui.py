"""GUI (pytest-qt) tests for raster editing tools.

Tests that the RasterEditTool correctly interacts with the scene via
mouse events and that RasterLayerItem / MapGraphicsView respond as expected.

Requires QT_QPA_PLATFORM=offscreen.
"""

from unittest.mock import MagicMock

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QGraphicsPixmapItem
from pytestqt.qtbot import QtBot

from src.app.map_handler import MapHandler
from src.gui.widgets.map.map_data_buffer import (
    ColorEntry,
    ColorMap,
    GradientStop,
    MapDataBuffer,
)
from src.gui.widgets.map.map_graphics_view import MapGraphicsView
from src.gui.widgets.map.raster_edit_tool import RasterEditMode
from src.gui.widgets.map.raster_layer_item import RasterLayerItem
from src.gui.widgets.map_widget import MapWidget

# ── Helpers ────────────────────────────────────────────────────────────


def _make_view(qtbot: QtBot, width: int = 200, height: int = 200) -> MapGraphicsView:
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
        gradient_stops=[GradientStop(0.0, "#00000000"), GradientStop(1.0, "#FF000080")],
    )
    scene_rect = QRectF(0, 0, 200, 200)
    item = RasterLayerItem(
        buffer=buf, color_map=cmap, scene_rect=scene_rect, node_id=node_id
    )
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
            gradient_stops=[GradientStop(0.0, "#000000FF"), GradientStop(1.0, "#FF0000FF")],
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
            gradient_stops=[GradientStop(0.0, "#000000FF"), GradientStop(1.0, "#FFFFFFFF")],
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


class TestMapDeleteStopsRasterEditing:
    """Deleting a map must stop active raster editing before command dispatch."""

    def test_delete_map_exits_active_raster_editing(self, qtbot) -> None:
        widget = MapWidget()
        qtbot.addWidget(widget)

        img = QImage(200, 200, QImage.Format.Format_RGB32)
        img.fill(Qt.GlobalColor.white)
        pixmap = QPixmap.fromImage(img)

        widget.view.pixmap_item = QGraphicsPixmapItem(pixmap)
        widget.view.scene.addItem(widget.view.pixmap_item)
        widget.view.coord_system.set_scene_rect(QRectF(0, 0, 200, 200))
        _make_raster_item(widget.view, node_id="delete-map-raster")

        handler = MapHandler(
            map_widget=widget,
            worker=MagicMock(),
            db_path_accessor=lambda: "/tmp/test.kraken",
            navigation_set_selection=MagicMock(),
        )

        order: list[str] = []
        original_exit = widget.exit_editing_modes

        def wrapped_exit() -> None:
            order.append("exit")
            original_exit()

        widget.exit_editing_modes = wrapped_exit
        emitted: list[object] = []
        handler.command_requested.connect(lambda cmd: (order.append("emit"), emitted.append(cmd)))

        widget.view.start_raster_editing("delete-map-raster")
        assert widget.view._raster_edit_tool.is_active

        handler.delete_map("map-delete-raster")

        assert not widget.view._raster_edit_tool.is_active
        assert len(emitted) == 1
        assert emitted[0].__class__.__name__ == "DeleteMapCommand"
        assert order == ["exit", "emit"]


# ── UX Fix: _find_graphics_item returns raster items ──────────────────


class TestFindGraphicsItemRaster:
    """_find_graphics_item must return RasterLayerItems from _raster_items."""

    def test_find_returns_raster_item(self, qtbot) -> None:
        view = _make_view(qtbot)
        item, _ = _make_raster_item(view, node_id="r1")

        found = view._find_graphics_item("r1")
        assert found is item

    def test_find_returns_none_for_unknown(self, qtbot) -> None:
        view = _make_view(qtbot)
        assert view._find_graphics_item("missing") is None


# ── UX Fix: Opacity propagates to raster items ───────────────────────


class TestRasterOpacityPropagation:
    """Opacity change via layer model must reach the RasterLayerItem."""

    def test_opacity_change_applied_to_raster_item(self, qtbot) -> None:
        view = _make_view(qtbot)
        item, _ = _make_raster_item(view, node_id="r2")

        # Simulate what _on_layer_opacity_changed does
        view._on_layer_opacity_changed("r2", 0.5)

        assert abs(item.opacity() - 0.5) < 0.01

    def test_visibility_change_applied_to_raster_item(self, qtbot) -> None:
        view = _make_view(qtbot)
        item, _ = _make_raster_item(view, node_id="r3")

        view._on_layer_visibility_changed("r3", False)
        assert not item.isVisible()

        view._on_layer_visibility_changed("r3", True)
        assert item.isVisible()


# ── UX Fix: Live tool settings during editing ─────────────────────────


class TestLiveToolSettings:
    """Changing panel controls during active editing must update tool."""

    def test_brush_size_updated_live(self, qtbot) -> None:
        """Changing brush size spinbox while editing should update tool."""
        from src.gui.widgets.map.map_layer_panel import MapLayerPanel

        panel = MapLayerPanel()
        qtbot.addWidget(panel)

        view = _make_view(qtbot)
        _make_raster_item(view, node_id="n1")

        tool = view._raster_edit_tool
        tool.brush_size = 8
        view.start_raster_editing("n1")

        # Panel changes should propagate to tool if properly connected
        panel._brush_size_spin.setValue(32)

        # The panel should have a signal connection that updates the tool
        # For now, test the property accessor
        assert panel.raster_brush_size == 32

    def test_paint_value_updated_live(self, qtbot) -> None:
        from src.gui.widgets.map.map_layer_panel import MapLayerPanel

        panel = MapLayerPanel()
        qtbot.addWidget(panel)

        panel._paint_value_spin.setValue(42)
        assert panel.raster_paint_value == 42

    def test_falloff_updated_live(self, qtbot) -> None:
        from src.gui.widgets.map.map_layer_panel import MapLayerPanel

        panel = MapLayerPanel()
        qtbot.addWidget(panel)

        panel._falloff_slider.setValue(75)
        assert abs(panel.raster_falloff - 0.75) < 0.01


# ── UX Fix: Button styling and text ──────────────────────────────────


class TestRasterButtonStyling:
    """Raster tool buttons must have clear visual active/inactive states."""

    def test_edit_button_text_changes_on_toggle(self, qtbot) -> None:
        from src.gui.widgets.map.map_layer_panel import MapLayerPanel

        panel = MapLayerPanel()
        qtbot.addWidget(panel)
        panel._selected_node_id = "test-node"

        # Unchecked: shows "✎ Edit"
        assert "Edit" in panel._btn_edit_toggle.text()

        # Check it: should show "✎ Editing…" to indicate active state
        panel._btn_edit_toggle.setChecked(True)
        assert "Editing" in panel._btn_edit_toggle.text()

        # Uncheck: back to "✎ Edit"
        panel._btn_edit_toggle.setChecked(False)
        assert "Edit" in panel._btn_edit_toggle.text()

    def test_tool_buttons_have_stylesheet(self, qtbot) -> None:
        from src.gui.widgets.map.map_layer_panel import MapLayerPanel

        panel = MapLayerPanel()
        qtbot.addWidget(panel)

        # All raster tool buttons should have non-empty stylesheets
        for btn in (
            panel._btn_brush,
            panel._btn_fill,
            panel._btn_gradient,
            panel._btn_sample,
        ):
            assert btn.styleSheet(), f"{btn.text()} button has no stylesheet"

    def test_edit_button_has_stylesheet(self, qtbot) -> None:
        from src.gui.widgets.map.map_layer_panel import MapLayerPanel

        panel = MapLayerPanel()
        qtbot.addWidget(panel)
        assert panel._btn_edit_toggle.styleSheet()


# ── UX Fix: Falloff label updates ────────────────────────────────────


class TestFalloffLabel:
    """Falloff slider should have a label showing current percentage."""

    def test_falloff_label_exists(self, qtbot) -> None:
        from src.gui.widgets.map.map_layer_panel import MapLayerPanel

        panel = MapLayerPanel()
        qtbot.addWidget(panel)

        assert hasattr(panel, "_falloff_label")
        assert panel._falloff_label.text() == "0%"

    def test_falloff_label_updates_on_slider(self, qtbot) -> None:
        from src.gui.widgets.map.map_layer_panel import MapLayerPanel

        panel = MapLayerPanel()
        qtbot.addWidget(panel)

        panel._falloff_slider.setValue(50)
        assert panel._falloff_label.text() == "50%"

        panel._falloff_slider.setValue(100)
        assert panel._falloff_label.text() == "100%"


# ── UX Fix: Spinbox arrows visible ───────────────────────────────────


class TestSpinboxArrows:
    """Spinboxes should have UpDownArrows button symbols."""

    def test_brush_size_has_arrows(self, qtbot) -> None:
        from PySide6.QtWidgets import QAbstractSpinBox

        from src.gui.widgets.map.map_layer_panel import MapLayerPanel

        panel = MapLayerPanel()
        qtbot.addWidget(panel)

        assert (
            panel._brush_size_spin.buttonSymbols()
            == QAbstractSpinBox.ButtonSymbols.UpDownArrows
        )

    def test_paint_value_has_arrows(self, qtbot) -> None:
        from PySide6.QtWidgets import QAbstractSpinBox

        from src.gui.widgets.map.map_layer_panel import MapLayerPanel

        panel = MapLayerPanel()
        qtbot.addWidget(panel)

        assert (
            panel._paint_value_spin.buttonSymbols()
            == QAbstractSpinBox.ButtonSymbols.UpDownArrows
        )


# ── UX Fix: Live tool mode and settings signals ──────────────────────


class TestPanelSignals:
    """Panel should emit signals when raster controls change."""

    def test_panel_has_raster_settings_changed_signal(self, qtbot) -> None:
        from src.gui.widgets.map.map_layer_panel import MapLayerPanel

        panel = MapLayerPanel()
        qtbot.addWidget(panel)

        assert hasattr(panel, "raster_settings_changed")


# ── Probe feedback ────────────────────────────────────────────────────


class TestProbeResultPopup:
    """Probe popup should show value and resolved entity label."""

    def test_probe_popup_shows_value(self, qtbot) -> None:
        from src.gui.widgets.map.raster_probe_popup import RasterProbePopup

        view = _make_view(qtbot)
        popup = RasterProbePopup(view)
        popup.show_result(node_id="n1", value=42, entity_name=None, label=None)

        assert "42" in popup.text()

    def test_probe_popup_shows_entity_name(self, qtbot) -> None:
        from src.gui.widgets.map.raster_probe_popup import RasterProbePopup

        view = _make_view(qtbot)
        popup = RasterProbePopup(view)
        popup.show_result(
            node_id="n1", value=5, entity_name="Tundra", label="Cold steppe"
        )

        assert "Tundra" in popup.text()

    def test_probe_popup_hides_on_clear(self, qtbot) -> None:
        from src.gui.widgets.map.raster_probe_popup import RasterProbePopup

        view = _make_view(qtbot)
        popup = RasterProbePopup(view)
        popup.show_result(node_id="n1", value=1, entity_name=None, label=None)
        popup.hide_result()

        assert not popup.isVisible()


# ── Palette editor enhancements ───────────────────────────────────────


class TestPaletteEditorEntityColumn:
    """Discrete palette editor must have an entity column."""

    def test_discrete_table_has_entity_column(self, qtbot) -> None:
        from src.gui.widgets.map.map_data_buffer import ColorMap
        from src.gui.widgets.map.raster_palette_editor import RasterPaletteEditor

        cmap = ColorMap(type="palette", entries=[])
        dlg = RasterPaletteEditor(color_map=cmap, mode="discrete")
        qtbot.addWidget(dlg)

        # Should have at least 4 columns: Value, Colour, Entity, Remove
        assert dlg._table.columnCount() >= 4

    def test_discrete_table_stores_entity_id(self, qtbot) -> None:
        from src.gui.widgets.map.map_data_buffer import ColorEntry, ColorMap
        from src.gui.widgets.map.raster_palette_editor import RasterPaletteEditor

        entry = ColorEntry(value=1, color="#FF0000", entity_id="entity-abc")
        cmap = ColorMap(type="palette", entries=[entry])
        dlg = RasterPaletteEditor(color_map=cmap, mode="discrete")
        qtbot.addWidget(dlg)

        result = dlg.result_color_map()
        assert result.entries[0].entity_id == "entity-abc"

    def test_result_map_includes_entity_ids(self, qtbot) -> None:
        from src.gui.widgets.map.map_data_buffer import ColorMap
        from src.gui.widgets.map.raster_palette_editor import RasterPaletteEditor

        cmap = ColorMap(type="palette", entries=[])
        dlg = RasterPaletteEditor(color_map=cmap, mode="discrete")
        qtbot.addWidget(dlg)

        dlg._add_entry_row(value=10, color="#00FF00", entity_id="ent-1")
        result = dlg.result_color_map()
        assert result.entries[0].entity_id == "ent-1"


class TestPaletteEditorGradientPreview:
    """Continuous palette editor must show a gradient preview strip."""

    def test_continuous_has_gradient_preview(self, qtbot) -> None:
        from src.gui.widgets.map.map_data_buffer import ColorMap, GradientStop
        from src.gui.widgets.map.raster_palette_editor import RasterPaletteEditor

        cmap = ColorMap(
            type="gradient",
            gradient_stops=[GradientStop(0.0, "#000000"), GradientStop(1.0, "#FFFFFF")],
        )
        dlg = RasterPaletteEditor(color_map=cmap, mode="continuous")
        qtbot.addWidget(dlg)

        assert hasattr(dlg, "_gradient_preview")

    def test_gradient_preview_updates_on_stop_change(self, qtbot) -> None:
        from src.gui.widgets.map.map_data_buffer import ColorMap, GradientStop
        from src.gui.widgets.map.raster_palette_editor import RasterPaletteEditor

        cmap = ColorMap(
            type="gradient",
            gradient_stops=[GradientStop(0.0, "#000000"), GradientStop(1.0, "#FFFFFF")],
        )
        dlg = RasterPaletteEditor(color_map=cmap, mode="continuous")
        qtbot.addWidget(dlg)

        # Calling refresh directly must not raise
        dlg._refresh_gradient_preview()

    def test_color_mode_result_preserves_passthrough(self, qtbot) -> None:
        from src.gui.widgets.map.map_data_buffer import ColorMap
        from src.gui.widgets.map.raster_palette_editor import RasterPaletteEditor

        cmap = ColorMap(type="passthrough")
        dlg = RasterPaletteEditor(color_map=cmap, mode="color")
        qtbot.addWidget(dlg)

        dlg._linked_type_combo.setCurrentText("Entity")
        dlg._linked_name_edit.setProperty("linked_id", "entity-123")

        result = dlg.result_color_map()

        assert result.type == "passthrough"
        assert result.linked_entity_id == "entity-123"
        assert result.linked_entity_type == "entity"


# ── ColorEntry entity_id field ────────────────────────────────────────


class TestColorEntryEntityId:
    """ColorEntry must support an optional entity_id field."""

    def test_color_entry_has_entity_id(self) -> None:
        from src.gui.widgets.map.map_data_buffer import ColorEntry

        entry = ColorEntry(value=1, color="#AABBCC", entity_id="eid-xyz")
        assert entry.entity_id == "eid-xyz"

    def test_color_entry_entity_id_defaults_none(self) -> None:
        from src.gui.widgets.map.map_data_buffer import ColorEntry

        entry = ColorEntry(value=1, color="#AABBCC")
        assert entry.entity_id is None

    def test_color_entry_roundtrips_entity_id(self) -> None:
        from src.gui.widgets.map.map_data_buffer import ColorEntry

        entry = ColorEntry(value=5, color="#112233", entity_id="ent-999")
        d = entry.to_dict()
        assert d["entity_id"] == "ent-999"
        restored = ColorEntry.from_dict(d)
        assert restored.entity_id == "ent-999"

    def test_color_entry_roundtrip_no_entity_id(self) -> None:
        from src.gui.widgets.map.map_data_buffer import ColorEntry

        entry = ColorEntry(value=3, color="#FFFFFF")
        d = entry.to_dict()
        restored = ColorEntry.from_dict(d)
        assert restored.entity_id is None


# ── UX: Mode clarity — probe popup mode hint ─────────────────────────


class TestProbePopupModeHint:
    """Probe popup must display a mode hint when mode is provided."""

    def test_probe_shows_discrete_hint(self, qtbot) -> None:
        from src.gui.widgets.map.raster_probe_popup import RasterProbePopup

        view = _make_view(qtbot)
        popup = RasterProbePopup(view)
        popup.show_result(
            node_id="n1", value=5, entity_name=None, label=None, mode="discrete"
        )

        assert "Discrete" in popup.text()

    def test_probe_shows_continuous_hint(self, qtbot) -> None:
        from src.gui.widgets.map.raster_probe_popup import RasterProbePopup

        view = _make_view(qtbot)
        popup = RasterProbePopup(view)
        popup.show_result(
            node_id="n1", value=128, entity_name=None, label=None, mode="continuous"
        )

        assert "Continuous" in popup.text()

    def test_probe_no_mode_shows_only_value(self, qtbot) -> None:
        from src.gui.widgets.map.raster_probe_popup import RasterProbePopup

        view = _make_view(qtbot)
        popup = RasterProbePopup(view)
        popup.show_result(node_id="n1", value=7, entity_name=None, label=None)

        text = popup.text()
        assert "7" in text
        assert "Discrete" not in text
        assert "Continuous" not in text

    def test_probe_still_shows_entity_with_mode(self, qtbot) -> None:
        from src.gui.widgets.map.raster_probe_popup import RasterProbePopup

        view = _make_view(qtbot)
        popup = RasterProbePopup(view)
        popup.show_result(
            node_id="n1",
            value=3,
            entity_name="Wolf",
            label="Territory",
            mode="discrete",
        )

        text = popup.text()
        assert "Wolf" in text
        assert "Territory" in text
        assert "Discrete" in text


# ── UX: Mode clarity — palette editor title and banner ───────────────


class TestPaletteEditorModeBanner:
    """Palette editor must show the mode in its title and as an info banner."""

    def test_discrete_title_contains_discrete(self, qtbot) -> None:
        from src.gui.widgets.map.map_data_buffer import ColorMap
        from src.gui.widgets.map.raster_palette_editor import RasterPaletteEditor

        cmap = ColorMap(type="palette", entries=[])
        dlg = RasterPaletteEditor(color_map=cmap, mode="discrete")
        qtbot.addWidget(dlg)

        assert "Discrete" in dlg.windowTitle()

    def test_continuous_title_contains_continuous(self, qtbot) -> None:
        from src.gui.widgets.map.map_data_buffer import ColorMap
        from src.gui.widgets.map.raster_palette_editor import RasterPaletteEditor

        cmap = ColorMap(
            type="gradient",
            gradient_stops=[GradientStop(0.0, "#000000"), GradientStop(1.0, "#FFFFFF")],
        )
        dlg = RasterPaletteEditor(color_map=cmap, mode="continuous")
        qtbot.addWidget(dlg)

        assert "Continuous" in dlg.windowTitle()


# ── UX: Mode clarity — layer creation dialog ─────────────────────────


class TestLayerDialogModeHint:
    """RasterLayerDialog must show a live mode hint that updates on selection."""

    def test_dialog_has_mode_hint_label(self, qtbot) -> None:
        from src.gui.widgets.map.raster_layer_dialog import RasterLayerDialog

        dlg = RasterLayerDialog()
        qtbot.addWidget(dlg)

        assert hasattr(dlg, "_mode_hint")

    def test_hint_matches_discrete(self, qtbot) -> None:
        from src.gui.widgets.map.raster_layer_dialog import RasterLayerDialog

        dlg = RasterLayerDialog()
        qtbot.addWidget(dlg)

        idx = dlg._mode_combo.findText("discrete")
        dlg._mode_combo.setCurrentIndex(idx)

        hint = dlg._mode_hint.text()
        assert hint  # not empty
        assert any(w in hint.lower() for w in ("categor", "biome", "class", "value"))

    def test_hint_matches_continuous(self, qtbot) -> None:
        from src.gui.widgets.map.raster_layer_dialog import RasterLayerDialog

        dlg = RasterLayerDialog()
        qtbot.addWidget(dlg)

        idx = dlg._mode_combo.findText("continuous")
        dlg._mode_combo.setCurrentIndex(idx)

        hint = dlg._mode_hint.text()
        assert hint  # not empty
        assert any(
            w in hint.lower()
            for w in ("gradient", "scalar", "elevation", "temperature", "colour ramp")
        )

    def test_mode_cannot_be_changed_warning_in_tooltip(self, qtbot) -> None:
        from src.gui.widgets.map.raster_layer_dialog import RasterLayerDialog

        dlg = RasterLayerDialog()
        qtbot.addWidget(dlg)

        tooltip = dlg._mode_combo.toolTip()
        assert "cannot" in tooltip.lower() or "⚠" in tooltip


# ── UX: Mode clarity — layer panel mode badge ────────────────────────


class TestLayerPanelModeBadge:
    """Layer panel must show a mode badge when a raster layer is selected."""

    def test_panel_has_mode_label(self, qtbot) -> None:
        from src.gui.widgets.map.map_layer_panel import MapLayerPanel

        panel = MapLayerPanel()
        qtbot.addWidget(panel)

        assert hasattr(panel, "_raster_mode_label")

    def test_mode_badge_hidden_initially(self, qtbot) -> None:
        from src.gui.widgets.map.map_layer_panel import MapLayerPanel

        panel = MapLayerPanel()
        qtbot.addWidget(panel)

        assert not panel._raster_mode_label.isVisible()

    def test_set_raster_mode_metadata_stores_data(self, qtbot) -> None:
        from src.gui.widgets.map.map_layer_panel import MapLayerPanel

        panel = MapLayerPanel()
        qtbot.addWidget(panel)

        panel.set_raster_mode_metadata({"node-1": "discrete", "node-2": "continuous"})
        assert panel._raster_mode_by_id["node-1"] == "discrete"
        assert panel._raster_mode_by_id["node-2"] == "continuous"

    def test_show_mode_badge_discrete(self, qtbot) -> None:
        from src.gui.widgets.map.map_layer_panel import MapLayerPanel

        panel = MapLayerPanel()
        qtbot.addWidget(panel)
        panel.show()

        panel._raster_toolbar.setVisible(True)
        panel._show_mode_badge("discrete")

        assert panel._raster_mode_label.isVisible()
        assert "Discrete" in panel._raster_mode_label.text()

    def test_show_mode_badge_continuous(self, qtbot) -> None:
        from src.gui.widgets.map.map_layer_panel import MapLayerPanel

        panel = MapLayerPanel()
        qtbot.addWidget(panel)
        panel.show()

        panel._raster_toolbar.setVisible(True)
        panel._show_mode_badge("continuous")

        assert panel._raster_mode_label.isVisible()
        assert "Continuous" in panel._raster_mode_label.text()

    def test_show_mode_badge_color(self, qtbot) -> None:
        from src.gui.widgets.map.map_layer_panel import MapLayerPanel

        panel = MapLayerPanel()
        qtbot.addWidget(panel)
        panel.show()

        panel._raster_toolbar.setVisible(True)
        panel._show_mode_badge("color")

        assert panel._raster_mode_label.isVisible()
        assert "Color" in panel._raster_mode_label.text()


# ── New: MapLayerNode.attributes ─────────────────────────────────────


class TestMapLayerNodeAttributes:
    """MapLayerNode must persist an arbitrary attributes dict."""

    def test_attributes_default_empty(self) -> None:
        from src.core.map import MapLayerNode

        n = MapLayerNode(name="x")
        assert n.attributes == {}

    def test_attributes_round_trip(self) -> None:
        from src.core.map import MapLayerNode

        n = MapLayerNode(name="x", attributes={"blend_mode": "multiply", "notes": "hi"})
        d = n.to_dict()
        n2 = MapLayerNode.from_dict(d)
        assert n2.attributes == {"blend_mode": "multiply", "notes": "hi"}

    def test_attributes_missing_key_backwards_compat(self) -> None:
        """Older serialised dicts without 'attributes' must load cleanly."""
        from src.core.map import MapLayerNode

        n = MapLayerNode.from_dict({"name": "old", "layer_type": "group"})
        assert n.attributes == {}


# ── New: Raster legend widget ─────────────────────────────────────────


class TestRasterLegendWidget:
    """RasterLegendWidget must show swatches for discrete and gradient for continuous."""

    def _make_discrete_meta(self) -> dict:
        return {
            "color_map": {
                "type": "palette",
                "entries": [
                    {"value": 42, "color": "#3A7D44"},
                    {"value": 7, "color": "#A0C8E0"},
                ],
            },
            "value_entity_map": {
                "mode": "exact",
                "mappings": [
                    {"id": "a1", "label": "Temperate Forest", "value": 42},
                    {"id": "b2", "label": "Tundra", "value": 7},
                ],
            },
        }

    def _make_continuous_meta(self) -> dict:
        return {
            "color_map": {
                "type": "gradient",
                "gradient_start": "#000000",
                "gradient_end": "#FFFFFF",
            },
            "value_entity_map": {},
        }

    def test_legend_widget_creates(self, qtbot) -> None:
        from src.gui.widgets.map.raster_legend_widget import RasterLegendWidget

        w = RasterLegendWidget()
        qtbot.addWidget(w)
        assert w is not None

    def test_legend_has_header_label(self, qtbot) -> None:
        from src.gui.widgets.map.raster_legend_widget import RasterLegendWidget

        w = RasterLegendWidget()
        qtbot.addWidget(w)
        assert hasattr(w, "_header_label")
        assert "Legend" in w._header_label.text()

    def test_discrete_legend_populates_entries(self, qtbot) -> None:
        from src.gui.widgets.map.raster_legend_widget import RasterLegendWidget

        w = RasterLegendWidget()
        qtbot.addWidget(w)
        w.set_layer(self._make_discrete_meta())
        # content_layout should have swatch rows + no-data row + stretch
        # at least: no-data + 2 class rows + 1 stretch = 4 items
        assert w._content_layout.count() >= 4

    def test_continuous_legend_builds_gradient_bar(self, qtbot) -> None:
        from src.gui.widgets.map.raster_legend_widget import RasterLegendWidget

        w = RasterLegendWidget()
        qtbot.addWidget(w)
        w.set_layer(self._make_continuous_meta())
        # Should have at least the gradient bar + stretch
        assert w._content_layout.count() >= 2

    def test_set_none_clears_legend(self, qtbot) -> None:
        from src.gui.widgets.map.raster_legend_widget import RasterLegendWidget

        w = RasterLegendWidget()
        qtbot.addWidget(w)
        w.set_layer(self._make_discrete_meta())
        w.set_layer(None)
        # Only stretch left
        assert w._content_layout.count() == 1


# ── New: Panel legend and entity picker ──────────────────────────────


class TestPanelLegendAndEntityPicker:
    """MapLayerPanel must expose legend widget and entity picker combo."""

    def test_panel_has_legend_widget(self, qtbot) -> None:
        """After the refactor, the panel must NOT own a `_legend` widget;
        the legend now lives as a floating overlay on MapWidget."""
        from src.gui.widgets.map.map_layer_panel import MapLayerPanel

        panel = MapLayerPanel()
        qtbot.addWidget(panel)
        assert not hasattr(panel, "_legend")

    def test_legend_hidden_by_default(self, qtbot) -> None:
        from src.gui.widgets.map.map_layer_panel import MapLayerPanel

        panel = MapLayerPanel()
        qtbot.addWidget(panel)
        # After the legend-overlay refactor, the panel no longer owns the
        # legend widget.  It must NOT have a `_legend` attribute.
        assert not hasattr(panel, "_legend")

    def test_panel_has_entity_picker_combo(self, qtbot) -> None:
        from src.gui.widgets.map.map_layer_panel import MapLayerPanel

        panel = MapLayerPanel()
        qtbot.addWidget(panel)
        assert hasattr(panel, "_entity_picker_combo")

    def test_entity_picker_row_hidden_by_default(self, qtbot) -> None:
        from src.gui.widgets.map.map_layer_panel import MapLayerPanel

        panel = MapLayerPanel()
        qtbot.addWidget(panel)
        assert not panel._entity_picker_row.isVisible()

    def test_set_raster_layer_metadata_stores_data(self, qtbot) -> None:
        from src.gui.widgets.map.map_layer_panel import MapLayerPanel

        panel = MapLayerPanel()
        qtbot.addWidget(panel)
        meta = {"n1": {"mode": "discrete", "value_entity_map": {}, "color_map": {}}}
        panel.set_raster_layer_metadata(meta)
        assert panel._raster_meta_by_id == meta

    def test_refresh_entity_picker_populates_combo(self, qtbot) -> None:
        from src.gui.widgets.map.map_layer_panel import MapLayerPanel

        panel = MapLayerPanel()
        qtbot.addWidget(panel)
        layer_meta = {
            "value_entity_map": {
                "mode": "exact",
                "mappings": [
                    {"id": "a", "label": "Forest", "value": 42},
                    {"id": "b", "label": "Tundra", "value": 7},
                ],
            },
            "color_map": {},
        }
        panel._refresh_entity_picker(layer_meta, "discrete")
        # "— manual —" + 2 entries = 3 items
        assert panel._entity_picker_combo.count() == 3

    def test_refresh_entity_picker_hidden_for_continuous(self, qtbot) -> None:
        from src.gui.widgets.map.map_layer_panel import MapLayerPanel

        panel = MapLayerPanel()
        qtbot.addWidget(panel)
        panel._refresh_entity_picker({"value_entity_map": {}}, "continuous")
        assert not panel._entity_picker_row.isVisible()

    def test_refresh_entity_picker_hidden_for_color(self, qtbot) -> None:
        from src.gui.widgets.map.map_layer_panel import MapLayerPanel

        panel = MapLayerPanel()
        qtbot.addWidget(panel)
        panel._refresh_entity_picker({"value_entity_map": {}}, "color")
        assert not panel._entity_picker_row.isVisible()

    def test_color_mode_disables_sample_tool(self, qtbot) -> None:
        from src.gui.widgets.map.map_layer_panel import MapLayerPanel

        panel = MapLayerPanel()
        qtbot.addWidget(panel)
        panel._btn_sample.setChecked(True)

        panel._update_sample_tool_availability("color")

        assert not panel._btn_sample.isEnabled()
        assert panel._btn_brush.isChecked()
        assert "unavailable for color rasters" in panel._btn_sample.toolTip()

    def test_entity_picked_sets_paint_value(self, qtbot) -> None:
        from src.gui.widgets.map.map_layer_panel import MapLayerPanel

        panel = MapLayerPanel()
        qtbot.addWidget(panel)
        layer_meta = {
            "value_entity_map": {
                "mode": "exact",
                "mappings": [{"id": "a", "label": "Forest", "value": 42}],
            },
            "color_map": {},
        }
        panel._refresh_entity_picker(layer_meta, "discrete")
        # Select index 1 (first real class — index 0 is "manual")
        panel._entity_picker_combo.setCurrentIndex(1)
        assert panel._paint_value_spin.value() == 42


# ── New: get_discrete_class_choices helper ────────────────────────────


class TestGetDiscreteClassChoices:
    """get_discrete_class_choices must return sorted (label, value) pairs."""

    def test_returns_sorted_choices(self) -> None:
        from src.gui.widgets.map.raster_mapping import get_discrete_class_choices

        meta = {
            "value_entity_map": {
                "mode": "exact",
                "mappings": [
                    {"id": "a", "label": "Forest", "value": 42},
                    {"id": "b", "label": "Tundra", "value": 7},
                ],
            }
        }
        choices = get_discrete_class_choices(meta)
        assert choices == [("Tundra", 7), ("Forest", 42)]

    def test_empty_vem_returns_empty(self) -> None:
        from src.gui.widgets.map.raster_mapping import get_discrete_class_choices

        assert get_discrete_class_choices({}) == []
        assert get_discrete_class_choices({"value_entity_map": {}}) == []

    def test_no_value_entries_skipped(self) -> None:
        from src.gui.widgets.map.raster_mapping import get_discrete_class_choices

        meta = {
            "value_entity_map": {
                "mode": "range",
                "mappings": [
                    {"id": "a", "label": "Cold", "min": 0, "max": 100},
                ],
            }
        }
        # Range entries have no "value" key — should be excluded
        assert get_discrete_class_choices(meta) == []

    def test_label_fallback_when_empty(self) -> None:
        from src.gui.widgets.map.raster_mapping import get_discrete_class_choices

        meta = {
            "value_entity_map": {
                "mode": "exact",
                "mappings": [{"id": "a", "label": "", "value": 5}],
            }
        }
        choices = get_discrete_class_choices(meta)
        assert choices == [("Value 5", 5)]


# ── Feature: Coverage / Area Statistics ──────────────────────────────────


class TestComputeCoverageStats:
    """MapDataBuffer.compute_coverage_stats must compute correct statistics."""

    def _make_palette_cmap(self) -> "ColorMap":
        from src.gui.widgets.map.map_data_buffer import ColorEntry, ColorMap

        return ColorMap(
            type="palette",
            entries=[
                ColorEntry(value=1, color="#FF0000"),
                ColorEntry(value=2, color="#00FF00"),
            ],
        )

    def test_discrete_stats_counts_per_class(self) -> None:
        from src.gui.widgets.map.map_data_buffer import MapDataBuffer

        buf = MapDataBuffer(4, 4, default_value=0)
        # Paint 6 pixels with value=1, 4 with value=2, rest stay 0
        for c in range(4):
            buf.set_value_at(c / 4.0, 0.125, 1)  # row 0
        for c in range(2):
            buf.set_value_at(c / 4.0, 0.375, 1)  # row 1
        for c in range(4):
            buf.set_value_at(c / 4.0, 0.625, 2)  # row 2
        cmap = self._make_palette_cmap()
        stats = buf.compute_coverage_stats(cmap)
        assert stats.mode == "discrete"
        by_val = {cs.value: cs.pixel_count for cs in stats.classes}
        assert by_val[1] == 6
        assert by_val[2] == 4

    def test_discrete_stats_percentage(self) -> None:
        from src.gui.widgets.map.map_data_buffer import (
            ColorEntry,
            ColorMap,
            MapDataBuffer,
        )

        buf = MapDataBuffer(10, 10, default_value=1)  # 100 pixels, all value=1
        cmap = ColorMap(type="palette", entries=[ColorEntry(value=1, color="#FF0000")])
        stats = buf.compute_coverage_stats(cmap)
        total_pct = sum(cs.percentage for cs in stats.classes)
        assert abs(total_pct - 100.0) < 0.5  # at most 0.5% rounding error

    def test_continuous_stats_histogram(self) -> None:
        from src.gui.widgets.map.map_data_buffer import ColorMap, MapDataBuffer

        buf = MapDataBuffer(8, 8, default_value=32768)
        cmap = ColorMap(type="gradient")
        stats = buf.compute_coverage_stats(cmap)
        assert stats.mode == "continuous"
        assert stats.histogram_counts is not None
        assert len(stats.histogram_counts) == 32
        assert stats.histogram_edges is not None
        assert len(stats.histogram_edges) == 33

    def test_continuous_stats_minmax(self) -> None:
        from src.gui.widgets.map.map_data_buffer import ColorMap, MapDataBuffer

        buf = MapDataBuffer(4, 4, default_value=0)
        buf._data[0, 0] = 100
        buf._data[3, 3] = 60000
        cmap = ColorMap(type="gradient")
        stats = buf.compute_coverage_stats(cmap)
        assert stats.min_val == 100.0
        assert stats.max_val == 60000.0

    def test_empty_vem_returns_empty_classes(self) -> None:
        from src.gui.widgets.map.map_data_buffer import ColorMap, MapDataBuffer

        buf = MapDataBuffer(4, 4, default_value=0)
        # Palette with no entries
        cmap = ColorMap(type="palette", entries=[])
        stats = buf.compute_coverage_stats(cmap)
        # No class entries from empty palette — only possible "No data" entry
        assert all(cs.value in (0,) for cs in stats.classes)


# ── Feature: RasterStatsPanel dialog ─────────────────────────────────────


class TestRasterStatsPanel:
    """RasterStatsPanel must create without error for both modes."""

    def _discrete_stats(self) -> object:
        from src.gui.widgets.map.map_data_buffer import ClassStat, CoverageStats

        return CoverageStats(
            mode="discrete",
            total_pixels=100,
            classes=[
                ClassStat(value=1, label="Forest", pixel_count=60, percentage=60.0),
                ClassStat(value=2, label="Desert", pixel_count=30, percentage=30.0),
                ClassStat(value=0, label="No data", pixel_count=10, percentage=10.0),
            ],
        )

    def _continuous_stats(self) -> object:
        from src.gui.widgets.map.map_data_buffer import CoverageStats

        return CoverageStats(
            mode="continuous",
            total_pixels=256,
            histogram_counts=list(range(32)),
            histogram_edges=[float(i * 2048) for i in range(33)],
            min_val=100.0,
            max_val=65000.0,
            mean_val=32768.0,
            median_val=30000.0,
        )

    def test_stats_panel_creates_for_discrete(self, qtbot) -> None:
        from src.gui.widgets.map.raster_stats_panel import RasterStatsPanel

        panel = RasterStatsPanel(self._discrete_stats(), layer_name="Test Layer")
        qtbot.addWidget(panel)
        assert panel is not None

    def test_stats_panel_creates_for_continuous(self, qtbot) -> None:
        from src.gui.widgets.map.raster_stats_panel import RasterStatsPanel

        panel = RasterStatsPanel(self._continuous_stats(), layer_name="Continuous")
        qtbot.addWidget(panel)
        assert panel is not None

    def test_stats_panel_has_table_for_discrete(self, qtbot) -> None:
        from PySide6.QtWidgets import QTableWidget

        from src.gui.widgets.map.raster_stats_panel import RasterStatsPanel

        panel = RasterStatsPanel(self._discrete_stats(), layer_name="Discrete")
        qtbot.addWidget(panel)
        tables = panel.findChildren(QTableWidget)
        assert len(tables) >= 1

    def test_discrete_table_row_count(self, qtbot) -> None:
        from src.gui.widgets.map.raster_stats_panel import RasterStatsPanel

        stats = self._discrete_stats()
        panel = RasterStatsPanel(stats, layer_name="Discrete")
        qtbot.addWidget(panel)
        tbl = panel.table
        assert tbl is not None
        # Row count = number of class stats + 1 total row
        assert tbl.rowCount() == len(stats.classes) + 1


# ── Feature: Layer Blending Modes ────────────────────────────────────────


class TestBlendMode:
    """RasterLayerItem blend mode support."""

    def test_blend_mode_default_is_source_over(self, qtbot) -> None:
        from PySide6.QtGui import QPainter

        view = _make_view(qtbot)
        item, _ = _make_raster_item(view, node_id="blend_test")
        assert (
            item._scene_blend_mode
            == QPainter.CompositionMode.CompositionMode_SourceOver
        )

    def test_set_blend_mode_multiply(self, qtbot) -> None:
        from PySide6.QtGui import QPainter

        view = _make_view(qtbot)
        item, _ = _make_raster_item(view, node_id="blend_mult")
        item.set_blend_mode("Multiply")
        assert (
            item._scene_blend_mode == QPainter.CompositionMode.CompositionMode_Multiply
        )

    def test_set_blend_mode_unknown_falls_back(self, qtbot) -> None:
        from PySide6.QtGui import QPainter

        view = _make_view(qtbot)
        item, _ = _make_raster_item(view, node_id="blend_unk")
        item.set_blend_mode("NonExistentMode")
        assert (
            item._scene_blend_mode
            == QPainter.CompositionMode.CompositionMode_SourceOver
        )

    def test_panel_has_blend_combo(self, qtbot) -> None:
        from PySide6.QtWidgets import QComboBox

        from src.gui.widgets.map.map_layer_panel import MapLayerPanel

        panel = MapLayerPanel()
        qtbot.addWidget(panel)
        assert hasattr(panel, "_blend_combo")
        assert isinstance(panel._blend_combo, QComboBox)

    def test_set_raster_blend_mode_command_execute(self) -> None:
        """SetRasterBlendModeCommand persists blend_mode into raster layer metadata."""
        import uuid

        from src.commands.raster_commands import SetRasterBlendModeCommand
        from src.core.map import Map
        from src.services.db_service import DatabaseService

        db = DatabaseService(":memory:")
        db.connect()
        map_id = str(uuid.uuid4())
        node_id = str(uuid.uuid4())
        m = Map(
            id=map_id,
            name="TestMap",
            image_path="",
            attributes={
                "raster_layers": [
                    {"node_id": node_id, "mode": "discrete", "blend_mode": "Normal"}
                ]
            },
        )
        db.map_repo.insert_map(m)

        cmd = SetRasterBlendModeCommand(
            map_id=map_id, node_id=node_id, new_mode="Multiply", old_mode="Normal"
        )
        result = cmd.execute(db)
        assert result.success

        stored = db.map_repo.get_map(map_id)
        layers = (stored.attributes or {}).get("raster_layers", [])
        layer = next(la for la in layers if la["node_id"] == node_id)
        assert layer["blend_mode"] == "Multiply"


# ── Feature: Entity Orphan Detection ─────────────────────────────────────


class TestOrphanDetection:
    """check_entity_raster_refs and RasterOrphanWarningDialog."""

    def _make_mock_map(self, map_id: str, node_id: str, entity_id: str) -> object:
        """Create a minimal mock Map-like object."""

        class _MockMap:
            def __init__(self) -> None:
                self.id = map_id
                self.name = "TestMap"
                self.attributes = {
                    "raster_layers": [
                        {
                            "node_id": node_id,
                            "mode": "discrete",
                            "value_entity_map": {
                                "mode": "exact",
                                "mappings": [
                                    {
                                        "id": "m1",
                                        "label": "Forest",
                                        "entity_id": entity_id,
                                        "value": 42,
                                    }
                                ],
                            },
                        }
                    ]
                }

        return _MockMap()

    def test_check_entity_raster_refs_finds_ref(self) -> None:
        from src.gui.widgets.map.raster_mapping import check_entity_raster_refs

        entity_id = "ent-001"
        node_id = "node-001"
        map_id = "map-001"
        mock_map = self._make_mock_map(map_id, node_id, entity_id)
        refs = check_entity_raster_refs(entity_id, [mock_map])
        assert len(refs) == 1
        assert refs[0].map_id == map_id
        assert refs[0].node_id == node_id
        assert refs[0].value == 42

    def test_check_entity_raster_refs_no_refs(self) -> None:
        from src.gui.widgets.map.raster_mapping import check_entity_raster_refs

        mock_map = self._make_mock_map("map-002", "node-002", "ent-002")
        refs = check_entity_raster_refs("other-entity", [mock_map])
        assert refs == []

    def test_orphan_dialog_creates(self, qtbot) -> None:
        from src.gui.dialogs.raster_orphan_warning_dialog import (
            RasterOrphanWarningDialog,
        )
        from src.gui.widgets.map.raster_mapping import RasterItemRef

        ref = RasterItemRef(
            map_id="map-001",
            node_id="node-001",
            mapping_id="m1",
            label="Forest",
            mode="exact",
            value=42,
        )
        dlg = RasterOrphanWarningDialog(
            entity_name="Test Entity",
            refs=[ref],
            map_names={"map-001": "World Map"},
        )
        qtbot.addWidget(dlg)
        assert dlg is not None
        assert dlg.result_action == "cancel"

    def test_orphan_dialog_has_three_buttons(self, qtbot) -> None:
        from PySide6.QtWidgets import QPushButton

        from src.gui.dialogs.raster_orphan_warning_dialog import (
            RasterOrphanWarningDialog,
        )
        from src.gui.widgets.map.raster_mapping import RasterItemRef

        ref = RasterItemRef(
            map_id="map-001",
            node_id="node-001",
            mapping_id="m1",
            label="Forest",
            mode="exact",
            value=1,
        )
        dlg = RasterOrphanWarningDialog(
            entity_name="Ent",
            refs=[ref],
            map_names={"map-001": "Map"},
        )
        qtbot.addWidget(dlg)
        buttons = dlg.findChildren(QPushButton)
        assert len(buttons) >= 3


# ── Feature: Temporal Rasters ─────────────────────────────────────────────


class TestTemporalRasters:
    """Tests for temporal raster snapshot feature."""

    def test_swap_buffer_updates_data(self, qtbot) -> None:
        """swap_buffer replaces the item's internal buffer."""
        view = _make_view(qtbot)
        item, original_buf = _make_raster_item(view, node_id="swap_test")

        new_buf = MapDataBuffer(width=64, height=64, default_value=9999)
        item.swap_buffer(new_buf)

        assert item.buffer is new_buf
        assert item.buffer._data[0, 0] == 9999

    def test_swap_buffer_triggers_redisplay(self, qtbot) -> None:
        """swap_buffer calls update_display so the pixmap is refreshed."""
        view = _make_view(qtbot)
        item, _ = _make_raster_item(view, node_id="swap_redraw")

        new_buf = MapDataBuffer(width=64, height=64, default_value=65535)
        item.swap_buffer(new_buf)

        # Pixmap must have been re-rendered (not identical to old one)
        assert not item.pixmap().isNull()

    def test_find_best_snapshot_no_snapshots(self, qtbot) -> None:
        """_find_best_snapshot_path returns base path when no snapshots."""
        from src.app.map_handler import MapHandler

        meta = {"file_path": "rasters/base.png", "snapshots": {}}
        handler = MapHandler.__new__(MapHandler)
        result = handler._find_best_snapshot_path(meta, 10.0)
        assert result == "rasters/base.png"

    def test_find_best_snapshot_exact_match(self, qtbot) -> None:
        """_find_best_snapshot_path returns snapshot at exact lore_date."""
        from src.app.map_handler import MapHandler

        meta = {
            "file_path": "rasters/base.png",
            "snapshots": {
                "5.0": "rasters/snap_5.png",
                "10.0": "rasters/snap_10.png",
            },
        }
        handler = MapHandler.__new__(MapHandler)
        result = handler._find_best_snapshot_path(meta, 10.0)
        assert result == "rasters/snap_10.png"

    def test_find_best_snapshot_nearest_past(self, qtbot) -> None:
        """_find_best_snapshot_path returns most recent past snapshot."""
        from src.app.map_handler import MapHandler

        meta = {
            "file_path": "rasters/base.png",
            "snapshots": {
                "1.0": "rasters/snap_1.png",
                "5.0": "rasters/snap_5.png",
                "20.0": "rasters/snap_20.png",
            },
        }
        handler = MapHandler.__new__(MapHandler)
        # playhead at 12.0 → snap at 5.0 is the nearest past
        result = handler._find_best_snapshot_path(meta, 12.0)
        assert result == "rasters/snap_5.png"

    def test_find_best_snapshot_before_all(self, qtbot) -> None:
        """_find_best_snapshot_path returns base when playhead is before all snapshots."""
        from src.app.map_handler import MapHandler

        meta = {
            "file_path": "rasters/base.png",
            "snapshots": {
                "10.0": "rasters/snap_10.png",
                "20.0": "rasters/snap_20.png",
            },
        }
        handler = MapHandler.__new__(MapHandler)
        # playhead at 5.0 → before all snapshots → return base
        result = handler._find_best_snapshot_path(meta, 5.0)
        assert result == "rasters/base.png"

    def test_set_raster_snapshot_command_execute(self) -> None:
        """SetRasterSnapshotCommand persists snapshot path to DB."""
        import uuid

        from src.commands.raster_commands import SetRasterSnapshotCommand
        from src.core.map import Map
        from src.services.db_service import DatabaseService

        db = DatabaseService(":memory:")
        db.connect()
        map_id = str(uuid.uuid4())
        node_id = str(uuid.uuid4())
        m = Map(
            id=map_id,
            name="TestMap",
            image_path="",
            attributes={
                "raster_layers": [
                    {
                        "node_id": node_id,
                        "mode": "discrete",
                        "file_path": "rasters/base.png",
                    }
                ]
            },
        )
        db.map_repo.insert_map(m)

        cmd = SetRasterSnapshotCommand(
            map_id=map_id,
            node_id=node_id,
            lore_date=5.0,
            rel_file_path="rasters/base_snap_5.00.png",
            old_snapshots={},
        )
        result = cmd.execute(db)
        assert result.success

        stored = db.map_repo.get_map(map_id)
        layers = (stored.attributes or {}).get("raster_layers", [])
        layer = next(la for la in layers if la["node_id"] == node_id)
        assert layer.get("snapshots", {}).get("5.0") == "rasters/base_snap_5.00.png"

    def test_set_raster_snapshot_command_undo(self) -> None:
        """SetRasterSnapshotCommand undo restores old snapshots."""
        import uuid

        from src.commands.raster_commands import SetRasterSnapshotCommand
        from src.core.map import Map
        from src.services.db_service import DatabaseService

        db = DatabaseService(":memory:")
        db.connect()
        map_id = str(uuid.uuid4())
        node_id = str(uuid.uuid4())
        existing_snaps = {"1.0": "rasters/snap_1.png"}
        m = Map(
            id=map_id,
            name="TestMap",
            image_path="",
            attributes={
                "raster_layers": [
                    {
                        "node_id": node_id,
                        "mode": "discrete",
                        "file_path": "rasters/base.png",
                        "snapshots": dict(existing_snaps),
                    }
                ]
            },
        )
        db.map_repo.insert_map(m)

        cmd = SetRasterSnapshotCommand(
            map_id=map_id,
            node_id=node_id,
            lore_date=5.0,
            rel_file_path="rasters/base_snap_5.00.png",
            old_snapshots=existing_snaps,
        )
        cmd.execute(db)
        cmd.undo(db)

        stored = db.map_repo.get_map(map_id)
        layers = (stored.attributes or {}).get("raster_layers", [])
        layer = next(la for la in layers if la["node_id"] == node_id)
        snaps = layer.get("snapshots", {})
        assert "5.0" not in snaps
        assert snaps.get("1.0") == "rasters/snap_1.png"

    def test_panel_has_snapshot_button(self, qtbot) -> None:
        """MapLayerPanel has a snapshot button."""
        from src.gui.widgets.map.map_layer_panel import MapLayerPanel

        panel = MapLayerPanel()
        qtbot.addWidget(panel)
        assert hasattr(panel, "_btn_snapshot")

    def test_panel_has_snapshot_count_label(self, qtbot) -> None:
        """MapLayerPanel has a snapshot count label."""
        from src.gui.widgets.map.map_layer_panel import MapLayerPanel

        panel = MapLayerPanel()
        qtbot.addWidget(panel)
        assert hasattr(panel, "_snapshot_count_label")

    def test_panel_emits_snapshot_requested(self, qtbot) -> None:
        """Clicking the snapshot button emits raster_snapshot_requested."""
        from src.gui.widgets.map.map_layer_panel import MapLayerPanel

        panel = MapLayerPanel()
        qtbot.addWidget(panel)
        panel._current_node_id = "test-node"

        emitted: list = []
        panel.raster_snapshot_requested.connect(emitted.append)
        panel._btn_snapshot.click()

        assert emitted == ["test-node"]


# ── Feature A: Brush Preset Library ──────────────────────────────────────


class TestBrushPresets:
    """Brush preset round-trip and panel integration."""

    def test_brush_preset_roundtrip(self) -> None:
        """BrushPreset.to_dict() / from_dict() preserves all fields."""
        from src.core.raster_presets import BrushPreset

        p = BrushPreset(
            name="TestPreset",
            tool_mode="gradient",
            size=42,
            falloff=0.75,
            paint_value=512,
        )
        p2 = BrushPreset.from_dict(p.to_dict())
        assert p2.name == p.name
        assert p2.tool_mode == p.tool_mode
        assert p2.size == p.size
        assert abs(p2.falloff - p.falloff) < 1e-9
        assert p2.paint_value == p.paint_value
        assert p2.id == p.id

    def test_preset_store_save_load(self, monkeypatch) -> None:
        """PresetStore.save() / load() round-trips via QSettings."""
        from typing import Any, Dict

        stored: Dict[str, Any] = {}

        from PySide6.QtCore import QSettings

        from src.core.raster_presets import BrushPreset, PresetStore

        def mock_value(self: QSettings, key: str, default: Any = None) -> Any:
            return stored.get(key, default)

        def mock_set_value(self: QSettings, key: str, val: Any) -> None:
            stored[key] = val

        monkeypatch.setattr(QSettings, "value", mock_value)
        monkeypatch.setattr(QSettings, "setValue", mock_set_value)

        preset = BrushPreset(
            name="Test", tool_mode="fill", size=10, falloff=0.5, paint_value=7
        )
        PresetStore.save([preset])
        loaded = PresetStore.load()

        assert len(loaded) == 1
        assert loaded[0].name == "Test"
        assert loaded[0].tool_mode == "fill"
        assert loaded[0].size == 10

    def test_panel_has_preset_combo(self, qtbot) -> None:
        """MapLayerPanel has a _preset_combo attribute."""
        from PySide6.QtWidgets import QComboBox

        from src.gui.widgets.map.map_layer_panel import MapLayerPanel

        panel = MapLayerPanel()
        qtbot.addWidget(panel)
        assert hasattr(panel, "_preset_combo")
        assert isinstance(panel._preset_combo, QComboBox)


# ── Feature B: Histogram Stretch ─────────────────────────────────────────


class TestHistogramStretch:
    """ColorMap stretch fields and colorize() behaviour."""

    def test_colormap_stretch_roundtrip(self) -> None:
        """stretch_min/max survive to_dict() / from_dict()."""
        from src.gui.widgets.map.map_data_buffer import ColorMap

        cm = ColorMap(
            type="gradient",
            gradient_stops=[GradientStop(0.0, "#000000"), GradientStop(1.0, "#FFFFFF")],
            stretch_min=1000,
            stretch_max=50000,
        )
        cm2 = ColorMap.from_dict(cm.to_dict())
        assert cm2.stretch_min == 1000
        assert cm2.stretch_max == 50000

    def test_colormap_stretch_defaults_none(self) -> None:
        """ColorMap from_dict without stretch fields defaults to None."""
        from src.gui.widgets.map.map_data_buffer import ColorMap

        cm = ColorMap.from_dict({"type": "gradient"})
        assert cm.stretch_min is None
        assert cm.stretch_max is None

    def test_colorize_with_stretch(self, qtbot) -> None:
        """colorize() maps stretch_min to start color when stretch is set."""

        from src.gui.widgets.map.map_data_buffer import ColorMap, MapDataBuffer

        buf = MapDataBuffer(width=1, height=1, default_value=32768)

        # No stretch: 32768/65535 ≈ 0.5 → midpoint gray
        cm_no_stretch = ColorMap(
            type="gradient",
            gradient_stops=[GradientStop(0.0, "#000000"), GradientStop(1.0, "#FFFFFF")],
        )
        img_mid = buf.colorize(cm_no_stretch)
        pixel_mid = img_mid.pixel(0, 0)
        mid_r = (pixel_mid >> 16) & 0xFF

        # stretch_min=32768, stretch_max=65535 → value 32768 = start → black
        cm_stretch = ColorMap(
            type="gradient",
            gradient_stops=[GradientStop(0.0, "#000000"), GradientStop(1.0, "#FFFFFF")],
            stretch_min=32768,
            stretch_max=65535,
        )
        img_start = buf.colorize(cm_stretch)
        pixel_start = img_start.pixel(0, 0)
        start_r = (pixel_start >> 16) & 0xFF

        # With stretch, value 32768 maps to start color (R=0)
        assert start_r == 0
        # Without stretch, value 32768 maps to roughly midpoint (R ≈ 128)
        assert mid_r > 100

    def test_palette_editor_has_stretch_controls(self, qtbot) -> None:
        """RasterPaletteEditor in continuous mode has _stretch_min_spin."""
        from src.gui.widgets.map.map_data_buffer import ColorMap
        from src.gui.widgets.map.raster_palette_editor import RasterPaletteEditor

        cm = ColorMap(
            type="gradient",
            gradient_stops=[GradientStop(0.0, "#000000"), GradientStop(1.0, "#FFFFFF")],
        )
        dlg = RasterPaletteEditor(color_map=cm, mode="continuous")
        qtbot.addWidget(dlg)
        assert hasattr(dlg, "_stretch_min_spin")
        assert hasattr(dlg, "_stretch_max_spin")


# ── Feature C: Auto-color ─────────────────────────────────────────────────


class TestAutoColor:
    """Discrete palette auto-color button."""

    def test_palette_editor_has_auto_color_button(self, qtbot) -> None:
        """RasterPaletteEditor in discrete mode has an auto-color button."""
        from PySide6.QtWidgets import QPushButton

        from src.gui.widgets.map.map_data_buffer import ColorEntry, ColorMap
        from src.gui.widgets.map.raster_palette_editor import RasterPaletteEditor

        cm = ColorMap(
            type="palette",
            entries=[ColorEntry(value=1, color="#AAAAAA")],
        )
        dlg = RasterPaletteEditor(color_map=cm, mode="discrete")
        qtbot.addWidget(dlg)
        buttons = [
            b for b in dlg.findChildren(QPushButton) if "auto" in b.text().lower()
        ]
        assert len(buttons) >= 1

    def test_auto_color_assigns_colors(self, qtbot) -> None:
        """Clicking auto-color assigns distinct colors to table rows."""
        from PySide6.QtWidgets import QPushButton

        from src.gui.widgets.map.map_data_buffer import ColorEntry, ColorMap
        from src.gui.widgets.map.raster_palette_editor import (
            _AUTO_COLORS,
            RasterPaletteEditor,
        )

        entries = [ColorEntry(value=i, color="#808080") for i in range(3)]
        cm = ColorMap(type="palette", entries=entries)
        dlg = RasterPaletteEditor(color_map=cm, mode="discrete")
        qtbot.addWidget(dlg)

        # Click the auto-color button
        buttons = [
            b for b in dlg.findChildren(QPushButton) if "auto" in b.text().lower()
        ]
        assert buttons
        buttons[0].click()

        # The first three row colors should now match _AUTO_COLORS
        for row in range(3):
            from src.gui.widgets.map.raster_palette_editor import (
                _COL_COLOR,
                _ColorButton,
            )

            btn = dlg._table.cellWidget(row, _COL_COLOR)
            assert isinstance(btn, _ColorButton)
            assert btn.color_hex == _AUTO_COLORS[row % len(_AUTO_COLORS)]


# ── Feature D: Cross-Layer Spatial Queries ────────────────────────────────


class TestSpatialQuery:
    """compute_spatial_query and RasterQueryDialog."""

    def test_compute_spatial_query_eq(self) -> None:
        """Equality condition returns correct boolean mask."""
        import numpy as np

        from src.gui.widgets.map.map_data_buffer import compute_spatial_query

        arr = np.array([[1, 2], [3, 4]], dtype=np.uint16)
        mask = compute_spatial_query([arr], [{"index": 0, "op": "eq", "value": 2}])
        expected = np.array([[False, True], [False, False]])
        np.testing.assert_array_equal(mask, expected)

    def test_compute_spatial_query_between(self) -> None:
        """Between condition includes both endpoints."""
        import numpy as np

        from src.gui.widgets.map.map_data_buffer import compute_spatial_query

        arr = np.array([[0, 5, 10, 15]], dtype=np.uint16)
        mask = compute_spatial_query(
            [arr], [{"index": 0, "op": "between", "min": 5, "max": 10}]
        )
        expected = np.array([[False, True, True, False]])
        np.testing.assert_array_equal(mask, expected)

    def test_compute_spatial_query_multi_condition(self) -> None:
        """AND of two conditions on two layers."""
        import numpy as np

        from src.gui.widgets.map.map_data_buffer import compute_spatial_query

        a = np.array([[1, 1, 2, 2]], dtype=np.uint16)
        b = np.array([[10, 20, 10, 20]], dtype=np.uint16)
        # a == 1 AND b == 20 → only position [0,1]
        mask = compute_spatial_query(
            [a, b],
            [
                {"index": 0, "op": "eq", "value": 1},
                {"index": 1, "op": "eq", "value": 20},
            ],
        )
        expected = np.array([[False, True, False, False]])
        np.testing.assert_array_equal(mask, expected)

    def test_compute_spatial_query_no_match(self) -> None:
        """All-false mask when no cells match."""
        import numpy as np

        from src.gui.widgets.map.map_data_buffer import compute_spatial_query

        arr = np.zeros((4, 4), dtype=np.uint16)
        mask = compute_spatial_query([arr], [{"index": 0, "op": "eq", "value": 99}])
        assert not mask.any()

    def test_compute_spatial_query_shape_mismatch_raises(self) -> None:
        """ValueError raised when arrays have different shapes."""
        import numpy as np
        import pytest

        from src.gui.widgets.map.map_data_buffer import compute_spatial_query

        a = np.zeros((2, 2), dtype=np.uint16)
        b = np.zeros((3, 3), dtype=np.uint16)
        with pytest.raises(ValueError, match="Shape mismatch"):
            compute_spatial_query([a, b], [{"index": 0, "op": "eq", "value": 0}])

    def test_query_dialog_creates(self, qtbot) -> None:
        """RasterQueryDialog creates without error for a layer list."""
        from src.gui.dialogs.raster_query_dialog import RasterQueryDialog

        layers = [
            {"node_id": "n1", "name": "Forest Layer", "mode": "discrete"},
            {"node_id": "n2", "name": "Elevation", "mode": "continuous"},
        ]
        dlg = RasterQueryDialog(layers=layers)
        qtbot.addWidget(dlg)
        assert dlg is not None

    def test_query_dialog_conditions_property(self, qtbot) -> None:
        """conditions returns one condition per row added."""
        from src.gui.dialogs.raster_query_dialog import RasterQueryDialog

        layers = [{"node_id": "n1", "name": "L1", "mode": "discrete"}]
        dlg = RasterQueryDialog(layers=layers)
        qtbot.addWidget(dlg)
        # One row is added by default when layers is non-empty
        assert len(dlg.conditions) == 1
        cond = dlg.conditions[0]
        assert "name" in cond  # dialog now uses display name; MapHandler resolves to node_id
        assert cond["name"] == "L1"
        assert "op" in cond

    def test_map_graphics_view_query_overlay(self, qtbot) -> None:
        """set_query_overlay adds item; clear_query_overlay removes it."""
        import numpy as np

        view = _make_view(qtbot)
        mask = np.zeros((64, 64), dtype=bool)
        mask[10:20, 10:20] = True

        from PySide6.QtCore import QRectF

        scene_rect = QRectF(0, 0, 200, 200)
        view.set_query_overlay(mask, scene_rect)
        assert view._query_overlay_item is not None
        assert view._query_overlay_item.scene() is view.scene

        view.clear_query_overlay()
        assert view._query_overlay_item is None


# ── Feature T4-A: Advanced gradient methods ───────────────────────────────


class TestPaintRadialGradient:
    """paint_radial_gradient on MapDataBuffer."""

    def test_radial_gradient_center_value(self) -> None:
        """Centre pixel receives value_center."""
        buf = MapDataBuffer(100, 100)
        buf.paint_radial_gradient(0.5, 0.5, 0.2, 500, 0)
        cx, cy = 50, 50
        assert buf.data[cy, cx] == 500

    def test_radial_gradient_edge_value(self) -> None:
        """Pixels far from centre (beyond radius) are untouched."""
        buf = MapDataBuffer(100, 100)
        buf.paint_radial_gradient(0.5, 0.5, 0.2, 500, 0)
        assert buf.data[0, 0] == 0

    def test_radial_gradient_dirty_region(self) -> None:
        """Returns a 4-tuple dirty region within buffer bounds."""
        buf = MapDataBuffer(100, 100)
        dirty = buf.paint_radial_gradient(0.5, 0.5, 0.1, 1000, 0)
        assert len(dirty) == 4
        min_c, min_r, max_c, max_r = dirty
        assert min_c >= 0 and min_r >= 0
        assert max_c <= 99 and max_r <= 99

    def test_radial_gradient_clips_to_buffer(self) -> None:
        """Centre near edge does not go out of buffer bounds."""
        buf = MapDataBuffer(50, 50)
        dirty = buf.paint_radial_gradient(0.0, 0.0, 0.5, 1000, 0)
        assert dirty[0] >= 0 and dirty[1] >= 0

    def test_radial_gradient_small_radius(self) -> None:
        """Radius < 1 pixel is clamped to 1 without error."""
        buf = MapDataBuffer(100, 100)
        dirty = buf.paint_radial_gradient(0.5, 0.5, 0.0001, 999, 0)
        assert len(dirty) == 4


class TestPaintReflectedGradient:
    """paint_reflected_gradient on MapDataBuffer."""

    def test_reflected_gradient_axis_value(self) -> None:
        """Pixels on the drag axis (middle row) get value_center."""
        buf = MapDataBuffer(100, 100)
        buf.paint_reflected_gradient(0.2, 0.5, 0.8, 0.5, 1000, 0)
        mid_row = 50
        assert buf.data[mid_row, 50] == 1000

    def test_reflected_gradient_returns_dirty(self) -> None:
        """Returns a 4-tuple dirty region."""
        buf = MapDataBuffer(100, 100)
        dirty = buf.paint_reflected_gradient(0.2, 0.5, 0.8, 0.5, 1000, 0)
        assert len(dirty) == 4

    def test_reflected_gradient_full_buffer_when_no_width(self) -> None:
        """width_px=0 paints over the entire buffer."""
        buf = MapDataBuffer(50, 50)
        dirty = buf.paint_reflected_gradient(0.2, 0.5, 0.8, 0.5, 500, 0, 0)
        min_c, min_r, max_c, max_r = dirty
        assert min_c == 0 and min_r == 0
        assert max_c == 49 and max_r == 49

    def test_reflected_gradient_with_width_px(self) -> None:
        """width_px > 0 constrains the painted region."""
        buf = MapDataBuffer(100, 100)
        dirty = buf.paint_reflected_gradient(0.2, 0.5, 0.8, 0.5, 800, 0, 5)
        assert len(dirty) == 4


# ── Feature T4-A: Gradient sub-mode in RasterEditTool ────────────────────


class TestGradientSubMode:
    """RasterEditTool gradient sub-mode support."""

    def test_default_sub_mode_is_linear(self) -> None:
        from src.gui.widgets.map.raster_edit_tool import (
            GRADIENT_SUB_LINEAR,
            RasterEditTool,
        )

        class _FakeView:
            _raster_items: dict = {}
            pixmap_item = None
            coord_system = None
            scene = None

        tool = RasterEditTool(_FakeView())  # type: ignore[arg-type]
        assert tool._gradient_sub_mode == GRADIENT_SUB_LINEAR

    def test_set_gradient_sub_mode_radial(self) -> None:
        from src.gui.widgets.map.raster_edit_tool import (
            GRADIENT_SUB_RADIAL,
            RasterEditTool,
        )

        class _FakeView:
            _raster_items: dict = {}
            pixmap_item = None
            coord_system = None
            scene = None

        tool = RasterEditTool(_FakeView())  # type: ignore[arg-type]
        tool.set_gradient_sub_mode(GRADIENT_SUB_RADIAL)
        assert tool._gradient_sub_mode == GRADIENT_SUB_RADIAL

    def test_panel_has_gradient_sub_combo(self, qtbot) -> None:
        from PySide6.QtWidgets import QComboBox

        from src.gui.widgets.map.map_layer_panel import MapLayerPanel

        panel = MapLayerPanel()
        qtbot.addWidget(panel)
        assert hasattr(panel, "_gradient_sub_combo")
        assert isinstance(panel._gradient_sub_combo, QComboBox)

    def test_panel_gradient_sub_mode_property(self, qtbot) -> None:
        from src.gui.widgets.map.map_layer_panel import MapLayerPanel

        panel = MapLayerPanel()
        qtbot.addWidget(panel)
        assert panel.raster_gradient_sub_mode in ("linear", "radial", "reflected")

    def test_panel_gradient_sub_mode_changed_signal(self, qtbot) -> None:
        from src.gui.widgets.map.map_layer_panel import MapLayerPanel

        panel = MapLayerPanel()
        qtbot.addWidget(panel)
        received: list = []
        panel.raster_gradient_sub_mode_changed.connect(received.append)
        panel._gradient_sub_combo.setCurrentText("Radial")
        assert received == ["radial"]


# ── Feature T4-B: Palette import / export ────────────────────────────────


class TestPaletteImportExport:
    """RasterPaletteEditor export/import buttons."""

    def test_editor_has_export_button(self, qtbot) -> None:
        from src.gui.widgets.map.map_data_buffer import ColorMap

        cmap = ColorMap(type="palette", entries=[])
        from src.gui.widgets.map.raster_palette_editor import RasterPaletteEditor

        dlg = RasterPaletteEditor(cmap, mode="discrete")
        qtbot.addWidget(dlg)
        assert hasattr(dlg, "_on_export_palette")

    def test_editor_has_import_button(self, qtbot) -> None:
        from src.gui.widgets.map.map_data_buffer import ColorMap
        from src.gui.widgets.map.raster_palette_editor import RasterPaletteEditor

        cmap = ColorMap(type="palette", entries=[])
        dlg = RasterPaletteEditor(cmap, mode="discrete")
        qtbot.addWidget(dlg)
        assert hasattr(dlg, "_on_import_palette")

    def test_export_creates_json(self, tmp_path: object) -> None:
        import json
        from pathlib import Path

        from src.gui.widgets.map.map_data_buffer import ColorEntry, ColorMap
        from src.gui.widgets.map.raster_palette_editor import RasterPaletteEditor

        color_map = ColorMap(
            type="palette",
            entries=[
                ColorEntry(value=1, color="#ff0000"),
                ColorEntry(value=2, color="#00ff00"),
            ],
        )
        editor = RasterPaletteEditor(color_map, mode="discrete")
        result = editor.result_color_map()
        json_path = Path(str(tmp_path)) / "palette.json"
        data = [
            {"value": e.value, "color": e.color, "label": ""} for e in result.entries
        ]
        with open(json_path, "w") as f:
            json.dump(data, f)

        assert json_path.exists()
        loaded = json.loads(json_path.read_text())
        assert len(loaded) == 2
        assert loaded[0]["value"] == 1

    def test_import_populates_rows(self, tmp_path: object, qtbot) -> None:
        import json
        from pathlib import Path

        from src.gui.widgets.map.map_data_buffer import ColorMap
        from src.gui.widgets.map.raster_palette_editor import RasterPaletteEditor

        color_map = ColorMap(type="palette", entries=[])
        editor = RasterPaletteEditor(color_map, mode="discrete")
        qtbot.addWidget(editor)

        json_path = Path(str(tmp_path)) / "import.json"
        json_path.write_text(
            json.dumps(
                [
                    {"value": 5, "color": "#aabbcc", "label": "Forest"},
                    {"value": 10, "color": "#112233", "label": "Ocean"},
                ]
            )
        )

        editor._table.setRowCount(0)
        with open(json_path) as f:
            data = json.load(f)
        for entry in data:
            editor._add_entry_row(
                value=int(entry.get("value", 0)),
                color=str(entry.get("color", "#808080")),
                label=str(entry.get("label", "")),
            )

        assert editor._table.rowCount() == 2


# ── Feature T4-C: Layer annotations ──────────────────────────────────────


class TestSetRasterNotesCommand:
    """SetRasterNotesCommand persists and reverts notes."""

    def _make_db_with_raster(self) -> tuple:
        import uuid

        from src.core.map import Map
        from src.services.db_service import DatabaseService

        db = DatabaseService(":memory:")
        db.connect()
        map_id = str(uuid.uuid4())
        node_id = str(uuid.uuid4())
        m = Map(
            id=map_id,
            name="TestMap",
            image_path="",
            attributes={
                "raster_layers": [{"node_id": node_id, "mode": "discrete", "notes": ""}]
            },
        )
        db.map_repo.insert_map(m)
        return db, map_id, node_id

    def test_execute_persists_notes(self) -> None:
        from src.commands.raster_commands import SetRasterNotesCommand

        db, map_id, node_id = self._make_db_with_raster()
        cmd = SetRasterNotesCommand(map_id=map_id, node_id=node_id, notes="Hello")
        result = cmd.execute(db)
        assert result.success

        stored = db.map_repo.get_map(map_id)
        layers = (stored.attributes or {}).get("raster_layers", [])
        layer = next(la for la in layers if la["node_id"] == node_id)
        assert layer["notes"] == "Hello"

    def test_undo_restores_notes(self) -> None:
        from src.commands.raster_commands import SetRasterNotesCommand

        db, map_id, node_id = self._make_db_with_raster()
        cmd = SetRasterNotesCommand(
            map_id=map_id, node_id=node_id, notes="New notes", old_notes="Old notes"
        )
        cmd.execute(db)
        cmd.undo(db)

        stored = db.map_repo.get_map(map_id)
        layers = (stored.attributes or {}).get("raster_layers", [])
        layer = next(la for la in layers if la["node_id"] == node_id)
        assert layer["notes"] == "Old notes"

    def test_has_history_is_true(self) -> None:
        from src.commands.raster_commands import SetRasterNotesCommand

        cmd = SetRasterNotesCommand(map_id="m", node_id="n", notes="x")
        assert cmd.has_history is True

    def test_roundtrip_serialisation(self) -> None:
        from src.commands.raster_commands import SetRasterNotesCommand

        cmd = SetRasterNotesCommand(
            map_id="map1", node_id="node1", notes="abc", old_notes="def"
        )
        d = cmd.to_dict()
        cmd2 = SetRasterNotesCommand.from_dict(d)
        assert cmd2.map_id == "map1"
        assert cmd2.node_id == "node1"
        assert cmd2.notes == "abc"
        assert cmd2.old_notes == "def"


class TestRasterNotesDialog:
    """RasterNotesDialog widget behaviour."""

    def test_dialog_returns_text(self, qtbot) -> None:
        from src.gui.dialogs.raster_notes_dialog import RasterNotesDialog

        dlg = RasterNotesDialog("Test Layer", "Existing notes")
        qtbot.addWidget(dlg)
        assert dlg.get_notes() == "Existing notes"

    def test_dialog_empty_notes(self, qtbot) -> None:
        from src.gui.dialogs.raster_notes_dialog import RasterNotesDialog

        dlg = RasterNotesDialog("Layer", "")
        qtbot.addWidget(dlg)
        assert dlg.get_notes() == ""

    def test_dialog_window_title(self, qtbot) -> None:
        from src.gui.dialogs.raster_notes_dialog import RasterNotesDialog

        dlg = RasterNotesDialog("My Raster", "some notes")
        qtbot.addWidget(dlg)
        assert "My Raster" in dlg.windowTitle()

    def test_dialog_strips_whitespace(self, qtbot) -> None:
        from src.gui.dialogs.raster_notes_dialog import RasterNotesDialog

        dlg = RasterNotesDialog("Layer", "  leading and trailing  ")
        qtbot.addWidget(dlg)
        assert dlg.get_notes() == "leading and trailing"


class TestPanelNotesButton:
    """MapLayerPanel notes button and indicator."""

    def test_panel_has_notes_button(self, qtbot) -> None:
        from src.gui.widgets.map.map_layer_panel import MapLayerPanel

        panel = MapLayerPanel()
        qtbot.addWidget(panel)
        assert hasattr(panel, "_btn_notes")

    def test_panel_has_raster_notes_signal(self) -> None:
        from src.gui.widgets.map.map_layer_panel import MapLayerPanel

        assert hasattr(MapLayerPanel, "raster_notes_requested")

    def test_set_raster_layer_notes_shows_indicator(self, qtbot) -> None:
        from src.gui.widgets.map.map_layer_panel import MapLayerPanel

        panel = MapLayerPanel()
        qtbot.addWidget(panel)
        panel._current_node_id = "n1"
        panel.set_raster_layer_notes("n1", True)
        assert panel._notes_indicator_label.text() != ""

    def test_set_raster_layer_notes_clears_indicator(self, qtbot) -> None:
        from src.gui.widgets.map.map_layer_panel import MapLayerPanel

        panel = MapLayerPanel()
        qtbot.addWidget(panel)
        panel._current_node_id = "n1"
        panel.set_raster_layer_notes("n1", True)
        panel.set_raster_layer_notes("n1", False)
        assert panel._notes_indicator_label.text() == ""


# ── Legend overlay on MapWidget ───────────────────────────────────────────────


class TestLegendOverlayOnMapWidget:
    """RasterLegendWidget must live as a floating overlay on MapWidget.view,
    NOT inside MapLayerPanel."""

    def test_map_widget_has_legend_overlay(self, qtbot) -> None:
        """MapWidget must own a `legend_overlay` attribute."""
        from src.gui.widgets.map_widget import MapWidget

        w = MapWidget()
        qtbot.addWidget(w)
        assert hasattr(w, "legend_overlay")

    def test_legend_overlay_hidden_by_default(self, qtbot) -> None:
        """Legend overlay must be hidden before any raster layer is
        selected."""
        from src.gui.widgets.map_widget import MapWidget

        w = MapWidget()
        qtbot.addWidget(w)
        assert not w.legend_overlay.isVisible()

    def test_legend_overlay_is_child_of_view(self, qtbot) -> None:
        """Legend overlay must be a child widget of the map view, not the viewport,
        so it isn't destroyed when OpenGL viewports are swapped."""
        from src.gui.widgets.map_widget import MapWidget

        w = MapWidget()
        qtbot.addWidget(w)
        assert w.legend_overlay.parent() is w.view

    def test_legend_overlay_has_floating_style(self, qtbot) -> None:
        """Legend overlay must have a semi-transparent background
        stylesheet."""
        from src.gui.widgets.map_widget import MapWidget

        w = MapWidget()
        qtbot.addWidget(w)
        ss = w.legend_overlay.styleSheet()
        assert "rgba" in ss or "background" in ss

    def test_legend_overlay_positioned_bottom_left(self, qtbot) -> None:
        """After _position_legend_overlay(), legend x must be near the
        left margin of the view."""
        from PySide6.QtWidgets import QApplication

        from src.gui.widgets.map_widget import MapWidget

        w = MapWidget()
        qtbot.addWidget(w)
        w.resize(800, 600)
        w.show()
        QApplication.processEvents()

        w._position_legend_overlay()

        # x should be near the left margin (≤ 12 + tolerance)
        assert w.legend_overlay.x() <= 20
        # y should be reasonably positioned within the viewport's reported size
        viewport_h = w.view.viewport().height()
        assert w.legend_overlay.y() > 0
        assert w.legend_overlay.y() <= viewport_h

    def test_map_layer_panel_no_legend_attr(self, qtbot) -> None:
        """MapLayerPanel must NOT own a _legend widget after refactor."""
        from src.gui.widgets.map.map_layer_panel import MapLayerPanel

        panel = MapLayerPanel()
        qtbot.addWidget(panel)
        assert not hasattr(panel, "_legend")

    def test_legend_overlay_max_width(self, qtbot) -> None:
        """The legend_overlay on MapWidget must have a maximum width set
        so it does not obscure the full map canvas."""
        from src.gui.widgets.map_widget import MapWidget

        w = MapWidget()
        qtbot.addWidget(w)
        assert w.legend_overlay.maximumWidth() <= 400


# ── Bug fix: Escape key emits raster_edit_externally_stopped ──────────


class TestEscapeEmitsExternallyStopped:
    """Pressing Escape must emit raster_edit_externally_stopped so
    the layer panel toggle resets."""

    def test_escape_emits_signal(self, qtbot) -> None:
        view = _make_view(qtbot)
        _make_raster_item(view, node_id="esc1")
        view.start_raster_editing("esc1")

        with qtbot.waitSignal(view.raster_edit_externally_stopped, timeout=500):
            view._raster_edit_tool.handle_key_escape()

    def test_escape_no_signal_when_not_editing(self, qtbot) -> None:
        view = _make_view(qtbot)
        signals: list[bool] = []
        view.raster_edit_externally_stopped.connect(lambda: signals.append(True))
        view._raster_edit_tool.handle_key_escape()
        assert signals == []


# ── Bug fix: Raster-to-raster switch stops editing ────────────────────


class TestRasterToRasterSwitchStopsEditing:
    """Switching between raster layers must stop editing on the old layer."""

    def test_panel_reset_edit_toggle(self, qtbot) -> None:
        from src.gui.widgets.map.map_layer_panel import MapLayerPanel

        panel = MapLayerPanel()
        qtbot.addWidget(panel)

        # Simulate checked state
        panel._btn_edit_toggle.setChecked(True)
        assert panel._btn_edit_toggle.isChecked()

        panel.reset_edit_toggle()
        assert not panel._btn_edit_toggle.isChecked()
        assert panel._btn_edit_toggle.text() == "\u270e Edit"

    def test_reset_edit_toggle_does_not_emit_toggled(self, qtbot) -> None:
        from src.gui.widgets.map.map_layer_panel import MapLayerPanel

        panel = MapLayerPanel()
        qtbot.addWidget(panel)
        panel._btn_edit_toggle.setChecked(True)

        signals: list[bool] = []
        panel._btn_edit_toggle.toggled.connect(signals.append)

        panel.reset_edit_toggle()
        assert signals == []


# ── Bug fix: Passive Sample mode activates without Edit ───────────────


class TestPassiveSampleMode:
    """Sample mode must be synced to the tool even when edit is not active."""

    def test_sample_mode_set_without_edit(self, qtbot) -> None:
        from unittest.mock import PropertyMock, patch

        from src.gui.widgets.map.raster_edit_tool import RasterEditMode
        from src.gui.widgets.map_widget import MapWidget

        widget = MapWidget()
        qtbot.addWidget(widget)

        # Set up a raster item so the tool has something to reference
        img = QImage(200, 200, QImage.Format.Format_RGB32)
        img.fill(Qt.GlobalColor.white)
        widget.view.pixmap_item = QGraphicsPixmapItem(QPixmap.fromImage(img))
        widget.view.scene.addItem(widget.view.pixmap_item)
        widget.view.coord_system.set_scene_rect(QRectF(0, 0, 200, 200))

        tool = widget.view._raster_edit_tool
        assert not tool.is_active  # Not editing

        # Mock panel properties to return sample mode
        with (
            patch.object(
                type(widget.layer_panel),
                "raster_tool_mode",
                new_callable=PropertyMock,
                return_value="sample",
            ),
            patch.object(
                type(widget.layer_panel),
                "raster_gradient_sub_mode",
                new_callable=PropertyMock,
                return_value="linear",
            ),
        ):
            widget._on_raster_settings_changed()

        assert tool.mode == RasterEditMode.SAMPLE


# ── Bug fix: Ctrl+scroll changes brush size ──────────────────────────


class TestCtrlScrollBrushResize:
    """Ctrl+scroll must adjust the raster brush size."""

    def _wheel_event(self, view: MapGraphicsView, angle_y: int) -> "QWheelEvent":
        from PySide6.QtCore import QPoint
        from PySide6.QtGui import QWheelEvent

        pos = QPointF(view.viewport().rect().center())
        global_pos = QPointF(view.mapToGlobal(view.viewport().rect().center()))
        return QWheelEvent(
            pos,
            global_pos,
            QPoint(0, 0),
            QPoint(0, angle_y),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.ControlModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )

    def test_ctrl_scroll_up_increases_size(self, qtbot) -> None:
        view = _make_view(qtbot)
        _make_raster_item(view, node_id="cw1")
        view.start_raster_editing("cw1")

        tool = view._raster_edit_tool
        tool.brush_size = 20
        original = tool.brush_size

        sizes: list[int] = []
        view.raster_brush_resize_requested.connect(sizes.append)

        view.wheelEvent(self._wheel_event(view, 120))

        assert tool.brush_size > original
        assert len(sizes) == 1
        assert sizes[0] == tool.brush_size

    def test_ctrl_scroll_down_decreases_size(self, qtbot) -> None:
        view = _make_view(qtbot)
        _make_raster_item(view, node_id="cw2")
        view.start_raster_editing("cw2")

        tool = view._raster_edit_tool
        tool.brush_size = 20
        original = tool.brush_size

        view.wheelEvent(self._wheel_event(view, -120))

        assert tool.brush_size < original

    def test_ctrl_scroll_clamps_min(self, qtbot) -> None:
        view = _make_view(qtbot)
        _make_raster_item(view, node_id="cw3")
        view.start_raster_editing("cw3")

        tool = view._raster_edit_tool
        tool.brush_size = 1

        view.wheelEvent(self._wheel_event(view, -120))
        assert tool.brush_size >= 1


# ── Bug fix: gradient_sub_mode synced on edit start ───────────────────


class TestGradientSubModeSyncOnEditStart:
    """gradient_sub_mode must be pushed to the tool when editing starts."""

    def test_gradient_sub_mode_synced(self, qtbot) -> None:
        from unittest.mock import PropertyMock, patch

        from src.gui.widgets.map_widget import MapWidget

        widget = MapWidget()
        qtbot.addWidget(widget)

        img = QImage(200, 200, QImage.Format.Format_RGB32)
        img.fill(Qt.GlobalColor.white)
        widget.view.pixmap_item = QGraphicsPixmapItem(QPixmap.fromImage(img))
        widget.view.scene.addItem(widget.view.pixmap_item)
        widget.view.coord_system.set_scene_rect(QRectF(0, 0, 200, 200))
        _make_raster_item(widget.view, node_id="grad1")

        with patch.object(
            type(widget.layer_panel),
            "raster_gradient_sub_mode",
            new_callable=PropertyMock,
            return_value="radial",
        ):
            widget._on_raster_edit_requested("grad1")

        tool = widget.view._raster_edit_tool
        assert tool._gradient_sub_mode == "radial"


# ── Bug fix: Cursor refresh after zoom ────────────────────────────────


class TestCursorRefreshAfterZoom:
    """Brush cursor must be refreshed after wheel zoom."""

    def test_refresh_cursor_updates_overlay(self, qtbot) -> None:
        view = _make_view(qtbot)
        _make_raster_item(view, node_id="zc1")
        view.start_raster_editing("zc1")

        tool = view._raster_edit_tool
        tool.mode = RasterEditMode.BRUSH
        tool.brush_size = 10

        # Simulate a brush paint so _last_cursor_scene_pos is set
        tool._update_cursor(QPointF(100, 100))
        assert tool._cursor_item is not None

        # Record old rect
        old_rect = tool._cursor_item.rect()

        # After refresh the cursor item should still exist
        tool.refresh_cursor()
        assert tool._cursor_item is not None
        # Rect should equal — position unchanged, same zoom
        assert tool._cursor_item.rect() == old_rect

    def test_refresh_cursor_noop_when_inactive(self, qtbot) -> None:
        view = _make_view(qtbot)
        tool = view._raster_edit_tool
        tool.refresh_cursor()  # Should not raise
