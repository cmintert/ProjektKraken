"""Unit tests for Phase 2 raster editing extensions.

Covers: flood_fill, paint_gradient, colorize_region, StrokeRasterCommand,
SetRasterMappingCommand, and value→entity mapping helpers.
"""

import numpy as np
import pytest

from src.gui.widgets.map.map_data_buffer import ColorEntry, ColorMap, MapDataBuffer
from src.gui.widgets.map.raster_mapping import (
    ProbeResult,
    lookup_entity_for_value,
    lookup_label_for_value,
    probe_all_layers,
)


# ── Flood fill ─────────────────────────────────────────────────────────


class TestFloodFill:
    """Tests for MapDataBuffer.flood_fill."""

    def test_flood_fill_replaces_connected_region(self) -> None:
        buf = MapDataBuffer(width=16, height=16, default_value=0)
        # Paint a small 3×3 block of value 5 at top-left
        buf._data[0:3, 0:3] = 5
        # Flood fill from (0,0) with value 99
        dirty = buf.flood_fill(0.0, 0.0, 99)
        # The 3×3 block should be 99
        assert buf._data[0, 0] == 99
        assert buf._data[2, 2] == 99
        # Rest remains 0
        assert buf._data[5, 5] == 0
        # Dirty region should enclose the 3×3 block
        assert dirty[0] <= 0 and dirty[1] <= 0
        assert dirty[2] >= 2 and dirty[3] >= 2

    def test_flood_fill_noop_when_same_value(self) -> None:
        buf = MapDataBuffer(width=8, height=8, default_value=42)
        dirty = buf.flood_fill(0.5, 0.5, 42)
        # No change, dirty region is the seed pixel
        assert np.all(buf._data == 42)

    def test_flood_fill_fills_entire_uniform_buffer(self) -> None:
        buf = MapDataBuffer(width=32, height=32, default_value=0)
        dirty = buf.flood_fill(0.5, 0.5, 100)
        assert np.all(buf._data == 100)
        assert dirty == (0, 0, 31, 31)

    def test_flood_fill_respects_boundaries(self) -> None:
        buf = MapDataBuffer(width=10, height=10, default_value=0)
        # Create a wall of value 1 around a 3×3 interior
        buf._data[2, 2:6] = 1
        buf._data[5, 2:6] = 1
        buf._data[2:6, 2] = 1
        buf._data[2:6, 5] = 1
        # Fill interior (pixel 3,3 is value 0, surrounded by 1s)
        # Normalized center: (3/9, 3/9) ≈ (0.333, 0.333)
        buf.flood_fill(3 / 9, 3 / 9, 50)
        # Interior should be 50
        assert buf._data[3, 3] == 50
        assert buf._data[4, 4] == 50
        # Exterior should still be 0
        assert buf._data[0, 0] == 0
        assert buf._data[9, 9] == 0
        # Wall should still be 1
        assert buf._data[2, 3] == 1


# ── Gradient paint ─────────────────────────────────────────────────────


class TestGradientPaint:
    """Tests for MapDataBuffer.paint_gradient."""

    def test_gradient_start_and_end_values(self) -> None:
        buf = MapDataBuffer(width=100, height=1, default_value=0)
        buf.paint_gradient(0.0, 0.5, 1.0, 0.5, 0, 1000, width_px=0)
        # Start should be near 0, end near 1000
        assert buf._data[0, 0] < 50
        assert buf._data[0, -1] > 950

    def test_gradient_returns_dirty_region(self) -> None:
        buf = MapDataBuffer(width=64, height=64, default_value=0)
        dirty = buf.paint_gradient(0.0, 0.0, 1.0, 1.0, 0, 500, width_px=0)
        assert dirty[0] == 0
        assert dirty[1] == 0
        assert dirty[2] == 63
        assert dirty[3] == 63

    def test_gradient_with_width_constraint(self) -> None:
        buf = MapDataBuffer(width=64, height=64, default_value=0)
        # Horizontal gradient through middle with width=5
        buf.paint_gradient(0.0, 0.5, 1.0, 0.5, 100, 500, width_px=5)
        # Center row should have gradient values
        assert buf._data[32, 0] > 0
        # Far corner should be 0 (outside width)
        assert buf._data[0, 0] == 0

    def test_gradient_monotonic(self) -> None:
        buf = MapDataBuffer(width=200, height=1, default_value=0)
        buf.paint_gradient(0.0, 0.5, 1.0, 0.5, 0, 60000, width_px=0)
        vals = buf._data[0, :]
        # Values should be non-decreasing along the gradient axis
        diffs = np.diff(vals.astype(np.int32))
        assert np.all(diffs >= 0)


