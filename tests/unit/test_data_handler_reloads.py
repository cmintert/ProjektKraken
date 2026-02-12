"""Tests for DataHandler reload signal emission."""

import pytest
from unittest.mock import MagicMock
from src.app.data_handler import DataHandler
from src.commands.base_command import CommandResult


@pytest.fixture
def data_handler(qapp):
    """Fixture to provide a DataHandler instance."""
    return DataHandler()


def test_on_command_finished_rename_layer_emits_reloads(data_handler):
    """Verify RenameLayerCommand triggers maps, markers, and lore reloads."""
    # Setup mocks for reload signals
    data_handler.reload_maps = MagicMock()
    data_handler.reload_markers_for_current_map = MagicMock()
    data_handler.reload_entities = MagicMock()
    data_handler.reload_events = MagicMock()

    result = CommandResult(
        success=True, command_name="RenameLayerCommand", message="Renamed", data={}
    )

    # Execute
    data_handler.on_command_finished(result)

    # Verify
    data_handler.reload_maps.emit.assert_called_once()
    data_handler.reload_entities.emit.assert_called_once()
    data_handler.reload_events.emit.assert_called_once()
    data_handler.reload_markers_for_current_map.emit.assert_called_once()


def test_on_command_finished_other_map_command_emits_maps_only(data_handler):
    """Verify generic Map commands only trigger map reloads, not lore."""
    data_handler.reload_maps = MagicMock()
    data_handler.reload_entities = MagicMock()
    data_handler.reload_events = MagicMock()

    result = CommandResult(
        success=True, command_name="SaveLayerTreeCommand", message="Saved", data={}
    )

    # Execute
    data_handler.on_command_finished(result)

    # Verify
    data_handler.reload_maps.emit.assert_called_once()
    data_handler.reload_entities.emit.assert_not_called()
    data_handler.reload_events.emit.assert_not_called()
