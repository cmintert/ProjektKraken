"""Tests for temporal-raster snapshot switching on playhead changes.

Covers:
- Immediate apply on single playhead change (no stale debounce-only lag).
- Debounce coalescing during rapid scrubbing.
- LRU eviction of ``_snapshot_cache`` when entries exceed the configured max.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from src.app.map_handler import MapHandler
from src.gui.widgets.map.map_data_buffer import ColorMap, MapDataBuffer

# ── helpers ───────────────────────────────────────────────────────────


def _make_temporal_handler(
    map_id: str = "map-1",
    node_id: str = "node-A",
    world_dir: str = "/tmp/world",
    snapshots: dict | None = None,
) -> tuple[MapHandler, MagicMock, MagicMock]:
    """Build a MapHandler wired for temporal-raster tests.

    ``snapshots`` is a ``{str_lore_date: rel_path}`` dict that will
    be injected into the raster-layer metadata of the mock map.

    Returns:
        (handler, mock_map_widget, mock_raster_item)
    """
    mock_widget = MagicMock()
    mock_widget.get_selected_map_id.return_value = map_id

    mock_map = MagicMock()
    mock_map.id = map_id
    raster_meta: dict = {
        "node_id": node_id,
        "mode": "discrete",
        "file_path": "rasters/base.png",
        "value_entity_map": {},
        "color_map": None,
    }
    if snapshots is not None:
        raster_meta["snapshots"] = snapshots
    mock_map.attributes = {"raster_layers": [raster_meta]}
    mock_widget.maps_data = [mock_map]

    mock_item = MagicMock()
    mock_item.color_map = ColorMap(type="gradient")
    mock_item.buffer = MagicMock()
    mock_widget.view._raster_items = {node_id: mock_item}

    mock_worker = MagicMock()
    handler = MapHandler(
        map_widget=mock_widget,
        worker=mock_worker,
        db_path_accessor=lambda: str(Path(world_dir) / "world.kraken"),
        navigation_set_selection=MagicMock(),
    )
    # Simulate that the handler already has a current map loaded
    handler._current_map_id = map_id

    return handler, mock_widget, mock_item


# ── Tests: immediate apply on playhead change ─────────────────────────


class TestPlayheadImmediateApply:
    """on_playhead_changed must apply temporal rasters immediately
    when the debounce timer is not already active."""

    def test_apply_called_immediately_on_first_change(self, qapp):
        """_apply_temporal_rasters is called right away on a single playhead change."""
        handler, widget, item = _make_temporal_handler(
            snapshots={"5.00": "rasters/snap_5.png", "10.00": "rasters/snap_10.png"},
        )

        fake_buf = MagicMock(spec=MapDataBuffer)
        with patch.object(
            MapDataBuffer, "from_file", return_value=fake_buf
        ):
            handler.on_playhead_changed(7.0)

        # swap_buffer should have been called immediately (not after 300ms)
        item.swap_buffer.assert_called_once_with(fake_buf)

    def test_lore_date_stored_before_apply(self, qapp):
        """_current_lore_date must be updated before _apply_temporal_rasters runs."""
        handler, widget, item = _make_temporal_handler(
            snapshots={"5.00": "rasters/snap_5.png"},
        )

        fake_buf = MagicMock(spec=MapDataBuffer)
        with patch.object(MapDataBuffer, "from_file", return_value=fake_buf):
            handler.on_playhead_changed(6.0)

        assert handler._current_lore_date == 6.0

    def test_no_apply_when_no_map(self, qapp):
        """If no map is loaded, _apply_temporal_rasters should not be called."""
        handler, widget, item = _make_temporal_handler()
        handler._current_map_id = None

        with patch.object(handler, "_apply_temporal_rasters") as mock_apply:
            handler.on_playhead_changed(5.0)

        mock_apply.assert_not_called()


# ── Tests: debounce coalescing ────────────────────────────────────────


class TestPlayheadDebounce:
    """Rapid playhead changes must still start/restart the debounce timer
    so that a final _apply_temporal_rasters fires after scrubbing stops."""

    def test_debounce_timer_started_on_change(self, qapp):
        """The debounce timer must be active after on_playhead_changed."""
        handler, widget, item = _make_temporal_handler(
            snapshots={"5.00": "rasters/snap_5.png"},
        )

        fake_buf = MagicMock(spec=MapDataBuffer)
        with patch.object(MapDataBuffer, "from_file", return_value=fake_buf):
            handler.on_playhead_changed(7.0)

        assert handler._temporal_debounce_timer.isActive()

    def test_debounce_prevents_redundant_apply_on_rapid_changes(self, qapp):
        """When the timer is already active (rapid scrubbing), _apply_temporal_rasters
        should not be called again immediately — only via the timer."""
        handler, widget, item = _make_temporal_handler(
            snapshots={"5.00": "rasters/snap_5.png"},
        )

        fake_buf = MagicMock(spec=MapDataBuffer)
        with patch.object(MapDataBuffer, "from_file", return_value=fake_buf):
            # First call: immediate apply + starts timer
            handler.on_playhead_changed(6.0)
            first_count = item.swap_buffer.call_count

            # Second call while timer is active: no immediate apply
            handler.on_playhead_changed(7.0)
            second_count = item.swap_buffer.call_count

        # Only the first call should have triggered an immediate swap
        assert first_count == 1
        assert second_count == first_count, (
            "swap_buffer should not be called again while debounce is active"
        )


# ── Tests: LRU snapshot cache ────────────────────────────────────────


class TestSnapshotCacheLRU:
    """_snapshot_cache must evict the least-recently-used entry
    when its size exceeds the configured maximum."""

    def test_cache_evicts_oldest_entry(self, qapp):
        """When cache exceeds max entries, the oldest entry is evicted."""
        handler, widget, item = _make_temporal_handler()

        # Set a small cache limit
        handler._snapshot_cache_max = 3

        # Manually populate the cache with 3 entries
        for i in range(3):
            handler._snapshot_cache[f"/path/snap_{i}.png"] = MagicMock()

        assert len(handler._snapshot_cache) == 3

        # Add a 4th entry — the oldest (snap_0) should be evicted
        handler._snapshot_cache["/path/snap_3.png"] = MagicMock()
        handler._evict_snapshot_cache()

        assert len(handler._snapshot_cache) <= 3
        assert "/path/snap_0.png" not in handler._snapshot_cache

    def test_cache_retains_recent_entries(self, qapp):
        """Recent entries must survive eviction."""
        handler, widget, item = _make_temporal_handler()
        handler._snapshot_cache_max = 3

        for i in range(4):
            handler._snapshot_cache[f"/path/snap_{i}.png"] = MagicMock()
        handler._evict_snapshot_cache()

        # snap_1, snap_2, snap_3 should survive
        assert "/path/snap_1.png" in handler._snapshot_cache
        assert "/path/snap_2.png" in handler._snapshot_cache
        assert "/path/snap_3.png" in handler._snapshot_cache

    def test_eviction_triggered_on_apply(self, qapp):
        """_apply_temporal_rasters should trigger cache eviction
        after adding new entries."""
        handler, widget, item = _make_temporal_handler(
            snapshots={
                "1.00": "rasters/snap_1.png",
                "2.00": "rasters/snap_2.png",
                "3.00": "rasters/snap_3.png",
                "4.00": "rasters/snap_4.png",
                "5.00": "rasters/snap_5.png",
            },
        )
        handler._snapshot_cache_max = 3

        # Load multiple snapshots by changing playhead
        fake_buf = MagicMock(spec=MapDataBuffer)
        with patch.object(MapDataBuffer, "from_file", return_value=fake_buf):
            handler.on_playhead_changed(5.0)

        assert len(handler._snapshot_cache) <= handler._snapshot_cache_max


class TestSnapshotSelectionAndDeletion:
    """Selection jumps playhead, deletion emits a persistence command."""

    def test_snapshot_selected_emits_playhead_jump(self, qapp):
        """MapHandler should route snapshot selection to playhead jump signal."""
        handler, widget, _item = _make_temporal_handler()
        handler.on_raster_snapshot_selected("node-A", 15.0)
        widget.jump_to_time_requested.emit.assert_called_once_with(15.0)

    def test_snapshot_delete_emits_command_and_removes_meta(self, qapp, tmp_path):
        """Deleting a snapshot should emit RemoveRasterSnapshotCommand and update metadata."""
        snapshots = {
            "2.0": "rasters/snap_2.png",
            "5.0": "rasters/snap_5.png",
        }
        handler, widget, _item = _make_temporal_handler(
            world_dir=str(tmp_path),
            snapshots=snapshots,
        )

        # Create snapshot file that is about to be removed.
        snap_abs = tmp_path / "rasters" / "snap_5.png"
        snap_abs.parent.mkdir(parents=True, exist_ok=True)
        snap_abs.write_bytes(b"snapshot-bytes")

        emitted: list = []
        handler.command_requested.connect(emitted.append)

        with patch("src.app.map_handler.QMessageBox.question", return_value=0x4000):
            handler.on_raster_snapshot_delete_requested("node-A", 5.0)

        from src.commands.raster_commands import RemoveRasterSnapshotCommand

        assert len(emitted) == 1
        assert isinstance(emitted[0], RemoveRasterSnapshotCommand)
        assert emitted[0].node_id == "node-A"
        assert emitted[0].lore_date == 5.0

        # The database aggregate is canonical. The view remains unchanged until
        # the worker confirms the command and the map is reloaded.
        meta = widget.maps_data[0].attributes["raster_layers"][0]
        assert "5.0" in meta.get("snapshots", {})
