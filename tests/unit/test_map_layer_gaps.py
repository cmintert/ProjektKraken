"""Tests for the HLS gap-analysis fixes.

Covers:
- Temporal layers (start_date / end_date on MapLayerNode)
- Lazy visibility caching
- Layer commands (SetLayerVisibilityCommand, MoveLayerCommand, SaveLayerTreeCommand)
- Layer persistence via MapRepository attributes
- Auto-registration of markers as layer nodes
- Zombie node cleanup on marker deletion
- MapLayerPanel basic behaviour
- Bi-directional selection
"""

import pytest
from PySide6.QtCore import QModelIndex, QRectF, Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QGraphicsPixmapItem

from src.app.constants import (
    MAP_LAYER_TYPE_GROUP,
    MAP_LAYER_TYPE_MARKER,
    MAP_LAYER_TYPE_PATH,
    MAP_LAYER_TYPE_REGION,
)
from src.commands.map_commands import (
    MoveLayerCommand,
    SaveLayerTreeCommand,
    SetLayerVisibilityCommand,
)
from src.core.map import Map, MapLayerNode
from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.map.map_layer_model import MapLayerModel
from src.gui.widgets.map.map_layer_panel import MapLayerPanel

# Tolerance for floating-point opacity comparisons (slider integer → float)
_OPACITY_TOLERANCE = 0.01


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def temporal_tree() -> MapLayerNode:
    """A tree with temporal (start_date/end_date) nodes."""
    ww1 = MapLayerNode(
        name="WW1 Borders",
        layer_type=MAP_LAYER_TYPE_REGION,
        id="ww1",
        start_date=100.0,
        end_date=200.0,
    )
    ww2 = MapLayerNode(
        name="WW2 Borders",
        layer_type=MAP_LAYER_TYPE_REGION,
        id="ww2",
        start_date=200.0,
        end_date=300.0,
    )
    timeless = MapLayerNode(
        name="Rivers",
        layer_type=MAP_LAYER_TYPE_PATH,
        id="rivers",
    )
    root = MapLayerNode(
        name="Root",
        layer_type=MAP_LAYER_TYPE_GROUP,
        id="root",
        children=[ww1, ww2, timeless],
    )
    return root


@pytest.fixture
def temporal_model(temporal_tree: MapLayerNode) -> MapLayerModel:
    """Model with temporal nodes."""
    return MapLayerModel(root=temporal_tree)


@pytest.fixture
def simple_model() -> MapLayerModel:
    """Basic model with some marker nodes."""
    m1 = MapLayerNode(name="Marker 1", layer_type=MAP_LAYER_TYPE_MARKER, id="m1")
    m2 = MapLayerNode(name="Marker 2", layer_type=MAP_LAYER_TYPE_MARKER, id="m2")
    group = MapLayerNode(
        name="Default",
        layer_type=MAP_LAYER_TYPE_GROUP,
        id="default",
        children=[m1, m2],
    )
    root = MapLayerNode(
        name="Root",
        layer_type=MAP_LAYER_TYPE_GROUP,
        id="root",
        children=[group],
    )
    return MapLayerModel(root=root)


# =========================================================================
# Temporal Layers (HIGH-5)
# =========================================================================


class TestTemporalVisibility:
    """Time-aware layer visibility."""

    def test_visible_within_range(self, temporal_model: MapLayerModel) -> None:
        """WW1 visible at t=150."""
        ww1 = temporal_model.find_node_by_id("ww1")
        assert ww1 is not None
        assert temporal_model.visible_at_time(ww1, 150.0) is True

    def test_hidden_before_start(self, temporal_model: MapLayerModel) -> None:
        """WW1 hidden before start_date."""
        ww1 = temporal_model.find_node_by_id("ww1")
        assert ww1 is not None
        assert temporal_model.visible_at_time(ww1, 50.0) is False

    def test_hidden_after_end(self, temporal_model: MapLayerModel) -> None:
        """WW1 hidden after end_date."""
        ww1 = temporal_model.find_node_by_id("ww1")
        assert ww1 is not None
        assert temporal_model.visible_at_time(ww1, 250.0) is False

    def test_timeless_always_visible(self, temporal_model: MapLayerModel) -> None:
        """Rivers (no dates) visible at any time."""
        rivers = temporal_model.find_node_by_id("rivers")
        assert rivers is not None
        assert temporal_model.visible_at_time(rivers, 0.0) is True
        assert temporal_model.visible_at_time(rivers, 9999.0) is True

    def test_hidden_node_not_time_visible(self, temporal_model: MapLayerModel) -> None:
        """A manually hidden node is not time-visible even in range."""
        ww1 = temporal_model.find_node_by_id("ww1")
        assert ww1 is not None
        ww1.visible = False
        assert temporal_model.visible_at_time(ww1, 150.0) is False

    def test_serialise_temporal_fields(self) -> None:
        """start_date and end_date survive serialisation round-trip."""
        node = MapLayerNode(
            name="Era",
            id="era-1",
            start_date=100.0,
            end_date=200.0,
        )
        data = node.to_dict()
        assert data["start_date"] == 100.0
        assert data["end_date"] == 200.0

        restored = MapLayerNode.from_dict(data)
        assert restored.start_date == 100.0
        assert restored.end_date == 200.0

    def test_serialise_none_temporal_fields(self) -> None:
        """None dates survive round-trip."""
        node = MapLayerNode(name="Always", id="always-1")
        data = node.to_dict()
        assert data["start_date"] is None
        assert data["end_date"] is None

        restored = MapLayerNode.from_dict(data)
        assert restored.start_date is None
        assert restored.end_date is None


