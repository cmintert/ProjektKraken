"""Regression tests for zoom-aware horizontal timeline navigation."""

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent

from src.core.events import Event
from src.gui.widgets.timeline import TimelineView


@pytest.fixture
def timeline_view(qtbot):
    """Create a visible timeline view with stable viewport geometry."""
    view = TimelineView()
    qtbot.addWidget(view)
    view.resize(1200, 500)
    view.show()
    qtbot.waitUntil(lambda: view.viewport().width() > 0)
    view.set_events([])
    return view


def _visible_center_date(view: TimelineView) -> float:
    center = view.viewport().rect().center()
    return view.mapToScene(center).x() / view.scale_factor


def _normalized_scroll_delta(view: TimelineView, fraction: float = 0.01) -> float:
    scrollbar = view.horizontalScrollBar()
    scroll_range = scrollbar.maximum() - scrollbar.minimum()
    start = scrollbar.minimum() + scroll_range // 2
    end = start + max(1, round(scroll_range * fraction))

    scrollbar.setValue(start)
    start_date = _visible_center_date(view)
    scrollbar.setValue(end)
    return abs(_visible_center_date(view) - start_date)


@pytest.mark.parametrize("zoom", [1.0, 10.0, 100.0])
def test_horizontal_window_spans_twenty_viewports(
    timeline_view, qtbot, zoom: float
) -> None:
    """The scrollbar domain should stay local at every zoom level."""
    timeline_view._apply_zoom(zoom)
    qtbot.wait(0)

    transformed_width = (
        timeline_view.graphics_scene.sceneRect().width()
        * timeline_view.transform().m11()
    )
    assert transformed_width == pytest.approx(
        timeline_view.viewport().width()
        * timeline_view.HORIZONTAL_WINDOW_VIEWPORTS,
        rel=0.02,
    )


def test_normalized_thumb_travel_scales_with_zoom(timeline_view, qtbot) -> None:
    """The same thumb motion should navigate finer time when zoomed in."""
    timeline_view._apply_zoom(1.0)
    qtbot.wait(0)
    day_delta_at_one = _normalized_scroll_delta(timeline_view)

    timeline_view._apply_zoom(100.0)
    qtbot.wait(0)
    day_delta_at_one_hundred = _normalized_scroll_delta(timeline_view)

    assert day_delta_at_one_hundred == pytest.approx(
        day_delta_at_one / 100.0,
        rel=0.08,
    )


def test_maximum_zoom_does_not_saturate_qt_scroll_range(
    timeline_view, qtbot
) -> None:
    """A local window must stay comfortably inside Qt's integer limit."""
    timeline_view._apply_zoom(timeline_view.MAX_ZOOM)
    qtbot.wait(0)

    scrollbar = timeline_view.horizontalScrollBar()
    assert abs(scrollbar.minimum()) < 2_000_000_000
    assert abs(scrollbar.maximum()) < 2_000_000_000


def test_programmatic_zoom_preserves_visible_center(timeline_view, qtbot) -> None:
    """Changing zoom must not move the date at the viewport center."""
    timeline_view._set_horizontal_window(425.5)
    before = _visible_center_date(timeline_view)

    timeline_view._apply_zoom(25.0)
    qtbot.wait(0)

    assert _visible_center_date(timeline_view) == pytest.approx(before, abs=0.01)


def test_slider_rebase_waits_for_release_and_preserves_date(
    timeline_view, qtbot
) -> None:
    """Thumb dragging should rebase only after release without a visual jump."""
    scrollbar = timeline_view.horizontalScrollBar()
    original_window_center = timeline_view.graphics_scene.sceneRect().center().x()

    scrollbar.setSliderDown(True)
    scrollbar.setValue(scrollbar.maximum())
    qtbot.wait(0)
    selected_date = _visible_center_date(timeline_view)

    assert timeline_view.graphics_scene.sceneRect().center().x() == pytest.approx(
        original_window_center
    )

    scrollbar.setSliderDown(False)
    qtbot.wait(0)

    center_shift_px = abs(_visible_center_date(timeline_view) - selected_date) * (
        timeline_view.scale_factor * timeline_view.transform().m11()
    )
    assert center_shift_px <= 1.01
    assert timeline_view.graphics_scene.sceneRect().center().x() == pytest.approx(
        selected_date * timeline_view.scale_factor,
        abs=1.0,
    )


