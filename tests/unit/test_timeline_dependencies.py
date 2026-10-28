"""Full-world strand identity, endpoint painting and contextual display settings."""

from copy import deepcopy
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QImage, QPainter, QTransform

from src.core.event_timing.definitions import EndpointDefinition, EventTimingDefinition
from src.core.event_timing.queries import canonical_events
from src.core.events import Event
from src.core.temporal_context import TemporalResolutionContext
from src.core.timeline_dependencies import timeline_dependencies
from src.gui.widgets.timeline import EventItem, TimelineView, TimelineWidget

pytestmark = pytest.mark.ci_fast


def follower(
    identity, source, source_endpoint="start", target_endpoint="start", offset=6
):
    reference = EndpointDefinition(
        kind="event",
        anchor_id=f"event:{source}",
        endpoint=source_endpoint,
        offset={"unit": "days", "value": offset},
    )
    timing = (
        EventTimingDefinition(reference)
        if target_endpoint == "start"
        else EventTimingDefinition(
            EndpointDefinition(instant=2), "independent", reference
        )
    )
    return Event(id=identity, name=identity, lore_date=7, attributes=timing.apply({}))


def sample(source_endpoint="start", target_endpoint="start", offset=6):
    return canonical_events(
        [
            Event(id="a", name="The march begins", lore_date=1, lore_duration=2),
            follower("b", "a", source_endpoint, target_endpoint, offset),
        ],
        None,
    )


def effect(event, operation="upsert"):
    return {
        "object_type": "event",
        "object_id": event.id,
        "operation": operation,
        "snapshot": event.to_dict() if operation == "upsert" else None,
    }


@pytest.fixture
def view(qtbot):
    result = TimelineView()
    qtbot.addWidget(result)
    result.resize(1000, 650)
    return result


