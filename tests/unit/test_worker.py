from unittest.mock import MagicMock, patch

import pytest

from src.commands.base_command import CommandResult
from src.commands.entity_commands import CreateEntityCommand
from src.commands.registry import get_command_types
from src.core.temporal_state import ResolvedEntityState
from src.services.worker import DatabaseWorker


@pytest.fixture
def mock_db_service():
    with patch("src.services.worker.DatabaseService") as MockDB:
        mock_instance = MockDB.return_value
        mock_instance.get_all_events.return_value = ["event1", "event2"]
        mock_instance.get_all_entities.return_value = ["entity1"]
        mock_instance.get_all_maps.return_value = ["map1"]
        mock_instance.get_markers_for_map.return_value = ["marker1"]
        mock_instance.get_trajectory_snapshots_by_map.return_value = [
            {"marker_id": "marker1", "trajectory_id": "trajectory1"}
        ]
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
    worker = DatabaseWorker("test.db", get_command_types())
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


def test_analysis_command_requires_initialized_database(worker):
    """Analysis reports a lifecycle error without executing the command."""
    command = MagicMock()
    result_signal = MagicMock()
    start_spy = MagicMock()
    finish_spy = MagicMock()
    error_spy = MagicMock()
    worker.operation_started.connect(start_spy)
    worker.operation_finished.connect(finish_spy)
    worker.error_occurred.connect(error_spy)

    worker._run_analysis_command(
        command,
        result_signal,
        "Validating world…",
        "Validation complete.",
        "Validation",
    )

    command.execute.assert_not_called()
    result_signal.emit.assert_not_called()
    start_spy.assert_called_once_with("Validating world…")
    error_spy.assert_called_once_with("Database not ready for validation.")
    finish_spy.assert_called_once_with("Validation complete.")


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


def test_load_trajectories_emits_map_scoped_snapshots(worker, mock_db_service):
    """Trajectory loads cross threads as map-scoped serializable values."""
    worker.db_service = mock_db_service
    spy = MagicMock()
    worker.trajectories_loaded.connect(spy)

    worker.load_trajectories("map1")

    mock_db_service.get_trajectory_snapshots_by_map.assert_called_once_with("map1")
    spy.assert_called_once_with(
        "map1", [{"marker_id": "marker1", "trajectory_id": "trajectory1"}]
    )


def test_run_command_success(worker, mock_db_service):
    worker.db_service = mock_db_service

    command = CreateEntityCommand({"name": "Test", "type": "Concept"})
    request = {
        "type": command.__class__.__name__,
        "data": command.to_dict(),
        "base": command.base_state_dict(),
    }

    finished_spy = MagicMock()
    worker.command_finished.connect(finished_spy)

    worker.run_command(request)

    mock_db_service.insert_entity.assert_called_once()
    finished_spy.assert_called_once()
    result = finished_spy.call_args[0][0]
    assert isinstance(result, CommandResult)
    assert result.success is True
    assert result.command_name == "CreateEntityCommand"


def test_run_command_failure(worker, mock_db_service):
    worker.db_service = mock_db_service

    command = CreateEntityCommand({"name": "Test", "type": "Concept"})
    request = {
        "type": command.__class__.__name__,
        "data": command.to_dict(),
        "base": command.base_state_dict(),
    }
    mock_db_service.insert_entity.side_effect = Exception("Boom")

    finished_spy = MagicMock()
    error_spy = MagicMock()
    worker.command_finished.connect(finished_spy)
    worker.error_occurred.connect(error_spy)

    worker.run_command(request)

    error_spy.assert_not_called()
    finished_spy.assert_called_once()
    result = finished_spy.call_args[0][0]
    assert result.success is False
    assert "Boom" in result.message


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


def test_resolve_entity_state_emits_serialized_snapshot(worker):
    worker.temporal_manager = MagicMock()
    worker.temporal_manager.get_entity_state_at.return_value = ResolvedEntityState(
        entity_id="entity-1",
        description="Resolved description",
        attributes={"status": "Ruined"},
    )
    spy = MagicMock()
    worker.entity_state_resolved.connect(spy)

    worker.resolve_entity_state("entity-1", 736.0)

    spy.assert_called_once_with(
        "entity-1",
        {
            "entity_id": "entity-1",
            "description": "Resolved description",
            "attributes": {"status": "Ruined"},
        },
    )
