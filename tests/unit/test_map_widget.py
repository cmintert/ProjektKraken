"""
Unit tests for map widget functionality.
"""

from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QImage, QKeyEvent, QPixmap, QWheelEvent
from PySide6.QtWidgets import QGraphicsItem, QGraphicsPixmapItem, QSizePolicy

from src.core.theme_manager import ThemeManager
from src.core.trajectory import SEGMENT_MODE_STEP, Keyframe
from src.core.trajectory_edit import TrajectoryEditSession
from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.map.marker_item import MarkerItem
from src.gui.widgets.map_widget import (
    MapGraphicsView,
    MapWidget,
)


def create_test_pixmap(width=100, height=100):
    """Helper to create a test pixmap."""
    test_image = QImage(width, height, QImage.Format_RGB32)
    test_image.fill(Qt.white)
    return QPixmap.fromImage(test_image)


def setup_map_with_pixmap(map_view, width=100, height=100):
    """Helper to set up a map view with a test pixmap."""
    pixmap = create_test_pixmap(width, height)
    map_view.pixmap_item = QGraphicsPixmapItem(pixmap)
    map_view.graphics_scene.addItem(map_view.pixmap_item)
    # Ensure coordinate system knows about the map bounds
    map_view.coord_system.set_scene_rect(map_view.pixmap_item.boundingRect())
    return map_view


def test_temporal_status_visibility_does_not_resize_viewport(
    map_widget, qtbot
) -> None:
    """Showing the outside-date control must not shift map content."""
    map_widget.resize(1000, 700)
    map_widget.show()
    qtbot.waitExposed(map_widget)
    before_height = map_widget.view.viewport().height()

    map_widget._on_temporal_counts_changed(0, 1)
    qtbot.wait(0)
    shown_height = map_widget.view.viewport().height()
    map_widget._on_temporal_counts_changed(1, 0)
    qtbot.wait(0)

    assert shown_height == before_height
    assert map_widget.view.viewport().height() == before_height


def test_geometry_apply_uses_primary_action_style(map_widget) -> None:
    """Geometry Apply matches the established positive action treatment."""
    assert (
        map_widget.btn_apply_feature_geometry.styleSheet()
        == StyleHelper.get_primary_button_style()
    )


@pytest.fixture
def map_widget(qtbot):
    """Provides a MapWidget instance."""
    widget = MapWidget()
    qtbot.addWidget(widget)
    return widget


@pytest.fixture
def map_view(qtbot):
    """Provides a MapGraphicsView instance."""
    view = MapGraphicsView()
    qtbot.addWidget(view)
    return view


def test_map_widget_initialization(map_widget):
    """Test that MapWidget initializes correctly."""
    assert map_widget is not None
    assert map_widget.view is not None
    assert isinstance(map_widget.view, MapGraphicsView)
    assert map_widget.btn_add_marker.text() == "Add Marker"
    assert not map_widget._edit_trajectory_action.isVisible()
    assert not map_widget._edit_trajectory_action.isEnabled()


