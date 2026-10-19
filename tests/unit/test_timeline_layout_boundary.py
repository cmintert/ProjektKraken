"""Detached packing and controlled asynchronous lifecycle regressions."""

import dataclasses
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QThread

from src.core.events import Event
from src.core.timeline_grouping import build_group_metadata, events_for_group
from src.core.timeline_layout import TimelineLayoutInput, pack_timeline_intervals
from src.gui.widgets.timeline import EventItem, TimelineView
from src.gui.widgets.timeline_lane_packer import TimelineLanePacker
from src.gui.workers.layout_worker import LayoutWorker
from tests.unit.test_timeline_event_preparation_service import effect

pytestmark = pytest.mark.ci_fast


@pytest.fixture
def controlled(qtbot):
    view = TimelineView()
    qtbot.addWidget(view)
    pool = Mock()
    view._thread_pool = pool
    view.set_events(
        [Event(id=str(i), name=f"Event {i}", lore_date=i / 8) for i in range(50)]
    )
    assert pool.start.call_count == 1
    return view, pool


def finish(view, worker):
    assignments, heights = pack_timeline_intervals(worker.intervals)
    view._on_layout_finished(worker.request_token, assignments, heights, 0.01)


def test_pure_packing_stable_ties_and_variable_heights():
    intervals = (
        TimelineLayoutInput("a", -1.5, 0, 20),
        TimelineLayoutInput("b", -1.5, 0.125, 30),
        TimelineLayoutInput("c", 0, 0.25, 40),
    )
    assert pack_timeline_intervals(intervals) == ({"a": 0, "b": 1, "c": 0}, [40, 30])
    assert pack_timeline_intervals(()) == ({}, [])


def test_measured_inputs_are_detached(qapp, monkeypatch):
    event = Event(id="a", name="A", lore_date=-0.125, lore_duration=0.25)
    packer = TimelineLanePacker(20)
    intervals = packer.measure_events([event])
    expected = packer.pack_events([event])
    event.name = "Changed"
    event.lore_date = 300
    monkeypatch.setattr(EventItem, "_calendar_converter", object())
    assert pack_timeline_intervals(intervals) == expected
    assert set(dataclasses.asdict(intervals[0])) == {
        "event_id",
        "start",
        "end",
        "height",
    }
    with pytest.raises(dataclasses.FrozenInstanceError):
        intervals[0].start = 10


def test_latest_request_coalesces_and_ignores_obsolete_callbacks(controlled):
    view, pool = controlled
    old = view._layout_worker
    apply = Mock(wraps=view._apply_layout_results)
    view._apply_layout_results = apply
    for zoom in (2, 3, 4):
        view._apply_zoom(zoom)
    assert pool.start.call_count == 1
    finish(view, old)
    assert not apply.called
    assert pool.start.call_count == 2
    latest = view._layout_worker
    finish(view, old)
    view._on_layout_error(old.request_token, "obsolete")
    assert view._layout_worker is latest
    assert view._layout_in_progress
    finish(view, latest)
    assert apply.call_count == 1
    assert not view._layout_in_progress
    assert latest.intervals == view._lane_packer.measure_events(view.events)


@pytest.mark.parametrize("count", [0, 1])
@pytest.mark.parametrize("error", [False, True])
def test_stale_completion_redispatches_current_threshold(controlled, count, error):
    view, pool = controlled
    old = view._layout_worker
    view.set_events(view.events[:count])
    expected = {key: item.pos() for key, item in view._event_items.items()}
    if error:
        view._on_layout_error(old.request_token, "obsolete")
    else:
        finish(view, old)
    assert pool.start.call_count == 1
    assert not view._layout_in_progress
    assert {key: item.pos() for key, item in view._event_items.items()} == expected
    assert len(view._drop_lines) == count


def test_current_error_falls_back_to_fresh_sync_layout(controlled):
    view, pool = controlled
    worker = view._layout_worker
    view._on_layout_error(worker.request_token, "failed")
    assert not view._layout_in_progress
    assert pool.start.call_count == 1
    assert all(item.y() >= view.RULER_HEIGHT for item in view._event_items.values())


def test_calendar_change_invalidates_active_result(controlled):
    view, pool = controlled
    old = view._layout_worker
    view.set_ruler_calendar(None)
    finish(view, old)
    assert pool.start.call_count == 2
    assert view._layout_worker is not old


def test_worker_returns_token_and_only_packs_records(qapp):
    worker = LayoutWorker([TimelineLayoutInput("a", 0, 1, 20)], 42)
    finished = Mock()
    worker.signals.finished.connect(finished)
    worker.run()
    finished.assert_called_once_with(42, {"a": 0}, [20], pytest.approx(0, abs=1))


def test_worker_failure_retains_token(qapp, monkeypatch):
    worker = LayoutWorker([], 42)
    error = Mock()
    worker.signals.error.connect(error)
    monkeypatch.setattr(
        "src.gui.workers.layout_worker.pack_timeline_intervals",
        Mock(side_effect=ValueError("failed")),
    )
    worker.run()
    error.assert_called_once_with(42, "failed")


