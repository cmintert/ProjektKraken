"""Readable node-editor wire geometry and stable branch presentation."""

from unittest.mock import Mock

import pytest
from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import (
    QImage,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QTransform,
)

from src.gui.widgets.timeline.wire_router import Wire, route_wires

pytestmark = pytest.mark.ci_fast


def stroke(path):
    stroker = QPainterPathStroker()
    stroker.setWidth(3)
    return stroker.createStroke(path)


def assert_side_tangents(path, wire):
    assert not path.isEmpty()
    assert path.pointAtPercent(0) == wire.source
    assert path.pointAtPercent(1) == wire.target
    # Curved as well as straight stubs must depart and arrive horizontally.
    assert path.elementAt(1).y == wire.source.y()
    last_control = path.elementAt(path.elementCount() - 2)
    assert last_control.y == wire.target.y()
    assert sum(path.elementAt(i).isMoveTo() for i in range(path.elementCount())) == 1


def test_clear_route_is_one_smooth_cubic():
    wire = Wire(QPointF(10, 20), QPointF(300, 140), 1, -1)
    path = route_wires([wire], [])[0]
    assert path.elementCount() == 4
    assert_side_tangents(path, wire)
    samples = [path.pointAtPercent(i / 100) for i in range(101)]
    assert all(
        first.x() <= second.x() and first.y() <= second.y()
        for first, second in zip(samples, samples[1:])
    )


@pytest.mark.parametrize("cluster", [False, True])
def test_forward_blocker_gets_broad_cubic_bypass_without_overshoot(cluster):
    wire = Wire(QPointF(0, 100), QPointF(600, 100), 1, -1)
    obstacles = [QRectF(200, 75, 100, 50)]
    if cluster:
        obstacles.extend([QRectF(315, 90, 70, 70), QRectF(400, 60, 50, 60)])
    path = route_wires([wire], obstacles)[0]
    assert_side_tangents(path, wire)
    assert not any(stroke(path).intersects(rect) for rect in obstacles)
    # A broad, continuously tangent cubic bypass, rather than rounded elbows.
    assert path.elementCount() <= 13
    assert all(not path.elementAt(i).isLineTo() for i in range(1, path.elementCount()))
    samples = [path.pointAtPercent(i / 400) for i in range(401)]
    assert all(a.x() <= b.x() for a, b in zip(samples, samples[1:]))
    assert path.boundingRect().left() >= wire.source.x()
    assert path.boundingRect().right() <= wire.target.x()
    changes = [b.y() - a.y() for a, b in zip(samples, samples[1:])]
    signs = [1 if value > 0 else -1 for value in changes if abs(value) > 1e-6]
    assert sum(a != b for a, b in zip(signs, signs[1:])) <= 1


def test_twenty_shared_corridor_wires_do_not_reuse_exact_straight_tracks():
    from scripts.render_timeline_wire_refinement import corridor, shared_length

    wires, obstacles = corridor(20)
    paths = route_wires(wires, obstacles)
    for wire, path in zip(wires, paths):
        assert_side_tangents(path, wire)
        assert not any(stroke(path).intersects(rect) for rect in obstacles)
    assert shared_length(paths) < 1
    assert paths == route_wires(wires, list(reversed(obstacles)))


@pytest.mark.parametrize("zoom", [0.8, 2.0])
def test_hundred_wire_corridor_keeps_every_path_without_stroke_overlap(zoom):
    from scripts.render_timeline_wire_refinement import corridor, shared_length

    wires, obstacles = corridor(100, zoom)
    paths = route_wires(wires, obstacles)
    strokes = []
    for wire, path in zip(wires, paths):
        assert_side_tangents(path, wire)
        current = stroke(path)
        assert not any(current.intersects(rect) for rect in obstacles)
        assert not any(current.intersects(earlier) for earlier in strokes)
        strokes.append(current)
    assert shared_length(paths) == 0


def test_closed_socket_is_not_painted_as_a_false_connection():
    wire = Wire(QPointF(0, 100), QPointF(600, 100), 1, -1)
    assert route_wires([wire], [QRectF(-10, 90, 40, 20)])[0].isEmpty()