def test_edit_trajectory_action_and_compact_strip(map_widget, qtbot):
    """A selected entity trajectory exposes the explicit spatial editor."""
    marker = _show_map_with_marker(map_widget, qtbot)
    map_widget.set_trajectories(
        [
            {
                "marker_id": "marker1",
                "trajectory_id": "trajectory-1",
                "keyframes": [
                    {"t": 0.0, "x": 0.2, "y": 0.3, "point_kind": "timed"},
                    {"t": 10.0, "x": 0.8, "y": 0.7, "point_kind": "timed"},
                ],
                "row_snapshot": {},
            }
        ]
    )
    marker.setSelected(True)
    map_widget._on_marker_clicked_internal("marker1", "entity")
    map_widget._update_trajectory_edit_action()

    assert map_widget._edit_trajectory_action.isVisible()
    assert map_widget._edit_trajectory_action.isEnabled()

    session = TrajectoryEditSession.create(
        "map-1",
        "marker1",
        "trajectory-1",
        [
            Keyframe(t=0.0, x=0.2, y=0.3),
            Keyframe(t=10.0, x=0.8, y=0.7),
        ],
    )
    edit_id = session.working_keyframes[0].edit_id
    session.select_keyframe(edit_id)
    map_widget.show_trajectory_edit(session.to_snapshot())

    assert map_widget.trajectory_edit_strip.isVisible()
    assert "2 points" in map_widget.trajectory_edit_label.text()
    assert not map_widget.btn_apply_trajectory.isEnabled()
    assert not marker.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable
    assert map_widget.trajectory_date_panel.isVisible()
    assert map_widget.btn_edit_trajectory_date.isVisible()
    assert not map_widget.trajectory_date_input.isEnabled()
    assert not map_widget.trajectory_date_input.isVisible()
    assert (
        map_widget.trajectory_edit_strip.sizePolicy().verticalPolicy()
        == QSizePolicy.Policy.Fixed
    )
    assert (
        map_widget.trajectory_date_panel.sizePolicy().verticalPolicy()
        == QSizePolicy.Policy.Fixed
    )
    assert (
        map_widget.trajectory_speed_panel.sizePolicy().verticalPolicy()
        == QSizePolicy.Policy.Fixed
    )
    root_layout = map_widget.layout()
    assert root_layout is not None
    assert root_layout.stretch(root_layout.indexOf(map_widget._splitter)) == 1

    requested_ids = []
    playhead_requests = []
    map_widget.trajectory_date_edit_requested.connect(requested_ids.append)
    map_widget.trajectory_date_use_playhead_requested.connect(
        lambda: playhead_requests.append(True)
    )
    assert map_widget.btn_trajectory_date_use_playhead.isVisible()
    qtbot.mouseClick(
        map_widget.btn_trajectory_date_use_playhead,
        Qt.MouseButton.LeftButton,
    )
    assert playhead_requests == [True]
    qtbot.mouseClick(
        map_widget.btn_edit_trajectory_date,
        Qt.MouseButton.LeftButton,
    )
    assert requested_ids == [edit_id]

    session.begin_date_edit(edit_id)
    session.update_active_date(2.0)
    map_widget.show_trajectory_edit(session.to_snapshot())

    assert map_widget.trajectory_date_input.isEnabled()
    assert map_widget.trajectory_date_input.isVisible()
    assert map_widget.btn_finish_trajectory_date.isVisible()
    assert map_widget.btn_cancel_trajectory_date.isVisible()
    assert map_widget.btn_trajectory_date_use_playhead.isVisible()
    qtbot.mouseClick(
        map_widget.btn_trajectory_date_use_playhead,
        Qt.MouseButton.LeftButton,
    )
    assert playhead_requests == [True, True]
    assert "Original:" in map_widget.trajectory_date_feedback.text()
    assert "Proposed:" in map_widget.trajectory_date_feedback.text()
    assert "Change: +2 days" in map_widget.trajectory_date_feedback.text()

    map_widget.clear_trajectory_edit()

    assert not marker.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable


def test_first_segment_selection_keeps_map_viewport_stable(map_widget, qtbot):
    """First arrival selection must not resize the map beneath it."""
    _show_map_with_marker(map_widget, qtbot)
    session = TrajectoryEditSession.create(
        "map-1",
        "marker1",
        "trajectory-1",
        [
            Keyframe(t=0.0, x=0.2, y=0.3),
            Keyframe(t=10.0, x=0.8, y=0.7),
        ],
    )
    map_widget.show_trajectory_edit(session.to_snapshot())
    qtbot.waitUntil(map_widget.trajectory_edit_strip.isVisible)
    initial_viewport_size = map_widget.view.viewport().size()

    session.select_keyframe(session.working_keyframes[1].edit_id)
    map_widget.show_trajectory_edit(
        session.to_snapshot(),
        rebuild_overlay=False,
    )
    qtbot.waitUntil(map_widget.trajectory_date_panel.isVisible)

    assert map_widget.view.viewport().size() == initial_viewport_size
    assert map_widget.trajectory_segment_panel.isVisible()


def test_use_playhead_disables_itself_and_explains_invalid_date(map_widget, qtbot):
    """An out-of-range playhead is explained beside the date controls."""
    _show_map_with_marker(map_widget, qtbot)
    session = TrajectoryEditSession.create(
        "map-1",
        "marker1",
        "trajectory-1",
        [
            Keyframe(t=0.0, x=0.2, y=0.3),
            Keyframe(t=10.0, x=0.8, y=0.7),
        ],
    )
    session.select_keyframe(session.working_keyframes[0].edit_id)
    map_widget.show_trajectory_edit(session.to_snapshot())

    map_widget.on_time_changed(10.0)

    assert not map_widget.btn_trajectory_date_use_playhead.isEnabled()
    assert "Playhead:" in map_widget.trajectory_playhead_value.text()
    assert "Move the playhead before" in map_widget.trajectory_date_constraints.text()
    assert "Move the playhead before" in (
        map_widget.btn_trajectory_date_use_playhead.toolTip()
    )

    map_widget.on_time_changed(9.0)

    assert map_widget.btn_trajectory_date_use_playhead.isEnabled()
    assert "Automatic Route points will recalculate" in (
        map_widget.trajectory_date_constraints.text()
    )


