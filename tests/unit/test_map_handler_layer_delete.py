"""Regression tests for the layer-deletion persistence bug.

Root cause: the ``on_layer_tree_changed`` guard used stale ``maps_data`` and
ran inline (AutoConnection), causing a ghost ``SaveLayerTreeCommand`` to
overwrite the correct save whenever a marker/path/region layer was deleted.

The fix:
- Guard removed from ``on_layer_tree_changed``.
- Guard moved to ``on_markers_ready`` (incremental path only), gated behind
  ``_pending_layer_node_sync`` which is only True after a fresh ``maps_data``
  reload via ``on_maps_ready``.
- ``_incremental_marker_update`` now calls ``map_widget.remove_marker``
  (not ``view.remove_marker`` directly) so that the layer panel node is
  unregistered as well.
"""

from unittest.mock import MagicMock, call

import pytest

from src.app.map_handler import MapHandler
from src.commands.layer_commands import SaveLayerTreeCommand
from src.commands.marker_commands import DeleteMarkerCommand
from src.core.map import MapLayerNode
from src.core.marker import Marker


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_node(node_id: str, layer_type: str = "group") -> MapLayerNode:
    """Build a minimal ``MapLayerNode`` with a predictable id."""
    return MapLayerNode(name=node_id, layer_type=layer_type, id=node_id)


def _make_handler(
    map_id: str = "map-1",
) -> tuple[MapHandler, MagicMock]:
    """Build a ``MapHandler`` with a fully-mocked ``MapWidget``.

    Returns:
        (handler, mock_widget)
    """
    mock_widget = MagicMock()
    mock_widget.get_selected_map_id.return_value = map_id
    mock_widget.map_selector.currentData.return_value = map_id
    mock_widget._cached_entities = []
    mock_widget._cached_events = []
    mock_widget.maps_data = []

    mock_model = MagicMock()
    mock_model.root = _make_node("root")
    mock_widget.get_layer_model.return_value = mock_model

    mock_view = MagicMock()
    mock_view.scene.selectedItems.return_value = []
    mock_widget.view = mock_view
    mock_widget.layer_panel.selected_node_id = None

    handler = MapHandler(
        map_widget=mock_widget,
        worker=MagicMock(),
        db_path_accessor=lambda: "/tmp/world.kraken",
        navigation_set_selection=MagicMock(),
    )
    return handler, mock_widget


def _make_marker_dict(object_id: str, x: float = 0.5, y: float = 0.5) -> dict:
    """Build a minimal processed-marker dict."""
    return {
        "id": f"db-{object_id}",
        "object_id": object_id,
        "object_type": "entity",
        "label": object_id,
        "x": x,
        "y": y,
        "icon": None,
        "color": None,
        "description": "",
        "connection_count": 0,
        "feature_type": "point",
    }


# ---------------------------------------------------------------------------
# Phase 1 tests — guard moved to on_markers_ready
# ---------------------------------------------------------------------------