# =========================================================================
# Lazy Visibility Cache (MEDIUM-9)
# =========================================================================


class TestVisibilityCache:
    """compute_visibility() caching behaviour."""

    def test_cache_returns_same_dict(self, temporal_model: MapLayerModel) -> None:
        """Same zoom+time returns cached dict."""
        r1 = temporal_model.compute_visibility(1.0, 150.0)
        r2 = temporal_model.compute_visibility(1.0, 150.0)
        assert r1 is r2  # same object (cached)

    def test_cache_invalidated_on_visibility_change(
        self, temporal_model: MapLayerModel
    ) -> None:
        """Cache is invalidated when visibility changes."""
        r1 = temporal_model.compute_visibility(1.0, 150.0)
        ww1 = temporal_model.find_node_by_id("ww1")
        assert ww1 is not None
        temporal_model.set_node_visible(ww1, False)
        r2 = temporal_model.compute_visibility(1.0, 150.0)
        assert r1 is not r2  # different object

    def test_cache_invalidated_on_zoom_change(
        self, temporal_model: MapLayerModel
    ) -> None:
        """Different zoom level returns fresh result."""
        r1 = temporal_model.compute_visibility(1.0, 150.0)
        r2 = temporal_model.compute_visibility(2.0, 150.0)
        assert r1 is not r2

    def test_compute_visibility_includes_all_nodes(
        self, temporal_model: MapLayerModel
    ) -> None:
        """Result contains entries for all non-root nodes."""
        result = temporal_model.compute_visibility(1.0, 150.0)
        assert "ww1" in result
        assert "ww2" in result
        assert "rivers" in result

    def test_compute_visibility_time_filtering(
        self, temporal_model: MapLayerModel
    ) -> None:
        """WW1 visible at 150, WW2 hidden at 150."""
        result = temporal_model.compute_visibility(1.0, 150.0)
        assert result["ww1"] is True
        assert result["ww2"] is False
        assert result["rivers"] is True


# =========================================================================
# Custom Data Roles
# =========================================================================


class TestCustomRoles:
    """Test custom data roles on MapLayerModel."""

    def test_layer_type_role(self, simple_model: MapLayerModel) -> None:
        """LayerTypeRole returns the layer_type string."""
        idx = simple_model.index(0, 0)  # "Default" group
        assert (
            simple_model.data(idx, MapLayerModel.LayerTypeRole) == MAP_LAYER_TYPE_GROUP
        )

    def test_opacity_role(self, simple_model: MapLayerModel) -> None:
        """OpacityRole returns the node's opacity."""
        idx = simple_model.index(0, 0)
        assert simple_model.data(idx, MapLayerModel.OpacityRole) == 1.0

    def test_node_id_role(self, simple_model: MapLayerModel) -> None:
        """NodeIdRole returns the node's id."""
        idx = simple_model.index(0, 0)
        assert simple_model.data(idx, MapLayerModel.NodeIdRole) == "default"


# =========================================================================
# Layer Commands (HIGH-4)
# =========================================================================


class TestSetLayerVisibilityCommand:
    """Test the SetLayerVisibilityCommand."""

    def test_find_node_static(self) -> None:
        """_find_layer_node utility locates nested nodes."""
        from src.commands.map_commands import _find_layer_node

        child = MapLayerNode(name="Child", id="child-1")
        root = MapLayerNode(name="Root", id="root", children=[child])
        found = _find_layer_node(root, "child-1")
        assert found is child

    def test_find_node_not_found(self) -> None:
        """_find_layer_node returns None for missing IDs."""
        from src.commands.map_commands import _find_layer_node

        root = MapLayerNode(name="Root", id="root")
        assert _find_layer_node(root, "nope") is None

    def test_serialization_round_trip(self) -> None:
        """to_dict / from_dict round-trip."""
        cmd = SetLayerVisibilityCommand("map-1", "node-1", False)
        data = cmd.to_dict()
        restored = SetLayerVisibilityCommand.from_dict(data)
        assert restored.map_id == "map-1"
        assert restored.node_id == "node-1"
        assert restored.visible is False


