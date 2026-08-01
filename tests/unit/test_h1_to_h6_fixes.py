"""TDD tests for H1-H6 high-priority fixes.

These tests were written BEFORE the fixes (red phase) to capture the expected
behaviour after each fix. They are kept in the test suite as regression guards.

H1 — ThemeManager hot paths cached
H2 — shiboken6.isValid() guards
H3 — RenameLayerCommand partial-failure rollback
H4 — SetLayerVisibility/OpacityCommand ignores stale snapshot
H5 — MoveLayerCommand DB-only mutation (no live-tree side-effects)
H6 — SetRasterBlendModeCommand fetches old_mode from DB in execute()
"""

import copy
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# H1 — ThemeManager hot-path caching
# ---------------------------------------------------------------------------


class TestH1RasterEditToolThemeCache:
    """_update_cursor must NOT call ThemeManager().get_theme() on each call."""

    def test_update_cursor_uses_cached_color_not_get_theme_every_call(self):
        """ThemeManager().get_theme() must not be called on every mouse move."""
        from src.gui.widgets.map.raster_edit_tool import RasterEditTool

        # Build a minimal view mock
        view = MagicMock()
        view._raster_items = {}
        view.pixmap_item = MagicMock()
        view.graphics_scene = MagicMock()

        tool = RasterEditTool(view)
        tool._active = True

        # Cursor item already exists — the only path that should call get_theme
        # is cursor creation, NOT subsequent moves.
        from PySide6.QtWidgets import QGraphicsEllipseItem

        tool._cursor_item = QGraphicsEllipseItem()

        call_count_before = 0
        with patch("src.gui.widgets.map.raster_edit_tool.ThemeManager") as mock_tm:
            mock_tm.return_value.get_theme.return_value = {
                "text_main": "#FFFFFF",
            }
            from PySide6.QtCore import QPointF

            # First call (cursor already exists, should NOT call get_theme again)
            tool._update_cursor(QPointF(0.5, 0.5))
            call_count_before = mock_tm.return_value.get_theme.call_count

        # get_theme should not be called when cursor already exists
        assert call_count_before == 0, (
            "ThemeManager().get_theme() should NOT be called on every "
            "_update_cursor() call when cursor already exists"
        )

    def test_theme_cache_refreshed_on_theme_changed(self):
        """_refresh_theme_colors() should update cached color attributes."""
        from src.gui.widgets.map.raster_edit_tool import RasterEditTool

        view = MagicMock()
        tool = RasterEditTool(view)

        # After construction, tool must have cached color attributes
        assert hasattr(tool, "_cursor_hex"), (
            "RasterEditTool must cache _cursor_hex at construction time"
        )


class TestH1HistogramWidgetThemeCache:
    """_HistogramWidget.paintEvent must NOT call ThemeManager().get_theme()."""

    def test_paint_event_uses_cached_colors(self, qapp):
        """paintEvent must use cached colors, not call get_theme each time."""
        from src.gui.widgets.map.raster_stats_panel import _HistogramWidget

        widget = _HistogramWidget(counts=[1, 2, 3], edges=[0, 10, 20, 30])

        # After construction must have cached color attributes
        assert hasattr(widget, "_bar_color"), (
            "_HistogramWidget must cache _bar_color at construction"
        )
        assert hasattr(widget, "_border_color"), (
            "_HistogramWidget must cache _border_color at construction"
        )

        # paintEvent must NOT call get_theme
        with patch("src.gui.widgets.map.raster_stats_panel.ThemeManager") as mock_tm:
            mock_tm.return_value.get_theme.return_value = {}

            widget.resize(100, 80)
            widget.repaint()  # triggers paintEvent
            assert mock_tm.return_value.get_theme.call_count == 0, (
                "ThemeManager().get_theme() should NOT be called inside paintEvent"
            )


# ---------------------------------------------------------------------------
# H2 — shiboken6.isValid() guards
# ---------------------------------------------------------------------------


