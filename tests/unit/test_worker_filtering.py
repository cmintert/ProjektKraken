from unittest.mock import MagicMock

import pytest

from src.core.entities import Entity
from src.core.events import Event
from src.services.worker import DatabaseWorker


@pytest.mark.unit
class TestWorkerFiltering:
    """Tests for Worker filter orchestration."""

    @pytest.fixture
    def worker(self):
        """Creates a worker with a mocked db_service."""
        db_mock = MagicMock()
        worker = DatabaseWorker("dummy.db")
        worker.db_service = db_mock  # Inject mock specifically
        return worker

    def test_apply_filter_flow(self, worker):
        """
        Test that apply_filter calls filter_ids_by_tags then get_objects_by_ids,
        and finally emits the results.
        """
        # mocks
        mock_config = {
            "include": ["tag1"],
            "include_mode": "any",
            "exclude": ["tag2"],
            "exclude_mode": "all",
        }

        # db returns some IDs
        mock_ids = [("event", "ev1"), ("entity", "en1")]
        worker.db_service.filter_ids_by_tags.return_value = mock_ids

        # db hydrates them
        mock_events = [Event(name="Ev1", lore_date=0.0)]
        mock_entities = [Entity(name="En1", type="char")]
        worker.db_service.get_objects_by_ids.return_value = (mock_events, mock_entities)

        # Mock signal
        worker.filter_results_ready = MagicMock()

        # Act
        worker.apply_filter(mock_config)

        # Verify DB calls
        worker.db_service.filter_ids_by_tags.assert_called_once_with(
            object_type=None,
            include=["tag1"],
            include_mode="any",
            exclude=["tag2"],
            exclude_mode="all",
            case_sensitive=False,
        )

        worker.db_service.get_objects_by_ids.assert_called_once_with(mock_ids)

        # Verify Signal emission
        # Signals in PySide are tricky to mock directly if they are class attributes
        # But commonly in unit tests without QObject/QApp, we might need a spy or
        # just check if the method logic flow is correct.
        # However, the Worker inherits from QObject.
        # For unit testing logic without spinning up QApp, we can inspect
        # if the code attempted to emit.

        worker.filter_results_ready.emit.assert_called_once_with(
            mock_events, mock_entities
        )

    def test_apply_filter_empty_config_passes_none(self, worker):
        """Test defaults are handled (passed as None to DB)."""
        worker.db_service.filter_ids_by_tags.return_value = []
        worker.db_service.get_objects_by_ids.return_value = ([], [])
        worker.filter_results_ready = MagicMock()

        worker.apply_filter({})

        worker.db_service.filter_ids_by_tags.assert_called_once_with(
            object_type=None,
            include=None,
            include_mode="any",
            exclude=None,
            exclude_mode="any",
            case_sensitive=False,
        )
