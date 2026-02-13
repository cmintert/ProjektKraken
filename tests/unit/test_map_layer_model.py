"""Unit tests for the Hierarchical Layer System (MapLayerNode + MapLayerModel).

Tests cover:
    1. Layer nesting and child visibility inheritance.
    2. Mutually exclusive group logic (radio-button behaviour).
    3. Z-sorting updates when model rows are moved.
    4. Opacity inheritance (global × local).
    5. Scale-dependent visibility.
    6. Serialisation round-trip (to_dict / from_dict).
    7. Visibility preset save / load.
"""

import pytest

from src.app.constants import (
    MAP_LAYER_DEFAULT_MAX_ZOOM,
    MAP_LAYER_DEFAULT_MIN_ZOOM,
    MAP_LAYER_DEFAULT_OPACITY,
    MAP_LAYER_TYPE_GROUP,
    MAP_LAYER_TYPE_MARKER,
    MAP_LAYER_TYPE_PATH,
    MAP_LAYER_TYPE_REGION,
    MAP_LAYER_Z_BASE,
    MAP_LAYER_Z_SPACING,
)
from src.core.map import Map, MapLayerNode
from src.gui.widgets.map.map_layer_model import MapLayerModel

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def simple_tree() -> MapLayerNode:
    """A small hierarchy::

        Root (group)
        ├── Group A (group)
        │   ├── Markers (marker layer)
        │   └── Paths   (path layer)
        └── Group B (group)
            └── Regions (region layer)
    """
    markers = MapLayerNode(
        name="Markers", layer_type=MAP_LAYER_TYPE_MARKER, id="markers-1"
    )
    paths = MapLayerNode(
        name="Paths", layer_type=MAP_LAYER_TYPE_PATH, id="paths-1"
    )
    regions = MapLayerNode(
        name="Regions", layer_type=MAP_LAYER_TYPE_REGION, id="regions-1"
    )
    group_a = MapLayerNode(
        name="Group A",
        layer_type=MAP_LAYER_TYPE_GROUP,
        id="group-a",
        children=[markers, paths],
    )
    group_b = MapLayerNode(
        name="Group B",
        layer_type=MAP_LAYER_TYPE_GROUP,
        id="group-b",
        children=[regions],
    )
    root = MapLayerNode(
        name="Root",
        layer_type=MAP_LAYER_TYPE_GROUP,
        id="root",
        children=[group_a, group_b],
    )
    return root


@pytest.fixture
def model(simple_tree: MapLayerNode) -> MapLayerModel:
    """MapLayerModel backed by :func:`simple_tree`."""
    return MapLayerModel(root=simple_tree)


# =========================================================================
# Test 1 — Layer nesting and child visibility inheritance
# =========================================================================


class TestVisibilityInheritance:
    """Hiding a parent must hide all descendants."""

    def test_all_visible_by_default(self, model: MapLayerModel) -> None:
        """Every node starts as visible."""
        for nid in ("group-a", "group-b", "markers-1", "paths-1", "regions-1"):
            node = model.find_node_by_id(nid)
            assert node is not None
            assert node.visible is True

    def test_hide_parent_hides_children_signals(
        self, model: MapLayerModel
    ) -> None:
        """Hiding Group A emits visibility=False for its children."""
        received: list[tuple[str, bool]] = []
        model.layer_visibility_changed.connect(
            lambda nid, vis: received.append((nid, vis))
        )

        group_a = model.find_node_by_id("group-a")
        assert group_a is not None
        model.set_node_visible(group_a, False)

        # Group A, Markers, Paths should all report invisible
        ids_hidden = {nid for nid, vis in received if not vis}
        assert "group-a" in ids_hidden
        assert "markers-1" in ids_hidden
        assert "paths-1" in ids_hidden

    def test_effective_visible_respects_parent(
        self, model: MapLayerModel
    ) -> None:
        """A child that is locally visible but with a hidden parent is
        effectively invisible."""
        group_a = model.find_node_by_id("group-a")
        markers = model.find_node_by_id("markers-1")
        assert group_a is not None and markers is not None

        model.set_node_visible(group_a, False)

        # markers still locally visible
        assert markers.visible is True
        # but effectively hidden
        assert markers.effective_visible(parent_visible=False) is False

    def test_show_parent_restores_children(
        self, model: MapLayerModel
    ) -> None:
        """Re-showing a parent re-emits visibility for descendants."""
        group_a = model.find_node_by_id("group-a")
        assert group_a is not None
        model.set_node_visible(group_a, False)

        received: list[tuple[str, bool]] = []
        model.layer_visibility_changed.connect(
            lambda nid, vis: received.append((nid, vis))
        )
        model.set_node_visible(group_a, True)

        ids_shown = {nid for nid, vis in received if vis}
        assert "group-a" in ids_shown
        assert "markers-1" in ids_shown