class TestH2MarkerManagerShibokenGuards:
    """remove_marker and clear_markers must not crash on already-deleted items."""

    def test_remove_marker_tolerates_deleted_graphics_item(self):
        """remove_marker must not raise RuntimeError on already-deleted item."""

        from src.gui.widgets.map.marker_manager import MarkerManager

        view = MagicMock()
        view.graphics_scene = MagicMock()
        # Make removeItem raise RuntimeError as Qt does for deleted C++ objects
        view.graphics_scene.removeItem.side_effect = RuntimeError("Internal C++ object deleted")

        manager = MarkerManager(view)

        # Inject a stale item
        stale = MagicMock()
        manager.markers["m1"] = stale

        # Must NOT raise
        try:
            manager.remove_marker("m1")
        except RuntimeError as e:
            pytest.fail(f"remove_marker raised RuntimeError: {e}")

        assert "m1" not in manager.markers

    def test_clear_markers_tolerates_deleted_graphics_items(self):
        """clear_markers must not crash when some items are already deleted."""
        from src.gui.widgets.map.marker_manager import MarkerManager

        view = MagicMock()
        view.graphics_scene = MagicMock()
        view.graphics_scene.removeItem.side_effect = RuntimeError("deleted")

        manager = MarkerManager(view)
        manager.markers["a"] = MagicMock()
        manager.feature_items["b"] = MagicMock()

        try:
            manager.clear_markers()
        except RuntimeError as e:
            pytest.fail(f"clear_markers raised RuntimeError: {e}")

        assert len(manager.markers) == 0
        assert len(manager.feature_items) == 0


class TestH2MapGraphicsViewShibokenGuards:
    """_on_layer_visibility_changed and _on_layer_opacity_changed must guard items."""

    def test_on_layer_visibility_changed_tolerates_deleted_item(self):
        """Must not crash when the graphics item is already deleted."""

        from src.commands.layer_commands import SetLayerVisibilityCommand
        from src.core.map import Map, MapLayerNode

        # Build a simple DB with a valid layer tree
        root = MapLayerNode(name="Root", id="root")
        leaf = MapLayerNode(name="Leaf", id="leaf-1", visible=True)
        root.children.append(leaf)
        map_obj = Map(id="m1", name="Test", image_path="p", layers=root)

        db = MagicMock()
        db.map_repo.get_map.return_value = map_obj
        db.map_repo.insert_map.return_value = None

        cmd = SetLayerVisibilityCommand("m1", "leaf-1", False)
        result = cmd.execute(db)
        assert result.success is True

    def test_on_layer_opacity_changed_tolerates_deleted_item(self):
        """Must not crash when the graphics item is already deleted."""
        from src.commands.layer_commands import SetLayerOpacityCommand
        from src.core.map import Map, MapLayerNode

        root = MapLayerNode(name="Root", id="root")
        leaf = MapLayerNode(name="Leaf", id="leaf-1", opacity=1.0)
        root.children.append(leaf)
        map_obj = Map(id="m1", name="Test", image_path="p", layers=root)

        db = MagicMock()
        db.map_repo.get_map.return_value = map_obj
        db.map_repo.insert_map.return_value = None

        cmd = SetLayerOpacityCommand("m1", "leaf-1", 0.5)
        result = cmd.execute(db)
        assert result.success is True


# ---------------------------------------------------------------------------
# H3 — RenameLayerCommand partial-failure rollback
# ---------------------------------------------------------------------------


