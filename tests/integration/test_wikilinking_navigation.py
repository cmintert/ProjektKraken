"""
Integration test for WikiLink navigation in MainWindow.
"""

from unittest.mock import MagicMock

from src.app.main import MainWindow
from src.core.entities import Entity


def test_navigate_to_entity_success(qtbot):
    """Test navigation to an existing entity."""
    from unittest.mock import patch

    with (
        patch("src.app.worker_manager.DatabaseWorker"),
        patch("src.app.main_window.QTimer"),
        patch("src.app.worker_manager.QThread"),
    ):
        window = MainWindow()
        # Mock worker
        window.worker = MagicMock()

        # Setup cache
        target_entity = Entity(id="ent-1", name="Gandalf", type="Character")
        window.data_coordinator._cached_entities = [target_entity]

        # Mock load method on data_coordinator
        window.data_coordinator.load_entity_details = MagicMock()

        # Execute
        window.navigation_coordinator.navigate_to_entity("Gandalf")

        # Verify
        window.data_coordinator.load_entity_details.assert_called_once_with("ent-1")

        window.close()


def test_navigate_to_entity_case_insensitive(qtbot):
    """Test case-insensitive lookup."""
    from unittest.mock import patch

    with (
        patch("src.app.worker_manager.DatabaseWorker"),
        patch("src.app.main_window.QTimer"),
        patch("src.app.worker_manager.QThread"),
    ):
        window = MainWindow()
        window.worker = MagicMock()
        window.data_coordinator._cached_entities = [Entity(id="ent-1", name="Gandalf", type="Character")]
        window.data_coordinator.load_entity_details = MagicMock()

        window.navigation_coordinator.navigate_to_entity("gAnDaLf")

        window.data_coordinator.load_entity_details.assert_called_once_with("ent-1")
        window.close()


def test_navigate_to_entity_not_found(qtbot, monkeypatch):
    """Test behavior when entity is not found."""
    from unittest.mock import patch

    with (
        patch("src.app.worker_manager.DatabaseWorker"),
        patch("src.app.main_window.QTimer"),
        patch("src.app.worker_manager.QThread"),
    ):
        window = MainWindow()
        window.worker = MagicMock()
        window.data_coordinator._cached_entities = []
        window.data_coordinator._cached_events = []  # Also need to mock events cache
        window.data_coordinator.load_entity_details = MagicMock()

        # Mock the _prompt_create_missing_target method to prevent blocking dialog
        mock_prompt = MagicMock()
        window.navigation_coordinator._prompt_create_missing_target = mock_prompt

        window.navigation_coordinator.navigate_to_entity("Unknown")

        window.data_coordinator.load_entity_details.assert_not_called()
        mock_prompt.assert_called_once_with("Unknown")

        window.close()
