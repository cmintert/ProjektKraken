"""Tests for DataHandler reload signal emission."""

from unittest.mock import MagicMock

import pytest

from src.app.data_handler import DataHandler
from src.commands.base_command import CommandResult
from src.commands.composite_command import CompositeCommand
from src.commands.entity_commands import CreateEntityCommand
from src.commands.event_commands import CreateEventCommand
from src.commands.marker_commands import CreateMarkerCommand
from src.core.map import Map


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


def test_create_marker_reloads_exact_affected_map(data_handler):
    """Point-marker creation refreshes its map without current-map inference."""
    data_handler.reload_markers = MagicMock()
    data_handler.reload_markers_for_current_map = MagicMock()
    result = CommandResult(
        success=True,
        command_name="CreateMarkerCommand",
        message="Created",
        data={"id": "marker-1", "map_id": "map-1"},
    )

    data_handler.on_command_finished(result)

    data_handler.reload_markers.emit.assert_called_once_with("map-1")
    data_handler.reload_markers_for_current_map.emit.assert_not_called()


def test_composite_creation_reloads_exact_map_after_lore_cache(
    data_handler, db_service
):
    """Atomic object-marker creation waits for fresh lore, then reloads its map."""
    db_service.insert_map(
        Map(id="map-1", name="Test Map", image_path="test.png")
    )
    command = CompositeCommand(
        [
            CreateEntityCommand(
                {"id": "entity-1", "name": "Grey Watch", "type": "Location"}
            ),
            CreateMarkerCommand(
                {
                    "map_id": "map-1",
                    "object_id": "entity-1",
                    "object_type": "entity",
                    "x": 0.25,
                    "y": 0.75,
                    "label": "Grey Watch",
                }
            ),
        ],
        "Create Grey Watch and Place Marker",
    )
    result = command.execute(db_service)
    assert result.success
    assert result.data["index_requests"] == [
        {"object_type": "entity", "object_id": "entity-1"}
    ]
    assert result.data["marker_map_ids"] == ["map-1"]

    data_handler.reload_entities = MagicMock()
    data_handler.reload_markers = MagicMock()
    data_handler.reload_markers_for_current_map = MagicMock()

    data_handler.on_command_finished(result)
    data_handler.reload_entities.emit.assert_called_once()
    data_handler.reload_markers.emit.assert_not_called()

    data_handler.on_entities_loaded([db_service.get_entity("entity-1")])

    data_handler.reload_markers.emit.assert_called_once_with("map-1")
    data_handler.reload_markers_for_current_map.emit.assert_not_called()


def test_event_marker_composite_reports_created_event(db_service):
    """New-event composites expose the event ID needed by refresh handling."""
    db_service.insert_map(
        Map(id="map-1", name="Test Map", image_path="test.png")
    )
    command = CompositeCommand(
        [
            CreateEventCommand(
                {"id": "event-1", "name": "The Crossing", "lore_date": 42.0}
            ),
            CreateMarkerCommand(
                {
                    "map_id": "map-1",
                    "object_id": "event-1",
                    "object_type": "event",
                    "x": 0.5,
                    "y": 0.5,
                    "label": "The Crossing",
                }
            ),
        ]
    )

    result = command.execute(db_service)

    assert result.success
    assert result.data["index_requests"] == [
        {"object_type": "event", "object_id": "event-1"}
    ]


def test_on_command_finished_other_map_command_emits_maps_only(data_handler):
    """Verify generic Map commands trigger map reloads, not lore.

    Uses CreateMapCommand as an example — it matches 'Map' in name
    and is not in the no-reload set, so it emits reload_maps.
    """
    data_handler.reload_maps = MagicMock()
    data_handler.reload_entities = MagicMock()
    data_handler.reload_events = MagicMock()

    result = CommandResult(
        success=True, command_name="CreateMapCommand", message="Created", data={}
    )

    # Execute
    data_handler.on_command_finished(result)

    # Verify
    data_handler.reload_maps.emit.assert_called_once()
    data_handler.reload_entities.emit.assert_not_called()
    data_handler.reload_events.emit.assert_not_called()


def test_on_command_finished_undo_emits_all_reloads(data_handler):
    """Verify undo commands trigger a full suite of reloads."""
    data_handler.reload_maps = MagicMock()
    data_handler.reload_markers_for_current_map = MagicMock()
    data_handler.reload_entities = MagicMock()
    data_handler.reload_events = MagicMock()
    data_handler.reload_active_editor_relations = MagicMock()

    result = CommandResult(
        success=True, command_name="Undo_EventCommand", message="Undone", data={}
    )

    data_handler.on_command_finished(result)

    data_handler.reload_maps.emit.assert_called_once()
    data_handler.reload_entities.emit.assert_called_once()
    data_handler.reload_events.emit.assert_called_once()
    data_handler.reload_markers_for_current_map.emit.assert_called_once()
    data_handler.reload_active_editor_relations.emit.assert_called_once()


def test_set_raster_mapping_command_emits_reload_maps(data_handler):
    """SetRasterMappingCommand must trigger reload_maps so maps_data stays fresh.

    Without this, the in-memory maps_data remains stale after a palette edit.
    When reload_markers_for_current_map later fires (e.g. on entity creation),
    load_raster_layers() reads the stale maps_data and reverts the palette.
    """
    data_handler.reload_maps = MagicMock()
    data_handler.reload_entities = MagicMock()
    data_handler.reload_events = MagicMock()

    result = CommandResult(
        success=True,
        command_name="SetRasterMappingCommand",
        message="Mapping updated.",
        data={},
    )

    data_handler.on_command_finished(result)

    data_handler.reload_maps.emit.assert_called_once()
    # Lore signals must NOT be emitted — this is map-only metadata
    data_handler.reload_entities.emit.assert_not_called()
    data_handler.reload_events.emit.assert_not_called()


def test_stroke_raster_command_does_not_emit_reload_maps(data_handler):
    """StrokeRasterCommand and PaintRasterCommand must NOT trigger reload_maps.

    These are high-frequency in-session-only commands (called on every brush
    stroke) that never touch the DB.  Triggering a full maps reload on each
    stroke would cause noticeable UI disruption.
    """
    data_handler.reload_maps = MagicMock()

    for cmd_name in ("StrokeRasterCommand", "PaintRasterCommand"):
        data_handler.reload_maps.reset_mock()
        result = CommandResult(
            success=True,
            command_name=cmd_name,
            message="Stroke applied.",
            data={},
        )
        data_handler.on_command_finished(result)
        (
            data_handler.reload_maps.emit.assert_not_called(),
            (f"{cmd_name} should not emit reload_maps"),
        )


def test_create_raster_layer_command_emits_reload_maps(data_handler):
    """CreateRasterLayerCommand contains 'Layer', so it must trigger reload_maps."""
    data_handler.reload_maps = MagicMock()

    result = CommandResult(
        success=True,
        command_name="CreateRasterLayerCommand",
        message="Created.",
        data={},
    )

    data_handler.on_command_finished(result)

    data_handler.reload_maps.emit.assert_called_once()