def test_focus_event_recenters_window_for_distant_item(
    timeline_view, qtbot
) -> None:
    """Event focus must work when the item is outside the local window."""
    target = Event(id="target", name="Far Away", lore_date=1_000_000.0)
    timeline_view.set_events([Event(name="Origin", lore_date=0.0), target])
    timeline_view._apply_zoom(100.0)
    timeline_view._set_horizontal_window(0.0)

    timeline_view.focus_event(target.id)
    qtbot.wait(0)

    assert _visible_center_date(timeline_view) == pytest.approx(
        target.lore_date,
        abs=0.01,
    )


def test_resize_preserves_center_and_twenty_viewport_window(
    timeline_view, qtbot
) -> None:
    """Responsive resizing should retain both date and navigation semantics."""
    timeline_view._set_horizontal_window(425.5)
    before = _visible_center_date(timeline_view)

    timeline_view.resize(800, 500)
    qtbot.wait(0)

    center_shift_px = abs(_visible_center_date(timeline_view) - before) * (
        timeline_view.scale_factor * timeline_view.transform().m11()
    )
    transformed_width = (
        timeline_view.graphics_scene.sceneRect().width()
        * timeline_view.transform().m11()
    )
    assert center_shift_px <= 1.01
    assert transformed_width == pytest.approx(
        timeline_view.viewport().width()
        * timeline_view.HORIZONTAL_WINDOW_VIEWPORTS,
        rel=0.02,
    )


def test_hand_pan_rebases_immediately_at_window_edge(timeline_view, qtbot) -> None:
    """Non-slider panning should regain headroom as soon as it nears an edge."""
    scrollbar = timeline_view.horizontalScrollBar()

    scrollbar.setValue(scrollbar.maximum())
    qtbot.wait(0)

    visible_center_x = (
        _visible_center_date(timeline_view) * timeline_view.scale_factor
    )
    assert timeline_view.graphics_scene.sceneRect().center().x() == pytest.approx(
        visible_center_x,
        abs=1.01,
    )
    assert scrollbar.value() != scrollbar.maximum()


def test_wheel_zoom_keeps_date_under_cursor(timeline_view, qtbot) -> None:
    """Refreshing the navigation window must preserve zoom-to-cursor behavior."""
    cursor = QPointF(300.0, 200.0)
    before = timeline_view.mapToScene(QPoint(300, 200)).x()
    event = QWheelEvent(
        cursor,
        cursor,
        QPoint(0, 0),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )

    timeline_view.wheelEvent(event)
    qtbot.wait(0)

    after = timeline_view.mapToScene(QPoint(300, 200)).x()
    assert after == pytest.approx(before, abs=1.0)


def test_event_refresh_preserves_local_navigation_center(
    timeline_view, qtbot
) -> None:
    """Incremental data refreshes should not pull users away from their date."""
    timeline_view._apply_zoom(10.0)
    timeline_view._set_horizontal_window(425.5)
    before = _visible_center_date(timeline_view)

    timeline_view.set_events([Event(name="Elsewhere", lore_date=10.0)])
    qtbot.wait(0)

    center_shift_px = abs(_visible_center_date(timeline_view) - before) * (
        timeline_view.scale_factor * timeline_view.transform().m11()
    )
    assert center_shift_px <= 1.01


def test_event_drop_line_stays_one_pixel_wide_at_hour_zoom(
    timeline_view, qtbot
) -> None:
    """Horizontal zoom must not magnify the dashed event guide stroke."""
    event = Event(id="point", name="Point Event", lore_date=10.0)
    timeline_view.set_events([event])
    timeline_view._apply_zoom(timeline_view.MAX_ZOOM)
    qtbot.wait(0)

    pen = timeline_view._drop_lines[event.id].pen()
    assert pen.style() == Qt.PenStyle.DashLine
    assert pen.isCosmetic()
    assert pen.widthF() == pytest.approx(1.0)


def test_incremental_event_drop_line_uses_cosmetic_pen(
    timeline_view, qtbot
) -> None:
    """Incrementally inserted events must use the same fixed-width guide."""
    event = Event(id="incremental", name="New Event", lore_date=20.0)

    timeline_view.apply_event_effects(
        [
            {
                "object_type": "event",
                "operation": "upsert",
                "object_id": event.id,
                "snapshot": event.to_dict(),
                "relations_changed": False,
            }
        ]
    )
    qtbot.wait(0)

    pen = timeline_view._drop_lines[event.id].pen()
    assert pen.style() == Qt.PenStyle.DashLine
    assert pen.isCosmetic()
