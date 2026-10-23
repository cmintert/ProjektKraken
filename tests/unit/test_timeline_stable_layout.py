"""Continuity, capacity and accepted-history regressions for lane repair."""

import random
from itertools import product
from unittest.mock import Mock

import pytest

from src.core.events import Event
from src.core.timeline_layout import (
    TimelineLayoutInput as Interval,
)
from src.core.timeline_layout import (
    TimelineLayoutSnapshot,
    pack_stable_timeline_intervals,
    pack_timeline_intervals,
)
from src.gui.widgets.timeline import TimelineWidget
from tests.unit.test_timeline_layout_boundary import CachedGroups

pytestmark = pytest.mark.ci_fast


def snapshot(lanes, heights):
    return TimelineLayoutSnapshot(tuple(sorted(lanes.items())), tuple(heights))


def assert_safe(intervals, lanes):
    for first, second in product(intervals, repeat=2):
        if (
            first.event_id != second.event_id
            and lanes[first.event_id] == lanes[second.event_id]
        ):
            assert first.end <= second.start or second.end <= first.start


def assert_chronological(intervals, lanes):
    ordered = sorted(
        intervals, key=lambda i: (i.start if i.anchor is None else i.anchor, i.event_id)
    )
    for i, first in enumerate(ordered):
        for second in ordered[i + 1 :]:
            if first.start < second.end and second.start < first.end:
                assert lanes[first.event_id] < lanes[second.event_id]


def test_chronology_uses_anchor_not_visual_start():
    spans = [Interval("early", 2, 6, 20, 0), Interval("later", -10, 3, 20, 1)]
    assert pack_stable_timeline_intervals(spans)[0] == {"early": 0, "later": 1}


def test_equal_anchor_ties_ignore_reversed_history():
    spans = [Interval("b", 0, 4, 20, 1), Interval("a", 1, 3, 20, 1)]
    old = snapshot({"b": 0, "a": 1}, [20, 20])
    assert pack_stable_timeline_intervals(spans, old)[0] == {"a": 0, "b": 1}


def test_preserves_rows_even_when_visual_start_order_changes():
    old = snapshot({"a": 1, "b": 0}, [80, 40])
    spans = [Interval("a", -3, 0, 20), Interval("b", -4, 1, 30)]
    assert pack_stable_timeline_intervals(spans, old) == ({"a": 1, "b": 0}, [30, 20])


def test_future_reservations_and_compact_fallback():
    spans = [
        Interval("a", 0, 3, 20),
        Interval("b", 2, 4, 20),
        Interval("c", 3, 5, 20),
        Interval("far", 20, 21, 20),
    ]
    old = snapshot({"a": 0, "b": 0, "c": 1, "far": 1}, [20, 20])
    lanes, heights = pack_stable_timeline_intervals(spans, old)
    assert_safe(spans, lanes)
    assert len(heights) == 3
    assert lanes == {"a": 0, "b": 1, "c": 2, "far": 0}


def test_zoom_in_reclaims_all_spare_rows_and_heights():
    spans = [Interval(str(i), i * 10, i * 10 + 1, 20) for i in range(5)]
    old = snapshot({str(i): i for i in range(5)}, [100] * 5)
    lanes, heights = pack_stable_timeline_intervals(spans, old)
    assert set(lanes.values()) == {0}
    assert heights == [20]


def test_repair_obeys_smaller_budget_when_old_reservations_block_it():
    spans = [Interval("a", 0, 3, 20), Interval("b", 2, 4, 20), Interval("c", 3, 5, 20)]
    old = snapshot({"a": 2, "b": 0, "c": 1}, [40, 40, 40])
    lanes, heights = pack_stable_timeline_intervals(spans, old)
    assert len(heights) == 3
    assert set(lanes.values()) == {0, 1, 2}
    assert_safe(spans, lanes)


def test_seeded_zoom_cycles_are_safe_bounded_and_idempotent():
    rng = random.Random(107)
    starts = [rng.uniform(-10, 10) for _ in range(30)]
    old = TimelineLayoutSnapshot()
    for width in [1, 2, 4, 2, 1] * 6:
        spans = [
            Interval(str(i), start, start + width, 20 + i % 3)
            for i, start in enumerate(starts)
        ]
        lanes, heights = pack_stable_timeline_intervals(spans, old)
        assert len(heights) == len(pack_timeline_intervals(spans)[1])
        assert_safe(spans, lanes)
        assert_chronological(spans, lanes)
        old = snapshot(lanes, heights)
        assert pack_stable_timeline_intervals(list(reversed(spans)), old) == (
            lanes,
            heights,
        )


