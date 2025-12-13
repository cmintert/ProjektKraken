import pytest
from unittest.mock import patch, MagicMock
from src.app.main import MainWindow
from src.commands.base_command import CommandResult


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
        main_window.on_command_finished(cmd_result)
        mock_load.assert_called_once()

    # Check pending state
    assert main_window._pending_select_id == "new-ent-id"
    assert main_window._pending_select_type == "entity"

    # 5. Simulate entities loaded
    mock_entity = MagicMock()
    mock_entity.id = "new-ent-id"
    mock_entity.name = "New Entity"
    mock_entity.type = "Concept"

    with patch.object(main_window.unified_list, "select_item") as mock_select:
        main_window.on_entities_loaded([mock_entity])

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
        main_window.on_command_finished(cmd_result)
        mock_load.assert_called_once()

    assert main_window._pending_select_id == "new-evt-id"
    assert main_window._pending_select_type == "event"

    # 5. Simulate events loaded
    mock_event = MagicMock()
    mock_event.id = "new-evt-id"
    mock_event.name = "New Event"
    mock_event.lore_date = 0.0

    with patch.object(main_window.unified_list, "select_item") as mock_select:
        with patch.object(main_window.timeline, "set_events"):
            main_window.on_events_loaded([mock_event])

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
    # Mock data objects
    mock_entity = MagicMock()
    mock_entity.id = "ent1"
    mock_entity.name = "Entity 1"
    mock_entity.type = "Concept"

    mock_event = MagicMock()
    mock_event.id = "evt1"
    mock_event.name = "Event 1"
    mock_event.lore_date = 10.0

    # Pre-populate
    main_window._cached_entities = [mock_entity]
    main_window._cached_events = [mock_event]

    # We must mock timeline.set_events if we call set_data on main_window or unified_list logic?
    # No, unified_list.set_data is safe.
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