# =========================================================================
# Test 2 — Mutually exclusive group logic
# =========================================================================


class TestMutuallyExclusiveGroups:
    """When a group is marked mutually_exclusive, only one child can be
    visible at a time."""

    @pytest.fixture
    def era_model(self) -> MapLayerModel:
        """Model with a mutually-exclusive "Eras" group."""
        era1 = MapLayerNode(
            name="Era 1", layer_type=MAP_LAYER_TYPE_GROUP, id="era-1", visible=True
        )
        era2 = MapLayerNode(
            name="Era 2", layer_type=MAP_LAYER_TYPE_GROUP, id="era-2", visible=False
        )
        era3 = MapLayerNode(
            name="Era 3", layer_type=MAP_LAYER_TYPE_GROUP, id="era-3", visible=False
        )
        eras = MapLayerNode(
            name="Eras",
            layer_type=MAP_LAYER_TYPE_GROUP,
            id="eras",
            mutually_exclusive=True,
            children=[era1, era2, era3],
        )
        root = MapLayerNode(
            name="Root",
            layer_type=MAP_LAYER_TYPE_GROUP,
            id="root",
            children=[eras],
        )
        return MapLayerModel(root=root)

    def test_enabling_one_disables_others(
        self, era_model: MapLayerModel
    ) -> None:
        """Enabling Era 2 should disable Era 1."""
        era1 = era_model.find_node_by_id("era-1")
        era2 = era_model.find_node_by_id("era-2")
        assert era1 is not None and era2 is not None

        assert era1.visible is True
        assert era2.visible is False

        era_model.set_node_visible(era2, True)

        assert era2.visible is True
        assert era1.visible is False

    def test_enabling_third_disables_second(
        self, era_model: MapLayerModel
    ) -> None:
        """Switching from Era 2 → Era 3."""
        era2 = era_model.find_node_by_id("era-2")
        era3 = era_model.find_node_by_id("era-3")
        assert era2 is not None and era3 is not None

        era_model.set_node_visible(era2, True)
        assert era2.visible is True

        era_model.set_node_visible(era3, True)
        assert era3.visible is True
        assert era2.visible is False

    def test_disabling_does_not_auto_enable_sibling(
        self, era_model: MapLayerModel
    ) -> None:
        """Hiding the last visible era should NOT auto-enable another."""
        era1 = era_model.find_node_by_id("era-1")
        assert era1 is not None

        era_model.set_node_visible(era1, False)
        # All eras hidden
        for eid in ("era-1", "era-2", "era-3"):
            node = era_model.find_node_by_id(eid)
            assert node is not None
            assert node.visible is False

    def test_signals_emitted_for_siblings(
        self, era_model: MapLayerModel
    ) -> None:
        """Verify visibility signals are emitted for disabled siblings."""
        received: list[tuple[str, bool]] = []
        era_model.layer_visibility_changed.connect(
            lambda nid, vis: received.append((nid, vis))
        )

        era2 = era_model.find_node_by_id("era-2")
        assert era2 is not None
        era_model.set_node_visible(era2, True)

        # Era 1 should have been flagged invisible
        era1_signals = [(nid, vis) for nid, vis in received if nid == "era-1"]
        assert any(not vis for _, vis in era1_signals)


# =========================================================================
# Test 3 — Z-sorting updates when model rows are moved
# =========================================================================


class TestZSorting:
    """Z-order must reflect the DFS traversal order of the tree."""

    def test_initial_z_order(self, model: MapLayerModel) -> None:
        """Depth-first order: group-a, markers-1, paths-1, group-b, regions-1."""
        z = model.compute_z_order()
        assert z["group-a"] < z["markers-1"]
        assert z["markers-1"] < z["paths-1"]
        assert z["paths-1"] < z["group-b"]
        assert z["group-b"] < z["regions-1"]

    def test_z_order_spacing(self, model: MapLayerModel) -> None:
        """Z values should increase by MAP_LAYER_Z_SPACING."""
        z = model.compute_z_order()
        assert z["group-a"] == pytest.approx(MAP_LAYER_Z_BASE)
        assert z["markers-1"] == pytest.approx(
            MAP_LAYER_Z_BASE + MAP_LAYER_Z_SPACING
        )

    def test_z_order_after_move(self, model: MapLayerModel) -> None:
        """After moving Group B before Group A, the Z order reflects the
        new tree structure."""
        # Move group-b (row 1 under root) to row 0 under root
        group_b = model.find_node_by_id("group-b")
        assert group_b is not None
        group_b_index = model.index_from_node(group_b)
        root_index = model.index_from_node(model.root)

        model.move_layer(group_b_index, root_index, 0)

        # Verify tree structure was modified correctly
        assert model.root.children[0].id == "group-b"
        assert model.root.children[1].id == "group-a"

        z = model.compute_z_order()
        # Now: group-b comes first
        assert z["group-b"] < z["regions-1"]
        assert z["regions-1"] < z["group-a"]
        assert z["group-a"] < z["markers-1"]

    def test_layer_order_signal_emitted_on_move(
        self, model: MapLayerModel
    ) -> None:
        """The layer_order_changed signal fires after a move."""
        received: list[bool] = []
        model.layer_order_changed.connect(lambda: received.append(True))

        group_b = model.find_node_by_id("group-b")
        assert group_b is not None
        idx = model.index_from_node(group_b)
        model.move_layer(idx, model.index_from_node(model.root), 0)

        assert len(received) >= 1