def test_small_cases_compact_row_count_matches_exhaustive_oracle():
    spans = [
        Interval("a", -1, 1, 20),
        Interval("b", 0, 2, 30),
        Interval("c", 1, 3, 20),
        Interval("d", 4, 5, 20),
    ]
    for count in range(1, 5):
        possible = []
        for coloring in product(range(count), repeat=len(spans)):
            lanes = dict(zip([span.event_id for span in spans], coloring))
            try:
                assert_safe(spans, lanes)
                assert_chronological(spans, lanes)
                possible.append(lanes)
            except AssertionError:
                pass
        if possible:
            assert len(pack_timeline_intervals(spans)[1]) == count
            break


def test_compact_menu_preserves_time_selection_and_fit_click(qtbot):
    widget = TimelineWidget()
    qtbot.addWidget(widget)
    view = widget.view
    view.set_events(
        [Event(id="a", name="A", lore_date=0), Event(id="b", name="B", lore_date=0)]
    )
    view._event_items["b"].setSelected(True)
    view._apply_zoom(10)
    view.events[1].lore_date = 1000
    view.repack_events()
    assert len(view._lane_history.snapshot().heights) == 1
    time = view._playhead._time
    widget.compact_action.trigger()
    assert len(view._lane_history.snapshot().heights) == 1
    assert view._event_items["b"].isSelected()
    assert view._playhead._time == time
    assert widget.btn_fit.menu() is widget.fit_menu
    assert any(
        item.action.menu() is widget.fit_menu for item in widget.action_toolbar._items
    )
    fit = Mock()
    view.fit_all = fit
    widget.btn_fit.click()
    fit.assert_called_once()


def test_group_histories_are_independent_and_collapse_keeps_state(qtbot):
    widget = TimelineWidget()
    qtbot.addWidget(widget)
    view = widget.view
    a = Event(id="a", name="A", lore_date=0)
    b = Event(id="b", name="B", lore_date=0)
    a.tags = ["Alpha", "Beta"]
    b.tags = ["Alpha"]
    view.set_events([a, b])
    view.set_data_provider(CachedGroups(view))
    view.set_grouping_config(["Alpha", "Beta"])
    assert len(view._lane_history.snapshot("tag:Alpha").heights) == 2
    assert len(view._lane_history.snapshot("tag:Beta").heights) == 1
    before = view._lane_history.snapshot("tag:Alpha")
    view._band_manager._on_collapse_requested("Alpha")
    view._apply_zoom(2)
    assert view._lane_history.snapshot("tag:Alpha") == before
    view.compact_lanes()
    view._band_manager._on_expand_requested("Alpha")
    assert view._lane_history.snapshot("tag:Alpha").lanes


def test_compact_invalidates_active_worker_without_accepting_history(qtbot):
    widget = TimelineWidget()
    qtbot.addWidget(widget)
    view = widget.view
    view._thread_pool = Mock()
    view.set_events([Event(id=str(i), name=str(i), lore_date=i) for i in range(50)])
    old = view._layout_worker
    view.compact_lanes()
    lanes, heights = pack_timeline_intervals(old.intervals)
    view._on_layout_finished(old.request_token, lanes, heights, 0)
    assert not view._lane_history.snapshot().lanes
    latest = view._layout_worker
    assert latest is not old
    latest.run()
    qtbot.waitUntil(lambda: not view._layout_in_progress)
    assert view._lane_history.snapshot().lanes


@pytest.mark.parametrize("count", [49, 50, 51])
def test_threshold_uses_accepted_history_and_empty_clears_it(qtbot, count):
    widget = TimelineWidget()
    qtbot.addWidget(widget)
    view = widget.view
    view._thread_pool = Mock()
    events = [Event(id=str(i), name=str(i), lore_date=i * 100) for i in range(count)]
    view.set_events(events)
    if count >= 50:
        view._layout_worker.run()
        qtbot.waitUntil(lambda: not view._layout_in_progress)
    accepted = view._lane_history.snapshot()
    assert accepted.lanes
    view._apply_zoom(view._current_zoom * 1.1)
    if count >= 50:
        assert view._layout_worker.previous == accepted
        view._layout_worker.run()
        qtbot.waitUntil(lambda: not view._layout_in_progress)
    assert view._lane_history.snapshot().lanes == accepted.lanes
    view.set_events([])
    assert not view._lane_history.snapshot().lanes


def test_empty_menu_and_newly_available_compaction(qtbot):
    widget = TimelineWidget()
    qtbot.addWidget(widget)
    widget._update_layout_menu()
    assert not widget.compact_action.isEnabled()
    widget.set_events([Event(id="a", name="A", lore_date=0)])
    widget._update_layout_menu()
    assert widget.compact_action.isEnabled()
