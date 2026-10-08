"""Decision, acknowledgement and stale-result tests for map draft transitions."""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtTest import QTest

from src.app.coordinators.map_edit_transition_coordinator import (
    MapEditTransitionCoordinator,
)
from src.core.map import Map
from src.gui.dialogs.map_edit_transition_dialog import MapEditTransitionDialog
from src.gui.widgets.map_widget import MapWidget

pytestmark = pytest.mark.ci_fast


class Owner(QObject):
    transition_finished = Signal(dict)

    def __init__(self, *, dirty=True, new=False, can_apply=True):
        super().__init__()
        self.status = {
            "session_id": "session",
            "world_id": "world",
            "map_id": "map",
            "target_id": "target",
            "label": "Tasgillia's journey",
            "dirty": dirty,
            "new": new,
            "pending": False,
            "conflicted": False,
            "command_id": None,
            "can_apply": can_apply,
            "explanation": "Finish the second location before applying.",
        }
        self.applies = 0
        self.discards = 0

    def edit_status(self):
        return deepcopy(self.status)

    def apply_for_transition(self):
        self.applies += 1
        self.status.update(pending=True, command_id="command")

    def discard_for_transition(self):
        self.discards += 1
        self.status = None

    def finish(self, *, success=True, command_id="command", session_id="session"):
        if success and command_id == "command" and session_id == "session":
            self.status = None
        elif not success:
            self.status.update(pending=False, command_id=None)
        self.transition_finished.emit(
            {
                "session_id": session_id,
                "command_id": command_id,
                "success": success,
            }
        )


def compose(owner, decision="keep"):
    decisions, messages, actions = [], [], []
    world = ["world"]

    def decide(reason, status):
        decisions.append((reason, status))
        return decision

    guard = MapEditTransitionCoordinator(
        [owner], lambda: world[0], decide, messages.append
    )
    return guard, decisions, messages, actions, world


@pytest.mark.parametrize(
    "reason",
    [
        "open another map",
        "edit another geometry target",
        "delete this feature",
        "delete this map",
        "select another world",
        "restore the backup",
        "close Kraken",
    ],
)
@pytest.mark.parametrize("decision", ["keep", "discard", "apply"])
def test_all_transition_reasons_require_resolution(reason, decision):
    owner = Owner()
    guard, decisions, _messages, actions, _world = compose(owner, decision)
    guard.request_transition(reason, lambda: actions.append(reason))
    assert decisions[0][0] == reason
    if decision == "keep":
        assert actions == [] and owner.status is not None
    elif decision == "discard":
        assert actions == [reason] and owner.discards == 1 and owner.applies == 0
    else:
        assert actions == [] and owner.applies == 1 and guard.is_waiting
        owner.finish()
        assert actions == [reason] and not guard.is_waiting
        owner.finish()
        assert actions == [reason]


def test_clean_existing_edit_leaves_without_decision():
    owner = Owner(dirty=False)
    guard, decisions, _, actions, _ = compose(owner)
    guard.request_transition("leave", lambda: actions.append(True))
    assert decisions == [] and actions == [True] and owner.discards == 1


def test_new_draft_requires_decision_even_when_unchanged():
    owner = Owner(dirty=False, new=True)
    guard, decisions, _, actions, _ = compose(owner)
    guard.request_transition("leave", lambda: actions.append(True))
    assert len(decisions) == 1 and actions == [] and owner.status is not None


def test_invalid_apply_cannot_release_action():
    owner = Owner(can_apply=False)
    guard, _, _, actions, _ = compose(owner, "apply")
    guard.request_transition("leave", lambda: actions.append(True))
    assert actions == [] and owner.applies == 0 and not guard.is_waiting


def test_failure_and_unrelated_results_retain_draft_and_cancel_action():
    owner = Owner()
    guard, _, messages, actions, _ = compose(owner, "apply")
    guard.request_transition("leave", lambda: actions.append(True))
    owner.finish(command_id="unrelated")
    owner.finish(session_id="unrelated")
    assert guard.is_waiting and actions == []
    owner.finish(success=False)
    assert not guard.is_waiting and actions == [] and owner.status is not None
    assert messages


def test_first_pending_action_wins_and_world_change_invalidates_it():
    owner = Owner()
    owner.apply_for_transition()
    guard, decisions, messages, actions, world = compose(owner)
    guard.request_transition("first", lambda: actions.append("first"))
    guard.request_transition("second", lambda: actions.append("second"))
    assert decisions == [] and messages and guard.is_waiting
    world[0] = "different-world"
    owner.finish()
    assert actions == [] and not guard.is_waiting