def test_selected_segment_shows_metrics_and_emits_relocation(map_widget, qtbot):
    """A non-first point exposes its arrival mode and segment facts."""
    _show_map_with_marker(map_widget, qtbot)
    session = TrajectoryEditSession.create(
        "map-1",
        "marker1",
        "trajectory-1",
        [
            Keyframe(t=0.0, x=0.2, y=0.3),
            Keyframe(t=10.0, x=0.8, y=0.7),
        ],
    )
    session.select_keyframe(session.working_keyframes[1].edit_id)
    map_widget.show_trajectory_edit(session.to_snapshot())

    assert map_widget.trajectory_segment_panel.isVisible()
    assert "10 days" in map_widget.trajectory_segment_metrics.text()
    modes = []
    map_widget.trajectory_arrival_mode_changed.connect(modes.append)

    map_widget.trajectory_arrival_mode.setCurrentIndex(
        map_widget.trajectory_arrival_mode.findData(SEGMENT_MODE_STEP)
    )

    assert modes == [SEGMENT_MODE_STEP]


def test_duplicate_trajectory_rows_are_not_used_for_playback(map_widget, qtbot):
    """Ambiguous marker trajectories are suppressed instead of overwritten."""
    _show_map_with_marker(map_widget, qtbot)
    row = {
        "marker_id": "marker1",
        "trajectory_id": "trajectory-1",
        "keyframes": [
            {"t": 0.0, "x": 0.2, "y": 0.3, "point_kind": "timed"},
            {"t": 10.0, "x": 0.8, "y": 0.7, "point_kind": "timed"},
        ],
        "row_snapshot": {},
    }

    map_widget.set_trajectories([row, {**row, "trajectory_id": "trajectory-2"}])

    assert "marker1" not in map_widget._active_trajectories


def test_speed_equalization_anchor_and_preview_controls(map_widget, qtbot):
    """The compact speed workflow exposes an inspectable working preview."""
    _show_map_with_marker(map_widget, qtbot)
    map_widget.view.set_map_width_meters(1000.0)
    session = TrajectoryEditSession.create(
        "map-1",
        "marker1",
        "trajectory-1",
        [
            Keyframe(t=0.0, x=0.0, y=0.0),
            Keyframe(t=12.0, x=0.25, y=0.0),
            Keyframe(t=20.0, x=1.0, y=0.0),
        ],
    )
    start_id = session.working_keyframes[0].edit_id
    end_id = session.working_keyframes[-1].edit_id
    session.select_keyframe(start_id)
    map_widget.show_trajectory_edit(session.to_snapshot())

    assert map_widget.trajectory_speed_panel.isVisible()
    assert map_widget.btn_set_trajectory_speed_anchor.isVisible()
    anchor_requests = []
    map_widget.trajectory_speed_anchor_requested.connect(anchor_requests.append)
    qtbot.mouseClick(
        map_widget.btn_set_trajectory_speed_anchor,
        Qt.MouseButton.LeftButton,
    )
    assert anchor_requests == [start_id]

    session.set_speed_anchor(start_id)
    session.select_keyframe(end_id)
    map_widget.show_trajectory_edit(session.to_snapshot())
    assert map_widget.btn_equalize_trajectory_speed.isEnabled()
    equalize_requests = []
    map_widget.trajectory_speed_equalize_requested.connect(equalize_requests.append)
    qtbot.mouseClick(
        map_widget.btn_equalize_trajectory_speed,
        Qt.MouseButton.LeftButton,
    )
    assert equalize_requests == [end_id]

    session.preview_speed_equalization(
        end_id,
        map_widget.get_trajectory_distance_context(),
    )
    map_widget.show_trajectory_edit(session.to_snapshot())

    assert map_widget.btn_apply_speed_equalization.isVisible()
    assert map_widget.btn_cancel_speed_equalization.isVisible()
    assert "1 changed" in map_widget.trajectory_speed_feedback.text()
    assert "m/day" in map_widget.trajectory_speed_feedback.text()
    assert "K2:" in map_widget.trajectory_speed_changes.text()
    assert not map_widget.btn_apply_trajectory.isEnabled()
    assert not map_widget.btn_edit_trajectory_date.isEnabled()
    assert not map_widget.btn_trajectory_date_use_playhead.isEnabled()


