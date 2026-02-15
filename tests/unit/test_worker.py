from unittest.mock import MagicMock, patch

import pytest

from src.commands.base_command import CommandResult
from src.services.worker import DatabaseWorker


@pytest.fixture
def mock_db_service():
    with patch("src.services.worker.DatabaseService") as MockDB:
        mock_instance = MockDB.return_value
        mock_instance.get_all_events.return_value = ["event1", "event2"]
        mock_instance.get_all_entities.return_value = ["entity1"]
        mock_instance.get_all_maps.return_value = ["map1"]
        mock_instance.get_markers_for_map.return_value = ["marker1"]
        mock_instance.get_current_time.return_value = 100.5
        mock_instance._attachment_repo = MagicMock()
        yield mock_instance


@pytest.fixture
def mock_asset_store():
    with patch("src.services.worker.AssetStore") as MockStore:
        yield MockStore.return_value


@pytest.fixture
def mock_attachment_service():
    with patch("src.services.worker.AttachmentService") as MockAtt:
        yield MockAtt.return_value


@pytest.fixture
def worker(mock_db_service, mock_asset_store, mock_attachment_service):
    # Initialize worker without calling initialize_db automatically in fixture
    # unless we want to test loaded state.
    worker = DatabaseWorker("test.db")
    return worker


def test_initialization(
    worker, mock_db_service, mock_asset_store, mock_attachment_service
):
    # Setup spies
    init_spy = MagicMock()
    start_spy = MagicMock()
    finish_spy = MagicMock()

    worker.initialized.connect(init_spy)
    worker.operation_started.connect(start_spy)
    worker.operation_finished.connect(finish_spy)

    worker.initialize_db()

    init_spy.assert_called_once_with(True)
    assert worker.db_service is not None
    assert worker.asset_store is not None
    assert worker.attachment_service is not None


def test_initialization_failure(worker):
    with patch(
        "src.services.worker.DatabaseService",
        side_effect=Exception("Connection failed"),
    ):
        init_spy = MagicMock()
        error_spy = MagicMock()

        worker.initialized.connect(init_spy)
        worker.error_occurred.connect(error_spy)

        worker.initialize_db()

        init_spy.assert_called_once_with(False)
        error_spy.assert_called_once()


def test_load_events(worker, mock_db_service):
    worker.db_service = mock_db_service  # Inject mocked service manually

    spy = MagicMock()
    worker.events_loaded.connect(spy)

    worker.load_events()

    mock_db_service.get_all_events.assert_called_once()
    spy.assert_called_once_with(["event1", "event2"])


def test_load_entities(worker, mock_db_service):
    worker.db_service = mock_db_service

    spy = MagicMock()
    worker.entities_loaded.connect(spy)

    worker.load_entities()

    mock_db_service.get_all_entities.assert_called_once()
    spy.assert_called_once_with(["entity1"])


def test_run_command_success(worker, mock_db_service):
    worker.db_service = mock_db_service

    command = MagicMock()
    command.__class__.__name__ = "TestCommand"
    command.execute.return_value = True  # Returns bool success

    finished_spy = MagicMock()
    worker.command_finished.connect(finished_spy)

    worker.run_command(command)

    command.execute.assert_called_once_with(mock_db_service)
    finished_spy.assert_called_once()
    result = finished_spy.call_args[0][0]
    assert isinstance(result, CommandResult)
    assert result.success is True
    assert result.command_name == "TestCommand"


def test_run_command_failure(worker, mock_db_service):
    worker.db_service = mock_db_service

    command = MagicMock()
    command.__class__.__name__ = "FailCommand"
    command.execute.side_effect = Exception("Boom")

    finished_spy = MagicMock()
    error_spy = MagicMock()
    worker.command_finished.connect(finished_spy)
    worker.error_occurred.connect(error_spy)

    worker.run_command(command)

    error_spy.assert_called_once()
    finished_spy.assert_called_once()
    result = finished_spy.call_args[0][0]
    assert result.success is False
    assert "unexpected error" in result.message


def test_load_current_time(worker, mock_db_service):
    worker.db_service = mock_db_service

    spy = MagicMock()
    worker.current_time_loaded.connect(spy)

    worker.load_current_time()

    mock_db_service.get_current_time.assert_called_once()
    spy.assert_called_once_with(100.5)


def test_save_current_time(worker, mock_db_service):
    worker.db_service = mock_db_service

    worker.save_current_time(200.0)

    mock_db_service.set_current_time.assert_called_once_with(200.0)


def test_load_event_details_not_found_emits_signal(worker, mock_db_service):
    """Worker should emit event_not_found when the event doesn't exist."""
    worker.db_service = mock_db_service
    mock_db_service.get_event.return_value = None

    spy = MagicMock()
    worker.event_not_found.connect(spy)

    worker.load_event_details("evt-deleted")

    spy.assert_called_once_with("evt-deleted")


def test_load_event_details_found_emits_details(worker, mock_db_service):
    """Worker should emit event_details_loaded when event exists."""
    worker.db_service = mock_db_service
    mock_event = MagicMock()
    mock_event.id = "evt-123"
    mock_db_service.get_event.return_value = mock_event
    mock_db_service.get_relations.return_value = []
    mock_db_service.get_incoming_relations.return_value = []

    found_spy = MagicMock()
    not_found_spy = MagicMock()
    worker.event_details_loaded.connect(found_spy)
    worker.event_not_found.connect(not_found_spy)

    worker.load_event_details("evt-123")

    found_spy.assert_called_once()
    not_found_spy.assert_not_called()


def test_load_entity_details_not_found_emits_signal(worker, mock_db_service):
    """Worker should emit entity_not_found when the entity doesn't exist."""
    worker.db_service = mock_db_service
    mock_db_service.get_entity.return_value = None

    spy = MagicMock()
    worker.entity_not_found.connect(spy)

    worker.load_entity_details("ent-deleted")

    spy.assert_called_once_with("ent-deleted")


def test_load_entity_details_found_emits_details(worker, mock_db_service):
    """Worker should emit entity_details_loaded when entity exists."""
    worker.db_service = mock_db_service
    mock_entity = MagicMock()
    mock_entity.id = "ent-456"
    mock_db_service.get_entity.return_value = mock_entity
    mock_db_service.get_relations.return_value = []
    mock_db_service.get_incoming_relations.return_value = []

    found_spy = MagicMock()
    not_found_spy = MagicMock()
    worker.entity_details_loaded.connect(found_spy)
    worker.entity_not_found.connect(not_found_spy)

    worker.load_entity_details("ent-456")

    found_spy.assert_called_once()
    not_found_spy.assert_not_called()