@pytest.mark.parametrize("scene", ["staggered-cluster", "branches-and-merges"])
@pytest.mark.parametrize("zoom", [0.8, 2.0])
def test_multi_blocker_scenes_keep_all_wires_separate(scene, zoom):
    from scripts.render_timeline_wire_refinement import blocker_scenes, shared_length
    from src.gui.widgets.timeline.wire_geometry import route_conflicts, valid_candidate

    wires, obstacles = blocker_scenes()[scene]
    wires = [
        Wire(w.source * zoom, w.target * zoom, w.source_side, w.target_side)
        for w in wires
    ]
    obstacles = [QRectF(r.topLeft() * zoom, r.size() * zoom) for r in obstacles]
    paths = route_wires(wires, obstacles)
    previous = []
    for wire, path in zip(wires, paths):
        assert_side_tangents(path, wire)
        candidate = valid_candidate(wire, path, obstacles, None)
        assert candidate is not None
        assert not route_conflicts(candidate, previous)[0]
        previous.append(candidate)
    assert shared_length(paths) == 0


def test_shared_source_fans_out_without_losing_a_dependency():
    from scripts.render_timeline_wire_refinement import shared_length

    wires = [Wire(QPointF(30, 100), QPointF(900, y), 1, -1) for y in (100, 150, 200)]
    paths = route_wires(wires, [])
    assert all(not path.isEmpty() for path in paths)
    # Small shared terminal neighbourhoods are intentional; no shared bus follows.
    assert shared_length(paths) == 0
    sockets = QPainterPath()
    sockets.addEllipse(wires[0].source, 24, 24)
    assert (
        not stroke(paths[0])
        .subtracted(sockets)
        .intersects(stroke(paths[1]).subtracted(sockets))
    )


def test_horizontal_path_is_not_culled_as_an_empty_rectangle(qtbot):
    from src.gui.widgets.timeline import TimelineView
    from tests.unit.test_timeline_dependencies import sample

    view = TimelineView()
    qtbot.addWidget(view)
    view.set_events(sample())
    for item in view._event_items.values():
        item.setY(200)
    image = QImage(1200, 900, QImage.Format.Format_ARGB32)
    painter = QPainter(image)
    try:
        curves, _ = view._dependencies.curves(
            list(view._event_items.values()),
            painter,
            viewport=QRectF(-500, 85, 2000, 500),
        )
        assert len(curves) == 1
    finally:
        painter.end()


def test_tight_arrowhead_clearance_is_validated():
    wire = Wire(QPointF(0, 100), QPointF(600, 100), 1, -1)
    # The centre line is clear, but the arrow's upper arm is blocked.
    assert route_wires([wire], [QRectF(593, 95, 3, 2)])[0].isEmpty()


def test_vertical_pan_and_culling_do_not_reallocate_routes(qtbot, monkeypatch):
    import src.gui.widgets.timeline.dependency_layer as module
    from src.gui.widgets.timeline import TimelineView
    from tests.unit.test_timeline_dependencies import sample

    router = Mock(wraps=module.route_wires)
    monkeypatch.setattr(module, "route_wires", router)
    view = TimelineView()
    qtbot.addWidget(view)
    view.set_events(sample())
    image = QImage(1200, 900, QImage.Format.Format_ARGB32)
    painter = QPainter(image)
    try:
        items = list(view._event_items.values())
        viewport = QRectF(0, 85, 1200, 500)
        initial = view._dependencies.curves(items, painter, 85, viewport)[0]
        painter.setWorldTransform(QTransform.fromTranslate(0, 30))
        panned = view._dependencies.curves(items, painter, 85, viewport)[0]
        assert router.call_count == 1
        assert panned[0].path() == QTransform.fromTranslate(0, 30).map(
            initial[0].path()
        )
        # Changing only which wires are painted does not change batch allocation.
        view._dependencies.curves(items, painter, 85, QRectF(0, 5000, 1200, 500))
        assert router.call_count == 1
    finally:
        painter.end()