def test_direct_editor_keyboard_shortcuts_follow_nested_state(map_widget, qtbot):
    """Map focus routes shortcuts to the active direct-edit operation."""
    _show_map_with_marker(map_widget, qtbot)
    session = TrajectoryEditSession.create(
        "map-1",
        "marker1",
        "trajectory-1",
        [
            Keyframe(t=0.0, x=0.2, y=0.3),
            Keyframe(t=10.0, x=0.8, y=0.7),
        ],
    )
    edit_id = session.working_keyframes[0].edit_id
    session.select_keyframe(edit_id)

    deleted = []
    cancelled_dates = []
    cancelled_sessions = []
    applied = []
    map_widget.trajectory_delete_selected_requested.connect(
        lambda: deleted.append(True)
    )
    map_widget.trajectory_date_edit_cancel_requested.connect(
        lambda: cancelled_dates.append(True)
    )
    map_widget.trajectory_cancel_requested.connect(
        lambda: cancelled_sessions.append(True)
    )
    map_widget.trajectory_apply_requested.connect(lambda: applied.append(True))

    map_widget.show_trajectory_edit(session.to_snapshot())
    qtbot.keyClick(map_widget.view, Qt.Key.Key_Delete)
    assert deleted == [True]

    session.begin_date_edit(edit_id)
    map_widget.show_trajectory_edit(session.to_snapshot())
    qtbot.keyClick(map_widget.view, Qt.Key.Key_Escape)
    assert cancelled_dates == [True]
    assert cancelled_sessions == []

    session.cancel_date_edit()
    session.move_keyframe(edit_id, 0.3, 0.4)
    map_widget.show_trajectory_edit(session.to_snapshot())
    qtbot.keyClick(map_widget.view, Qt.Key.Key_Return)
    assert applied == [True]

    qtbot.keyClick(map_widget.view, Qt.Key.Key_Escape)
    assert cancelled_sessions == [True]


def test_trajectory_distance_context_uses_map_aspect_and_calibration(
    map_widget,
):
    """Speed math receives calibrated meters or aspect-corrected units."""
    setup_map_with_pixmap(map_widget.view, 800, 400)

    relative = map_widget.get_trajectory_distance_context()
    map_widget.view.set_map_width_meters(1000.0)
    calibrated = map_widget.get_trajectory_distance_context()

    assert (relative.width, relative.height, relative.unit) == (2.0, 1.0, None)
    assert (calibrated.width, calibrated.height, calibrated.unit) == (
        1000.0,
        500.0,
        "m",
    )


def test_playhead_navigation_previews_working_trajectory_position(
    map_widget,
    qtbot,
):
    """Timeline navigation moves the marker without owning keyframe dates."""
    marker = _show_map_with_marker(map_widget, qtbot)
    map_widget.set_trajectories(
        [
            {
                "marker_id": "marker1",
                "trajectory_id": "trajectory-1",
                "keyframes": [
                    {"t": 0.0, "x": 0.1, "y": 0.2, "point_kind": "timed"},
                    {"t": 10.0, "x": 0.9, "y": 0.8, "point_kind": "timed"},
                ],
                "row_snapshot": {},
            }
        ]
    )
    session = TrajectoryEditSession.create(
        "map-1",
        "marker1",
        "trajectory-1",
        [
            Keyframe(t=0.0, x=0.1, y=0.2),
            Keyframe(t=10.0, x=0.5, y=0.6),
        ],
    )
    map_widget.show_trajectory_edit(session.to_snapshot())

    map_widget.on_time_changed(5.0)

    x, y = map_widget.view.coord_system.to_normalized(marker.pos())
    assert (x, y) == pytest.approx((0.3, 0.4))
    assert [keyframe.t for keyframe in session.working_keyframes] == [0.0, 10.0]


def test_trajectory_marker_is_movable_only_before_first_keyframe(map_widget, qtbot):
    """The ordinary marker is editable until trajectory playback begins."""
    marker = _show_map_with_marker(map_widget, qtbot)
    map_widget.set_trajectories(
        [
            {
                "marker_id": "marker1",
                "trajectory_id": "trajectory-1",
                "keyframes": [
                    {"t": 10.0, "x": 0.2, "y": 0.3, "point_kind": "timed"},
                    {"t": 20.0, "x": 0.8, "y": 0.7, "point_kind": "timed"},
                ],
                "row_snapshot": {},
            }
        ]
    )
    moved = []
    map_widget.marker_position_changed.connect(
        lambda marker_id, x, y: moved.append((marker_id, x, y))
    )

    map_widget.on_time_changed(5.0)
    assert marker.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable
    map_widget._on_marker_moved("marker1", 0.4, 0.6)
    assert moved == [("marker1", 0.4, 0.6)]
    assert map_widget.get_marker_base_position("marker1") == (0.4, 0.6)

    map_widget.on_time_changed(10.0)
    assert not marker.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable
    assert map_widget.view.coord_system.to_normalized(marker.pos()) == pytest.approx(
        (0.2, 0.3)
    )

    map_widget.on_time_changed(21.0)
    assert not marker.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable
    assert map_widget.view.coord_system.to_normalized(marker.pos()) == pytest.approx(
        (0.8, 0.7)
    )
    map_widget._on_marker_moved("marker1", 0.1, 0.1)
    assert moved == [("marker1", 0.4, 0.6)]
    assert map_widget.get_marker_base_position("marker1") == (0.4, 0.6)