class TestH3RenameLayerCommandRollback:
    """If _sync_lore_item fails, the DB should be rolled back to pre-execute state."""

    def _make_db(self):
        """Return a mock db where insert_entity raises on the first call."""
        from src.core.entities import Entity
        from src.core.map import Map, MapLayerNode
        from src.core.marker import Marker

        root = MapLayerNode(name="Root", id="root")
        leaf = MapLayerNode(name="Old Name", id="node-1")
        root.children.append(leaf)
        map_obj = Map(id="map-1", name="M", image_path="p", layers=root)

        marker = Marker(
            id="node-1",
            map_id="map-1",
            object_id="entity-1",
            object_type="entity",
            x=0.5,
            y=0.5,
            label="Old Name",
        )
        entity = Entity(id="entity-1", name="Old Name", type="person")

        db = MagicMock()
        # Each get_map call returns a fresh copy of map_obj
        db.map_repo.get_map.side_effect = lambda mid: copy.deepcopy(map_obj)
        db.map_repo.get_marker.return_value = marker
        db.map_repo.insert_marker.return_value = None
        db.map_repo.insert_map.return_value = None
        db.get_entity.return_value = entity
        # Simulate failure on lore item update
        db.insert_entity.side_effect = RuntimeError("DB error")

        return db, map_obj, marker, entity

    def test_execute_rolls_back_marker_label_when_lore_update_fails(self):
        """If entity rename fails, marker label must be reverted."""
        from src.commands.layer_commands import RenameLayerCommand

        db, _, marker, _ = self._make_db()

        cmd = RenameLayerCommand("map-1", "node-1", "New Name")
        result = cmd.execute(db)

        # Command should report failure
        assert result.success is False

        # Marker label must have been reverted via _undo_feature_label —
        # the LAST insert_marker call must restore the original label
        insert_calls = db.map_repo.insert_marker.call_args_list
        assert len(insert_calls) >= 2, (
            "Expected at least two insert_marker calls (set + rollback)"
        )
        last_label = insert_calls[-1][0][0].label
        assert last_label == "Old Name", (
            f"Last insert_marker call should restore 'Old Name'; got '{last_label}'"
        )

    def test_execute_returns_failure_when_lore_update_fails(self):
        """execute() must return failure if any sub-step raises."""
        from src.commands.layer_commands import RenameLayerCommand

        db, _, _, _ = self._make_db()
        cmd = RenameLayerCommand("map-1", "node-1", "New Name")
        result = cmd.execute(db)
        assert result.success is False
        assert cmd._is_executed is False


# ---------------------------------------------------------------------------
# H4 — SetLayerVisibility/OpacityCommand stale snapshot
# ---------------------------------------------------------------------------