# ── Partial colorize ──────────────────────────────────────────────────


class TestColorizeRegion:
    """Tests for MapDataBuffer.colorize_region."""

    def test_colorize_region_returns_correct_size(self) -> None:
        buf = MapDataBuffer(width=64, height=64, default_value=0)
        cmap = ColorMap(type="palette", entries=[ColorEntry(0, "#FF0000")])
        img = buf.colorize_region(cmap, 10, 10, 30, 25)
        assert img.width() == 21  # 30-10+1
        assert img.height() == 16  # 25-10+1

    def test_colorize_region_matches_full(self) -> None:
        buf = MapDataBuffer(width=16, height=16, default_value=5)
        cmap = ColorMap(type="palette", entries=[ColorEntry(5, "#00FF00")])
        full = buf.colorize(cmap)
        partial = buf.colorize_region(cmap, 0, 0, 15, 15)
        # Same dimensions
        assert full.width() == partial.width()
        assert full.height() == partial.height()

    def test_colorize_region_gradient_mode(self) -> None:
        buf = MapDataBuffer(width=32, height=32, default_value=0)
        buf._data[5, 5] = 32768  # midpoint
        cmap = ColorMap(type="gradient", gradient_start="#000000", gradient_end="#FFFFFF")
        img = buf.colorize_region(cmap, 0, 0, 31, 31)
        assert img.width() == 32


# ── Stroke command ─────────────────────────────────────────────────────


class TestStrokeRasterCommand:
    """Tests for StrokeRasterCommand undo/redo."""

    def test_stroke_undo_restores_region(self) -> None:
        from src.commands.raster_commands import StrokeRasterCommand

        buf = MapDataBuffer(width=16, height=16, default_value=0)
        # Simulate painting: save before, paint, save after
        before = buf.get_region(2, 2, 6, 6)
        buf._data[2:7, 2:7] = 42
        after = buf.get_region(2, 2, 6, 6)

        cmd = StrokeRasterCommand(
            map_id="m1",
            node_id="n1",
            dirty_region=(2, 2, 6, 6),
            before_bytes=before.tobytes(),
            after_bytes=after.tobytes(),
        )
        cmd.buffer = buf

        # Undo → should restore zeros
        cmd._is_executed = True
        cmd.undo(None)  # type: ignore[arg-type]
        assert buf._data[4, 4] == 0

        # Re-execute → should re-apply 42
        cmd.execute(None)  # type: ignore[arg-type]
        assert buf._data[4, 4] == 42

    def test_stroke_has_no_history(self) -> None:
        from src.commands.raster_commands import StrokeRasterCommand

        cmd = StrokeRasterCommand("m", "n", (0, 0, 1, 1), b"", b"")
        assert cmd.has_history is False

    def test_stroke_serialization(self) -> None:
        from src.commands.raster_commands import StrokeRasterCommand

        cmd = StrokeRasterCommand("m1", "n1", (1, 2, 3, 4), b"\x00", b"\x01")
        d = cmd.to_dict()
        assert d["map_id"] == "m1"
        assert d["dirty_region"] == [1, 2, 3, 4]
        restored = StrokeRasterCommand.from_dict(d)
        assert restored.map_id == "m1"


