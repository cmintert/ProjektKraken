"""Completed calculation, readable cascade review and guarded Apply/Cancel."""

import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel, QProgressDialog, QWidget

from src.app.coordinators.event_timing_coordinator import EventTimingCoordinator
from src.core.event_timing.definitions import EndpointDefinition, EventTimingDefinition
from src.core.events import Event
from src.core.theme_manager import ThemeManager
from src.gui.dialogs.event_timing_review_dialog import EventTimingReviewDialog

pytestmark = pytest.mark.ci_fast


def test_review_retains_clock_time_without_duplicate_dates():
    from src.core.calendar import CalendarConfig
    from src.services.event_timing.planning import TimingChangeRequest, prepare_change

    config = CalendarConfig.create_default()
    root = Event("March", 10.5, lore_duration=2, id="root")
    plan = prepare_change(
        {
            "world_id": "review-clock",
            "events": [root.to_dict()],
            "calendar": config.to_json(),
            "consumers": [],
        },
        TimingChangeRequest(updates={root.id: {"lore_date": 20.75}}),
    )
    assert not plan.errors
    change = plan.consequences[0]
    assert "12:00" in change["before_text"]
    assert "18:00" in change["after_text"]
    for key in ("before_text", "after_text"):
        assert change[key].count("Start:") == 1
        assert change[key].count("End:") == 1
        assert "Duration: 2 days" in change[key]
        assert "Timeline" not in change[key]


def test_calendar_review_uses_the_previous_calendar_for_before_dates():
    from src.core.calendar import CalendarConfig
    from src.services.event_timing.planning import TimingChangeRequest, prepare_change

    config = CalendarConfig.create_default()
    updated = CalendarConfig.from_json(config.to_json())
    updated.months[0].name = "Frost"
    root = Event("March", 10, id="root")
    plan = prepare_change(
        {
            "world_id": "review-calendar",
            "events": [root.to_dict()],
            "calendar": config.to_json(),
            "consumers": [],
        },
        TimingChangeRequest(
            updates={root.id: {"lore_date": 20}},
            calendar=updated.to_json(),
            calendar_changed=True,
        ),
    )
    assert not plan.errors
    change = plan.consequences[0]
    assert "January" in change["before_text"]
    assert "Frost" not in change["before_text"]
    assert "Frost" in change["after_text"]
    assert "00:00" not in change["after_text"]


def test_review_caption_retains_disjoint_strict_bounds():
    from src.core.event_timing.presentation import endpoint_caption

    caption = endpoint_caption(
        {
            "ranges": [("1/2", "3/2", False, True), ("5", "7", True, False)],
            "verified": True,
        },
        None,
        include_time=True,
    )
    assert caption == ("after 0.5 days; through 1.5 days or from 5 days; before 7 days")


@pytest.mark.parametrize("action", ["apply", "cancel", "world_change"])
def test_real_review_finishes_without_progress_overlap(
    qtbot, qapp, db_service, monkeypatch, action
):
    from src.commands.event_commands import UpdateEventCommand

    root = Event("March", 10, id="root")
    child = Event(
        "Battle",
        12,
        id="child",
        attributes=EventTimingDefinition(
            EndpointDefinition(
                "event", anchor_id="event:root", offset={"unit": "days", "value": 2}
            )
        ).apply({}),
    )
    for event in (root, child):
        db_service.insert_event(event)
    parent = QWidget()
    qtbot.addWidget(parent)
    parent.show()
    outgoing, failures, observed = [], [], []
    coordinator = EventTimingCoordinator(
        parent,
        qapp.thread(),
        lambda: db_service,
        lambda: db_service.db_path,
        outgoing.append,
    )
    coordinator.failed.connect(failures.append)
    native_exec = EventTimingReviewDialog.exec

    def review(dialog):
        def choose():
            observed.append(
                not any(
                    isinstance(widget, QProgressDialog) and widget.isVisible()
                    for widget in qapp.topLevelWidgets()
                )
            )
            if action == "apply":
                dialog.apply_button.click()
            elif action == "cancel":
                dialog.cancel_button.click()
            else:
                coordinator.cancel()

        QTimer.singleShot(350, dialog, choose)
        return native_exec(dialog)

    monkeypatch.setattr(EventTimingReviewDialog, "exec", review)
    try:
        assert coordinator.intercept(UpdateEventCommand(root.id, {"lore_date": 20}))
        qtbot.waitUntil(lambda: bool(outgoing or failures), timeout=5000)
        assert observed == [True]
        assert coordinator._progress is None
        assert coordinator._review_dialog is None
        assert coordinator._job == ""
        assert db_service.get_event(root.id).lore_date == 10
        if action == "apply":
            assert outgoing[0].execute(db_service).success
            assert db_service.get_event(child.id).lore_date == 22
        else:
            assert not outgoing
            assert len(failures) == 1
    finally:
        coordinator.shutdown()


@pytest.mark.parametrize(
    "theme",
    [
        "dark_mode",
        "light_mode",
        "fantasy_mode",
        "imperial_mode",
        "cyberpunk_mode",
        "muted_light_mode",
    ],
)
@pytest.mark.parametrize("width", [360, 680])
def test_review_wraps_visible_dates_and_actions(qtbot, theme, width):
    ThemeManager().set_theme(theme, persist=False)
    dialog = EventTimingReviewDialog(
        [
            {
                "kind": "event",
                "name": "The long winter council <draft> and the final treaty",
                "before_text": "Starts: after 1 January 1; before 9 January 1\nTimeline start: 3 January 1, 13:38",
                "after_text": "Starts: after 3 January 1; before 9 January 1\nTimeline start: 5 January 1, 13:38",
            }
        ]
        * 4
    )
    qtbot.addWidget(dialog)
    dialog.resize(width, 480)
    dialog.show()
    qtbot.wait(30)
    assert dialog.changes.horizontalScrollBar().maximum() == 0
    for button in (dialog.apply_button, dialog.cancel_button):
        assert button.isVisible()
        assert dialog.rect().contains(button.mapTo(dialog, button.rect().bottomRight()))
    for label in dialog.changes.findChildren(QLabel):
        assert label.textFormat() == Qt.TextFormat.PlainText
        assert label.height() >= label.heightForWidth(label.width())
    assert dialog.cancel_button.isDefault()
    qtbot.keyClick(dialog, Qt.Key.Key_Escape)
    assert not dialog.isVisible()


def test_review_help_keeps_event_timing_topic(qtbot):
    from src.app.coordinators.help_coordinator import HelpCoordinator
    from src.app.help_composition import HelpSurfaceBindings
    from src.gui.utils.help_context import HelpContextRegistry
    from src.services.help_bundle_service import HelpBundleService

    parent = QWidget()
    qtbot.addWidget(parent)
    registry = HelpContextRegistry()
    coordinator = HelpCoordinator(parent, registry, HelpBundleService())
    bindings = HelpSurfaceBindings(coordinator)
    dialog = EventTimingReviewDialog([], parent)
    qtbot.addWidget(dialog)
    for widget in [dialog, *dialog.findChildren(QWidget)]:
        bindings.bind(widget)
    topics, boundary = registry.candidates(dialog.apply_button)
    assert topics[0] == "event.timing"
    assert boundary is dialog
