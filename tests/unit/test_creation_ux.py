from unittest.mock import patch

import pytest

from src.app.main import MainWindow
from src.core.entities import Entity
from src.core.events import Event


@pytest.fixture
def main_window(qtbot):
    """Create MainWindow with mocked Worker."""
    from PySide6.QtWidgets import QMessageBox

    with patch("src.app.worker_manager.DatabaseWorker") as MockWorker:
        with (
            patch("src.app.worker_manager.QThread"),
            patch("src.app.main_window.QTimer"),
            patch(
                "src.app.main_window.QMessageBox.warning",
                return_value=QMessageBox.Discard,
            ),
        ):
            # Mock worker and DB
            mock_worker = MockWorker.return_value
            mock_worker.db_service.get_all_events.return_value = []

            window = MainWindow()
            # window.show()  # needed for visibility checks often
            qtbot.addWidget(window)
            yield window


def test_create_cancel_does_nothing(main_window):
    """Test cancelling creation."""
    with patch("src.app.main_window.QInputDialog.getText") as mock_input:
        mock_input.return_value = ("", False)

        with patch("src.app.main_window.CreateEntityCommand") as MockCmd:
            main_window.create_entity()
            MockCmd.assert_not_called()
            main_window.worker.run_command.assert_not_called()


def test_select_item_switches_filter_if_needed(main_window):
    """Verify that select_item switches selection if item is hidden."""
    # Use real objects to avoid MagicMock 'name' comparison issues
    test_entity = Entity(id="ent1", name="Entity 1", type="Concept")
    test_event = Event(id="evt1", name="Event 1", lore_date=10.0, type="generic")

    # Pre-populate
    main_window._cached_entities = [test_entity]
    main_window._cached_events = [test_event]

    # Set data on unified_list
    main_window.unified_list.set_data(
        main_window._cached_events, main_window._cached_entities
    )

    # 1. Set filter to "Entities Only"
    main_window.unified_list.filter_combo.setCurrentText("Entities Only")
    # Verify count - Entities Only shows entities
    assert main_window.unified_list.list_widget.count() == 1

    # 2. Select Event (which is hidden)
    # Patch list_widget.setCurrentItem to verify it gets called
    with patch.object(
        main_window.unified_list.list_widget, "setCurrentItem"
    ) as mock_set:
        with patch.object(main_window.unified_list.list_widget, "scrollToItem"):
            main_window.unified_list.select_item("event", "evt1")

            # Should have switched filter
            assert main_window.unified_list.filter_combo.currentText() == "All Items"
            assert mock_set.called