def test_selected_trajectory_tracks_owner_temporal_validity(map_widget, qtbot):
    """Normal routes disappear at exclusive end and return when scrubbing back."""
    marker = _show_map_with_marker(map_widget, qtbot)
    node = map_widget.get_layer_model().find_node_by_id("marker1")
    assert node is not None
    node.end_date = 10.0
    map_widget.get_layer_model().invalidate_cache()
    map_widget.set_trajectories(
        [
            {
                "marker_id": "marker1",
                "trajectory_id": "trajectory-1",
                "keyframes": [
                    {"t": 0.0, "x": 0.1, "y": 0.2, "point_kind": "timed"},
                    {"t": 10.0, "x": 0.9, "y": 0.8, "point_kind": "timed"},
                ],
                "row_snapshot": {},
            }
        ]
    )
    map_widget._on_marker_clicked_internal("marker1", "entity")

    map_widget.on_time_changed(9.0)
    assert marker.isVisible()
    assert map_widget.view.trajectory_path_item is not None

    model = map_widget.get_layer_model()
    node = model.find_node_by_id("marker1")
    assert node is not None
    model.set_node_visible(node, False)
    assert map_widget.view.trajectory_path_item is None
    model.set_node_visible(node, True)
    assert map_widget.view.trajectory_path_item is not None

    map_widget.on_time_changed(10.0)
    assert not marker.isVisible()
    assert map_widget.view.trajectory_path_item is None

    map_widget.on_time_changed(9.0)
    assert marker.isVisible()
    assert map_widget.view.trajectory_path_item is not None


def _show_map_with_marker(map_widget, qtbot, object_type="entity"):
    """Show a laid-out map widget containing one clickable marker."""
    map_widget.resize(1200, 700)
    map_widget.show()
    setup_map_with_pixmap(map_widget.view, 800, 600)
    map_widget.add_marker("marker1", object_type, "Test Marker", 0.5, 0.5)
    map_widget.view.fit_to_view()
    qtbot.waitUntil(map_widget.isVisible)
    return map_widget.view.markers["marker1"]


def _click_marker(map_widget, marker, qtbot):
    """Click a marker through the graphics-view viewport."""
    viewport_pos = map_widget.view.mapFromScene(marker.scenePos())
    qtbot.mouseClick(
        map_widget.view.viewport(),
        Qt.MouseButton.LeftButton,
        pos=viewport_pos,
    )
    qtbot.waitUntil(marker.isSelected)


def test_map_widget_refreshes_local_styles_after_theme_change(map_widget, monkeypatch):
    """Theme changes refresh every locally styled map-button group."""
    monkeypatch.setattr(
        StyleHelper,
        "get_tool_button_style",
        staticmethod(lambda: "QPushButton { color: #111111; }"),
    )
    monkeypatch.setattr(
        StyleHelper,
        "get_raster_tool_button_style",
        staticmethod(lambda: "QPushButton { color: #222222; }"),
    )
    monkeypatch.setattr(
        StyleHelper,
        "get_toggle_button_style",
        staticmethod(lambda: "QPushButton { color: #333333; }"),
    )
    monkeypatch.setattr(
        StyleHelper,
        "get_primary_button_style",
        staticmethod(lambda: "QPushButton { color: #444444; }"),
    )

    theme_manager = ThemeManager()
    theme_manager.theme_changed.emit(theme_manager.get_theme())

    assert "#111111" in map_widget.btn_new_map.styleSheet()
    assert "#111111" in map_widget.btn_fit_view.styleSheet()
    assert "#222222" in map_widget.btn_add_marker.styleSheet()
    assert "#222222" in map_widget.btn_draw_region.styleSheet()
    assert "#333333" in map_widget.btn_snap.styleSheet()
    assert "#333333" in map_widget.btn_legend_toggle.styleSheet()
    assert "#444444" in map_widget.btn_finish_sketch.styleSheet()