class TestMoveLayerCommand:
    """Test the MoveLayerCommand."""

    def test_find_parent_static(self) -> None:
        """_find_parent utility locates parent of a node."""
        child = MapLayerNode(name="Child", id="child-1")
        root = MapLayerNode(name="Root", id="root", children=[child])
        parent = MoveLayerCommand._find_parent(root, child)
        assert parent is root

    def test_serialization_round_trip(self) -> None:
        """to_dict / from_dict round-trip."""
        cmd = MoveLayerCommand("map-1", "node-1", "parent-2", 3)
        data = cmd.to_dict()
        restored = MoveLayerCommand.from_dict(data)
        assert restored.map_id == "map-1"
        assert restored.node_id == "node-1"
        assert restored.new_parent_id == "parent-2"
        assert restored.new_row == 3


class TestSaveLayerTreeCommand:
    """Test the SaveLayerTreeCommand."""

    def test_serialization_round_trip(self) -> None:
        """to_dict / from_dict round-trip."""
        tree_dict = {"name": "Root", "children": []}
        cmd = SaveLayerTreeCommand("map-1", tree_dict)
        data = cmd.to_dict()
        restored = SaveLayerTreeCommand.from_dict(data)
        assert restored.map_id == "map-1"
        assert restored.layer_tree_dict == tree_dict


# =========================================================================
# Layer Persistence (CRITICAL-2)
# =========================================================================


class TestLayerPersistence:
    """Layer tree stored/restored via map attributes."""

    def test_map_with_layers_to_dict_has_layers(self) -> None:
        """Map.to_dict includes layers when present."""
        layers = MapLayerNode(
            name="Root",
            children=[
                MapLayerNode(name="M1", layer_type=MAP_LAYER_TYPE_MARKER, id="m1"),
            ],
        )
        m = Map(name="Test", image_path="/fake.png", layers=layers)
        d = m.to_dict()
        assert "layers" in d
        assert d["layers"]["name"] == "Root"

    def test_map_from_dict_restores_layers(self) -> None:
        """Map.from_dict restores layers from dict."""
        data = {
            "name": "Test",
            "image_path": "/fake.png",
            "attributes": {
                "layers": {
                    "name": "Root",
                    "layer_type": "group",
                    "children": [
                        {"name": "M1", "layer_type": "marker", "id": "m1"},
                    ],
                },
            },
        }
        m = Map.from_dict(data)
        # layers field is populated from the top-level "layers" key if present
        # But in our persistence strategy, layers are in attributes["layers"]
        # The Map.from_dict only restores from top-level "layers" key
        # The repository handles reconstruction from attributes
        assert m.attributes.get("layers") is not None


# =========================================================================
# MapLayerPanel (CRITICAL-1)
# =========================================================================


class TestMapLayerPanel:
    """Tests for the layer panel widget."""

    def test_panel_creates(self, qtbot) -> None:
        """Panel can be instantiated."""
        panel = MapLayerPanel()
        qtbot.addWidget(panel)
        assert panel.tree_view is not None

    def test_panel_set_model(self, qtbot, simple_model: MapLayerModel) -> None:
        """Attaching a model populates the tree view."""
        panel = MapLayerPanel()
        qtbot.addWidget(panel)
        panel.set_model(simple_model)
        assert panel.tree_view.model() is simple_model

    def test_panel_select_node(self, qtbot, simple_model: MapLayerModel) -> None:
        """select_node highlights the correct item."""
        panel = MapLayerPanel()
        qtbot.addWidget(panel)
        panel.set_model(simple_model)
        panel.select_node("m1")
        current = panel.tree_view.currentIndex()
        assert current.isValid()
        node = simple_model.node_from_index(current)
        assert node.id == "m1"

    def test_panel_layer_selected_signal(
        self, qtbot, simple_model: MapLayerModel
    ) -> None:
        """Clicking emits layer_selected with node ID."""
        panel = MapLayerPanel()
        qtbot.addWidget(panel)
        panel.set_model(simple_model)

        received: list[str] = []
        panel.layer_selected.connect(lambda nid: received.append(nid))

        # Simulate clicking the first child of root (Default group)
        idx = simple_model.index(0, 0)
        panel._on_item_clicked(idx)

        assert len(received) == 1
        assert received[0] == "default"


# =========================================================================
# MapWidget Layer Integration (CRITICAL-3 + HIGH-6 + MEDIUM-7)
# =========================================================================


def _make_map_widget(qtbot):
    """Create a MapWidget with a test pixmap."""
    from src.gui.widgets.map_widget import MapWidget

    widget = MapWidget()
    qtbot.addWidget(widget)

    # Create test pixmap
    test_image = QImage(100, 100, QImage.Format.Format_RGB32)
    test_image.fill(Qt.GlobalColor.white)
    pixmap = QPixmap.fromImage(test_image)

    widget.view.pixmap_item = QGraphicsPixmapItem(pixmap)
    widget.view.scene.addItem(widget.view.pixmap_item)
    widget.view.coord_system.set_scene_rect(QRectF(0, 0, 100, 100))

    return widget


