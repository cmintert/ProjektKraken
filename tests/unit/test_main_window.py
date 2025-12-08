import pytest
from unittest.mock import patch
from src.app.main import MainWindow
from src.core.events import Event


@pytest.fixture
def main_window(qtbot):
    # Mock DB service to avoid real DB creation
    with patch("src.app.main.DatabaseService") as MockDB:
        mock_db = MockDB.return_value
        mock_db.get_all_events.return_value = []
        window = MainWindow()
        qtbot.addWidget(window)
        return window


def test_init_window(main_window):
    assert main_window.windowTitle() == "Project Kraken - v0.2.0 (Editor Phase)"
    assert main_window.timeline is not None


def test_load_event_details(main_window):
    # Setup mock return
    ev = Event(id="1", name="Test", lore_date=100.0)
    main_window.db_service.get_event.return_value = ev
    main_window.db_service.get_relations.return_value = []
    main_window.db_service.get_incoming_relations.return_value = []

    # Call
    main_window.load_event_details("1")

    # Assert
    assert main_window.event_editor.name_edit.text() == "Test"
    main_window.db_service.get_event.assert_called_with("1")
    # Verify timeline sync
    # We can check if timeline focus was called, but timeline is a real object here.


def test_create_event_flow(main_window):
    # Simulate save from editor
    ev = Event(id="1", name="New", lore_date=10.0)

    # Update implies existing event. Create is implicit in seeding?
    # MainWindow handles update_relation, remove_relation.
    # It passes update_event to command.

    main_window.update_event(ev)
    # This creates UpdateEventCommand. We should verify DB call via command?
    # Command executes on db_service.