def test_production_paint_defers_cold_routing_and_reuses_preparation(
    qtbot, monkeypatch
):
    import src.gui.widgets.timeline.dependency_layer as module
    from src.gui.widgets.timeline import TimelineView
    from tests.unit.test_timeline_dependencies import sample

    router = Mock(wraps=module.route_wires)
    monkeypatch.setattr(module, "route_wires", router)
    view = TimelineView()
    qtbot.addWidget(view)
    view.set_events(sample())
    view.set_dependency_selection("a")
    image = QImage(1200, 900, QImage.Format.Format_ARGB32)
    painter = QPainter(image)
    try:
        view.drawBackground(painter, QRectF(0, 0, 1200, 900))
        assert router.call_count == 0
        assert view._dependency_route_timer.isActive()
        view._dependency_route_timer.stop()
        view._prepare_dependency_routes()
        assert router.call_count == 1
        painter.setWorldTransform(view.viewportTransform())
        view.drawBackground(painter, QRectF(0, 0, 1200, 900))
        assert router.call_count == 1
        assert not view._dependencies.routing_pending
    finally:
        painter.end()


def test_close_forward_sockets_do_not_get_backtracking_bezier_handles():
    wire = Wire(QPointF(10, 20), QPointF(50, 400), 1, -1)
    path = route_wires([wire], [])[0]
    assert_side_tangents(path, wire)
    samples = [path.pointAtPercent(i / 100) for i in range(101)]
    assert all(first.x() <= second.x() for first, second in zip(samples, samples[1:]))


@pytest.mark.parametrize(
    "target", [QPointF(300, 180), QPointF(20, 180), QPointF(10, 180)]
)
def test_obstacles_are_routed_around_without_clipped_gaps(target):
    wire = Wire(QPointF(10, 30), target, 1, -1)
    obstacles = [QRectF(40, 50, 180, 65), QRectF(50, 140, 80, 25)]
    path = route_wires([wire], obstacles)[0]
    assert_side_tangents(path, wire)
    assert not any(stroke(path).intersects(rect) for rect in obstacles)


def test_crowded_routes_stay_below_the_sticky_ruler():
    wires = [
        Wire(QPointF(200, 120), QPointF(150, 250), 1, -1),
        Wire(QPointF(200, 120), QPointF(180, 320), 1, -1),
    ]
    obstacles = [QRectF(130, 100, 65, 35), QRectF(180, 160, 150, 40)]
    paths = route_wires(wires, obstacles, minimum_y=85)
    assert paths == route_wires(wires, list(reversed(obstacles)), minimum_y=85)
    for wire, path in zip(wires, paths):
        assert_side_tangents(path, wire)
        assert path.boundingRect().top() >= 85
        assert not any(stroke(path).intersects(rect) for rect in obstacles)


def test_layer_orders_branches_independently_of_scene_enumeration(qtbot):
    from src.core.event_timing.queries import canonical_events
    from src.gui.widgets.timeline import TimelineView
    from tests.unit.test_timeline_dependencies import follower, sample

    view = TimelineView()
    qtbot.addWidget(view)
    records = sample()
    records.extend([follower("c", "a", offset=3), follower("d", "a", offset=4)])
    view.set_events(canonical_events(records, None))
    image = QImage(1200, 900, QImage.Format.Format_ARGB32)
    painter = QPainter(image)
    try:
        items = list(view._event_items.values())
        first = view._dependencies.curves(items, painter)[0]
        second = view._dependencies.curves(list(reversed(items)), painter)[0]
        assert [curve.dependency for curve in first] == [
            curve.dependency for curve in second
        ]
        assert [curve.path() for curve in first] == [curve.path() for curve in second]
        assert [curve.target.y() for curve in first] == sorted(
            curve.target.y() for curve in first
        )
    finally:
        painter.end()


def test_routing_cache_survives_selection_and_panning(qtbot, monkeypatch):
    import src.gui.widgets.timeline.dependency_layer as module
    from src.gui.widgets.timeline import TimelineView
    from tests.unit.test_timeline_dependencies import sample

    router = Mock(wraps=module.route_wires)
    monkeypatch.setattr(module, "route_wires", router)
    view = TimelineView()
    qtbot.addWidget(view)
    view.set_events(sample())
    image = QImage(1200, 900, QImage.Format.Format_ARGB32)
    painter = QPainter(image)
    try:
        items = list(view._event_items.values())
        initial = view._dependencies.curves(items, painter)[0]
        view._event_items["a"].setSelected(True)
        view.set_dependency_selection("a")
        view._dependencies.curves(items, painter)
        painter.setWorldTransform(QTransform.fromTranslate(30, 40))
        panned = view._dependencies.curves(items, painter)[0]
        assert router.call_count == 1
        assert panned[0].source == initial[0].source + QPointF(30, 40)
        assert panned[0].emphasized
        view._event_items["a"].setY(220)
        view._dependencies.curves(items, painter)
        assert router.call_count == 2
    finally:
        painter.end()


