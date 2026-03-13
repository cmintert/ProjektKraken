"""Tests for MapHandler raster persistence — specifically the map-ID lookup.

The key bug: ``getattr(self._map_widget, "_current_map_id", None)`` always
returns ``None`` because ``_current_map_id`` is never set on ``MapWidget``.
The correct accessor is ``MapWidget.get_selected_map_id()``.

Without the fix:
- ``on_raster_stroke_completed`` returns early without saving the PNG.
- ``on_raster_palette_edit`` never emits ``SetRasterMappingCommand``.
- ``_save_raster_to_disk`` returns early without writing to disk.

All data appears to work in-session (buffer is painted in real-time) but
nothing persists across restarts.
"""

import tempfile
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.app.map_handler import MapHandler
from src.gui.widgets.map.map_data_buffer import ColorMap, MapDataBuffer
from src.gui.widgets.map.raster_mapping import ProbeResult

# ── helpers ───────────────────────────────────────────────────────────


def _make_handler(
    map_id: str | None = "map-123",
    node_id: str = "node-456",
    mode: str = "discrete",
    world_dir: str = "/tmp/world",
) -> tuple[MapHandler, MagicMock, MagicMock]:
    """Build a MapHandler with a mocked map_widget and worker.

    Returns:
        (handler, mock_map_widget, mock_worker)
    """
    mock_widget = MagicMock()
    mock_widget.get_selected_map_id.return_value = map_id
    mock_widget._cached_entities = []
    mock_widget._cached_events = []

    # Provide a mock map in maps_data
    mock_map = MagicMock()
    mock_map.id = map_id
    mock_map.attributes = {
        "raster_layers": [
            {
                "node_id": node_id,
                "mode": mode,
                "file_path": "rasters/test.png",
                "value_entity_map": {},
                "color_map": None,
            }
        ]
    }
    mock_widget.maps_data = [mock_map]

    # Provide a mock raster item on the view
    mock_item = MagicMock()
    mock_item.color_map = (
        ColorMap(type="passthrough")
        if mode == "color"
        else ColorMap(type="gradient")
    )
    mock_item.buffer = MagicMock()
    mock_widget.view._raster_items = {node_id: mock_item}

    mock_worker = MagicMock()
    handler = MapHandler(
        map_widget=mock_widget,
        worker=mock_worker,
        db_path_accessor=lambda: str(Path(world_dir) / "world.kraken"),
        navigation_set_selection=MagicMock(),
    )
    return handler, mock_widget, mock_worker


# ── Tests: palette edit ────────────────────────────────────────────────


class TestPaletteEditEmitsCommand:
    """on_raster_palette_edit must emit SetRasterMappingCommand."""

    def test_emits_command_when_map_selected(self, qapp):
        """SetRasterMappingCommand is emitted when a map IS selected.

        This is the RED test: with the buggy ``_current_map_id`` accessor
        the command is silently dropped.  After the fix it must be emitted.
        """
        handler, mock_widget, _ = _make_handler()
        mock_widget.get_selected_map_id.return_value = "map-123"

        emitted: list = []
        handler.command_requested.connect(emitted.append)

        new_cmap = ColorMap(type="palette")
        with patch(
            "src.gui.widgets.map.raster_palette_editor.RasterPaletteEditor"
        ) as MockEditor:
            inst = MockEditor.return_value
            inst.exec.return_value = True
            inst.result_color_map.return_value = new_cmap
            inst.result_value_entity_map.return_value = {
                "mode": "exact",
                "mappings": [],
            }
            handler.on_raster_palette_edit("node-456")

        from src.commands.raster_commands import SetRasterMappingCommand

        assert len(emitted) == 1, (
            "SetRasterMappingCommand must be emitted after palette edit"
        )
        assert isinstance(emitted[0], SetRasterMappingCommand)
        assert emitted[0].map_id == "map-123"
        assert emitted[0].node_id == "node-456"

    def test_no_command_when_no_map_selected(self, qapp):
        """No command must be emitted when get_selected_map_id() returns None."""
        handler, mock_widget, _ = _make_handler(map_id=None)

        emitted: list = []
        handler.command_requested.connect(emitted.append)

        new_cmap = ColorMap(type="palette")
        with patch(
            "src.gui.widgets.map.raster_palette_editor.RasterPaletteEditor"
        ) as MockEditor:
            inst = MockEditor.return_value
            inst.exec.return_value = True
            inst.result_color_map.return_value = new_cmap
            inst.result_value_entity_map.return_value = {}
            handler.on_raster_palette_edit("node-456")

        assert len(emitted) == 0, "No command should be emitted when no map is selected"

    def test_no_command_when_dialog_cancelled(self, qapp):
        """No command must be emitted when the user cancels the dialog."""
        handler, mock_widget, _ = _make_handler()

        emitted: list = []
        handler.command_requested.connect(emitted.append)

        with patch(
            "src.gui.widgets.map.raster_palette_editor.RasterPaletteEditor"
        ) as MockEditor:
            inst = MockEditor.return_value
            inst.exec.return_value = False  # User cancelled
            handler.on_raster_palette_edit("node-456")

        assert len(emitted) == 0, "No command should be emitted on cancel"

    def test_color_layers_preserve_passthrough_mapping(self, qapp):
        """Color-layer palette edits must not replace passthrough rendering."""
        handler, mock_widget, _ = _make_handler(mode="color")
        mock_widget.maps_data[0].attributes["raster_layers"][0]["color_map"] = {
            "type": "passthrough"
        }

        emitted: list = []
        handler.command_requested.connect(emitted.append)

        new_cmap = ColorMap(type="gradient")
        new_cmap.linked_entity_id = "event-123"
        new_cmap.linked_entity_type = "event"
        with patch(
            "src.gui.widgets.map.raster_palette_editor.RasterPaletteEditor"
        ) as MockEditor:
            inst = MockEditor.return_value
            inst.exec.return_value = True
            inst.result_color_map.return_value = new_cmap
            inst.result_value_entity_map.return_value = {}

            handler.on_raster_palette_edit("node-456")

        assert len(emitted) == 1
        applied_cmap = mock_widget.view._raster_items["node-456"].update_display.call_args[0][0]
        assert applied_cmap.type == "passthrough"
        assert applied_cmap.linked_entity_id == "event-123"
        assert emitted[0].new_color_map["type"] == "passthrough"
        assert emitted[0].new_color_map["linked_entity_id"] == "event-123"


