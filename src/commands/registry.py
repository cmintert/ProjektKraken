"""Command Registry Module.

Provides a centralized registry of command types for serialization and
deserialization by the HistoryService. This satisfies the Open/Closed
Principle: new commands are registered here without modifying the
WorkerManager initialization logic.

Usage:
    from src.commands.registry import get_command_types

    for name, cls in get_command_types().items():
        history_service.register_command_type(name, cls)
"""

import logging
from typing import Dict, Type

logger = logging.getLogger(__name__)

_COMMAND_TYPES: Dict[str, Type] = {}
_initialized: bool = False


def _init_registry() -> None:
    """Lazily imports and registers all known command types.

    Uses lazy imports to avoid circular dependencies at module load time.
    """
    global _initialized
    if _initialized:
        return

    from src.commands.analysis_commands import (
        AnalyzeTemporalCommand,
        RunIntelligenceAnalysisCommand,
        ValidateWorldCommand,
    )
    from src.commands.calendar_commands import UpdateCalendarConfigCommand
    from src.commands.composite_command import CompositeCommand
    from src.commands.entity_commands import (
        CreateEntityCommand,
        DeleteEntityCommand,
        UpdateEntityCommand,
    )
    from src.commands.event_commands import (
        CreateEventCommand,
        DeleteEventCommand,
        UpdateEventCommand,
    )
    from src.commands.layer_commands import (
        MoveLayerCommand,
        RenameLayerCommand,
        SaveLayerTreeCommand,
        SetLayerOpacityCommand,
        SetLayerVisibilityCommand,
    )
    from src.commands.map_commands import (
        CreateMapCommand,
        DeleteMapCommand,
        UpdateMapCommand,
    )
    from src.commands.marker_commands import (
        CreateMarkerCommand,
        DeleteKeyframeCommand,
        DeleteMarkerCommand,
        UpdateMarkerAttributeCommand,
        UpdateMarkerColorCommand,
        UpdateMarkerCommand,
        UpdateMarkerIconCommand,
    )
    from src.commands.raster_commands import (
        CreateRasterLayerCommand,
        DeleteRasterLayerCommand,
        RemoveRasterSnapshotCommand,
        SetRasterBlendModeCommand,
        SetRasterMappingCommand,
    )
    from src.commands.relation_commands import (
        AddRelationCommand,
        RemoveRelationCommand,
        UpdateRelationCommand,
    )
    from src.commands.wiki_commands import ProcessWikiLinksCommand

    _COMMAND_TYPES.update(
        {
            "CreateEventCommand": CreateEventCommand,
            "UpdateEventCommand": UpdateEventCommand,
            "DeleteEventCommand": DeleteEventCommand,
            "AddRelationCommand": AddRelationCommand,
            "UpdateRelationCommand": UpdateRelationCommand,
            "RemoveRelationCommand": RemoveRelationCommand,
            "CompositeCommand": CompositeCommand,
            "ProcessWikiLinksCommand": ProcessWikiLinksCommand,
            "CreateEntityCommand": CreateEntityCommand,
            "UpdateEntityCommand": UpdateEntityCommand,
            "DeleteEntityCommand": DeleteEntityCommand,
            "CreateMapCommand": CreateMapCommand,
            "UpdateMapCommand": UpdateMapCommand,
            "DeleteMapCommand": DeleteMapCommand,
            "RemoveRasterSnapshotCommand": RemoveRasterSnapshotCommand,
            "UpdateCalendarConfigCommand": UpdateCalendarConfigCommand,
            # Marker commands
            "CreateMarkerCommand": CreateMarkerCommand,
            "UpdateMarkerCommand": UpdateMarkerCommand,
            "DeleteMarkerCommand": DeleteMarkerCommand,
            "UpdateMarkerIconCommand": UpdateMarkerIconCommand,
            "UpdateMarkerColorCommand": UpdateMarkerColorCommand,
            "UpdateMarkerAttributeCommand": UpdateMarkerAttributeCommand,
            "DeleteKeyframeCommand": DeleteKeyframeCommand,
            # Layer commands
            "SetLayerVisibilityCommand": SetLayerVisibilityCommand,
            "MoveLayerCommand": MoveLayerCommand,
            "SaveLayerTreeCommand": SaveLayerTreeCommand,
            "SetLayerOpacityCommand": SetLayerOpacityCommand,
            "RenameLayerCommand": RenameLayerCommand,
            # Raster commands
            "CreateRasterLayerCommand": CreateRasterLayerCommand,
            "DeleteRasterLayerCommand": DeleteRasterLayerCommand,
            "SetRasterMappingCommand": SetRasterMappingCommand,
            "SetRasterBlendModeCommand": SetRasterBlendModeCommand,
            # Analysis commands
            "ValidateWorldCommand": ValidateWorldCommand,
            "AnalyzeTemporalCommand": AnalyzeTemporalCommand,
            "RunIntelligenceAnalysisCommand": RunIntelligenceAnalysisCommand,
        }
    )

    _initialized = True
    logger.debug(f"Command registry initialized with {len(_COMMAND_TYPES)} types")


def get_command_types() -> Dict[str, Type]:
    """Returns the registry mapping command names to their classes.

    Returns:
        Dict[str, Type]: A copy of the command type registry.

    """
    _init_registry()
    return dict(_COMMAND_TYPES)


def register_command_type(name: str, cls: Type) -> None:
    """Register an additional command type at runtime.

    Allows plugins or extensions to add command types without modifying
    the static registry.

    Args:
        name: The string key for the command (typically the class name).
        cls: The command class to register.

    """
    _init_registry()
    _COMMAND_TYPES[name] = cls
    logger.debug(f"Registered additional command type: {name}")