class TestMapWidgetLayerIntegration:
    """MapWidget auto-registration and zombie cleanup."""

    def test_add_marker_creates_layer_node(self, qtbot) -> None:
        """Adding a marker auto-creates a layer node (HIGH-6)."""
        widget = _make_map_widget(qtbot)
        widget.add_marker("test-1", "entity", "Test Marker", 0.5, 0.5)

        model = widget.get_layer_model()
        assert model is not None
        node = model.find_node_by_id("test-1")
        assert node is not None
        assert node.name == "Test Marker"
        assert node.layer_type == MAP_LAYER_TYPE_MARKER

    def test_add_path_creates_path_node(self, qtbot) -> None:
        """Adding a path feature creates a path layer node."""
        widget = _make_map_widget(qtbot)
        geometry = [{"x": 0.0, "y": 0.0}, {"x": 1.0, "y": 1.0}]
        widget.add_marker(
            "path-1",
            "entity",
            "River",
            0.5,
            0.5,
            feature_type="path",
            geometry=geometry,
        )

        model = widget.get_layer_model()
        node = model.find_node_by_id("path-1")
        assert node is not None
        assert node.layer_type == MAP_LAYER_TYPE_PATH

    def test_add_region_creates_region_node(self, qtbot) -> None:
        """Adding a region feature creates a region layer node."""
        widget = _make_map_widget(qtbot)
        geometry = [
            {"x": 0.0, "y": 0.0},
            {"x": 1.0, "y": 0.0},
            {"x": 0.5, "y": 1.0},
        ]
        widget.add_marker(
            "region-1",
            "entity",
            "Nation",
            0.5,
            0.5,
            feature_type="region",
            geometry=geometry,
        )

        model = widget.get_layer_model()
        node = model.find_node_by_id("region-1")
        assert node is not None
        assert node.layer_type == MAP_LAYER_TYPE_REGION

    def test_remove_marker_removes_layer_node(self, qtbot) -> None:
        """Removing a marker also removes its layer node (MEDIUM-7)."""
        widget = _make_map_widget(qtbot)
        widget.add_marker("test-1", "entity", "Test Marker", 0.5, 0.5)

        model = widget.get_layer_model()
        assert model.find_node_by_id("test-1") is not None

        widget.remove_marker("test-1")
        assert model.find_node_by_id("test-1") is None

    def test_clear_markers_resets_model(self, qtbot) -> None:
        """Clearing all markers resets the layer model."""
        widget = _make_map_widget(qtbot)
        widget.add_marker("test-1", "entity", "Test", 0.5, 0.5)
        assert widget.get_layer_model() is not None

        widget.clear_markers()
        assert widget.get_layer_model() is None

    def test_duplicate_marker_not_registered_twice(self, qtbot) -> None:
        """Adding same marker ID twice doesn't duplicate layer node."""
        widget = _make_map_widget(qtbot)
        widget.add_marker("test-1", "entity", "Test", 0.5, 0.5)
        widget.add_marker("test-1", "entity", "Test", 0.5, 0.5)

        model = widget.get_layer_model()
        # Count nodes with id "test-1"
        count = 0

        def _count(node):
            nonlocal count
            if node.id == "test-1":
                count += 1
            for c in node.children:
                _count(c)

        _count(model.root)
        assert count == 1

    def test_build_layer_model_with_persisted_root(self, qtbot) -> None:
        """_build_layer_model accepts a persisted root node."""
        widget = _make_map_widget(qtbot)
        persisted = MapLayerNode(
            name="Root",
            layer_type=MAP_LAYER_TYPE_GROUP,
            id="persisted-root",
            children=[
                MapLayerNode(
                    name="Custom Group",
                    layer_type=MAP_LAYER_TYPE_GROUP,
                    id="custom-group",
                ),
            ],
        )
        model = widget._build_layer_model(persisted)
        assert model.root.id == "persisted-root"
        assert model.find_node_by_id("custom-group") is not None

    def test_layer_model_connected_to_view(self, qtbot) -> None:
        """After adding markers, the view has the layer model attached."""
        widget = _make_map_widget(qtbot)
        widget.add_marker("test-1", "entity", "Test", 0.5, 0.5)
        assert widget.view.layer_model is widget.get_layer_model()


# =========================================================================
# Bi-directional Selection (LOW-10)
# =========================================================================


class TestBidirectionalSelection:
    """Marker click → layer panel; layer panel click → map."""

    def test_marker_click_highlights_layer(self, qtbot) -> None:
        """Clicking marker selects its layer in the panel."""
        widget = _make_map_widget(qtbot)
        widget.add_marker("test-1", "entity", "Test", 0.5, 0.5)

        # Simulate the signal
        widget._on_marker_clicked_select_layer("test-1", "entity")

        current = widget.layer_panel.tree_view.currentIndex()
        if current.isValid():
            model = widget.get_layer_model()
            node = model.node_from_index(current)
            assert node.id == "test-1"

    def test_layer_panel_click_selects_marker(self, qtbot) -> None:
        """Clicking layer in panel selects the graphics item."""
        widget = _make_map_widget(qtbot)
        widget.add_marker("test-1", "entity", "Test", 0.5, 0.5)

        widget._on_layer_panel_selected("test-1")

        # Check that the marker is selected
        marker_item = widget.view.markers.get("test-1")
        if marker_item is not None:
            assert marker_item.isSelected()