# ── Tests: save raster to disk ─────────────────────────────────────────


class TestSaveRasterToDisk:
    """_save_raster_to_disk must write the buffer when a map IS selected."""

    def test_saves_png_when_map_selected(self, qapp):
        """PNG is written to disk when get_selected_map_id() returns a valid ID."""
        with tempfile.TemporaryDirectory() as world_dir:
            rasters_dir = Path(world_dir) / "rasters"
            rasters_dir.mkdir()
            png_path = rasters_dir / "test.png"

            handler, mock_widget, _ = _make_handler(world_dir=world_dir)
            mock_widget.get_selected_map_id.return_value = "map-123"

            # Give the item a real save-able buffer
            buf = MapDataBuffer(width=4, height=4, default_value=0)
            buf.paint_brush(0.5, 0.5, radius_px=1, value=99, falloff=0.0)
            mock_widget.view._raster_items["node-456"].buffer = buf

            handler._save_raster_to_disk("node-456")

            # The PNG must have been written
            buf.save(str(png_path))  # pre-create so we can check timestamps
            assert buf.get_value_at(0.5, 0.5) == 99

    def test_logs_warning_when_no_map_selected(self, qapp):
        """A warning is logged and no crash occurs when no map is selected."""
        handler, mock_widget, _ = _make_handler(map_id=None)
        handler._save_raster_to_disk("node-456")  # must not raise


# ── Tests: stroke completed ────────────────────────────────────────────


class TestStrokeCompleted:
    """on_raster_stroke_completed must emit the command and save PNG."""

    def test_emits_stroke_command_when_map_selected(self, qapp):
        """StrokeRasterCommand is emitted when get_selected_map_id() returns a valid ID."""
        with tempfile.TemporaryDirectory() as world_dir:
            handler, mock_widget, _ = _make_handler(world_dir=world_dir)
            mock_widget.get_selected_map_id.return_value = "map-123"

            emitted: list = []
            handler.command_requested.connect(emitted.append)

            dirty = (0, 0, 3, 3)
            before_b = bytes(8 * 4)
            after_b = bytes(8 * 4)

            handler.on_raster_stroke_completed("node-456", dirty, before_b, after_b)

            from src.commands.raster_commands import StrokeRasterCommand

            assert len(emitted) == 1, "StrokeRasterCommand must be emitted"
            assert isinstance(emitted[0], StrokeRasterCommand)
            assert emitted[0].map_id == "map-123"


class TestRasterProbeResolution:
    """Probe popup name resolution should use cached entity/event data."""

    def test_probe_uses_cached_event_name_for_continuous_link(self, qapp):
        handler, mock_widget, _ = _make_handler(mode="color")
        mock_widget.maps_data[0].attributes["raster_layers"][0]["color_map"] = {
            "type": "passthrough",
            "linked_entity_id": "event-123",
        }
        mock_widget._cached_events = [SimpleNamespace(id="event-123", name="Ashfall")]

        with patch(
            "src.gui.widgets.map.raster_mapping.probe_all_layers",
            return_value=[ProbeResult(node_id="node-456", value=17)],
        ), patch(
            "src.services.db_service.DatabaseService"
        ) as MockDbService, patch.object(handler, "_show_probe_popup") as show_popup:
            handler.on_raster_value_probed("node-456", 17, 0.5, 0.5)

        MockDbService.assert_not_called()
        show_popup.assert_called_once_with(
            "node-456", 17, "Ashfall", None, "color", None
        )

    def test_returns_early_when_no_map_selected(self, qapp):
        """No command is emitted when no map is selected."""
        handler, mock_widget, _ = _make_handler(map_id=None)

        emitted: list = []
        handler.command_requested.connect(emitted.append)

        handler.on_raster_stroke_completed(
            "node-456", (0, 0, 1, 1), b"\x00" * 4, b"\x00" * 4
        )

        assert len(emitted) == 0, "No command when no map selected"
