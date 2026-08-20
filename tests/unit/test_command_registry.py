"""Unit tests for the command registry module.

Verifies that the centralized command registry correctly loads and provides
all known command types for history service registration.
"""

import pytest

from src.commands.registry import get_command_types, register_command_type

pytestmark = [pytest.mark.unit, pytest.mark.smoke]

# Expected command names that must always be present
EXPECTED_COMMANDS = [
    "ApplyMarkerAppearanceCommand",
    "CreateEventCommand",
    "UpdateEventCommand",
    "DeleteEventCommand",
    "AddRelationCommand",
    "UpdateRelationCommand",
    "RemoveRelationCommand",
    "CompositeCommand",
    "ProcessWikiLinksCommand",
    "CreateEntityCommand",
    "UpdateEntityCommand",
    "DeleteEntityCommand",
    "CreateMapCommand",
    "UpdateMapCommand",
    "DeleteMapCommand",
    "UpdateCalendarConfigCommand",
    # Marker commands
    "CreateMarkerCommand",
    "UpdateMarkerCommand",
    "DeleteMarkerCommand",
    "UpdateMarkerColorCommand",
    "UpdateMarkerAttributeCommand",
    "UpdateTrajectoryCommand",
    # Layer commands
    "SetLayerVisibilityCommand",
    "MoveLayerCommand",
    "SaveLayerTreeCommand",
    "SetLayerOpacityCommand",
    "RenameLayerCommand",
    # Raster commands
    "CreateRasterLayerCommand",
    "DeleteRasterLayerCommand",
    "SetRasterMappingCommand",
    "SetRasterBlendModeCommand",
]


def test_registry_returns_all_expected_commands():
    """Registry contains all known command types."""
    types = get_command_types()
    for name in EXPECTED_COMMANDS:
        assert name in types, f"Missing command type: {name}"


def test_registry_returns_dict_copy():
    """get_command_types returns a copy, not the internal dict."""
    types1 = get_command_types()
    types2 = get_command_types()
    assert types1 is not types2
    assert types1 == types2


def test_registry_does_not_deserialize_path_based_marker_icon_command():
    assert "UpdateMarkerIconCommand" not in get_command_types()


def test_registry_values_are_classes():
    """All registry values should be class types (callable)."""
    types = get_command_types()
    for name, cls in types.items():
        assert isinstance(cls, type), f"{name} is not a class: {type(cls)}"


def test_register_additional_command_type():
    """register_command_type allows runtime extension."""

    class DummyCommand:
        pass

    register_command_type("DummyCommand", DummyCommand)
    types = get_command_types()
    assert "DummyCommand" in types
    assert types["DummyCommand"] is DummyCommand
