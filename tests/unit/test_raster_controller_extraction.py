"""Characterization tests for the RasterController strangler extraction."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.app.map_handler import MapHandler
from src.app.raster_controller import RasterController


def _map_handler() -> tuple[MapHandler, MagicMock]:
    widget = MagicMock()
    widget.maps_data = []
    widget.map_selector.currentData.return_value = "map-1"
    handler = MapHandler(
        map_widget=widget,
        worker=MagicMock(),
        db_path_accessor=lambda: "C:/world/world.kraken",
        navigation_set_selection=MagicMock(),
    )
    return handler, widget


@pytest.mark.parametrize(
    ("method_name", "arguments"),
    [
        (
            "create_raster_layer",
            ("Layer", 8, 9, "discrete", 2, "", None, None, ""),
        ),
        ("delete_raster_layer", ("node-1",)),
        ("load_raster_layers", ("map-1",)),
        ("on_raster_stroke_completed", ("node-1", [], None, None)),
        ("has_pending_raster_strokes", ()),
        ("on_raster_palette_edit", ("node-1",)),
        ("on_raster_query_requested", ()),
        ("on_raster_query_cleared", ()),
        ("on_raster_value_probed", ("node-1", 3, 0.25, 0.75)),
        ("on_raster_stats_requested", ("node-1",)),
        ("on_raster_gradient_sub_mode_changed", ("radial",)),
        ("on_raster_notes_requested", ("node-1",)),
        ("on_playhead_changed", (12.0,)),
        ("on_raster_snapshot_requested", ("node-1",)),
        ("on_raster_snapshot_selected", ("node-1", 12.0)),
        ("on_raster_base_edit_requested", ("node-1",)),
        ("on_raster_snapshot_edit_requested", ("node-1", 12.0)),
        ("on_raster_snapshot_delete_requested", ("node-1", 12.0)),
    ],
)
def test_map_handler_raster_api_delegates_unchanged(
    qapp: object, method_name: str, arguments: tuple[object, ...]
) -> None:
    """Every public raster facade method forwards the original call."""
    handler, _ = _map_handler()
    sentinel = method_name == "has_pending_raster_strokes"
    with patch.object(
        handler._raster_controller,
        method_name,
        return_value=sentinel,
    ) as delegated:
        result = getattr(handler, method_name)(*arguments)

    delegated.assert_called_once_with(*arguments)
    if method_name == "has_pending_raster_strokes":
        assert result is sentinel
    else:
        assert result is None


def test_controller_signals_forward_once_through_map_handler(qapp: object) -> None:
    """Existing MapHandler observers receive controller intent unchanged."""
    handler, _ = _map_handler()
    commands: list[object] = []
    save_states: list[tuple[str, str, str]] = []
    handler.command_requested.connect(commands.append)
    handler.raster_save_state_changed.connect(
        lambda *values: save_states.append(values)
    )
    command = object()

    handler._raster_controller.command_requested.emit(command)
    handler._raster_controller.raster_save_state_changed.emit("node-1", "saved", "")

    assert commands == [command]
    assert save_states == [("node-1", "saved", "")]


def test_map_selection_notifies_controller_before_map_lookup(qapp: object) -> None:
    """Even an unavailable selection reaches raster lifecycle handling."""
    handler, _ = _map_handler()
    with patch.object(handler._raster_controller, "on_map_selected") as notify:
        handler.on_map_selected("missing-map")

    notify.assert_called_once_with("missing-map")


def test_marker_refresh_delegates_raster_loading_after_shared_sync(
    qapp: object,
) -> None:
    """MapHandler retains marker synchronization before raster delegation."""
    handler, widget = _map_handler()
    handler._loaded_markers_map_id = "map-1"
    widget.map_selector.currentData.return_value = "map-1"

    with (
        patch.object(handler, "_incremental_marker_update") as update_markers,
        patch.object(handler, "load_raster_layers") as load_rasters,
    ):
        handler.on_markers_ready("map-1", [])

    update_markers.assert_called_once_with("map-1", [])
    load_rasters.assert_called_once_with("map-1")


def test_command_effects_split_raster_and_generic_failure_paths(qapp: object) -> None:
    """Raster effects delegate while MapHandler retains generic reload recovery."""
    handler, _ = _map_handler()
    handler._raster_controller._current_map_id = "map-1"
    result = SimpleNamespace(success=False, command_name="RasterCommand", data={})

    with (
        patch.object(handler._raster_controller, "on_command_effects") as raster,
        patch.object(handler, "load_maps") as load_maps,
        patch.object(handler, "reload_markers") as reload_markers,
    ):
        handler.on_command_effects(result)

    raster.assert_called_once_with(result)
    load_maps.assert_called_once_with()
    reload_markers.assert_called_once_with("map-1")


def _controller(tmp_path: Path) -> tuple[RasterController, MagicMock]:
    widget = MagicMock()
    widget.maps_data = []
    widget.view._raster_items = {}
    controller = RasterController(
        map_widget=widget,
        db_path_accessor=lambda: str(tmp_path / "world.kraken"),
    )
    return controller, widget


def test_map_switch_clears_display_cache_and_query_but_keeps_pending_writes(
    qapp: object, tmp_path: Path
) -> None:
    """A new loaded map cannot reuse the previous map's raster display state."""
    controller, widget = _controller(tmp_path)
    old_item = MagicMock()
    widget.view._raster_items = {"old-node": old_item}
    widget.maps_data = [SimpleNamespace(id="map-2", attributes={"raster_layers": []})]
    controller._current_map_id = "map-1"
    controller._snapshot_cache[("old-node", "old.png", 1, 1)] = object()
    controller._current_snapshot_by_node["old-node"] = "old.png"
    controller._current_snapshot_identity_by_node["old-node"] = (
        "old-node",
        "old.png",
        1,
        1,
    )
    pending = object()
    controller._pending_raster_strokes["old-node"] = [pending]

    controller.load_raster_layers("map-2")

    assert controller.loaded_map_id == "map-2"
    assert not controller._snapshot_cache
    assert not controller._current_snapshot_by_node
    assert not controller._current_snapshot_identity_by_node
    assert controller._pending_raster_strokes == {"old-node": [pending]}
    widget.view.graphics_scene.removeItem.assert_called_once_with(old_item)
    widget.view.clear_query_overlay.assert_called_once_with()
    widget.layer_panel.set_query_active.assert_called_once_with(False)


