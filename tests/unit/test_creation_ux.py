from unittest.mock import patch

import pytest

from src.app.main import MainWindow
from src.commands.base_command import CommandResult
from src.core.entities import Entity
from src.core.events import Event


@pytest.fixture
def main_window(qtbot):
    """Create MainWindow with mocked Worker."""
    with patch("src.app.main.DatabaseWorker") as MockWorker:
        with patch("src.app.main.QThread"), patch("src.app.main.QTimer"):
            # Mock worker and DB
            mock_worker = MockWorker.return_value
            mock_worker.db_service.get_all_events.return_value = []

            window = MainWindow()
            window.show()  # needed for visibility checks often
            qtbot.addWidget(window)
            yield window


def test_create_entity_success_selects_item(main_window):
    """Verify that creating an entity selects it after loading."""
    # 1. Mock Input Dialog
    with patch("src.app.main.QInputDialog.getText") as mock_input:
        mock_input.return_value = ("New Entity", True)

        # 2. Mock Command
        with patch("src.app.main.CreateEntityCommand") as MockCmd:

            # Execute
            main_window.create_entity()

            # Verify command creation
            MockCmd.assert_called_once()
            args, _ = MockCmd.call_args
            assert args[0] == {"name": "New Entity", "type": "Concept"}

    # 3. Simulate Command Finish with Data
    cmd_result = CommandResult(
        success=True,
        message="Created",
        command_name="CreateEntityCommand",
        data={"id": "new-ent-id"},
    )

    # 4. Mock load_entities triggering
    with patch.object(main_window, "load_entities") as mock_load:
        main_window.data_handler.on_command_finished(cmd_result)
        mock_load.assert_called_once()

    # Check pending state
    assert main_window._pending_select_id == "new-ent-id"
    assert main_window._pending_select_type == "entity"

    # 5. Simulate entities loaded - use real Entity class
    test_entity = Entity(id="new-ent-id", name="New Entity", type="Concept")

    with patch.object(main_window.unified_list, "select_item") as mock_select:
        main_window.data_handler.on_entities_loaded([test_entity])

        # 6. Verify selection called
        mock_select.assert_called_once_with("entity", "new-ent-id")

    # Check pending state cleared
    assert main_window._pending_select_id is None
    assert main_window._pending_select_type is None


def test_create_event_success_selects_item(main_window):
    """Verify that creating an event selects it after loading."""
    # 1. Mock Input Dialog
    with patch("src.app.main.QInputDialog.getText") as mock_input:
        mock_input.return_value = ("New Event", True)

        # 2. Mock Command
        with patch("src.app.main.CreateEventCommand") as MockCmd:

            main_window.create_event()

            MockCmd.assert_called_once()
            args, _ = MockCmd.call_args
            assert args[0] == {"name": "New Event", "lore_date": 0.0}

    # 3. Simulate Command Finish
    cmd_result = CommandResult(
        success=True,
        message="Created",
        command_name="CreateEventCommand",
        data={"id": "new-evt-id"},
    )

    with patch.object(main_window, "load_events") as mock_load:
        main_window.data_handler.on_command_finished(cmd_result)
        mock_load.assert_called_once()

    assert main_window._pending_select_id == "new-evt-id"
    assert main_window._pending_select_type == "event"

    # 5. Simulate events loaded - use real Event class
    test_event = Event(id="new-evt-id", name="New Event", lore_date=0.0, type="generic")

    with patch.object(main_window.unified_list, "select_item") as mock_select:
        with patch.object(main_window.timeline, "set_events"):
            main_window.data_handler.on_events_loaded([test_event])

        mock_select.assert_called_once_with("event", "new-evt-id")

    assert main_window._pending_select_id is None


def test_create_cancel_does_nothing(main_window):
    """Test cancelling creation."""
    with patch("src.app.main.QInputDialog.getText") as mock_input:
        mock_input.return_value = ("", False)

        with patch("src.app.main.CreateEntityCommand") as MockCmd:
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