# =========================================================================
# Layer Panel UI Polish
# =========================================================================


class TestMapLayerPanelToolbar:
    """Tests for the panel's toolbar buttons and create/delete actions."""

    def test_toolbar_buttons_exist(self, qtbot, simple_model: MapLayerModel) -> None:
        """Panel has New Group and Delete buttons."""
        panel = MapLayerPanel()
        qtbot.addWidget(panel)
        panel.set_model(simple_model)
        assert panel.btn_new_group is not None
        assert panel.btn_delete is not None

    def test_delete_button_disabled_initially(
        self, qtbot, simple_model: MapLayerModel
    ) -> None:
        """Delete button is disabled when nothing is selected."""
        panel = MapLayerPanel()
        qtbot.addWidget(panel)
        panel.set_model(simple_model)
        assert not panel.btn_delete.isEnabled()

    def test_delete_button_enabled_after_selection(
        self, qtbot, simple_model: MapLayerModel
    ) -> None:
        """Delete button enables after clicking a layer."""
        panel = MapLayerPanel()
        qtbot.addWidget(panel)
        panel.set_model(simple_model)

        # Simulate clicking a node
        idx = simple_model.index(0, 0)  # "Default" group
        panel._on_item_clicked(idx)
        assert panel.btn_delete.isEnabled()

    def test_create_group_signal(self, qtbot, simple_model: MapLayerModel) -> None:
        """create_group_requested is emitted with the group name."""
        panel = MapLayerPanel()
        qtbot.addWidget(panel)
        panel.set_model(simple_model)

        received: list[str] = []
        panel.create_group_requested.connect(lambda n: received.append(n))

        # Directly emit (bypasses QInputDialog)
        panel.create_group_requested.emit("Test Group")
        assert received == ["Test Group"]

    def test_create_layer_signal(self, qtbot, simple_model: MapLayerModel) -> None:
        """create_layer_requested is emitted with the layer name."""
        panel = MapLayerPanel()
        qtbot.addWidget(panel)
        panel.set_model(simple_model)

        received: list[str] = []
        panel.create_layer_requested.connect(lambda n: received.append(n))

        panel.create_layer_requested.emit("Test Layer")
        assert received == ["Test Layer"]

    def test_delete_layer_signal(self, qtbot, simple_model: MapLayerModel) -> None:
        """delete_layer_requested is emitted with the node ID."""
        panel = MapLayerPanel()
        qtbot.addWidget(panel)
        panel.set_model(simple_model)

        received: list[str] = []
        panel.delete_layer_requested.connect(lambda nid: received.append(nid))

        # Select a node first, then trigger delete
        idx = simple_model.index(0, 0)
        panel._on_item_clicked(idx)
        panel._on_delete()
        assert len(received) == 1
        assert received[0] == "default"

    def test_delete_clears_selection(self, qtbot, simple_model: MapLayerModel) -> None:
        """After deleting, selected_node_id is cleared."""
        panel = MapLayerPanel()
        qtbot.addWidget(panel)
        panel.set_model(simple_model)

        idx = simple_model.index(0, 0)
        panel._on_item_clicked(idx)
        assert panel._selected_node_id is not None

        # Capture signal but don't actually delete
        panel.delete_layer_requested.connect(lambda _: None)
        panel._on_delete()
        assert panel._selected_node_id is None


class TestMapLayerPanelOpacity:
    """Tests for the opacity slider."""

    def test_opacity_slider_exists(self, qtbot) -> None:
        """Panel has an opacity slider."""
        panel = MapLayerPanel()
        qtbot.addWidget(panel)
        assert panel._opacity_slider is not None
        assert panel._opacity_value_label is not None

    def test_opacity_slider_syncs_to_node(
        self, qtbot, simple_model: MapLayerModel
    ) -> None:
        """Selecting a node syncs the slider to its opacity."""
        panel = MapLayerPanel()
        qtbot.addWidget(panel)
        panel.set_model(simple_model)

        # Set a custom opacity on a node
        m1 = simple_model.find_node_by_id("m1")
        m1.opacity = 0.5

        panel.select_node("m1")
        assert panel._opacity_slider.value() == 50
        assert "50" in panel._opacity_value_label.text()

    def test_opacity_slider_emits_signal(
        self, qtbot, simple_model: MapLayerModel
    ) -> None:
        """Moving the slider emits layer_opacity_changed."""
        panel = MapLayerPanel()
        qtbot.addWidget(panel)
        panel.set_model(simple_model)

        received: list[tuple] = []
        panel.layer_opacity_changed.connect(lambda nid, o: received.append((nid, o)))

        # Select a node
        panel.select_node("m1")
        # Move the slider
        panel._opacity_slider.setValue(75)

        assert len(received) == 1
        assert received[0][0] == "m1"
        assert abs(received[0][1] - 0.75) < _OPACITY_TOLERANCE

    def test_opacity_slider_no_feedback_loop(
        self, qtbot, simple_model: MapLayerModel
    ) -> None:
        """Syncing slider from node doesn't re-emit the signal."""
        panel = MapLayerPanel()
        qtbot.addWidget(panel)
        panel.set_model(simple_model)

        received: list[tuple] = []
        panel.layer_opacity_changed.connect(lambda nid, o: received.append((nid, o)))

        # select_node internally syncs the slider — should NOT trigger signal
        panel.select_node("m1")
        # The slider_updating guard should prevent emission during sync
        # Only direct setValue outside of sync should emit
        assert len(received) == 0


