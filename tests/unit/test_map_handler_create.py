"""Tests for in-place entity/event creation from the Map handler."""

from unittest.mock import MagicMock, patch

import pytest

from src.app.map_handler import MapHandler


@pytest.fixture
def mock_window():
    """Creates a mock MainWindow with cached entities/events."""
    window = MagicMock()
    window.data_handler = MagicMock()
    window.map_widget.map_selector.currentData.return_value = "map_1"
    window.map_widget.get_selected_map_id.return_value = "map_1"

    # Cached entities/events
    entity = MagicMock()
    entity.id = "ent_1"
    entity.name = "Rivendell"
    window._cached_entities = [entity]

    event = MagicMock()
    event.id = "evt_1"
    event.name = "Battle of Five Armies"
    window._cached_events = [event]

    return window


@pytest.fixture
def handler(mock_window):
    """Creates a MapHandler with a mocked window."""
    return MapHandler(mock_window)


class TestSelectExistingItem:
    """Tests for selecting existing entities/events (regression)."""

    def test_create_marker_existing_entity(self, handler):
        """Selecting an existing entity emits only CreateMarkerCommand."""
        with patch(
            "src.app.map_handler.QInputDialog"
        ) as MockDialog:
            MockDialog.getItem.return_value = ("Rivendell (Entity)", True)

            handler.create_marker(0.5, 0.5)

            # Should emit exactly one command (the marker)
            handler.window.command_requested.emit.assert_called_once()
            cmd = handler.window.command_requested.emit.call_args[0][0]
            assert cmd.__class__.__name__ == "CreateMarkerCommand"

    def test_on_feature_drawn_existing_event(self, handler):
        """Selecting an existing event for a feature emits only CreateMarkerCommand."""
        geometry = [{"x": 0.1, "y": 0.1}, {"x": 0.5, "y": 0.5}, {"x": 0.9, "y": 0.1}]
        with patch(
            "src.app.map_handler.QInputDialog"
        ) as MockDialog:
            MockDialog.getItem.return_value = (
                "Battle of Five Armies (Event)",
                True,
            )

            handler.on_feature_drawn("region", geometry)

            handler.window.command_requested.emit.assert_called_once()
            cmd = handler.window.command_requested.emit.call_args[0][0]
            assert cmd.__class__.__name__ == "CreateMarkerCommand"


class TestCreateNewInline:
    """Tests for the new in-place creation flow."""

    def test_create_marker_new_entity(self, handler):
        """Selecting '<New Entity...>' emits CreateEntityCommand + CreateMarkerCommand."""
        with patch(
            "src.app.map_handler.QInputDialog"
        ) as MockDialog:
            # First call: item selection -> choose sentinel
            # Second call: getText -> enter name
            MockDialog.getItem.return_value = ("<New Entity...>", True)
            MockDialog.getText.return_value = ("Mount Doom", True)

            handler.create_marker(0.3, 0.7)

            # Should emit two commands:
            # 1. CreateEntityCommand (the new entity)
            # 2. CreateMarkerCommand (the marker linked to it)
            assert handler.window.command_requested.emit.call_count == 2
            first_cmd = handler.window.command_requested.emit.call_args_list[0][0][0]
            second_cmd = handler.window.command_requested.emit.call_args_list[1][0][0]

            assert first_cmd.__class__.__name__ == "CreateEntityCommand"
            assert second_cmd.__class__.__name__ == "CreateMarkerCommand"

    def test_create_marker_new_event(self, handler):
        """Selecting '<New Event...>' emits CreateEventCommand + CreateMarkerCommand."""
        with patch(
            "src.app.map_handler.QInputDialog"
        ) as MockDialog:
            MockDialog.getItem.return_value = ("<New Event...>", True)
            MockDialog.getText.return_value = ("Dragon Attack", True)

            handler.create_marker(0.6, 0.4)

            assert handler.window.command_requested.emit.call_count == 2
            first_cmd = handler.window.command_requested.emit.call_args_list[0][0][0]
            second_cmd = handler.window.command_requested.emit.call_args_list[1][0][0]

            assert first_cmd.__class__.__name__ == "CreateEventCommand"
            assert second_cmd.__class__.__name__ == "CreateMarkerCommand"

    def test_new_entity_cancel_name_emits_nothing(self, handler):
        """Cancelling the name dialog after choosing '<New Entity...>' emits nothing."""
        with patch(
            "src.app.map_handler.QInputDialog"
        ) as MockDialog:
            MockDialog.getItem.return_value = ("<New Entity...>", True)
            MockDialog.getText.return_value = ("", False)  # User cancels

            handler.create_marker(0.5, 0.5)

            handler.window.command_requested.emit.assert_not_called()

    def test_on_feature_drawn_new_entity(self, handler):
        """Drawing a path and creating a new entity emits both commands."""
        geometry = [{"x": 0.1, "y": 0.2}, {"x": 0.8, "y": 0.9}]
        with patch(
            "src.app.map_handler.QInputDialog"
        ) as MockDialog:
            MockDialog.getItem.return_value = ("<New Entity...>", True)
            MockDialog.getText.return_value = ("River Anduin", True)

            handler.on_feature_drawn("path", geometry)

            assert handler.window.command_requested.emit.call_count == 2
            first_cmd = handler.window.command_requested.emit.call_args_list[0][0][0]
            second_cmd = handler.window.command_requested.emit.call_args_list[1][0][0]

            assert first_cmd.__class__.__name__ == "CreateEntityCommand"
            assert second_cmd.__class__.__name__ == "CreateMarkerCommand"

    def test_cancel_selection_emits_nothing(self, handler):
        """Cancelling the item selection dialog emits nothing."""
        with patch(
            "src.app.map_handler.QInputDialog"
        ) as MockDialog:
            MockDialog.getItem.return_value = ("", False)  # User cancels

            handler.create_marker(0.5, 0.5)

            handler.window.command_requested.emit.assert_not_called()
