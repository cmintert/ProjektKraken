"""Backward-compatible facade — re-exports all map command classes.

The commands have been split into three focused modules:

* ``map_crud_commands`` — CreateMapCommand, UpdateMapCommand, DeleteMapCommand
* ``marker_commands`` — CreateMarkerCommand, UpdateMarkerCommand, DeleteMarkerCommand,
  UpdateMarkerIconCommand, UpdateMarkerColorCommand, DeleteKeyframeCommand
* ``layer_commands`` — SetLayerVisibilityCommand, MoveLayerCommand,
  SaveLayerTreeCommand, SetLayerOpacityCommand, RenameLayerCommand,
  ``_find_layer_node``

This module re-exports every public name so that existing ``from
src.commands.map_commands import …`` statements continue to work
without modification.
"""

# Map CRUD
from src.commands.map_crud_commands import (  # noqa: F401
    CreateMapCommand,
    DeleteMapCommand,
    UpdateMapCommand,
)

# Marker / Feature
from src.commands.marker_commands import (  # noqa: F401
    CreateMarkerCommand,
    DeleteKeyframeCommand,
    DeleteMarkerCommand,
    UpdateMarkerColorCommand,
    UpdateMarkerCommand,
    UpdateMarkerIconCommand,
)

# Layer hierarchy
from src.commands.layer_commands import (  # noqa: F401
    MoveLayerCommand,
    RenameLayerCommand,
    SaveLayerTreeCommand,
    SetLayerOpacityCommand,
    SetLayerVisibilityCommand,
    _find_layer_node,
)

__all__ = [
    # Map CRUD
    "CreateMapCommand",
    "UpdateMapCommand",
    "DeleteMapCommand",
    # Marker / Feature
    "CreateMarkerCommand",
    "UpdateMarkerCommand",
    "DeleteMarkerCommand",
    "UpdateMarkerIconCommand",
    "UpdateMarkerColorCommand",
    "DeleteKeyframeCommand",
    # Layer hierarchy
    "SetLayerVisibilityCommand",
    "MoveLayerCommand",
    "SaveLayerTreeCommand",
    "SetLayerOpacityCommand",
    "RenameLayerCommand",
    "_find_layer_node",
]