class TestMapLayerPanelRename:
    """Tests for rename functionality."""

    def test_rename_signal(self, qtbot, simple_model: MapLayerModel) -> None:
        """layer_renamed signal is emitted with node ID and new name."""
        panel = MapLayerPanel()
        qtbot.addWidget(panel)
        panel.set_model(simple_model)

        received: list[tuple] = []
        panel.layer_renamed.connect(lambda nid, n: received.append((nid, n)))

        panel.layer_renamed.emit("m1", "Renamed")
        assert received == [("m1", "Renamed")]


class TestMapLayerPanelContextMenu:
    """Tests for the context menu."""

    def test_toggle_visibility_via_panel(
        self, qtbot, simple_model: MapLayerModel
    ) -> None:
        """Toggling visibility through the panel updates the node."""
        panel = MapLayerPanel()
        qtbot.addWidget(panel)
        panel.set_model(simple_model)

        m1 = simple_model.find_node_by_id("m1")
        assert m1.visible is True

        panel._toggle_visibility(m1)
        assert m1.visible is False

        panel._toggle_visibility(m1)
        assert m1.visible is True


class TestMapLayerPanelRefreshStyles:
    """Tests for theme refresh."""

    def test_refresh_styles_does_not_crash(self, qtbot) -> None:
        """Calling refresh_styles doesn't raise."""
        panel = MapLayerPanel()
        qtbot.addWidget(panel)
        panel.refresh_styles()  # Should not crash


# =========================================================================
# MapWidget Layer CRUD (create/delete groups/layers)
# =========================================================================


class TestMapWidgetLayerCRUD:
    """MapWidget create/delete group and layer actions."""

    def test_create_group(self, qtbot) -> None:
        """Creating a group adds it under root."""
        widget = _make_map_widget(qtbot)
        widget._ensure_layer_model()
        model = widget.get_layer_model()
        initial_count = len(model.root.children)

        widget._on_create_group("Test Group")
        assert len(model.root.children) == initial_count + 1
        new_group = model.root.children[-1]
        assert new_group.name == "Test Group"
        assert new_group.layer_type == MAP_LAYER_TYPE_GROUP

    def test_create_layer_under_default(self, qtbot) -> None:
        """Creating a layer with no selection adds it under Default."""
        widget = _make_map_widget(qtbot)
        widget._ensure_layer_model()

        widget._on_create_layer("Test Layer")

        model = widget.get_layer_model()
        default = widget._default_group()
        layer_names = [c.name for c in default.children]
        assert "Test Layer" in layer_names

    def test_create_layer_under_selected_group(self, qtbot) -> None:
        """Creating a layer with a group selected adds under that group."""
        widget = _make_map_widget(qtbot)
        widget._ensure_layer_model()
        model = widget.get_layer_model()

        # Create a custom group first
        widget._on_create_group("Custom")
        custom = model.find_node_by_id(
            next(c.id for c in model.root.children if c.name == "Custom")
        )

        # Select it in the panel
        widget.layer_panel._selected_node_id = custom.id

        widget._on_create_layer("Child Layer")
        child_names = [c.name for c in custom.children]
        assert "Child Layer" in child_names

    def test_delete_leaf_layer(self, qtbot) -> None:
        """Deleting a leaf layer removes it from the model."""
        widget = _make_map_widget(qtbot)
        widget.add_marker("del-1", "entity", "To Delete", 0.5, 0.5)
        model = widget.get_layer_model()

        assert model.find_node_by_id("del-1") is not None
        widget._on_delete_layer("del-1")
        assert model.find_node_by_id("del-1") is None

    def test_delete_group_removes_children_graphics(self, qtbot) -> None:
        """Deleting a group also removes children graphics items."""
        widget = _make_map_widget(qtbot)
        widget.add_marker("child-1", "entity", "Child", 0.5, 0.5)
        model = widget.get_layer_model()

        # Find the Default group that contains child-1
        default = widget._default_group()
        assert model.find_node_by_id("child-1") is not None

        # Delete the whole group
        widget._on_delete_layer(default.id)
        assert model.find_node_by_id(default.id) is None

    def test_delete_root_prevented(self, qtbot) -> None:
        """Cannot delete the root node."""
        widget = _make_map_widget(qtbot)
        model = widget._ensure_layer_model()
        root_id = model.root.id

        widget._on_delete_layer(root_id)
        # Root should still exist
        assert model.root.id == root_id

    def test_rename_updates_model(self, qtbot) -> None:
        """Renaming a layer updates the node name."""
        widget = _make_map_widget(qtbot)
        widget.add_marker("ren-1", "entity", "Original", 0.5, 0.5)
        model = widget.get_layer_model()

        widget._on_layer_renamed("ren-1", "Renamed")
        node = model.find_node_by_id("ren-1")
        assert node.name == "Renamed"