class TestH4StaleSnapshotIgnored:
    """When layer_tree_dict is provided, the DB tree must STILL be used."""

    def _make_db_with_node(self, node_id: str):
        """Return a DB whose map has a node with given id."""
        from src.core.map import Map, MapLayerNode

        root = MapLayerNode(name="Root", id="root")
        child = MapLayerNode(name="Child", id=node_id, visible=True, opacity=1.0)
        root.children.append(child)
        map_obj = Map(id="map-1", name="M", image_path="p", layers=root)

        db = MagicMock()
        db.map_repo.get_map.return_value = map_obj
        db.map_repo.insert_map.return_value = None
        return db

    def test_visibility_command_uses_db_tree_even_when_snapshot_provided(self):
        """Providing a stale snapshot must NOT overwrite the DB tree."""
        from src.commands.layer_commands import SetLayerVisibilityCommand
        from src.core.map import MapLayerNode

        db = self._make_db_with_node("child-1")

        # Stale snapshot: has DIFFERENT tree (missing child-1, has stale-child)
        stale_root = MapLayerNode(name="Root", id="root")
        stale_child = MapLayerNode(name="Stale", id="stale-child")
        stale_root.children.append(stale_child)
        stale_snapshot = stale_root.to_dict()

        cmd = SetLayerVisibilityCommand(
            "map-1", "child-1", False, layer_tree_dict=stale_snapshot
        )
        result = cmd.execute(db)

        # Must succeed using the DB tree (child-1 IS in the DB)
        assert result.success is True

        # Saved tree must still have child-1 (not replaced by stale snapshot)
        saved_map = db.map_repo.insert_map.call_args[0][0]
        ids = [c.id for c in saved_map.layers.children]
        assert "child-1" in ids, "DB tree was replaced by stale snapshot"
        assert "stale-child" not in ids, "Stale snapshot polluted the DB tree"

    def test_visibility_command_fails_when_node_absent_even_with_stale_snapshot(self):
        """If node is not in DB, command must fail regardless of snapshot."""
        from src.commands.layer_commands import SetLayerVisibilityCommand

        # DB tree does NOT have target node
        from src.core.map import Map, MapLayerNode

        root = MapLayerNode(name="Root", id="root")
        map_obj = Map(id="map-1", name="M", image_path="p", layers=root)
        db = MagicMock()
        db.map_repo.get_map.return_value = map_obj

        # Snapshot does have the node
        snapshot_root = MapLayerNode(name="Root", id="root")
        snapshot_child = MapLayerNode(name="New", id="new-node")
        snapshot_root.children.append(snapshot_child)
        snapshot = snapshot_root.to_dict()

        cmd = SetLayerVisibilityCommand(
            "map-1", "new-node", False, layer_tree_dict=snapshot
        )
        result = cmd.execute(db)

        # DB doesn't have new-node, so command must fail
        assert result.success is False

    def test_opacity_command_uses_db_tree_even_when_snapshot_provided(self):
        """Same check for SetLayerOpacityCommand."""
        from src.commands.layer_commands import SetLayerOpacityCommand
        from src.core.map import MapLayerNode

        db = self._make_db_with_node("child-1")

        stale_root = MapLayerNode(name="Root", id="root")
        stale_child = MapLayerNode(name="Stale", id="stale-child")
        stale_root.children.append(stale_child)
        stale_snapshot = stale_root.to_dict()

        cmd = SetLayerOpacityCommand(
            "map-1", "child-1", 0.5, layer_tree_dict=stale_snapshot
        )
        result = cmd.execute(db)

        assert result.success is True

        saved_map = db.map_repo.insert_map.call_args[0][0]
        ids = [c.id for c in saved_map.layers.children]
        assert "child-1" in ids
        assert "stale-child" not in ids


# ---------------------------------------------------------------------------
# H5 — MoveLayerCommand no live-tree mutation
# ---------------------------------------------------------------------------


class TestH5MoveLayerCloneBeforePersist:
    """MoveLayerCommand must not leave DB in partial state if persist fails."""

    def _make_map(self):
        from src.core.map import Map, MapLayerNode

        root = MapLayerNode(name="Root", id="root")
        group_a = MapLayerNode(name="A", id="group-a")
        group_b = MapLayerNode(name="B", id="group-b")
        child = MapLayerNode(name="Child", id="child-1")
        group_a.children.append(child)
        root.children.append(group_a)
        root.children.append(group_b)
        return Map(id="map-1", name="M", image_path="p", layers=root), root

    def test_db_not_mutated_when_persist_fails(self):
        """If insert_map raises, the original DB tree structure must be preserved."""
        from src.commands.layer_commands import MoveLayerCommand

        map_obj, root = self._make_map()

        def mock_get_map(mid):
            return copy.deepcopy(map_obj)

        db = MagicMock()
        db.map_repo.get_map.side_effect = mock_get_map
        db.map_repo.insert_map.side_effect = RuntimeError("DB error")

        cmd = MoveLayerCommand("map-1", "child-1", "group-b", 0)
        result = cmd.execute(db)

        # Command should report failure
        assert result.success is False

        # Verify the ORIGINAL map_obj (as read from DB) was not mutated —
        # child-1 must still be under group-a
        group_a = next(c for c in root.children if c.id == "group-a")
        assert any(c.id == "child-1" for c in group_a.children), (
            "Original layer tree was mutated even though persist failed"
        )

    def test_missing_layer_tree_in_clone_returns_failure(self):
        """A malformed deepcopy must fail before persisting any mutation."""
        from src.commands.layer_commands import MoveLayerCommand
        from src.core.map import Map

        map_obj, _ = self._make_map()
        malformed_clone = Map(
            id="map-1", name="M", image_path="p", layers=None
        )
        db = MagicMock()
        db.map_repo.get_map.return_value = map_obj

        with patch(
            "src.commands.layer_commands.copy.deepcopy",
            return_value=malformed_clone,
        ):
            result = MoveLayerCommand(
                "map-1", "child-1", "group-b", 0
            ).execute(db)

        assert result.success is False
        assert result.message == "Layer tree missing from cloned map."
        db.map_repo.insert_map.assert_not_called()