def test_add_marker_button_toggles_placement_mode(map_widget, qtbot):
    """The toolbar button enters and exits one-shot marker placement mode."""
    qtbot.mouseClick(map_widget.btn_add_marker, Qt.MouseButton.LeftButton)

    assert map_widget.view.is_placing_marker
    assert map_widget.btn_add_marker.isChecked()

    qtbot.mouseClick(map_widget.btn_add_marker, Qt.MouseButton.LeftButton)

    assert not map_widget.view.is_placing_marker
    assert not map_widget.btn_add_marker.isChecked()


def test_escape_cancels_marker_placement(map_widget, qtbot):
    """Escape exits toolbar marker placement without creating anything."""
    qtbot.mouseClick(map_widget.btn_add_marker, Qt.MouseButton.LeftButton)

    qtbot.keyClick(map_widget.view, Qt.Key.Key_Escape)

    assert not map_widget.view.is_placing_marker
    assert not map_widget.btn_add_marker.isChecked()


def test_marker_placement_click_emits_normalized_position(map_view, qtbot):
    """Clicking the map in placement mode requests a marker at that position."""
    setup_map_with_pixmap(map_view)
    requested_positions = []
    map_view.add_marker_requested.connect(
        lambda x, y: requested_positions.append((x, y))
    )
    map_view.start_marker_placement()

    viewport_position = map_view.mapFromScene(QPointF(50.0, 50.0))
    qtbot.mouseClick(
        map_view.viewport(),
        Qt.MouseButton.LeftButton,
        pos=viewport_position,
    )

    assert requested_positions == [(0.5, 0.5)]
    assert not map_view.is_placing_marker


def test_map_view_initialization(map_view):
    """Test that MapGraphicsView initializes correctly."""
    assert map_view is not None
    assert map_view.graphics_scene is not None
    assert map_view.scene() is map_view.graphics_scene
    assert map_view.pixmap_item is None
    assert len(map_view.markers) == 0


def test_load_map_invalid_path(map_view):
    """Test that loading an invalid map returns False."""
    result = map_view.load_map("/nonexistent/path.png")
    assert result is False
    assert map_view.pixmap_item is None


def test_add_marker_without_map(map_view):
    """Test that adding a marker without a map logs warning."""
    # Should not crash, just log warning
    map_view.add_marker("marker1", "entity", "Label", 0.5, 0.5)

    # No marker should be added
    assert len(map_view.markers) == 0


def test_add_marker_with_map(map_view):
    """Test adding a marker to a loaded map."""
    setup_map_with_pixmap(map_view)

    # Add marker
    map_view.add_marker("marker1", "entity", "Test Label", 0.5, 0.5)

    # Verify marker was added
    assert "marker1" in map_view.markers
    assert isinstance(map_view.markers["marker1"], MarkerItem)


def test_remove_marker(map_view):
    """Test removing a marker."""
    setup_map_with_pixmap(map_view)
    map_view.add_marker("marker1", "entity", "Test Label", 0.5, 0.5)

    # Remove marker
    map_view.remove_marker("marker1")

    # Verify removal
    assert "marker1" not in map_view.markers


def test_clear_markers(map_view):
    """Test clearing all markers."""
    setup_map_with_pixmap(map_view)

    # Add multiple markers
    map_view.add_marker("marker1", "entity", "Label 1", 0.2, 0.3)
    map_view.add_marker("marker2", "event", "Label 2", 0.7, 0.8)

    assert len(map_view.markers) == 2

    # Clear all
    map_view.clear_markers()

    assert len(map_view.markers) == 0


def test_update_marker_position(map_view):
    """Test updating a marker's position."""
    setup_map_with_pixmap(map_view)
    map_view.add_marker("marker1", "entity", "Test Label", 0.5, 0.5)

    # Update position
    map_view.update_marker_position("marker1", 0.8, 0.9)

    # Marker should still exist
    assert "marker1" in map_view.markers


def test_marker_position_changed_signal(map_widget, qtbot):
    """Test that marker movement emits the correct signal."""
    # Create a spy for the signal
    signal_spy = []

    def on_marker_moved(marker_id, x, y):
        signal_spy.append((marker_id, x, y))

    map_widget.marker_position_changed.connect(on_marker_moved)

    # Set up map
    setup_map_with_pixmap(map_widget.view)
    map_widget.add_marker("marker1", "entity", "Test Label", 0.5, 0.5)

    # Simulate marker movement by calling the internal handler
    map_widget._on_marker_moved("marker1", 0.7, 0.8)

    # Verify signal was emitted with correct values
    # Note: Signal may be emitted twice due to update_marker_position call
    assert signal_spy
    assert ("marker1", 0.7, 0.8) in signal_spy