def test_actual_worker_delivery_applies_scene_on_gui_thread(qtbot):
    view = TimelineView()
    qtbot.addWidget(view)
    threads = []
    apply = view._apply_layout_results

    def record(assignments, heights):
        threads.append(QThread.currentThread())
        apply(assignments, heights)

    view._apply_layout_results = record
    view.set_events([Event(name=str(i), lore_date=i) for i in range(50)])
    qtbot.waitUntil(lambda: not view._layout_in_progress)
    assert threads and all(thread == view.thread() for thread in threads)


def test_replacement_reuses_selected_item_and_removes_guides(qtbot):
    view = TimelineView()
    qtbot.addWidget(view)
    a = Event(id="a", name="A", lore_date=0)
    b = Event(id="b", name="B", lore_date=1)
    view.set_events([a, b])
    item = view._event_items["a"]
    item.setSelected(True)
    view.set_events([Event(id="a", name="Updated", lore_date=-0.25)])
    assert view._event_items == {"a": item}
    assert item.isSelected()
    assert set(view._drop_lines) == {"a"}


class CachedGroups:
    def __init__(self, view):
        self.view = view

    def get_group_metadata(self, tag_order, date_range=None):
        return build_group_metadata(self.view.events, tag_order, {}, date_range)

    def get_events_for_group(self, tag_name, date_range=None):
        return events_for_group(self.view.events, tag_name, date_range)


@pytest.mark.parametrize("mode,copies", [("DUPLICATE", 2), ("FIRST_MATCH", 1)])
def test_grouped_transition_ignores_pending_standard_layout(controlled, mode, copies):
    view, pool = controlled
    old = view._layout_worker
    view.events[0].tags = ["Alpha", "Beta"]
    view.set_data_provider(CachedGroups(view))
    view.set_grouping_config(["Alpha", "Beta"], mode)
    before = [item.pos() for item in view._duplicate_event_items]
    assert len(before) == copies
    finish(view, old)
    assert [item.pos() for item in view._duplicate_event_items] == before
    assert pool.start.call_count == 1
    view._band_manager._on_collapse_requested("Alpha")
    assert view._band_manager.get_band("Alpha").is_collapsed
    view.clear_grouping()
    assert not view._duplicate_event_items
    assert pool.start.call_count == 2
    finish(view, view._layout_worker)


def test_deleting_final_events_invalidates_worker_and_stops_timer(controlled):
    view, pool = controlled
    old = view._layout_worker
    view.apply_event_effects([effect(delete=event.id) for event in view.events])
    assert not view.events
    assert not view._event_items
    assert not view._drop_lines
    assert not view._incremental_layout_timer.isActive()
    finish(view, old)
    assert pool.start.call_count == 1


def test_preview_change_invalidates_worker(controlled):
    view, pool = controlled
    old = view._layout_worker
    view.update_event_preview({"id": "0", "name": "A much longer preview"})
    finish(view, old)
    assert pool.start.call_count == 2
    assert view._layout_worker.request_token != old.request_token
    assert view._event_items["0"].event.name == "A much longer preview"
    # The date caption can remain wider than either name; equal measured bounds
    # do not imply that a stale request was accepted.


def test_stale_completion_consumes_pending_debounce(controlled):
    view, pool = controlled
    old = view._layout_worker
    view.apply_event_effects([effect(Event(id="0", name="Changed", lore_date=20))])
    assert view._incremental_layout_timer.isActive()
    finish(view, old)
    assert not view._incremental_layout_timer.isActive()
    assert pool.start.call_count == 2
    finish(view, view._layout_worker)
    assert not view._layout_in_progress


def test_batch_missing_delete_keeps_one_debounced_layout(qtbot):
    view = TimelineView()
    qtbot.addWidget(view)
    view.set_events([Event(id="a", name="A", lore_date=0)])
    calls = Mock(wraps=view._repack_events_sync)
    view._repack_events_sync = calls
    view.apply_event_effects(
        [effect(Event(id="a", name="Moved", lore_date=1)), effect(delete="missing")]
    )
    qtbot.waitUntil(lambda: calls.call_count == 1)
    assert calls.call_count == 1
    assert view._event_items["a"].x() == view.scale_factor


def test_metadata_refresh_updates_group_duplicates_without_repack(qtbot):
    view = TimelineView()
    qtbot.addWidget(view)
    event = Event(id="a", name="A", lore_date=0)
    event.tags = ["Alpha"]
    view.set_events([event])
    view.set_data_provider(CachedGroups(view))
    view.set_grouping_config(["Alpha"])
    duplicate = view._duplicate_event_items[0]
    changed = Event.from_dict(event.to_dict())
    changed.description = "New prose"
    view.apply_event_effects([effect(changed)])
    assert view._duplicate_event_items == [duplicate]
    assert duplicate.event.description == "New prose"
    assert not view._incremental_layout_timer.isActive()