@pytest.fixture
def painting():
    image = QImage(1200, 900, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    yield painter, image
    painter.end()


def test_strands_include_branches_merges_and_hidden_bridge():
    records = [
        Event(id="a", name="a", lore_date=0),
        follower("b", "a"),
        follower("c", "a"),
        follower("d", "b"),
        Event(id="x", name="x", lore_date=0),
        follower("y", "x"),
    ]
    records[1].lore_date = None  # An unplaced bridge is still an authored connection.
    expected = timeline_dependencies(records)
    assert {edge.strand_id for edge in expected} == {"a", "x"}
    assert {edge.palette_index for edge in expected if edge.strand_id == "a"} == {
        expected[0].palette_index
    }
    assert timeline_dependencies(list(reversed(records))) == expected
    merge = EventTimingDefinition(
        EndpointDefinition(kind="event", anchor_id="event:c"),
        "independent",
        EndpointDefinition(kind="event", anchor_id="event:y"),
    )
    records.append(Event(id="z", name="merge", lore_date=8, attributes=merge.apply({})))
    assert {edge.strand_id for edge in timeline_dependencies(records)} == {"a"}
    assert {edge.strand_id for edge in timeline_dependencies(records[:-1])} == {
        "a",
        "x",
    }


def test_palette_is_bounded_and_reusable_without_python_hash():
    records = []
    for index in range(30):
        records.extend(
            [
                Event(id=f"root-{index}", name="root", lore_date=0),
                follower(f"child-{index}", f"root-{index}"),
            ]
        )
    slots = [edge.palette_index for edge in timeline_dependencies(records)]
    assert set(slots) == set(range(8))
    assert len(slots) > len(set(slots))


def test_missing_self_manual_and_unsupported_references_are_ignored():
    records = [
        Event(id="a", name="a", lore_date=0),
        follower("b", "missing"),
        follower("c", "c"),
        Event(
            id="d", name="d", lore_date=1, attributes={"_temporal_v2": {"schema": 999}}
        ),
    ]
    assert timeline_dependencies(records) == ()


@pytest.mark.parametrize("source_endpoint", ["start", "end"])
@pytest.mark.parametrize("target_endpoint", ["start", "end"])
def test_all_endpoint_combinations(view, painting, source_endpoint, target_endpoint):
    records = sample(source_endpoint, target_endpoint)
    before = deepcopy([event.to_dict() for event in records])
    view.set_events(records)
    painter, _ = painting
    curves, _ = view._dependencies.curves(list(view._event_items.values()), painter)
    assert len(curves) == 1
    curve = curves[0]
    assert (curve.dependency.source_endpoint, curve.dependency.target_endpoint) == (
        source_endpoint,
        target_endpoint,
    )
    assert curve.path().pointAtPercent(0) == curve.source
    assert curve.path().pointAtPercent(1) == curve.target
    if source_endpoint == "end":
        assert curve.source.x() > 3 * view.scale_factor
    if target_endpoint == "end":
        assert curve.target.y() > view._event_items["b"].y()
    assert [event.to_dict() for event in records] == before


def test_movement_zoom_selection_and_hidden_endpoints(view, painting):
    view.set_events(sample())
    first, second = view._event_items["a"], view._event_items["b"]
    first.setPos(100, 250)
    second.setY(400)
    painter, _ = painting
    painter.setWorldTransform(QTransform.fromScale(2, 1))
    curve = view._dependencies.curves([first, second], painter)[0][0]
    assert curve.source.y() == 250
    assert curve.source.x() < 200
    path = curve.path()
    assert path.elementAt(1).y == curve.source.y()
    assert path.elementAt(path.elementCount() - 2).y == curve.target.y()
    assert not curve.emphasized
    first.setSelected(True)
    assert view._dependencies.curves([first, second], painter)[0][0].emphasized
    first.hide()
    assert not view._dependencies.curves([first, second], painter)[0]


def test_group_copies_prefer_same_scope_then_nearest_source(view, painting):
    records = sample()
    view.set_events(records)
    first, second = view._event_items["a"], view._event_items["b"]
    duplicate = EventItem(records[0], view.scale_factor)
    view.graphics_scene.addItem(duplicate)
    first.setData(0, "all")
    second.setData(0, "tag:story")
    duplicate.setData(0, "tag:story")
    first.setY(300)
    second.setY(350)
    duplicate.setY(100)
    painter, _ = painting
    curves, _ = view._dependencies.curves([first, duplicate, second], painter)
    assert curves[0].source.y() == 100
    duplicate.hide()
    assert (
        view._dependencies.curves([first, duplicate, second], painter)[0][0].source.y()
        == 300
    )


def test_filtered_view_keeps_full_world_color(view, painting):
    records = sample()
    records.append(follower("c", "b"))
    context = TemporalResolutionContext.build(records, None)
    view.set_temporal_context(context)
    colors = {
        edge.target_id: edge.palette_index for edge in view._dependencies.dependencies
    }
    view.set_events(context.view_events()[1:])
    assert {
        edge.target_id: edge.palette_index for edge in view._dependencies.dependencies
    } == colors
    curves, _ = view._dependencies.curves(list(view._event_items.values()), painting[0])
    assert len(curves) == 1 and curves[0].dependency.target_id == "c"


def test_delete_detach_and_restore_refresh_topology(view, painting):
    records = sample()
    view.set_events(records)
    view.apply_event_effects([effect(records[1], "delete")])
    assert not view._dependencies.dependencies
    view.apply_event_effects([effect(records[1])])
    assert len(view._dependencies.dependencies) == 1
    detached = Event(id="b", name="b", lore_date=7)
    view.apply_event_effects([effect(detached)])
    assert not view._dependencies.dependencies
    view.apply_event_effects([effect(records[1])])
    assert len(view._dependencies.dependencies) == 1


def test_toggle_is_presentation_only_and_disabled_paint_is_empty(view, painting):
    view.set_events(sample())
    view._event_items["a"].setSelected(True)
    before = (
        view.get_playhead_time(),
        view.graphics_scene.sceneRect(),
        [(item.pos(), item.isSelected()) for item in view._event_items.values()],
    )
    view.repack_events = Mock()
    view.set_dependencies_visible(False)
    assert not view.are_dependencies_visible()
    view.repack_events.assert_not_called()
    painter, image = painting
    blank = image.copy()
    view._dependencies.paint(
        painter, list(view._event_items.values()), [], QRectF(0, 0, 1200, 900), {}
    )
    assert image == blank
    assert before == (
        view.get_playhead_time(),
        view.graphics_scene.sceneRect(),
        [(item.pos(), item.isSelected()) for item in view._event_items.values()],
    )


def test_paint_uses_cached_presentations_and_masks_captions(
    view, painting, monkeypatch
):
    import src.gui.widgets.timeline.dependency_layer as module
    from src.core.theme_manager import ThemeManager

    view.set_events(sample())
    monkeypatch.setattr(
        module,
        "event_temporal_presentation",
        Mock(side_effect=AssertionError("paint resolved timing")),
    )
    painter, image = painting
    blank = image.copy()
    view._dependencies.paint(
        painter,
        list(view._event_items.values()),
        [],
        QRectF(0, 0, 1200, 900),
        ThemeManager().get_theme(),
    )
    assert image != blank
    curves, mask = view._dependencies.curves(list(view._event_items.values()), painter)
    assert curves
    assert not mask.isEmpty()


def test_zero_duration_end_and_coincident_dates(view, painting):
    first = Event(
        id="a",
        name="a",
        lore_date=2,
        attributes=EventTimingDefinition(
            EndpointDefinition(instant=2), "duration", duration_days=0
        ).apply({}),
    )
    records = canonical_events([first, follower("b", "a", "end", offset=0)], None)
    view.set_events(records)
    curve = view._dependencies.curves(list(view._event_items.values()), painting[0])[0][
        0
    ]
    assert not curve.path().isEmpty()
    assert curve.source.x() != 0


def test_unresolved_end_has_no_connector(view, painting):
    records = sample("end")
    records[0].attributes["_temporal_v2"] = {
        "projection": {
            "start": {"coordinate": 1},
            "end": {"error": "Unavailable", "coordinate": None},
            "has_end": True,
            "duration_authored": True,
            "duration": 2,
        }
    }
    view.set_events(records)
    assert not view._dependencies.curves(list(view._event_items.values()), painting[0])[
        0
    ]


def test_setting_default_keyboard_persistence_and_overflow(qtbot, monkeypatch):
    import src.gui.widgets.timeline as module
    from src.gui.utils.settings_navigation import settings_navigation

    stored = {}

    class FakeSettings:
        def value(self, key, default=None, type=None):
            return stored.get(key, default)

    monkeypatch.setattr(module, "QSettings", FakeSettings)
    bus = settings_navigation()

    def save(key, value):
        stored[key] = value

    bus.contextual_changed.connect(save)
    try:
        widget = TimelineWidget()
        qtbot.addWidget(widget)
        assert widget.chk_show_dependencies.isChecked()
        widget.show()
        widget.chk_show_dependencies.setFocus()
        qtbot.keyClick(widget.chk_show_dependencies, Qt.Key.Key_Space)
        assert stored["timeline/show_dependencies"] is False
        assert not widget.view.are_dependencies_visible()
        restored = TimelineWidget()
        qtbot.addWidget(restored)
        assert not restored.chk_show_dependencies.isChecked()
        widget.setMaximumWidth(210)
        widget.resize(210, 500)
        widget.action_toolbar.refresh()
        assert (
            widget.chk_show_dependencies in widget.action_toolbar.overflowed_buttons()
        )
        action = next(
            action
            for action in widget.action_toolbar.overflow_menu.actions()
            if action.text() == "Show dependencies"
        )
        assert action.isCheckable() and not action.isChecked()
        action.trigger()
        assert widget.view.are_dependencies_visible()
    finally:
        bus.contextual_changed.disconnect(save)


def test_settings_center_synchronizes_checkbox_and_runtime(qtbot):
    from src.app.settings_composition import _refresh_local_consumers
    from src.gui.utils.settings_navigation import settings_navigation

    window = Mock()
    window.timeline = TimelineWidget()
    qtbot.addWidget(window.timeline)
    bus = settings_navigation()
    changed = Mock()
    bus.contextual_changed.connect(changed)
    try:
        _refresh_local_consumers(window, {"timeline/show_dependencies": False})
        assert not window.timeline.chk_show_dependencies.isChecked()
        assert not window.timeline.view.are_dependencies_visible()
        changed.assert_not_called()
    finally:
        bus.contextual_changed.disconnect(changed)


def test_uncertain_duration_end_uses_presence_not_detached_measure(view, painting):
    from src.core.calendar import CalendarConfig, CalendarConverter
    from src.core.date_parser import DateParser

    converter = CalendarConverter(CalendarConfig.create_default())
    expression = DateParser(converter._config).parse_expression("January 1")
    timing = EventTimingDefinition(
        EndpointDefinition(expression=expression.to_dict()), "duration", duration_days=2
    )
    first = Event(id="a", name="uncertain", lore_date=None, attributes=timing.apply({}))
    records = canonical_events([first, follower("b", "a", "end")], converter)
    before = deepcopy([event.to_dict() for event in records])
    EventItem.set_calendar_converter(converter)
    try:
        view.set_events(records)
        curve = view._dependencies.curves(
            list(view._event_items.values()), painting[0]
        )[0][0]
        item = view._event_items["a"]
        layout = item._layout()
        assert curve.source.y() == item.y() + layout.rows[-1].y
        assert curve.source.y() != item.y() + next(
            row.y for row in layout.rows if row.measure
        )
        assert curve.source.x() == pytest.approx(
            item.x() + layout.rows[-1].geometry.right + 2
        )
        assert [event.to_dict() for event in records] == before
    finally:
        EventItem.set_calendar_converter(None)


def test_contextual_setting_uses_canonical_local_adapter(qtbot, monkeypatch):
    from PySide6.QtCore import QSettings

    import src.gui.widgets.timeline as module
    from src.app.coordinators.settings_coordinator import SettingsCoordinator
    from src.gui.utils.settings_navigation import settings_navigation
    from src.gui.widgets.settings_center import SettingsCenter
    from src.services.local_settings import LocalSettingsAdapter

    settings = QSettings("KRT114", "dependencies-test")
    settings.remove("timeline/show_dependencies")
    adapter = LocalSettingsAdapter(settings)
    parent = TimelineWidget()
    qtbot.addWidget(parent)
    coordinator = SettingsCoordinator(lambda: {}, Mock(), parent, local=adapter)
    monkeypatch.setattr(module, "QSettings", lambda: settings)
    bus = settings_navigation()
    bus.contextual_changed.connect(coordinator.set_contextual)
    try:
        widget = TimelineWidget()
        qtbot.addWidget(widget)
        widget.chk_show_dependencies.setChecked(False)
        assert (
            adapter.snapshot(include_secrets=False)["timeline/show_dependencies"]
            is False
        )
        restored = TimelineWidget()
        qtbot.addWidget(restored)
        assert not restored.view.are_dependencies_visible()
        center = SettingsCenter()
        qtbot.addWidget(center)
        assert "timeline/show_dependencies" in center.controls
    finally:
        bus.contextual_changed.disconnect(coordinator.set_contextual)
        settings.remove("timeline/show_dependencies")
