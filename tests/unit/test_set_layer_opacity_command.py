"""Unit tests for SetLayerOpacityCommand persistence."""

from unittest.mock import MagicMock

import pytest

from src.commands.map_commands import SetLayerOpacityCommand
from src.core.map import Map, MapLayerNode


@pytest.fixture
def mock_db_service():
    """Mock database service."""
    service = MagicMock()
    # Mock map repo get_map to return a map with a layer
    layer = MapLayerNode(name="Test Layer", id="layer-1", opacity=0.8)
    map_obj = Map(id="map-1", name="Test Map", image_path="path", layers=layer)
    service.map_repo.get_map.return_value = map_obj
    return service


def test_command_uses_explicit_previous_opacity(mock_db_service):
    """Command should use the provided previous_opacity for undo."""
    # Init with explicit previous_opacity=0.5 (different from DB's 0.8)
    cmd = SetLayerOpacityCommand(
        map_id="map-1",
        node_id="layer-1",
        opacity=1.0,
        previous_opacity=0.5,
    )

    # Execute
    cmd.execute(mock_db_service)

    # Verify DB was updated to 1.0
    saved_map = mock_db_service.map_repo.insert_map.call_args[0][0]
    assert saved_map.layers.opacity == 1.0

    # Undo
    cmd.undo(mock_db_service)

    # Verify DB was reverted to 0.5 (from explicit arg), NOT 0.8 (from DB/model)
    reverted_map = mock_db_service.map_repo.insert_map.call_args[0][0]
    assert reverted_map.layers.opacity == 0.5


def test_command_falls_back_to_current_opacity_if_none_provided(mock_db_service):
    """Command should fallback to DB value if previous_opacity is None."""
    cmd = SetLayerOpacityCommand(
        map_id="map-1",
        node_id="layer-1",
        opacity=1.0,
        previous_opacity=None,
    )

    # Execute (should capture 0.8 from DB)
    cmd.execute(mock_db_service)

    # Undo
    cmd.undo(mock_db_service)

    # Verify DB reverted to 0.8
    reverted_map = mock_db_service.map_repo.insert_map.call_args[0][0]
    assert reverted_map.layers.opacity == 0.8