def test_loading_map_establishes_base_raster_display(
    qapp: object, tmp_path: Path
) -> None:
    """Initial raster loading reads and records the undated base state."""
    controller, widget = _controller(tmp_path)
    metadata = {
        "node_id": "node-1",
        "file_path": "rasters/base.png",
        "mode": "discrete",
    }
    widget.maps_data = [
        SimpleNamespace(
            id="map-1",
            attributes={"raster_layers": [metadata]},
        )
    ]
    widget.view.pixmap_item = MagicMock()
    buffer = MagicMock()
    raster_item = MagicMock()

    with (
        patch(
            "src.gui.widgets.map.map_data_buffer.MapDataBuffer.from_file",
            return_value=buffer,
        ) as load_buffer,
        patch(
            "src.gui.widgets.map.raster_layer_item.RasterLayerItem",
            return_value=raster_item,
        ),
    ):
        controller.load_raster_layers("map-1")

    expected = str(tmp_path / "rasters/base.png")
    load_buffer.assert_called_once_with(expected, mode="discrete")
    assert controller._current_snapshot_by_node == {"node-1": expected}
    assert widget.view._raster_items == {"node-1": raster_item}


def test_map_selection_resets_failures_only_when_no_strokes_are_pending(
    qapp: object, tmp_path: Path
) -> None:
    """Selection preserves failure guards while dependent writes still exist."""
    controller, _ = _controller(tmp_path)
    controller._failed_raster_nodes.add("node-1")
    controller._pending_raster_strokes["node-1"] = [object()]

    controller.on_map_selected("map-2")
    assert controller._failed_raster_nodes == {"node-1"}

    controller._pending_raster_strokes.clear()
    controller.on_map_selected("map-2")
    assert not controller._failed_raster_nodes


def test_snapshot_cache_identity_changes_when_same_path_changes(
    qapp: object, tmp_path: Path
) -> None:
    """File state participates in cache identity to prevent stale reuse."""
    controller, _ = _controller(tmp_path)
    raster_path = tmp_path / "state.png"
    raster_path.write_bytes(b"old")
    first = controller._snapshot_cache_key("node-1", str(raster_path))

    raster_path.write_bytes(b"new-state")
    second = controller._snapshot_cache_key("node-1", str(raster_path))

    assert first != second


