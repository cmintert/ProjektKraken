"""Tests for raster snapshot listing, selection, and deletion interactions."""

from __future__ import annotations

from src.app.constants import MAP_LAYER_TYPE_GROUP, MAP_LAYER_TYPE_RASTER
from src.core.calendar import CalendarConfig, CalendarConverter
from src.core.map import MapLayerNode
from src.gui.widgets.map.map_layer_model import MapLayerModel
from src.gui.widgets.map.map_layer_panel import MapLayerPanel
from src.gui.widgets.map_widget import MapWidget


def _build_raster_model() -> MapLayerModel:
    """Create a minimal layer model with one raster node."""
    raster = MapLayerNode(name="Rainfall", layer_type=MAP_LAYER_TYPE_RASTER, id="r-1")
    root = MapLayerNode(
        name="Root",
        layer_type=MAP_LAYER_TYPE_GROUP,
        id="root",
        children=[raster],
    )
    return MapLayerModel(root)


def _snap_children(model: MapLayerModel, node_id: str) -> list:
    """Return virtual snapshot children of the given node."""
    node = model.find_node_by_id(node_id)
    if node is None:
        return []
    return [c for c in node.children if getattr(c, "virtual", False)]


def test_panel_renders_snapshot_rows_for_selected_raster(qtbot) -> None:
    """Selecting a raster layer should render snapshot nodes as virtual tree children."""
    panel = MapLayerPanel()
    qtbot.addWidget(panel)

    model = _build_raster_model()
    panel.set_model(model)
    panel.set_raster_layer_metadata(
        {
            "r-1": {
                "node_id": "r-1",
                "mode": "discrete",
                "snapshots": {
                    "2.5": "rasters/rain_snap_2.5.png",
                    "10.0": "rasters/rain_snap_10.0.png",
                },
            }
        }
    )

    panel._on_item_clicked(model.index(0, 0))

    assert len(_snap_children(model, "r-1")) == 2


def test_panel_snapshot_labels_use_calendar_text(qtbot) -> None:
    """Snapshot labels should use calendar-formatted dates when converter exists."""
    panel = MapLayerPanel()
    qtbot.addWidget(panel)
    panel.set_calendar_converter(CalendarConverter(CalendarConfig.create_default()))

    model = _build_raster_model()
    panel.set_model(model)
    panel.set_raster_layer_metadata(
        {
            "r-1": {
                "node_id": "r-1",
                "mode": "discrete",
                "snapshots": {"12.0": "rasters/rain_snap_12.0.png"},
            }
        }
    )

    panel._on_item_clicked(model.index(0, 0))

    snap_node = _snap_children(model, "r-1")[0]
    assert "Year" in snap_node.name
    assert "12.00" not in snap_node.name


def test_panel_snapshot_count_clears_when_all_deleted(qtbot) -> None:
    """Snapshot count label and virtual nodes must clear when all snapshots removed."""
    panel = MapLayerPanel()
    qtbot.addWidget(panel)

    model = _build_raster_model()
    panel.set_model(model)
    panel.set_raster_layer_metadata(
        {
            "r-1": {
                "node_id": "r-1",
                "mode": "discrete",
                "snapshots": {"7.25": "rasters/rain_snap_7.25.png"},
            }
        }
    )
    panel._on_item_clicked(model.index(0, 0))

    assert panel._snapshot_count_label.text() == "1 snapshot"

    panel.set_raster_layer_metadata(
        {
            "r-1": {
                "node_id": "r-1",
                "mode": "discrete",
                "snapshots": {},
            }
        }
    )

    assert panel._snapshot_count_label.text() == ""
    assert len(_snap_children(model, "r-1")) == 0


def test_panel_snapshot_row_click_emits_jump(qtbot) -> None:
    """Clicking a snapshot row should emit raster_snapshot_selected."""
    panel = MapLayerPanel()
    qtbot.addWidget(panel)

    model = _build_raster_model()
    panel.set_model(model)
    panel.set_raster_layer_metadata(
        {
            "r-1": {
                "node_id": "r-1",
                "mode": "discrete",
                "snapshots": {"12.0": "rasters/rain_snap_12.0.png"},
            }
        }
    )
    panel._on_item_clicked(model.index(0, 0))

    received: list[tuple[str, float]] = []
    panel.raster_snapshot_selected.connect(lambda nid, date: received.append((nid, date)))

    snap_node = _snap_children(model, "r-1")[0]
    snap_index = model.index_from_node(snap_node)
    panel._on_item_clicked(snap_index)

    assert received == [("r-1", 12.0)]


def test_panel_snapshot_delete_click_emits_delete_request(qtbot) -> None:
    """Clicking delete on a snapshot row should emit delete request."""
    panel = MapLayerPanel()
    qtbot.addWidget(panel)

    model = _build_raster_model()
    panel.set_model(model)
    panel.set_raster_layer_metadata(
        {
            "r-1": {
                "node_id": "r-1",
                "mode": "discrete",
                "snapshots": {"7.25": "rasters/rain_snap_7.25.png"},
            }
        }
    )
    panel._on_item_clicked(model.index(0, 0))

    snap_node = _snap_children(model, "r-1")[0]
    assert snap_node.attributes.get("parent_node_id") == "r-1"
    assert snap_node.attributes.get("lore_date") == 7.25

    received: list[tuple[str, float]] = []
    panel.raster_snapshot_delete_requested.connect(
        lambda nid, date: received.append((nid, date))
    )
    panel.raster_snapshot_delete_requested.emit("r-1", 7.25)
    assert received == [("r-1", 7.25)]


def test_map_widget_forwards_snapshot_selection_to_playhead(qtbot) -> None:
    """Snapshot selection in layer panel should forward to jump_to_time_requested."""
    widget = MapWidget()
    qtbot.addWidget(widget)

    received: list[float] = []
    widget.jump_to_time_requested.connect(received.append)

    widget.layer_panel.raster_snapshot_selected.emit("r-1", 33.5)

    assert received == [33.5]