def test_long_wire_grid_keeps_local_ports_and_outer_gutters():
    from src.gui.widgets.timeline.wire_router import _axes

    wire = Wire(QPointF(200, 20), QPointF(100, 50000), 1, -1)
    obstacles = [QRectF(index % 400, 50 * index + 40, 140, 25) for index in range(1000)]
    xs, ys = _axes(wire, obstacles, 0, None)
    assert len(xs) < 80 and len(ys) < 80
    assert min(xs) < min(rect.left() for rect in obstacles)
    assert max(xs) > max(rect.right() for rect in obstacles)


@pytest.mark.parametrize("zoom", [0.8, 2.0])
def test_crowded_valid_dependencies_keep_complete_paths(qtbot, zoom):
    from scripts.render_timeline_dependencies import _events
    from src.core.calendar import CalendarConfig, CalendarConverter
    from src.core.temporal_context import TemporalResolutionContext
    from src.gui.widgets.timeline import EventItem, TimelineView

    converter = CalendarConverter(CalendarConfig.create_default())
    EventItem.set_calendar_converter(converter)
    view = TimelineView()
    qtbot.addWidget(view)
    view.resize(1200, 900)
    view.show()
    image = QImage(1200, 1000, QImage.Format.Format_ARGB32)
    painter = QPainter(image)
    try:
        view.set_temporal_context(
            TemporalResolutionContext.build(_events(True, converter), converter)
        )
        view._apply_zoom(zoom)
        view.verticalScrollBar().setValue(0)
        painter.setWorldTransform(view.viewportTransform())
        curves = view._dependencies.curves(
            list(view._event_items.values()), painter, minimum_y=view.RULER_HEIGHT
        )[0]
        assert len(curves) == len(view._dependencies.dependencies)
        assert all(not curve.path().isEmpty() for curve in curves)
    finally:
        painter.end()
        EventItem.set_calendar_converter(None)


def test_offscreen_culling_preserves_topology_and_spanning_wires(qtbot):
    from src.gui.widgets.timeline import TimelineView
    from tests.unit.test_timeline_dependencies import sample

    view = TimelineView()
    qtbot.addWidget(view)
    view.set_events(sample())
    source, target = view._event_items["a"], view._event_items["b"]
    source.setY(4900)
    target.setY(5000)
    topology = view._dependencies.dependencies
    image = QImage(800, 400, QImage.Format.Format_ARGB32)
    painter = QPainter(image)
    try:
        viewport = QRectF(0, 0, 800, 400)
        assert not view._dependencies.curves(
            [source, target], painter, viewport=viewport
        )[0]
        source.setY(100)
        assert (
            len(
                view._dependencies.curves([source, target], painter, viewport=viewport)[
                    0
                ]
            )
            == 1
        )
        assert view._dependencies.dependencies == topology
    finally:
        painter.end()


def test_transient_caption_refresh_moves_socket_without_rebuilding_topology(qtbot):
    from src.gui.widgets.timeline import TimelineView
    from tests.unit.test_timeline_dependencies import sample

    view = TimelineView()
    qtbot.addWidget(view)
    records = sample()
    records[0].lore_duration = 0
    view.set_events(records)
    image = QImage(1200, 900, QImage.Format.Format_ARGB32)
    painter = QPainter(image)
    try:
        initial = view._dependencies.curves(list(view._event_items.values()), painter)[
            0
        ][0]
        topology = view._dependencies.dependencies
        view.update_event_preview(
            {"id": "a", "name": "A much longer source caption " * 4}
        )
        refreshed = view._dependencies.curves(
            list(view._event_items.values()), painter
        )[0][0]
        assert refreshed.source.x() > initial.source.x()
        assert view._dependencies.dependencies == topology
    finally:
        painter.end()
