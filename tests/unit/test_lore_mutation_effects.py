"""Regression tests for incremental lore mutation effects."""

import pytest

from src.app.data_handler import DataHandler
from src.commands.base_command import CommandResult
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
from src.commands.marker_commands import CreateMarkerCommand
from src.commands.wiki_commands import ProcessWikiLinksCommand
from src.core.command import parse_lore_mutation_effects
from src.core.map import Map


def test_event_and_entity_crud_emit_persisted_effects(db_service) -> None:
    event_create = CreateEventCommand(
        {"id": "event-1", "name": "Event", "lore_date": 10.0}
    ).execute(db_service)
    entity_create = CreateEntityCommand(
        {"id": "entity-1", "name": "Entity", "type": "Person"}
    ).execute(db_service)

    results = [
        event_create,
        UpdateEventCommand("event-1", {"name": "Changed"}).execute(db_service),
        entity_create,
        UpdateEntityCommand("entity-1", {"name": "Changed"}).execute(db_service),
        DeleteEventCommand("event-1").execute(db_service),
        DeleteEntityCommand("entity-1").execute(db_service),
    ]

    for result in results:
        effects = parse_lore_mutation_effects(result.data.get("lore_effects"))
        assert effects is not None
        assert len(effects) == 1
        assert effects[0]["object_id"] == result.data["id"]
        assert (effects[0]["snapshot"] is None) == (effects[0]["operation"] == "delete")
    for result in (results[1], results[3]):
        effects = parse_lore_mutation_effects(result.data.get("lore_effects"))
        assert effects is not None
        assert effects[0]["relations_changed"] is False


def test_editor_save_composite_aggregates_one_effect(db_service) -> None:
    CreateEventCommand({"id": "event-1", "name": "Event", "lore_date": 10.0}).execute(
        db_service
    )
    result = CompositeCommand(
        [
            UpdateEventCommand("event-1", {"description": "No links"}),
            ProcessWikiLinksCommand("event-1", "No links"),
        ]
    ).execute(db_service)

    effects = parse_lore_mutation_effects(result.data.get("lore_effects"))
    assert effects is not None
    assert effects[0]["relations_changed"] is True


def test_incremental_handler_patches_cache_without_full_reload(qapp) -> None:
    handler = DataHandler()
    handler.on_events_loaded([])
    full_reloads: list[bool] = []
    dataset_reloads: list[str] = []
    applied: list[list] = []
    detail_checks: list[list] = []
    handler.reload_all_data.connect(lambda: full_reloads.append(True))
    handler.reload_events.connect(lambda: dataset_reloads.append("events"))
    handler.reload_entities.connect(lambda: dataset_reloads.append("entities"))
    handler.lore_mutation_ready.connect(applied.append)
    handler.reload_affected_editor_relations.connect(detail_checks.append)

    result = CommandResult(
        success=True,
        command_name="UpdateEventCommand",
        data={
            "lore_effects": [
                {
                    "object_type": "event",
                    "operation": "upsert",
                    "object_id": "event-1",
                    "snapshot": {
                        "id": "event-1",
                        "name": "Changed",
                        "lore_date": 2.0,
                    },
                    "relations_changed": False,
                }
            ]
        },
    )
    handler.on_command_finished(result)

    assert full_reloads == []
    assert dataset_reloads == []
    assert len(applied) == 1
    assert len(detail_checks) == 1
    assert [event.id for event in handler._cached_events] == ["event-1"]


def test_malformed_effect_uses_one_full_fallback(qapp) -> None:
    handler = DataHandler()
    full_reloads: list[bool] = []
    handler.reload_all_data.connect(lambda: full_reloads.append(True))
    handler.on_command_finished(
        CommandResult(
            success=True,
            command_name="UpdateEventCommand",
            data={"lore_effects": [{"object_type": "event"}]},
        )
    )
    assert full_reloads == [True]