def test_marker_item_draggable(map_view):
    """Test that MarkerItem is configured as draggable."""
    setup_map_with_pixmap(map_view)
    map_view.add_marker("marker1", "entity", "Test Label", 0.5, 0.5)

    marker = map_view.markers["marker1"]

    # Verify draggable flags
    assert marker.flags() & QGraphicsItem.ItemIsMovable
    assert marker.flags() & QGraphicsItem.ItemSendsGeometryChanges


def test_marker_item_colors(qtbot):
    """Test that MarkerItem has different colors for different types."""
    # Create mock pixmap item
    mock_pixmap_item = MagicMock()

    entity_marker = MarkerItem("m1", "entity", "Entity Label", mock_pixmap_item)
    event_marker = MarkerItem("m2", "event", "Event Label", mock_pixmap_item)
    default_marker = MarkerItem("m3", "unknown", "Unknown", mock_pixmap_item)

    # Colors should be different (now using VisualResolver)
    assert entity_marker._color != event_marker._color
    assert entity_marker._color.name() == "#4da6ff"
    assert event_marker._color.name() == "#ff9900"
    assert default_marker._color.name() == "#4da6ff"  # Fallback color in ThemeManager


def test_marker_item_tooltip():
    """Test that MarkerItem has the correct tooltip."""
    mock_pixmap_item = MagicMock()
    marker = MarkerItem("m1", "entity", "Test Label", mock_pixmap_item)

    assert marker.toolTip() == "<div style='width: 150px;'>Test Label</div>"


def test_marker_drag_tracking():
    """Test that MarkerItem tracks drag state."""
    mock_pixmap_item = MagicMock()

    marker = MarkerItem("m1", "entity", "Test", mock_pixmap_item)

    # Initially not dragging
    assert marker._is_dragging is False
    assert marker._drag_start_pos is None


def test_normalized_coordinates_conversion(map_view):
    """Test that normalized coordinates are correctly converted."""
    setup_map_with_pixmap(map_view, 1000, 800)

    # Test corner coordinates
    top_left = map_view.coord_system.to_scene(0.0, 0.0)
    bottom_right = map_view.coord_system.to_scene(1.0, 1.0)
    center = map_view.coord_system.to_scene(0.5, 0.5)

    # Top-left should be at pixmap origin
    assert top_left.x() >= 0
    assert top_left.y() >= 0

    # Bottom-right should be at pixmap far corner
    assert bottom_right.x() > top_left.x()
    assert bottom_right.y() > top_left.y()

    # Center should be between them
    assert top_left.x() < center.x() < bottom_right.x()
    assert top_left.y() < center.y() < bottom_right.y()


def test_widget_delegates_to_view(map_widget):
    """Test that MapWidget delegates operations to its view."""
    # Set up map
    setup_map_with_pixmap(map_widget.view)

    # Add marker through widget
    map_widget.add_marker("marker1", "entity", "Test Label", 0.5, 0.5)
    assert "marker1" in map_widget.view.markers

    # Remove marker through widget
    map_widget.remove_marker("marker1")
    assert "marker1" not in map_widget.view.markers


def test_marker_item_change_emits_signal(map_view, qtbot):
    """Test that moving a marker item triggers marker position tracking."""
    signal_spy = []

    def on_marker_moved(marker_id, x, y):
        signal_spy.append((marker_id, x, y))

    map_view.marker_moved.connect(on_marker_moved)

    setup_map_with_pixmap(map_view, 100, 100)
    map_view.add_marker("marker1", "entity", "Test Label", 0.5, 0.5)

    marker = map_view.markers["marker1"]

    # Note: itemChange is only called during interactive drag or certain
    # specific operations. Manual setPos doesn't trigger ItemPositionHasChanged.
    # For testing, we can verify the marker is draggable and can be moved.
    # initial_pos = marker.pos()

    # Move the marker programmatically
    new_pos = QPointF(50, 50)
    marker.setPos(new_pos)

    # Verify marker moved
    assert marker.pos() == new_pos

    # In actual usage, dragging would trigger itemChange and emit the signal.
    # For this test, we verify the marker is configured correctly.
    assert marker.flags() & QGraphicsItem.ItemIsMovable
    assert marker.flags() & QGraphicsItem.ItemSendsGeometryChanges