class TestPendingLayerNodeSyncFlag:
    """Guard in ``on_markers_ready`` is gated behind _pending_layer_node_sync."""

    def test_guard_skipped_when_flag_is_false(self, qapp) -> None:
        """When flag is False (deletion path), ``rebuild_layer_model`` must NOT be called.

        This is the critical regression check: a deletion never triggers
        ``on_maps_ready``, so the flag stays False and the guard is skipped.
        """
        handler, mock_widget = _make_handler()

        # DB tree has an extra node the model doesn't know about —
        # with the old code this would trigger a (wrong) rebuild.
        db_root = _make_node("root")
        db_root.children.append(_make_node("raster-extra", "raster"))

        mock_map = MagicMock()
        mock_map.id = "map-1"
        mock_map.layers = db_root
        mock_widget.maps_data = [mock_map]

        # Model root has only the root node (no raster child)
        mock_widget.get_layer_model.return_value.root = _make_node("root")

        # Simulate incremental path: same map already loaded
        handler._loaded_markers_map_id = "map-1"
        assert handler._pending_layer_node_sync is False  # default after __init__

        handler.on_markers_ready("map-1", [])

        mock_widget.rebuild_layer_model.assert_not_called()

    def test_guard_fires_when_flag_is_true_and_node_missing(self, qapp) -> None:
        """When flag is True (after reload) and DB has extra node, rebuild IS called.

        This covers the ``CreateRasterLayerCommand`` use-case: the command
        injects a new raster node into ``maps_data`` (via ``reload_maps`` →
        ``on_maps_ready``), but the in-memory model is still on the incremental
        path, so the guard must detect and sync the new node.
        """
        handler, mock_widget = _make_handler()

        db_root = _make_node("root")
        db_root.children.append(_make_node("raster-new", "raster"))

        mock_map = MagicMock()
        mock_map.id = "map-1"
        mock_map.layers = db_root
        mock_widget.maps_data = [mock_map]

        mock_widget.get_layer_model.return_value.root = _make_node("root")

        handler._loaded_markers_map_id = "map-1"
        handler._pending_layer_node_sync = True  # simulate on_maps_ready ran

        handler.on_markers_ready("map-1", [])

        mock_widget.rebuild_layer_model.assert_called_once_with(db_root)

    def test_pending_flag_consumed_after_first_on_markers_ready(self, qapp) -> None:
        """The flag is reset to False after the first incremental ``on_markers_ready``.

        A second call must not trigger another rebuild even if ``maps_data``
        still has the extra node.
        """
        handler, mock_widget = _make_handler()

        db_root = _make_node("root")
        db_root.children.append(_make_node("raster-new", "raster"))

        mock_map = MagicMock()
        mock_map.id = "map-1"
        mock_map.layers = db_root
        mock_widget.maps_data = [mock_map]

        mock_widget.get_layer_model.return_value.root = _make_node("root")

        handler._loaded_markers_map_id = "map-1"
        handler._pending_layer_node_sync = True

        # First call — flag consumed, rebuild called
        handler.on_markers_ready("map-1", [])
        assert handler._pending_layer_node_sync is False

        mock_widget.rebuild_layer_model.reset_mock()

        # Second call — flag is False now, no rebuild
        handler.on_markers_ready("map-1", [])
        mock_widget.rebuild_layer_model.assert_not_called()

    def test_flag_consumed_on_full_rebuild_path(self, qapp) -> None:
        """Flag is also consumed on the full-rebuild (map-switch) path.

        ``_full_marker_rebuild`` already resynchronises the model; we just
        need to ensure the flag doesn't linger for a future incremental call.
        """
        handler, mock_widget = _make_handler()

        # Full rebuild path: different map_id from _loaded_markers_map_id
        handler._loaded_markers_map_id = "map-old"
        handler._pending_layer_node_sync = True

        db_root = _make_node("root")
        mock_map = MagicMock()
        mock_map.id = "map-1"
        mock_map.layers = db_root
        mock_widget.maps_data = [mock_map]

        handler.on_markers_ready("map-1", [])

        assert handler._pending_layer_node_sync is False

    def test_on_maps_ready_sets_pending_flag(self, qapp) -> None:
        """``on_maps_ready`` must set ``_pending_layer_node_sync = True``."""
        handler, mock_widget = _make_handler()

        assert handler._pending_layer_node_sync is False

        handler.on_maps_ready([])

        assert handler._pending_layer_node_sync is True


# ---------------------------------------------------------------------------
# Phase 1 tests — guard removed from on_layer_tree_changed
# ---------------------------------------------------------------------------


class TestOnLayerTreeChangedNoRebuild:
    """``on_layer_tree_changed`` must never call ``rebuild_layer_model``."""

    def test_stale_maps_data_does_not_trigger_rebuild(self, qapp) -> None:
        """Even if ``maps_data`` has extra nodes, ``on_layer_tree_changed`` must NOT rebuild.

        This directly tests that the bug-inducing guard has been removed.
        """
        handler, mock_widget = _make_handler()

        # maps_data has an extra node — the old guard would have fired here
        db_root = _make_node("root")
        db_root.children.append(_make_node("ghost-node", "point"))

        mock_map = MagicMock()
        mock_map.id = "map-1"
        mock_map.layers = db_root
        mock_widget.maps_data = [mock_map]

        # Model root has only the root (missing ghost-node) — stale difference
        mock_widget.get_layer_model.return_value.root = _make_node("root")

        emitted: list = []
        handler.command_requested.connect(emitted.append)

        handler.on_layer_tree_changed()

        # Guard must be gone — rebuild_layer_model never called
        mock_widget.rebuild_layer_model.assert_not_called()

    def test_on_layer_tree_changed_emits_save_command(self, qapp) -> None:
        """``on_layer_tree_changed`` must still queue a ``SaveLayerTreeCommand``."""
        handler, mock_widget = _make_handler()

        emitted: list = []
        handler.command_requested.connect(emitted.append)

        handler.on_layer_tree_changed()

        assert len(emitted) == 1
        assert isinstance(emitted[0], SaveLayerTreeCommand)
        assert emitted[0].map_id == "map-1"


# ---------------------------------------------------------------------------
# Phase 2 tests — _incremental_marker_update uses map_widget.remove_marker
# ---------------------------------------------------------------------------


