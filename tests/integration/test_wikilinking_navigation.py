"""
Integration test for WikiLink navigation in MainWindow.
"""

from unittest.mock import MagicMock

from src.app.main import MainWindow
from src.core.entities import Entity


def test_navigate_to_entity_success(qtbot):
    """Test navigation to an existing entity."""
    from unittest.mock import patch

    from PySide6.QtWidgets import QMessageBox

    with (
        patch("src.app.main_window.DatabaseWorker"),
        patch("src.app.main_window.QTimer"),
        patch("src.app.main_window.QThread"),
        patch("src.app.main_window.QMessageBox.warning", return_value=QMessageBox.Discard),
    ):
        window = MainWindow()
        # Mock worker
        window.worker = MagicMock()

        # Setup cache
        target_entity = Entity(id="ent-1", name="Gandalf", type="Character")
        window._cached_entities = [target_entity]

        # Mock load method
        window.load_entity_details = MagicMock()

        # Execute
        window.navigate_to_entity("Gandalf")

        # Verify
        window.load_entity_details.assert_called_once_with("ent-1")

        window.close()


def test_navigate_to_entity_case_insensitive(qtbot):
    """Test case-insensitive lookup."""
    from unittest.mock import patch

    from PySide6.QtWidgets import QMessageBox

    with (
        patch("src.app.main_window.DatabaseWorker"),
        patch("src.app.main_window.QTimer"),
        patch("src.app.main_window.QThread"),
        patch("src.app.main_window.QMessageBox.warning", return_value=QMessageBox.Discard),
    ):
        window = MainWindow()
        window.worker = MagicMock()
        window._cached_entities = [Entity(id="ent-1", name="Gandalf", type="Character")]
        window.load_entity_details = MagicMock()

        window.navigate_to_entity("gAnDaLf")

        window.load_entity_details.assert_called_once_with("ent-1")
        window.close()


def test_navigate_to_entity_not_found(qtbot, monkeypatch):
    """Test behavior when entity is not found."""
    from unittest.mock import patch

    from PySide6.QtWidgets import QMessageBox

    with (
        patch("src.app.main_window.DatabaseWorker"),
        patch("src.app.main_window.QTimer"),
        patch("src.app.main_window.QThread"),
        patch("src.app.main_window.QMessageBox.warning", return_value=QMessageBox.Discard),
    ):
        window = MainWindow()
        window.worker = MagicMock()
        window._cached_entities = []
        window._cached_events = []  # Also need to mock events cache
        window.load_entity_details = MagicMock()

        # Mock the _prompt_create_missing_target method to prevent blocking dialog
        mock_prompt = MagicMock()
        window._prompt_create_missing_target = mock_prompt

        window.navigate_to_entity("Unknown")

        window.load_entity_details.assert_not_called()
        mock_prompt.assert_called_once_with("Unknown")

        window.close()