def test_delete_checks_active_detail_without_full_reload(qapp) -> None:
    handler = DataHandler()
    conditional: list[list] = []
    unconditional: list[bool] = []
    handler.reload_affected_editor_relations.connect(conditional.append)
    handler.reload_active_editor_relations.connect(lambda: unconditional.append(True))
    handler.on_command_finished(
        CommandResult(
            success=True,
            command_name="DeleteEventCommand",
            data={
                "lore_effects": [
                    {
                        "object_type": "event",
                        "operation": "delete",
                        "object_id": "event-1",
                        "snapshot": None,
                        "relations_changed": True,
                    }
                ]
            },
        )
    )

    assert len(conditional) == 1
    assert unconditional == []


@pytest.mark.ci_fast
@pytest.mark.parametrize("object_type", ["entity", "event"])
@pytest.mark.parametrize("malformed", [False, True])
@pytest.mark.parametrize("select", [False, True])
def test_creation_fallback_respects_selection_and_avoids_hydration(
    qapp, object_type, malformed, select
):
    handler = DataHandler()
    selections, full_reloads, datasets, markers = [], [], [], []
    handler.selection_requested.connect(lambda *args: selections.append(args))
    handler.reload_all_data.connect(lambda: full_reloads.append(True))
    handler.reload_events.connect(lambda: datasets.append("event"))
    handler.reload_entities.connect(lambda: datasets.append("entity"))
    handler.reload_markers_for_current_map.connect(lambda: markers.append(True))
    data = {"id": "new-object", "select_after_apply": select}
    if malformed:
        data["lore_effects"] = [{"object_type": object_type}]
    handler.on_command_finished(
        CommandResult(
            success=True,
            command_name="CreateEntityCommand"
            if object_type == "entity"
            else "CreateEventCommand",
            data=data,
        )
    )
    assert datasets == [object_type]
    assert full_reloads == []
    assert markers == []
    if object_type == "entity":
        handler.on_entities_loaded([])
    else:
        handler.on_events_loaded([])
    assert selections == ([(object_type, "new-object")] if select else [])
    assert markers == [True]


@pytest.mark.ci_fast
@pytest.mark.parametrize("object_type", ["entity", "event"])
def test_atomic_marker_failure_rolls_back_lore_creation(db_service, object_type):
    command_type = (
        CreateEntityCommand if object_type == "entity" else CreateEventCommand
    )
    data = {"id": "new-object", "name": "New"}
    data.update({"type": "Location"} if object_type == "entity" else {"lore_date": 2.0})
    create = command_type(data, select_after_create=False)
    marker = CreateMarkerCommand(
        {
            "map_id": "missing-map",
            "object_id": "new-object",
            "object_type": object_type,
            "x": 0.3,
            "y": 0.7,
        }
    )
    result = CompositeCommand([create, marker]).execute(db_service)
    assert not result.success
    lookup = db_service.get_entity if object_type == "entity" else db_service.get_event
    assert lookup("new-object") is None
    assert "lore_effects" not in result.data


@pytest.mark.parametrize("select", [False, True])
def test_creation_composite_preserves_child_selection(db_service, select):
    create = CreateEntityCommand(
        {"id": "new-object", "name": "New", "type": "Concept"},
        select_after_create=select,
    )
    result = CompositeCommand(
        [create, ProcessWikiLinksCommand("new-object", "No links")]
    ).execute(db_service)
    assert result.success
    assert result.data["select_after_apply"] == (
        {"object_type": "entity", "object_id": "new-object"} if select else False
    )


def test_unrelated_marker_composite_keeps_conservative_refresh(db_service):
    db_service.insert_map(Map(id="map", name="Map", image_path=""))
    CreateEntityCommand(
        {"id": "existing", "name": "Existing", "type": "Concept"}
    ).execute(db_service)
    result = CompositeCommand(
        [
            CreateEntityCommand({"id": "new", "name": "New", "type": "Concept"}),
            CreateMarkerCommand(
                {
                    "map_id": "map",
                    "object_id": "existing",
                    "object_type": "entity",
                    "x": 0.3,
                    "y": 0.7,
                }
            ),
        ]
    ).execute(db_service)
    assert result.success
    assert "lore_effects" not in result.data
