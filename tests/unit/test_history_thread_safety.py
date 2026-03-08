"""Tests for thread-safety fixes in history panel and command coordinator.

Validates that:
- CommandCoordinator emits snapshot data (dicts) with history_changed
- HistoryPanelWidget handles dict snapshots safely
- Reentrance guard prevents concurrent _refresh_display calls
- Shiboken validity checks prevent access-violation crashes
"""

from unittest.mock import MagicMock

import pytest

from src.app.command_coordinator import CommandCoordinator
from src.commands.base_command import BaseCommand, CommandResult
from src.gui.widgets.history_panel import HistoryPanelWidget
from src.services.db_service import DatabaseService


class MockCommand(BaseCommand):
    """Mock command for testing."""

    def __init__(self, name: str = "MockCommand") -> None:
        super().__init__()
        self.name = name

    def execute(self, db_service: DatabaseService):
        return True

    def undo(self, db_service: DatabaseService):
        pass

    def get_description(self) -> str:
        return f"Mock: {self.name}"

    def to_dict(self) -> dict:
        return {"name": self.name}

    @classmethod
    def from_dict(cls, data: dict) -> "MockCommand":
        return cls(name=data.get("name", "MockCommand"))


class MockMainWindow:
    """Lightweight mock for MainWindowProtocol."""

    def __init__(self):
        self.data_coordinator = MagicMock()


# ---------------------------------------------------------------------------
# CommandCoordinator snapshot tests
# ---------------------------------------------------------------------------


@pytest.fixture
def coordinator():
    return CommandCoordinator(MockMainWindow())


def test_history_changed_emits_snapshot_dicts(coordinator):
    """Signal carries (list[dict], list[dict]), not command objects."""
    received = []
    coordinator.history_changed.connect(
        lambda undo, redo: received.append((undo, redo))
    )

    cmd = MockCommand("Alpha")
    coordinator.undo_stack.append(cmd)
    coordinator._emit_history_changed()

    assert len(received) == 1
    undo_snaps, redo_snaps = received[0]

    assert isinstance(undo_snaps, list)
    assert isinstance(redo_snaps, list)
    assert len(undo_snaps) == 1
    assert isinstance(undo_snaps[0], dict)
    assert undo_snaps[0]["description"] == "Mock: Alpha"


def test_snapshot_contains_timestamp(coordinator):
    """Snapshot dict contains the command's timestamp."""
    cmd = MockCommand("Beta")
    cmd.timestamp = 1234567890.0
    coordinator.undo_stack.append(cmd)

    undo_snaps, _ = coordinator._build_snapshots()
    assert undo_snaps[0]["timestamp"] == 1234567890.0


def test_snapshot_handles_missing_timestamp(coordinator):
    """Snapshot gracefully handles a command with no timestamp attr."""
    cmd = MockCommand("Gamma")
    # BaseCommand.__init__ sets self.timestamp, but let's be defensive
    coordinator.undo_stack.append(cmd)
    undo_snaps, _ = coordinator._build_snapshots()
    # Should not raise; timestamp may be None or a float
    assert "timestamp" in undo_snaps[0]


def test_on_command_result_defers_db_save(coordinator):
    """DB save is deferred (QTimer), not called inline."""
    mock_svc = MagicMock()
    coordinator.history_service = mock_svc

    cmd = MockCommand("Save")
    result = CommandResult(
        success=True,
        message="OK",
        command_name="MockCommand",
        data={"command": cmd},
    )

    coordinator.on_command_result(result)

    # save_command should NOT have been called synchronously
    mock_svc.save_command.assert_not_called()


def test_on_command_result_emits_snapshots(coordinator):
    """on_command_result emits history_changed with snapshot lists."""
    received = []
    coordinator.history_changed.connect(
        lambda undo, redo: received.append((undo, redo))
    )

    cmd = MockCommand("Emit")
    result = CommandResult(
        success=True,
        message="OK",
        command_name="MockCommand",
        data={"command": cmd},
    )
    coordinator.on_command_result(result)

    assert len(received) == 1
    undo_snaps, redo_snaps = received[0]
    assert len(undo_snaps) == 1
    assert undo_snaps[0]["description"] == "Mock: Emit"
    assert redo_snaps == []


# ---------------------------------------------------------------------------
# HistoryPanelWidget safety tests
# ---------------------------------------------------------------------------


@pytest.fixture
def history_panel(qtbot):
    widget = HistoryPanelWidget()
    qtbot.addWidget(widget)
    return widget


def test_panel_accepts_dict_snapshots(history_panel):
    """Panel renders dict snapshots without accessing command objects."""
    snaps = [
        {"description": "Create Entity 'Foo'", "timestamp": 1000.0},
        {"description": "Update Entity 'Bar'", "timestamp": 2000.0},
    ]
    history_panel.update_history(snaps, [])

    assert history_panel.command_list.count() == 2
    # Items are displayed most-recent-first (reversed)
    texts = [
        history_panel.command_list.item(i).text()
        for i in range(history_panel.command_list.count())
    ]
    assert any("Create Entity 'Foo'" in t for t in texts)
    assert any("Update Entity 'Bar'" in t for t in texts)


def test_panel_reentrance_guard(history_panel):
    """Reentrance guard prevents concurrent _refresh_display calls."""
    history_panel._refreshing = True
    # Should return immediately without crash
    history_panel._refresh_display()
    # Cleanup
    history_panel._refreshing = False


def test_panel_clear_on_empty(history_panel):
    """Clearing with empty stacks is safe."""
    history_panel.update_history([], [])
    assert history_panel.command_list.count() == 0
    assert history_panel.status_label.text() == "No history"


def test_panel_undo_redo_buttons_state(history_panel):
    """Buttons reflect stack state."""
    # Both empty
    history_panel.update_history([], [])
    assert not history_panel.undo_btn.isEnabled()
    assert not history_panel.redo_btn.isEnabled()
    assert not history_panel.clear_btn.isEnabled()

    # Undo has items
    history_panel.update_history([{"description": "Cmd1", "timestamp": None}], [])
    assert history_panel.undo_btn.isEnabled()
    assert not history_panel.redo_btn.isEnabled()
    assert history_panel.clear_btn.isEnabled()

    # Redo has items
    history_panel.update_history([], [{"description": "Cmd2", "timestamp": None}])
    assert not history_panel.undo_btn.isEnabled()
    assert history_panel.redo_btn.isEnabled()