# =========================================================================
# Test 4 — Opacity inheritance
# =========================================================================


class TestOpacityInheritance:
    """Group opacity multiplied with child opacity."""

    def test_default_opacity(self, model: MapLayerModel) -> None:
        """All nodes start with opacity 1.0."""
        markers = model.find_node_by_id("markers-1")
        assert markers is not None
        assert markers.opacity == pytest.approx(MAP_LAYER_DEFAULT_OPACITY)

    def test_group_opacity_multiplies(self, model: MapLayerModel) -> None:
        """Setting Group A opacity to 0.5 and Markers to 0.8
        → effective = 0.4."""
        group_a = model.find_node_by_id("group-a")
        markers = model.find_node_by_id("markers-1")
        assert group_a is not None and markers is not None

        model.set_node_opacity(group_a, 0.5)
        markers.opacity = 0.8

        received: list[tuple[str, float]] = []
        model.layer_opacity_changed.connect(
            lambda nid, op: received.append((nid, op))
        )
        model.set_node_opacity(markers, 0.8)

        marker_op = [op for nid, op in received if nid == "markers-1"]
        assert len(marker_op) > 0
        assert marker_op[-1] == pytest.approx(0.4)

    def test_opacity_signal_propagates(self, model: MapLayerModel) -> None:
        """Changing parent opacity emits signals for children."""
        received: list[tuple[str, float]] = []
        model.layer_opacity_changed.connect(
            lambda nid, op: received.append((nid, op))
        )

        group_a = model.find_node_by_id("group-a")
        assert group_a is not None
        model.set_node_opacity(group_a, 0.5)

        child_ids = {nid for nid, _ in received}
        assert "markers-1" in child_ids
        assert "paths-1" in child_ids


# =========================================================================
# Test 5 — Scale-dependent visibility
# =========================================================================


class TestScaleDependentVisibility:
    """Layers should hide automatically based on zoom level."""

    def test_visible_in_range(self, model: MapLayerModel) -> None:
        """Node with default zoom range is visible at any zoom."""
        markers = model.find_node_by_id("markers-1")
        assert markers is not None
        assert model.visible_at_zoom(markers, 0.5)
        assert model.visible_at_zoom(markers, 100.0)

    def test_hidden_below_min_zoom(self, model: MapLayerModel) -> None:
        """Node below its min_zoom is hidden."""
        markers = model.find_node_by_id("markers-1")
        assert markers is not None
        markers.min_zoom = 2.0
        assert not model.visible_at_zoom(markers, 1.0)

    def test_hidden_above_max_zoom(self, model: MapLayerModel) -> None:
        """Node above its max_zoom is hidden."""
        markers = model.find_node_by_id("markers-1")
        assert markers is not None
        markers.max_zoom = 5.0
        assert not model.visible_at_zoom(markers, 10.0)

    def test_parent_visibility_overrides_zoom(
        self, model: MapLayerModel
    ) -> None:
        """A hidden parent makes children invisible regardless of zoom."""
        group_a = model.find_node_by_id("group-a")
        markers = model.find_node_by_id("markers-1")
        assert group_a is not None and markers is not None

        group_a.visible = False
        assert not model.visible_at_zoom(markers, 1.0)


# =========================================================================
# Test 6 — Serialisation round-trip
# =========================================================================