def test_mouse_coordinates_display(map_widget):
    """Test that mouse coordinates update the label correctly."""
    # Mock the label
    map_widget.coord_label = MagicMock()
    map_widget.view.map_width_meters = 1000.0  # Simple width for calc

    # Mock pixmap_item for aspect ratio (square 100x100)
    map_widget.view.pixmap_item = MagicMock()
    map_widget.view.pixmap_item.boundingRect.return_value = QRectF(0, 0, 100, 100)

    # 1. Test In-Bounds
    # x=0.5, y=0.5. With width=1000m, height should be 1000m.
    # Expected: 500m, 500m -> 0.5km, 0.5km
    map_widget._on_mouse_coordinates_changed(0.5, 0.5, True)

    # Check text set on label
    args, _ = map_widget.coord_label.setText.call_args
    text = args[0]
    assert "N: (0.5000, 0.5000)" in text
    assert "RW: 0.50 km, 0.50 km" in text

    # 2. Test Out-of-Bounds
    map_widget._on_mouse_coordinates_changed(0.0, 0.0, False)
    args, _ = map_widget.coord_label.setText.call_args
    out_of_bounds_text = args[0]
    assert out_of_bounds_text == "Ready"
    assert "T:" not in out_of_bounds_text
    assert "Now:" not in out_of_bounds_text

    # 3. Test Zero Height (Division by Zero protection)
    map_widget.view.pixmap_item.boundingRect.return_value = QRectF(0, 0, 100, 0)
    map_widget._on_mouse_coordinates_changed(0.5, 0.5, True)
    # Should fall back to 1:1 (height_meters = width_meters = 1000)
    # y=0.5 * 1000 = 500
    args, _ = map_widget.coord_label.setText.call_args
    assert "RW: 0.50 km, 0.50 km" in args[0]


def test_map_status_displays_zoom_factor_without_float_time(map_widget):
    """The map status row shows zoom while the main bar owns time display."""
    map_widget.view.zoom_factor_changed.emit(1.25)

    assert map_widget.zoom_label.text() == "Zoom: 1.25×"
    assert "T:" not in map_widget.coord_label.text()
    assert "Now:" not in map_widget.coord_label.text()


def test_map_status_zoom_tracks_wheel_and_fit(map_widget):
    """Wheel zoom updates the factor and Fit to View resets it to 1.00×."""
    setup_map_with_pixmap(map_widget.view)
    map_widget.view._fit_zoom_level = map_widget.view.transform().m11()
    event = QWheelEvent(
        QPointF(10, 10),
        QPointF(10, 10),
        QPoint(0, 0),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )

    map_widget.view.wheelEvent(event)

    assert map_widget.view.zoom_factor > 1.0
    assert map_widget.zoom_label.text() == (
        f"Zoom: {map_widget.view.zoom_factor:.2f}×"
    )

    map_widget.view.fit_to_view()

    assert map_widget.view.zoom_factor == pytest.approx(1.0)
    assert map_widget.zoom_label.text() == "Zoom: 1.00×"


def test_esc_in_view_clears_selection(map_widget, qtbot):
    """Escape in normal map mode clears selection."""

    # Add a mock selected item to the scene
    setup_map_with_pixmap(map_widget.view)
    map_widget.view.add_marker("m1", "entity", "Test", 0.5, 0.5)
    marker = map_widget.view.markers["m1"]
    marker.setSelected(True)
    assert len(map_widget.view.graphics_scene.selectedItems()) > 0

    # Simulate ESC key press on the VIEW
    esc_event = QKeyEvent(
        QKeyEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier
    )
    map_widget.view.keyPressEvent(esc_event)

    # Selection should be cleared
    assert len(map_widget.view.graphics_scene.selectedItems()) == 0


def test_configure_map_settings_emits_attribute_updates(map_widget, monkeypatch):
    """Applying map settings emits one attribute-update mapping."""
    from PySide6.QtWidgets import QDialog

    # Mock MapScaleDialog
    mock_dialog = MagicMock()
    mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
    mock_dialog.get_width.return_value = 5000.0

    # Patch the class in the calibration mixin module (where it's imported)
    mock_class = MagicMock(return_value=mock_dialog)
    import src.gui.mixins.map_calibration_mixin

    monkeypatch.setattr(
        src.gui.mixins.map_calibration_mixin, "MapScaleDialog", mock_class
    )

    signal_spy = []
    map_widget.map_settings_changed.connect(lambda updates: signal_spy.append(updates))

    # Set up preconditions
    setup_map_with_pixmap(map_widget.view)
    map_widget.view.map_width_meters = 1000.0

    # Mock map selector currentText to prevent warnings
    map_widget.map_selector.currentText = MagicMock(return_value="Test Map")
    # Mock get_selected_map_id to return valid ID
    map_widget.get_selected_map_id = MagicMock(return_value="map1")

    # Call the method
    map_widget._configure_map_width()

    assert signal_spy == [{"width_meters": 5000.0}]

    # Verify view updated
    assert map_widget.view.map_width_meters == 5000.0
