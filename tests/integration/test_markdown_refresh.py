"""Refresh and lazy-panel boundaries for imports through Transfer."""

from unittest.mock import MagicMock, Mock

import pytest
from PySide6.QtWidgets import QWidget

from src.app.coordinators.data_coordinator import DataCoordinator
from src.app.coordinators.transfer_coordinator import TransferCoordinator
from src.core.command import CommandResult
from src.services.worker import DatabaseWorker


@pytest.fixture
def import_completion(qtbot, tmp_path):
    parent = QWidget()
    qtbot.addWidget(parent)
    worker = DatabaseWorker(str(tmp_path / "world.kraken"), {})
    refresh = Mock()
    coordinator = TransferCoordinator(
        parent, worker, dict, Mock(), lambda: True, refresh, list, {}
    )
    coordinator.dialog = MagicMock()
    coordinator._command_id = "reviewed-import"
    coordinator._preview = {"delta": []}
    return worker, coordinator, refresh


class TestMarkdownImportRefresh:
    def test_successful_import_calls_load_data(self, import_completion, qtbot):
        worker, coordinator, refresh = import_completion
        result = CommandResult(True, data={"transfer_id": "reviewed-import"})

        worker.command_finished.emit(result)
        qtbot.waitUntil(lambda: refresh.call_count == 1)

        coordinator.dialog.show_result.assert_called_once()

    def test_failed_import_does_not_refresh(self, import_completion, qtbot):
        worker, coordinator, refresh = import_completion
        result = CommandResult(
            False, "Import rejected", data={"transfer_id": "reviewed-import"}
        )

        worker.command_finished.emit(result)
        qtbot.waitUntil(lambda: coordinator.dialog.status.setText.called)

        coordinator.dialog.status.setText.assert_called_once_with("Import rejected")
        refresh.assert_not_called()


@pytest.fixture
def data_refresh(qtbot, monkeypatch):
    window = QWidget()
    qtbot.addWidget(window)
    window.worker = Mock()
    window.event_editor = Mock(
        _current_event_id="open-event", current_event_id="open-event"
    )
    window.entity_editor = Mock(
        _current_entity_id="open-entity", current_entity_id="open-entity"
    )
    coordinator = DataCoordinator(window)
    queue = Mock()
    monkeypatch.setattr("src.app.coordinators.data_coordinator.invoke_queued", queue)
    return coordinator, queue


class TestImportRefreshDepth:
    def test_refresh_after_import_calls_core_loaders(self, data_refresh):
        coordinator, queue = data_refresh

        coordinator.load_data()

        requested = [call.args[1] for call in queue.call_args_list]
        assert requested[:2] == ["load_events", "load_entities"]
        assert "load_event_details" in requested
        assert "load_entity_details" in requested

    def test_refresh_after_import_does_not_call_longform(self, data_refresh):
        coordinator, queue = data_refresh

        coordinator.load_data()

        requested = [call.args[1] for call in queue.call_args_list]
        assert "load_longform_sequence" not in requested