class TestSerialisation:
    """to_dict / from_dict must survive a round-trip."""

    def test_layer_node_round_trip(self) -> None:
        """A single node serialises and deserialises correctly."""
        node = MapLayerNode(
            name="Test",
            layer_type=MAP_LAYER_TYPE_MARKER,
            id="test-1",
            visible=False,
            opacity=0.75,
            min_zoom=1.5,
            max_zoom=10.0,
        )
        data = node.to_dict()
        restored = MapLayerNode.from_dict(data)

        assert restored.id == "test-1"
        assert restored.name == "Test"
        assert restored.layer_type == MAP_LAYER_TYPE_MARKER
        assert restored.visible is False
        assert restored.opacity == pytest.approx(0.75)
        assert restored.min_zoom == pytest.approx(1.5)
        assert restored.max_zoom == pytest.approx(10.0)

    def test_nested_round_trip(self, simple_tree: MapLayerNode) -> None:
        """A nested tree survives serialisation."""
        data = simple_tree.to_dict()
        restored = MapLayerNode.from_dict(data)

        assert restored.name == "Root"
        assert len(restored.children) == 2
        assert restored.children[0].name == "Group A"
        assert len(restored.children[0].children) == 2
        assert restored.children[1].children[0].name == "Regions"

    def test_inf_max_zoom_round_trip(self) -> None:
        """Infinity max_zoom is stored as None and restored as inf."""
        node = MapLayerNode(name="Inf Test", max_zoom=float("inf"))
        data = node.to_dict()
        assert data["max_zoom"] is None
        restored = MapLayerNode.from_dict(data)
        assert restored.max_zoom == float("inf")

    def test_map_with_layers_round_trip(self) -> None:
        """Map.to_dict / from_dict preserves the layer tree."""
        layers = MapLayerNode(
            name="Root",
            children=[
                MapLayerNode(name="Markers", layer_type=MAP_LAYER_TYPE_MARKER)
            ],
        )
        m = Map(name="Test Map", image_path="/fake.png", layers=layers)
        data = m.to_dict()
        assert "layers" in data

        restored = Map.from_dict(data)
        assert restored.layers is not None
        assert restored.layers.name == "Root"
        assert len(restored.layers.children) == 1

    def test_map_without_layers_round_trip(self) -> None:
        """Map without layers still works (backward compat)."""
        m = Map(name="No Layers", image_path="/fake.png")
        data = m.to_dict()
        assert "layers" not in data

        restored = Map.from_dict(data)
        assert restored.layers is None


# =========================================================================
# Test 7 — Visibility presets
# =========================================================================


class TestVisibilityPresets:
    """Save / load visibility presets ("Map Themes")."""

    def test_save_and_load(self, model: MapLayerModel) -> None:
        """Round-trip: modify state → save → modify again → load → original."""
        group_a = model.find_node_by_id("group-a")
        assert group_a is not None
        model.set_node_visible(group_a, False)
        model.set_node_opacity(group_a, 0.3)

        preset = model.save_preset()

        # Modify further
        model.set_node_visible(group_a, True)
        model.set_node_opacity(group_a, 1.0)

        # Restore
        model.load_preset(preset)

        assert group_a.visible is False
        assert group_a.opacity == pytest.approx(0.3)

    def test_preset_contains_all_nodes(
        self, model: MapLayerModel
    ) -> None:
        """Preset snapshot includes every node."""
        preset = model.save_preset()
        for nid in (
            "root",
            "group-a",
            "group-b",
            "markers-1",
            "paths-1",
            "regions-1",
        ):
            assert nid in preset


# =========================================================================
# Test 8 — Model API (add / remove layer)
# =========================================================================


class TestModelAPI:
    """Basic model operations: add, remove, row/column counts."""

    def test_row_count(self, model: MapLayerModel) -> None:
        """Root has 2 children."""
        assert model.rowCount() == 2

    def test_column_count(self, model: MapLayerModel) -> None:
        """Single column."""
        assert model.columnCount() == 1

    def test_add_layer(self, model: MapLayerModel) -> None:
        """Adding a layer increases row count."""
        new_node = MapLayerNode(
            name="New Layer", layer_type=MAP_LAYER_TYPE_MARKER
        )
        root_idx = model.index_from_node(model.root)
        model.add_layer(root_idx, new_node)
        assert model.rowCount() == 3

    def test_remove_layer(self, model: MapLayerModel) -> None:
        """Removing a layer decreases row count."""
        group_b = model.find_node_by_id("group-b")
        assert group_b is not None
        idx = model.index_from_node(group_b)
        model.remove_layer(idx)
        assert model.rowCount() == 1

    def test_display_data(self, model: MapLayerModel) -> None:
        """DisplayRole returns the node name with type icon prefix."""
        from PySide6.QtCore import Qt

        idx = model.index(0, 0)
        display = model.data(idx, Qt.ItemDataRole.DisplayRole)
        assert "Group A" in display