def test_selecting_edit_target_recovers_failed_raster(
    qapp: object, tmp_path: Path
) -> None:
    """A successfully loaded edit target clears the persistence failure guard."""
    controller, widget = _controller(tmp_path)
    widget.get_selected_map_id.return_value = "map-1"
    widget.maps_data = [
        SimpleNamespace(
            id="map-1",
            attributes={
                "raster_layers": [
                    {
                        "node_id": "node-1",
                        "file_path": "rasters/base.png",
                        "mode": "discrete",
                    }
                ]
            },
        )
    ]
    raster_item = MagicMock()
    widget.view._raster_items = {"node-1": raster_item}
    controller._failed_raster_nodes.add("node-1")
    buffer = MagicMock()

    with patch(
        "src.gui.widgets.map.map_data_buffer.MapDataBuffer.from_file",
        return_value=buffer,
    ):
        controller._select_raster_edit_target("node-1", "rasters/base.png", "Base")

    assert "node-1" not in controller._failed_raster_nodes
    assert controller._raster_edit_target_by_node == {"node-1": "rasters/base.png"}
    raster_item.swap_buffer.assert_called_once_with(buffer)


def test_pending_stroke_blocks_edit_target_change(qapp: object, tmp_path: Path) -> None:
    """Pending persistence prevents an unsafe target change."""
    controller, _ = _controller(tmp_path)
    controller._pending_raster_strokes["node-1"] = [object()]

    with (
        patch("src.app.raster_controller.QMessageBox.warning") as warning,
        patch(
            "src.gui.widgets.map.map_data_buffer.MapDataBuffer.from_file"
        ) as load_buffer,
    ):
        controller._select_raster_edit_target("node-1", "state.png")

    warning.assert_called_once()
    load_buffer.assert_not_called()


def test_pending_strokes_dispatch_in_order_and_emit_terminal_saved_state(
    qapp: object, tmp_path: Path
) -> None:
    """Only the next stroke dispatches before a terminal saved notification."""
    controller, _ = _controller(tmp_path)
    first = SimpleNamespace(node_id="node-1", command_id="one", patches=[])
    second = SimpleNamespace(node_id="node-1", command_id="two", patches=[])
    controller._pending_raster_strokes["node-1"] = [first, second]
    dispatched: list[object] = []
    states: list[tuple[str, str, str]] = []
    controller.command_requested.connect(dispatched.append)
    controller.raster_save_state_changed.connect(lambda *values: states.append(values))

    controller._finalize_raster_stroke(first, True)
    controller._finalize_raster_stroke(second, True)

    assert dispatched == [second]
    assert states == [("node-1", "saved", "")]
    assert not controller.has_pending_raster_strokes()


def test_failed_stroke_reverts_queue_and_emits_failed_state(
    qapp: object, tmp_path: Path
) -> None:
    """One failure unwinds dependent optimistic patches and pauses editing."""
    controller, _ = _controller(tmp_path)
    first_patch = SimpleNamespace(region=(0, 0, 1, 1), before_data=b"a", dtype="uint16")
    second_patch = SimpleNamespace(
        region=(2, 2, 3, 3), before_data=b"b", dtype="uint16"
    )
    first = SimpleNamespace(node_id="node-1", command_id="one", patches=[first_patch])
    second = SimpleNamespace(node_id="node-1", command_id="two", patches=[second_patch])
    controller._pending_raster_strokes["node-1"] = [first, second]
    states: list[tuple[str, str, str]] = []
    controller.raster_save_state_changed.connect(lambda *values: states.append(values))

    with (
        patch.object(controller, "_apply_raster_patch_to_view") as revert,
        patch("src.app.raster_controller.QMessageBox.critical"),
    ):
        controller._finalize_raster_stroke(first, False)

    assert [call.args[1] for call in revert.call_args_list] == [
        second_patch.region,
        first_patch.region,
    ]
    assert states == [("node-1", "failed", "Save failed — editing paused")]
    assert controller._failed_raster_nodes == {"node-1"}
    assert not controller.has_pending_raster_strokes()