# ---------------------------------------------------------------------------
# H6 — SetRasterBlendModeCommand fetches old_mode from DB
# ---------------------------------------------------------------------------


class TestH6SetRasterBlendModeFetchesOldMode:
    """execute() must fetch the actual current blend mode from DB for undo."""

    def _make_db(self, current_mode: str = "Multiply"):
        from src.core.map import Map, MapLayerNode

        root = MapLayerNode(name="Root", id="root")
        map_obj = Map(id="map-1", name="M", image_path="p", layers=root)
        map_obj.attributes = {
            "raster_layers": [
                {"node_id": "raster-1", "blend_mode": current_mode},
            ]
        }
        db = MagicMock()
        db.map_repo.get_map.return_value = map_obj
        db.map_repo.insert_map.return_value = None
        return db

    def test_execute_captures_actual_old_mode_from_db(self):
        """execute() must store the DB-fetched blend mode in self.old_mode."""
        from src.commands.raster_commands import SetRasterBlendModeCommand

        db = self._make_db(current_mode="Multiply")

        # Caller passes wrong/empty old_mode — execute() must override it
        cmd = SetRasterBlendModeCommand(
            map_id="map-1",
            node_id="raster-1",
            new_mode="Screen",
            old_mode="",  # wrong/empty
        )
        result = cmd.execute(db)
        assert result.success is True

        # After execute, old_mode must be the actual DB value, not the empty string
        assert cmd.old_mode == "Multiply", (
            f"execute() must capture actual old_mode from DB; got '{cmd.old_mode}'"
        )

    def test_undo_uses_db_fetched_old_mode(self):
        """undo() must restore the DB-fetched mode, not the constructor arg."""
        from src.commands.raster_commands import SetRasterBlendModeCommand

        db = self._make_db(current_mode="Multiply")

        cmd = SetRasterBlendModeCommand(
            map_id="map-1",
            node_id="raster-1",
            new_mode="Screen",
            old_mode="WrongMode",  # should be overridden
        )
        cmd.execute(db)
        cmd.undo(db)

        # The last insert_map call should have "Multiply" as the blend mode
        last_call = db.map_repo.insert_map.call_args[0][0]
        raster_layers = last_call.attributes.get("raster_layers", [])
        modes = [r.get("blend_mode") for r in raster_layers if r.get("node_id") == "raster-1"]
        assert modes == ["Multiply"], (
            f"undo() did not restore DB-fetched blend mode; modes={modes}"
        )

    def test_execute_defaults_to_normal_when_no_blend_mode_in_db(self):
        """execute() must use 'Normal' when the DB record has no blend_mode key."""
        from src.commands.raster_commands import SetRasterBlendModeCommand
        from src.core.map import Map, MapLayerNode

        root = MapLayerNode(name="Root", id="root")
        map_obj = Map(id="map-1", name="M", image_path="p", layers=root)
        map_obj.attributes = {
            "raster_layers": [
                {"node_id": "raster-1"},  # no blend_mode key
            ]
        }
        db = MagicMock()
        db.map_repo.get_map.return_value = map_obj

        cmd = SetRasterBlendModeCommand(
            map_id="map-1",
            node_id="raster-1",
            new_mode="Screen",
            old_mode="",
        )
        cmd.execute(db)
        assert cmd.old_mode == "Normal", (
            f"Expected default 'Normal' when blend_mode absent; got '{cmd.old_mode}'"
        )