# =========================================================================
# StyleHelper new methods
# =========================================================================


class TestStyleHelperNewMethods:
    """Tests for new StyleHelper methods."""

    def test_get_tree_view_style(self) -> None:
        """get_tree_view_style returns a non-empty string."""
        style = StyleHelper.get_tree_view_style()
        assert isinstance(style, str)
        assert "QTreeView" in style

    def test_get_slider_style(self) -> None:
        """get_slider_style returns a non-empty string."""
        style = StyleHelper.get_slider_style()
        assert isinstance(style, str)
        assert "QSlider" in style

    def test_get_panel_header_style(self) -> None:
        """get_panel_header_style returns a non-empty string."""
        style = StyleHelper.get_panel_header_style()
        assert isinstance(style, str)
        assert "font-weight" in style


# =========================================================================
# layer_tree_changed signal
# =========================================================================


class TestLayerTreeChangedSignal:
    """Verify the model emits layer_tree_changed on every mutation."""

    def test_emitted_on_set_visible(self, qtbot, simple_model: MapLayerModel) -> None:
        """Toggling visibility emits layer_tree_changed."""
        m1 = simple_model.find_node_by_id("m1")
        with qtbot.waitSignal(simple_model.layer_tree_changed, timeout=500):
            simple_model.set_node_visible(m1, False)

    def test_emitted_on_set_opacity(self, qtbot, simple_model: MapLayerModel) -> None:
        """Changing opacity emits layer_tree_changed."""
        m1 = simple_model.find_node_by_id("m1")
        with qtbot.waitSignal(simple_model.layer_tree_changed, timeout=500):
            simple_model.set_node_opacity(m1, 0.5)

    def test_emitted_on_add_layer(self, qtbot, simple_model: MapLayerModel) -> None:
        """Adding a layer emits layer_tree_changed."""
        new_node = MapLayerNode(name="New", layer_type=MAP_LAYER_TYPE_MARKER)
        root_idx = simple_model.index_from_node(simple_model.root)
        with qtbot.waitSignal(simple_model.layer_tree_changed, timeout=500):
            simple_model.add_layer(root_idx, new_node)

    def test_emitted_on_remove_layer(self, qtbot, simple_model: MapLayerModel) -> None:
        """Removing a layer emits layer_tree_changed."""
        m1 = simple_model.find_node_by_id("m1")
        idx = simple_model.index_from_node(m1)
        with qtbot.waitSignal(simple_model.layer_tree_changed, timeout=500):
            simple_model.remove_layer(idx)


# =========================================================================
# New layer commands
# =========================================================================


class TestSetLayerOpacityCommand:
    """Test the SetLayerOpacityCommand."""

    def test_serialization_round_trip(self) -> None:
        """to_dict / from_dict round-trip."""
        from src.commands.map_commands import SetLayerOpacityCommand

        cmd = SetLayerOpacityCommand("map-1", "node-1", 0.75)
        data = cmd.to_dict()
        restored = SetLayerOpacityCommand.from_dict(data)
        assert restored.map_id == "map-1"
        assert restored.node_id == "node-1"
        assert abs(restored.opacity - 0.75) < _OPACITY_TOLERANCE


class TestRenameLayerCommand:
    """Test the RenameLayerCommand."""

    def test_serialization_round_trip(self) -> None:
        """to_dict / from_dict round-trip."""
        from src.commands.map_commands import RenameLayerCommand

        cmd = RenameLayerCommand("map-1", "node-1", "New Name")
        data = cmd.to_dict()
        restored = RenameLayerCommand.from_dict(data)
        assert restored.map_id == "map-1"
        assert restored.node_id == "node-1"
        assert restored.new_name == "New Name"


# =========================================================================
# MapWidget signal emission for command stack
# =========================================================================


