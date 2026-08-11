"""Regression coverage for temporal vector-feature validity."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QDialogButtonBox, QGraphicsItem, QGraphicsPixmapItem

from src.commands.layer_commands import UpdateLayerPropertiesCommand
from src.core.map import (
    MapLayerNode,
    TemporalValidityStatus,
    resolve_layer_temporal_validity,
)
from src.gui.dialogs.layer_properties_dialog import LayerPropertiesDialog
from src.gui.dialogs.temporal_validity_dialog import TemporalValidityDialog
from src.gui.widgets.map.map_graphics_view import MapGraphicsView
from src.gui.widgets.map.map_layer_model import MapLayerModel
from src.gui.widgets.map.map_layer_panel import MapLayerPanel


def _tree(*children: MapLayerNode) -> MapLayerNode:
    group = MapLayerNode(
        name="History",
        layer_type="group",
        id="group",
        children=list(children),
    )
    return MapLayerNode(name="Root", layer_type="group", id="root", children=[group])


def test_core_resolver_uses_half_open_interval_and_ancestor_bounds() -> None:
    feature = MapLayerNode(
        name="Ardent",
        layer_type="marker",
        id="ardent",
        start_date=600.0,
        end_date=634.25,
    )
    root = _tree(feature)

    before = resolve_layer_temporal_validity(root, feature.id, 599.9)
    assert before.status == TemporalValidityStatus.BEFORE_START
    assert resolve_layer_temporal_validity(root, feature.id, 600.0).valid
    assert resolve_layer_temporal_validity(root, feature.id, 634.2499).valid
    ended = resolve_layer_temporal_validity(root, feature.id, 634.25)
    assert ended.status == TemporalValidityStatus.AT_OR_AFTER_END

    root.children[0].end_date = 620.0
    inherited = resolve_layer_temporal_validity(root, feature.id, 620.0)
    assert not inherited.valid
    assert inherited.source_node_id == "group"


def test_ship_to_wreck_transition_has_no_overlap_or_gap() -> None:
    ship = MapLayerNode(
        name="MV Ardent",
        layer_type="marker",
        id="ship",
        end_date=634.25,
    )
    wreck = MapLayerNode(
        name="Wreck of the Ardent",
        layer_type="marker",
        id="wreck",
        start_date=634.25,
    )
    root = _tree(ship, wreck)
    assert resolve_layer_temporal_validity(root, ship.id, 634.2499).valid
    assert not resolve_layer_temporal_validity(root, wreck.id, 634.2499).valid
    assert not resolve_layer_temporal_validity(root, ship.id, 634.25).valid
    assert resolve_layer_temporal_validity(root, wreck.id, 634.25).valid


def test_core_resolver_ignores_raster_bounds() -> None:
    raster = MapLayerNode(
        name="Terrain",
        layer_type="raster",
        id="raster",
        start_date=100.0,
        end_date=200.0,
    )
    state = resolve_layer_temporal_validity(_tree(raster), raster.id, 300.0)
    assert not state.applicable
    assert state.valid


@pytest.mark.parametrize("layer_type", ["marker", "path", "region"])
def test_model_applies_identical_half_open_visibility_to_vectors(
    layer_type: str,
) -> None:
    node = MapLayerNode(
        name="Feature",
        layer_type=layer_type,
        id="feature",
        start_date=10.0,
        end_date=20.0,
    )
    model = MapLayerModel(_tree(node))
    assert model.compute_visibility(1.0, 10.0)[node.id]
    assert not model.compute_visibility(1.0, 20.0)[node.id]


def test_layer_property_command_rejects_empty_interval_before_mutation() -> None:
    node = MapLayerNode(name="Road", layer_type="path", start_date=1.0, end_date=2.0)
    with pytest.raises(ValueError, match="must be after"):
        UpdateLayerPropertiesCommand._apply(
            node,
            {"start_date": 5.0, "end_date": 5.0},
        )
    assert node.start_date == 1.0
    assert node.end_date == 2.0


def test_layer_property_command_preserves_omitted_fields() -> None:
    """Focused editors must not clear properties outside their scope."""
    node = MapLayerNode(
        name="Road",
        layer_type="path",
        start_date=1.0,
        end_date=2.0,
        attributes={"notes": "Old road", "zoom_basis": "fit_ratio"},
    )

    UpdateLayerPropertiesCommand._apply(node, {"opacity": 0.5})

    assert node.start_date == 1.0
    assert node.end_date == 2.0
    assert node.attributes["notes"] == "Old road"
    assert node.attributes["zoom_basis"] == "fit_ratio"


def _view_with_marker(qtbot) -> tuple[MapGraphicsView, MapLayerModel, str]:
    view = MapGraphicsView()
    qtbot.addWidget(view)
    image = QImage(100, 100, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.white)
    view.pixmap_item = QGraphicsPixmapItem(QPixmap.fromImage(image))
    view.graphics_scene.addItem(view.pixmap_item)
    view.coord_system.set_scene_rect(QRectF(0, 0, 100, 100))
    marker_id = "ardent"
    view.add_marker(marker_id, "entity", "Ardent", 0.5, 0.5)
    node = MapLayerNode(
        name="Ardent",
        layer_type="marker",
        id=marker_id,
        end_date=634.25,
    )
    model = MapLayerModel(_tree(node))
    view.set_layer_model(model)
    return view, model, marker_id


def test_view_combines_temporal_manual_zoom_and_ghost_visibility(qtbot) -> None:
    view, model, marker_id = _view_with_marker(qtbot)
    marker = view.markers[marker_id]
    node = model.find_node_by_id(marker_id)
    assert node is not None

    view.set_playhead_time(634.2499)
    assert marker.isVisible()
    view.set_playhead_time(634.25)
    assert not marker.isVisible()

    view.set_temporal_ghosts_visible(True)
    assert marker.isVisible()
    assert marker.is_temporal_ghost
    assert marker.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
    assert not marker.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable

    view.set_playhead_time(600.0)
    assert marker.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable
    view.set_playhead_time(634.25)

    model.set_node_visible(node, False)
    assert not marker.isVisible()
    model.set_node_visible(node, True)
    node.min_zoom = 10.0
    model.invalidate_cache()
    view._apply_effective_layer_visibility()
    assert not marker.isVisible()


def test_marker_opacity_composes_layer_future_and_ghost_factors(qtbot) -> None:
    view, model, marker_id = _view_with_marker(qtbot)
    marker = view.markers[marker_id]
    node = model.find_node_by_id(marker_id)
    assert node is not None
    model.set_node_opacity(node, 0.5)
    marker.set_temporal_state(is_future=True)
    view.set_playhead_time(634.25)
    view.set_temporal_ghosts_visible(True)
    assert marker.opacity() == pytest.approx(0.5 * 0.7 * 0.2)


def test_authoring_override_keeps_invalid_feature_visible(qtbot) -> None:
    view, _model, marker_id = _view_with_marker(qtbot)
    marker = view.markers[marker_id]
    view.set_playhead_time(700.0)
    assert not marker.isVisible()
    view.set_temporal_authoring_override(marker_id, True)
    assert marker.isVisible()
    assert not marker.is_temporal_ghost
    view.set_temporal_authoring_override(marker_id, False)
    assert not marker.isVisible()


def test_layer_panel_filters_outside_features_and_jumps_inside_range(qtbot) -> None:
    valid = MapLayerNode(name="Ship", layer_type="marker", id="ship")
    ended = MapLayerNode(
        name="Old Road",
        layer_type="path",
        id="road",
        start_date=10.0,
        end_date=20.0,
    )
    panel = MapLayerPanel()
    qtbot.addWidget(panel)
    model = MapLayerModel(_tree(valid, ended))
    panel.set_model(model)
    panel.set_playhead_time(25.0)
    panel.set_temporal_filter_enabled(True)

    proxy = panel.tree_view.model()
    assert proxy.rowCount() == 1  # ancestor group retained
    group_index = proxy.index(0, 0)
    assert proxy.rowCount(group_index) == 1

    ended_index = model.index_from_node(ended)
    tooltip = model.data(ended_index, Qt.ItemDataRole.ToolTipRole)
    assert "ended 20" in tooltip
    assert "Current playhead: 25" in tooltip

    with qtbot.waitSignal(panel.temporal_jump_requested) as blocker:
        panel.jump_to_valid_time("road")
    assert blocker.args == [19.0]


def test_temporal_dialog_rejects_equal_bounds(qtbot) -> None:
    node = MapLayerNode(name="Road", layer_type="path")
    dialog = TemporalValidityDialog(node, playhead_time=42.0)
    qtbot.addWidget(dialog)
    dialog._start_enabled.setChecked(True)
    dialog._end_enabled.setChecked(True)
    dialog._start.set_value(42.0)
    dialog._end.set_value(42.0)
    dialog._update_temporal_feedback()
    ok = dialog._buttons.button(QDialogButtonBox.StandardButton.Ok)
    assert ok is not None and not ok.isEnabled()


def test_temporal_dialog_use_playhead_preserves_exact_lore_float(qtbot) -> None:
    node = MapLayerNode(name="Site", layer_type="marker")
    dialog = TemporalValidityDialog(node, playhead_time=42.1234)
    qtbot.addWidget(dialog)
    dialog._copy_playhead(dialog._start_enabled, dialog._start)
    assert dialog.properties()["start_date"] == 42.1234


def test_properties_and_temporal_dialogs_have_distinct_scope(qtbot) -> None:
    node = MapLayerNode(
        name="Site",
        layer_type="marker",
        start_date=10.0,
        end_date=20.0,
    )
    properties_dialog = LayerPropertiesDialog(node)
    temporal_dialog = TemporalValidityDialog(node)
    qtbot.addWidget(properties_dialog)
    qtbot.addWidget(temporal_dialog)

    assert properties_dialog.windowTitle() == "Layer Properties"
    assert "start_date" not in properties_dialog.properties()
    assert "end_date" not in properties_dialog.properties()
    assert temporal_dialog.windowTitle() == "Temporal Validity — Site"
    assert temporal_dialog.properties() == {
        "start_date": 10.0,
        "end_date": 20.0,
    }


def test_layer_panel_temporal_editor_captures_two_playhead_dates(qtbot) -> None:
    node = MapLayerNode(name="Site", layer_type="marker", id="site")
    panel = MapLayerPanel()
    qtbot.addWidget(panel)
    panel.set_model(MapLayerModel(_tree(node)))
    panel.set_playhead_time(10.25)

    panel.edit_temporal_validity("site")
    dialog = panel._temporal_dialog
    assert dialog is not None
    assert not dialog.isModal()
    assert panel._properties_dialog is None
    dialog._copy_playhead(dialog._start_enabled, dialog._start)

    panel.set_playhead_time(20.75)
    dialog._copy_playhead(dialog._end_enabled, dialog._end)

    assert dialog.properties()["start_date"] == 10.25
    assert dialog.properties()["end_date"] == 20.75
    with qtbot.waitSignal(panel.layer_properties_changed) as blocker:
        dialog._accept_if_valid()
    assert blocker.args[0] == "site"
    assert blocker.args[1]["start_date"] == 10.25
    assert blocker.args[1]["end_date"] == 20.75


def test_layer_panel_switches_between_distinct_editors(qtbot) -> None:
    node = MapLayerNode(name="Site", layer_type="marker", id="site")
    panel = MapLayerPanel()
    qtbot.addWidget(panel)
    panel.set_model(MapLayerModel(_tree(node)))

    panel.edit_properties("site")
    assert panel._properties_dialog is not None
    assert panel._temporal_dialog is None

    panel.edit_temporal_validity("site")
    assert panel._properties_dialog is None
    assert panel._temporal_dialog is not None


def test_layer_model_refresh_preserves_selection_and_collapsed_groups(qtbot) -> None:
    first = MapLayerNode(name="Site", layer_type="marker", id="site")
    panel = MapLayerPanel()
    qtbot.addWidget(panel)
    first_model = MapLayerModel(_tree(first))
    panel.set_model(first_model)
    panel.select_node("site")
    first_group = first_model.find_node_by_id("group")
    assert first_group is not None
    first_group_index = panel._proxy_model.mapFromSource(
        first_model.index_from_node(first_group)
    )
    panel.tree_view.setExpanded(first_group_index, False)

    refreshed = MapLayerNode(
        name="Site",
        layer_type="marker",
        id="site",
        start_date=10.0,
    )
    refreshed_model = MapLayerModel(_tree(refreshed))
    panel.set_model(refreshed_model)
    refreshed_group = refreshed_model.find_node_by_id("group")
    assert refreshed_group is not None
    refreshed_group_index = panel._proxy_model.mapFromSource(
        refreshed_model.index_from_node(refreshed_group)
    )

    assert panel.selected_node_id == "site"
    assert not panel.tree_view.isExpanded(refreshed_group_index)