# ── SetRasterMappingCommand ──────────────────────────────────────────


class TestSetRasterMappingCommand:
    """Tests for SetRasterMappingCommand (requires DB)."""

    def test_mapping_command_serialization(self) -> None:
        from src.commands.raster_commands import SetRasterMappingCommand

        cmd = SetRasterMappingCommand(
            "m1", "n1",
            new_mapping={"mode": "exact", "mappings": [{"value": 1, "entity_id": "e1"}]},
            old_mapping={"mode": "exact", "mappings": []},
        )
        d = cmd.to_dict()
        assert d["new_mapping"]["mode"] == "exact"
        restored = SetRasterMappingCommand.from_dict(d)
        assert restored.new_mapping["mode"] == "exact"


# ── Value→Entity mapping ─────────────────────────────────────────────


class TestLookupEntityForValue:
    """Tests for lookup_entity_for_value."""

    def test_exact_lookup(self) -> None:
        meta = {
            "value_entity_map": {
                "mode": "exact",
                "mappings": [
                    {"value": 1, "entity_id": "e-tundra"},
                    {"value": 2, "entity_id": "e-forest"},
                ],
            }
        }
        assert lookup_entity_for_value(meta, 1) == "e-tundra"
        assert lookup_entity_for_value(meta, 2) == "e-forest"
        assert lookup_entity_for_value(meta, 99) is None

    def test_range_lookup(self) -> None:
        meta = {
            "value_entity_map": {
                "mode": "range",
                "mappings": [
                    {"min": 0, "max": 100, "entity_id": "e-low"},
                    {"min": 101, "max": 500, "entity_id": "e-mid"},
                ],
            }
        }
        assert lookup_entity_for_value(meta, 50) == "e-low"
        assert lookup_entity_for_value(meta, 200) == "e-mid"
        assert lookup_entity_for_value(meta, 600) is None

    def test_legacy_flat_dict_format(self) -> None:
        meta = {"value_entity_map": {"1": "e-tundra", "2": "e-forest"}}
        assert lookup_entity_for_value(meta, 1) == "e-tundra"
        assert lookup_entity_for_value(meta, 3) is None

    def test_empty_mapping(self) -> None:
        assert lookup_entity_for_value({}, 0) is None
        assert lookup_entity_for_value({"value_entity_map": None}, 0) is None


class TestLookupLabel:
    """Tests for lookup_label_for_value."""

    def test_label_found(self) -> None:
        meta = {
            "value_entity_map": {
                "mode": "exact",
                "mappings": [{"value": 5, "entity_id": "e1", "label": "Forest"}],
            }
        }
        assert lookup_label_for_value(meta, 5) == "Forest"

    def test_label_not_found(self) -> None:
        meta = {
            "value_entity_map": {
                "mode": "exact",
                "mappings": [{"value": 5, "entity_id": "e1"}],
            }
        }
        assert lookup_label_for_value(meta, 5) is None


class TestProbeAllLayers:
    """Tests for probe_all_layers."""

    def test_probe_returns_results_for_visible_layers(self) -> None:
        buf1 = MapDataBuffer(width=8, height=8, default_value=10)
        buf2 = MapDataBuffer(width=8, height=8, default_value=20)

        # Create mock items
        class MockItem:
            def __init__(self, buf: MapDataBuffer, visible: bool = True):
                self._buffer = buf
                self._visible = visible

            @property
            def buffer(self) -> MapDataBuffer:
                return self._buffer

            def isVisible(self) -> bool:
                return self._visible

        items = {"n1": MockItem(buf1), "n2": MockItem(buf2, visible=False)}
        meta_list = [
            {"node_id": "n1", "value_entity_map": {"1": "e1"}},
            {"node_id": "n2"},
        ]

        results = probe_all_layers(items, meta_list, 0.5, 0.5)
        # Only n1 is visible
        assert len(results) == 1
        assert results[0].node_id == "n1"
        assert results[0].value == 10