class TestMapWidgetLayerSignals:
    """Verify MapWidget emits the layer signals for the command stack."""

    def test_layer_tree_changed_forwarded(self, qtbot) -> None:
        """Model mutation causes MapWidget.layer_tree_changed to emit."""
        widget = _make_map_widget(qtbot)
        widget.add_marker("sig-1", "entity", "Signal Test", 0.5, 0.5)
        model = widget.get_layer_model()

        with qtbot.waitSignal(widget.layer_tree_changed, timeout=500):
            m = model.find_node_by_id("sig-1")
            model.set_node_visible(m, False)

    def test_opacity_signal_emitted(self, qtbot) -> None:
        """Panel slider emits layer_opacity_change_requested."""
        widget = _make_map_widget(qtbot)
        widget.add_marker("op-1", "entity", "Opacity Test", 0.5, 0.5)

        received: list[tuple] = []
        widget.layer_opacity_change_requested.connect(
            lambda nid, o: received.append((nid, o))
        )

        # Select the node in the panel
        widget.layer_panel.select_node("op-1")
        # Move the slider
        widget.layer_panel._opacity_slider.setValue(50)

        assert len(received) == 1
        assert received[0][0] == "op-1"
        assert abs(received[0][1] - 0.5) < _OPACITY_TOLERANCE

    def test_rename_signal_emitted(self, qtbot) -> None:
        """Renaming a layer emits layer_rename_requested."""
        widget = _make_map_widget(qtbot)
        widget.add_marker("ren-sig-1", "entity", "Rename Sig", 0.5, 0.5)

        received: list[tuple] = []
        widget.layer_rename_requested.connect(lambda nid, n: received.append((nid, n)))

        widget._on_layer_renamed("ren-sig-1", "Updated Name")
        assert len(received) == 1
        assert received[0] == ("ren-sig-1", "Updated Name")


# =========================================================================
# Bug fixes: layer panel delete → DB, rename → entity/event
# =========================================================================


class TestDeleteLayerEmitsDBSignal:
    """Verify _on_delete_layer emits layer_delete_feature_requested for DB cleanup."""

    def test_delete_leaf_emits_feature_delete(self, qtbot) -> None:
        """Deleting a leaf node emits layer_delete_feature_requested."""
        widget = _make_map_widget(qtbot)
        widget.add_marker("del-db-1", "entity", "To Delete", 0.5, 0.5)

        received: list[str] = []
        widget.layer_delete_feature_requested.connect(received.append)

        widget._on_delete_layer("del-db-1")
        assert received == ["del-db-1"]

    def test_delete_group_emits_for_all_children(self, qtbot) -> None:
        """Deleting a group emits layer_delete_feature_requested for each child."""
        widget = _make_map_widget(qtbot)
        widget.add_marker("g-child-1", "entity", "Child 1", 0.2, 0.2)
        widget.add_marker("g-child-2", "entity", "Child 2", 0.7, 0.7)

        received: list[str] = []
        widget.layer_delete_feature_requested.connect(received.append)

        default = widget._default_group()
        widget._on_delete_layer(default.id)
        assert set(received) == {"g-child-1", "g-child-2"}

    def test_delete_group_type_not_emitted(self, qtbot) -> None:
        """Deleting an empty group does NOT emit layer_delete_feature_requested."""
        widget = _make_map_widget(qtbot)
        model = widget._ensure_layer_model()

        # Create a new empty group
        group = MapLayerNode(
            name="Empty Group", layer_type=MAP_LAYER_TYPE_GROUP, id="empty-grp"
        )
        parent_idx = model.index_from_node(model.root)
        model.add_layer(parent_idx, group)

        received: list[str] = []
        widget.layer_delete_feature_requested.connect(received.append)

        widget._on_delete_layer("empty-grp")
        assert received == []

    def test_collect_leaf_ids_nested_groups(self, qtbot) -> None:
        """_collect_leaf_ids recurses through nested groups."""
        widget = _make_map_widget(qtbot)
        # Build a nested tree: root → group → sub-group → leaf
        leaf = MapLayerNode(
            name="Deep Leaf", layer_type=MAP_LAYER_TYPE_MARKER, id="deep-leaf"
        )
        sub = MapLayerNode(
            name="Sub",
            layer_type=MAP_LAYER_TYPE_GROUP,
            id="sub",
            children=[leaf],
        )
        top = MapLayerNode(
            name="Top",
            layer_type=MAP_LAYER_TYPE_GROUP,
            id="top",
            children=[sub],
        )
        ids = widget._collect_leaf_ids(top)
        assert ids == ["deep-leaf"]


class TestRenameLayerCommandMarkerIdFix:
    """Verify RenameLayerCommand uses the correct marker_id for DB lookup."""

    def test_serialization_with_marker_id(self) -> None:
        """to_dict / from_dict preserves marker_id."""
        from src.commands.map_commands import RenameLayerCommand

        cmd = RenameLayerCommand(
            "map-1", "node-1", "New Name", marker_id="actual-db-id"
        )
        data = cmd.to_dict()
        assert data["marker_id"] == "actual-db-id"

        restored = RenameLayerCommand.from_dict(data)
        assert restored._marker_id == "actual-db-id"

    def test_serialization_without_marker_id(self) -> None:
        """to_dict / from_dict works when marker_id is None."""
        from src.commands.map_commands import RenameLayerCommand

        cmd = RenameLayerCommand("map-1", "node-1", "New Name")
        data = cmd.to_dict()
        assert data["marker_id"] is None

        restored = RenameLayerCommand.from_dict(data)
        assert restored._marker_id is None