def test_repeated_requests_do_not_replace_approved_destination():
    owner = Owner()
    guard, _, _, actions, _ = compose(owner, "apply")
    guard.request_transition("first", lambda: actions.append("first"))
    guard.request_transition("second", lambda: actions.append("second"))
    owner.finish()
    assert actions == ["first"]


def test_selector_keeps_accepted_identity_and_same_map_refresh(qtbot):
    widget = MapWidget()
    qtbot.addWidget(widget)
    maps = [
        Map(id="first", name="First", image_path="a.png"),
        Map(id="second", name="Second", image_path="b.png"),
    ]
    widget.set_maps(maps)
    widget.select_map("first")
    owner = Owner()
    guard, decisions, _, _, _ = compose(owner)
    widget.edit_transition_handler = guard.request_transition
    accepted = []
    widget.map_selected.connect(accepted.append)
    widget.map_selector.setFocus()
    QTest.keyClick(widget.map_selector, Qt.Key.Key_Down)
    assert widget.get_selected_map_id() == "first"
    assert widget.map_selector.currentData() == "first" and accepted == []
    widget.set_maps(maps)
    widget.select_map("first")
    assert len(decisions) == 1 and accepted == []
    assert widget.get_selected_map_id() == "first"


@pytest.mark.parametrize(
    "button,decision",
    [
        ("apply_button", "apply"),
        ("keep_button", "keep"),
        ("discard_button", "discard"),
    ],
)
def test_enter_activates_focused_decision(qtbot, button, decision):
    dialog = MapEditTransitionDialog("open another map", Owner().status)
    qtbot.addWidget(dialog)
    dialog.show()
    control = getattr(dialog, button)
    control.setFocus()
    QTest.keyClick(control, Qt.Key.Key_Return)
    assert dialog.decision == decision


def test_escape_and_disabled_apply_keep_the_draft(qtbot):
    dialog = MapEditTransitionDialog("leave", Owner(can_apply=False).status)
    qtbot.addWidget(dialog)
    dialog.show()
    assert not dialog.apply_button.isEnabled()
    assert dialog.apply_button.toolTip()
    QTest.keyClick(dialog, Qt.Key.Key_Escape)
    assert dialog.decision == "keep"


@pytest.mark.parametrize("decision", ["keep", "discard", "apply"])
def test_close_event_is_ignored_until_guard_approves(qapp, monkeypatch, decision):
    from src.app.main_window import MainWindow

    owner = Owner()
    guard, _, _, _, _ = compose(owner, decision)
    callbacks = []
    monkeypatch.setattr(
        "src.app.main_window.QTimer.singleShot",
        lambda _delay, callback: callbacks.append(callback),
    )
    window = SimpleNamespace(
        backup_coordinator=SimpleNamespace(
            restore_in_progress=False, restore_shutdown_complete=False
        ),
        map_handler=SimpleNamespace(has_pending_raster_strokes=lambda: False),
        app_coordinator=SimpleNamespace(
            map_edits=guard,
            trajectory_edit=SimpleNamespace(is_active=True),
            feature_geometry=SimpleNamespace(is_active=False),
        ),
        close=Mock(),
        worker=Mock(),
    )
    event = QCloseEvent()
    MainWindow.closeEvent(window, event)
    assert not event.isAccepted()
    window.worker.cleanup.assert_not_called()
    if decision == "apply":
        assert callbacks == []
        owner.finish()
    if decision != "keep":
        assert len(callbacks) == 1
        callbacks[0]()
        window.close.assert_called_once()
    else:
        assert callbacks == []


def test_same_map_list_refresh_reloads_data_without_navigation_prompt(qtbot):
    from src.app.map_handler import MapHandler

    widget = MapWidget()
    qtbot.addWidget(widget)
    maps = [Map(id="first", name="First", image_path="a.png")]
    widget.set_maps(maps)
    widget.select_map("first")
    owner = Owner()
    guard, decisions, _, _, _ = compose(owner)
    widget.edit_transition_handler = guard.request_transition
    refreshed = []
    facade = SimpleNamespace(_map_widget=widget, on_map_selected=refreshed.append)
    MapHandler.on_maps_ready(facade, maps)
    assert refreshed == ["first"] and decisions == []
    assert widget.get_selected_map_id() == "first" and owner.status is not None