class TestIncrementalUpdateRemovesViaWidget:
    """Departed markers must be removed through ``map_widget.remove_marker``."""

    def test_departed_marker_calls_widget_remove_marker(self, qapp) -> None:
        """``map_widget.remove_marker`` (not ``view.remove_marker``) called for departed."""
        handler, mock_widget = _make_handler()

        initial = [_make_marker_dict("obj-a"), _make_marker_dict("obj-b")]

        # Seed the handler with initial markers via a full rebuild
        handler._loaded_markers_map_id = None  # force full path on first call
        mock_map = MagicMock()
        mock_map.id = "map-1"
        mock_map.layers = _make_node("root")
        mock_widget.maps_data = [mock_map]
        handler.on_markers_ready("map-1", initial)
        handler._loaded_markers_map_id = "map-1"  # now on incremental path

        mock_widget.remove_marker.reset_mock()
        mock_widget.view.remove_marker.reset_mock()

        # Reload without obj-a — it should be departed
        handler.on_markers_ready("map-1", [_make_marker_dict("obj-b")])

        # Must go through the widget (which calls _unregister_layer_node)
        mock_widget.remove_marker.assert_called_once_with("obj-a")

    def test_departed_marker_does_not_call_view_remove_marker_directly(
        self, qapp
    ) -> None:
        """``view.remove_marker`` must NOT be called directly for departed markers."""
        handler, mock_widget = _make_handler()

        initial = [_make_marker_dict("obj-x")]
        handler._loaded_markers_map_id = None
        mock_map = MagicMock()
        mock_map.id = "map-1"
        mock_map.layers = _make_node("root")
        mock_widget.maps_data = [mock_map]
        handler.on_markers_ready("map-1", initial)
        handler._loaded_markers_map_id = "map-1"

        mock_widget.view.remove_marker.reset_mock()

        # Reload with empty list — obj-x departed
        handler.on_markers_ready("map-1", [])

        # view.remove_marker must NOT be called for the departed marker's removal
        # (it may still be called for update-redraws, but not for departures)
        mock_widget.view.remove_marker.assert_not_called()


# ---------------------------------------------------------------------------
# Integration test — command sequence persists correct tree
# ---------------------------------------------------------------------------


def _insert_map_with_marker(db_service) -> tuple[str, str, str]:
    """Insert a map + marker, return (map_id, marker_id, marker_node_id).

    The map's layer tree contains one group and one marker node.
    """
    from src.core.map import Map

    root = _make_node("root-group", "group")
    marker_node = _make_node("marker-node-1", "point")
    root.children.append(marker_node)
    tree_dict = root.to_dict()

    map_obj = Map(name="Test Map", image_path="/img.png")
    map_obj.attributes = {"layers": tree_dict}
    db_service.insert_map(map_obj)

    marker = Marker(
        map_id=map_obj.id,
        object_id="entity-001",
        object_type="entity",
        x=0.5,
        y=0.5,
    )
    marker_id = db_service.insert_marker(marker)
    return map_obj.id, marker_id, "marker-node-1"


def test_save_tree_then_delete_marker_leaves_correct_state(db_service) -> None:
    """Commands run in the correct order must leave the DB in a consistent state.

    Simulates the fixed Worker FIFO sequence after a layer-panel delete:
      1. SaveLayerTreeCommand(tree WITHOUT marker node) — correct
      2. DeleteMarkerCommand(marker_id)

    Verifies:
    - Marker row is gone from DB.
    - The tree JSON stored in DB does NOT contain the deleted node.
    """
    map_id, marker_id, node_id = _insert_map_with_marker(db_service)

    # Build the "correct after-deletion" tree (without marker node)
    root_without_marker = _make_node("root-group", "group")
    tree_without_marker = root_without_marker.to_dict()

    # 1. SaveLayerTreeCommand with the pruned tree
    save_cmd = SaveLayerTreeCommand(map_id, tree_without_marker)
    result = save_cmd.execute(db_service)
    assert result.success, f"SaveLayerTreeCommand failed: {result.message}"

    # 2. DeleteMarkerCommand
    del_cmd = DeleteMarkerCommand(marker_id)
    result = del_cmd.execute(db_service)
    assert result.success, f"DeleteMarkerCommand failed: {result.message}"

    # Marker row must be gone
    assert db_service.get_marker(marker_id) is None

    # Tree in DB must NOT contain the marker node
    saved_map = db_service.map_repo.get_map(map_id)
    assert saved_map is not None
    layers_dict = saved_map.attributes.get("layers", {})
    # Walk the serialized dict looking for marker-node-1
    def _has_id(node_dict: dict, target_id: str) -> bool:
        if node_dict.get("id") == target_id:
            return True
        for child in node_dict.get("children", []):
            if _has_id(child, target_id):
                return True
        return False

    assert not _has_id(layers_dict, node_id), (
        f"Ghost node '{node_id}' still present in persisted tree: {layers_dict}"
    )
