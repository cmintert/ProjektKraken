"""Stored-row cross-world and native note preservation checks for KRT-121."""

import copy
import json
import sqlite3
import uuid

import frontmatter
import pytest

from src.commands.transfer_commands import ApplyTransferCommand
from src.core.calendar import CalendarConfig
from src.core.entities import Entity
from src.core.map import Map, MapLayerNode
from src.services.db_service import DatabaseService
from src.services.import_service import ImportService
from src.services.obsidian_exporter import ObsidianExporter
from src.services.repositories.transfer_repository import lore_data, snapshot
from src.services.transfer_exchange import csv_text, load_sources, table_manifest
from src.services.transfer_import import prepare_import
from src.services.world_transfer import export_world, import_world

pytestmark = pytest.mark.ci_fast


def uid():
    return str(uuid.uuid4())


def calendar(db):
    config = CalendarConfig.create_default()
    config.is_active = True
    db.insert_calendar_config(config)
    return config


def authored_event(db):
    review = prepare_import(
        db, {"events": [{"id": uid(), "name": "Year", "lore_date": "circa 1214"}]}, {}
    )
    assert not review["errors"]
    assert ApplyTransferCommand(review).execute(db).success
    return db.get_all_events()[0]


def test_cross_world_calendar_requires_explicit_compatible_mapping(db_service):
    source = calendar(db_service)
    original = authored_event(db_service)
    data = lore_data(snapshot(db_service.get_connection()))
    data["context"] = {"calendars": [source.to_dict()]}
    target = DatabaseService(":memory:")
    target.connect()
    try:
        destination = calendar(target)
        review = prepare_import(target, data, {})
        assert review["errors"]
        assert review["calendar_decisions"][0]["candidates"] == [destination.id]
        review = prepare_import(
            target, data, {"calendar_mappings": {source.id: destination.id}}
        )
        assert not review["errors"]
        assert ApplyTransferCommand(review).execute(target).success
        imported = target.get_event(original.id)
        expression = imported.attributes["_temporal_v2"]["expression"]
        assert expression["calendar_id"] == destination.id
        assert expression["precision"] == "year"
        assert expression["qualifier"] == "approximate"
        assert target.get_active_calendar_config().id == destination.id
    finally:
        target.close()


def test_incompatible_epoch_mapping_is_blocked(db_service):
    destination = calendar(db_service)
    source = copy.deepcopy(destination)
    source.id = uid()
    source.epoch_name = "Different era"
    data = {
        "events": [
            {
                "id": uid(),
                "name": "Foreign",
                "lore_date": None,
                "attributes": {
                    "_temporal_v2": {
                        "schema": 1,
                        "expression": {
                            "calendar_id": source.id,
                            "year": 1214,
                            "precision": "year",
                        },
                    }
                },
            }
        ],
        "context": {"calendars": [source.to_dict()]},
    }
    review = prepare_import(
        db_service, data, {"calendar_mappings": {source.id: destination.id}}
    )
    assert review["errors"]
    assert not review["delta"]
    unresolved = prepare_import(db_service, data, {"unresolved_calendars": [source.id]})
    assert not unresolved["errors"]
    assert unresolved["warnings"]
    assert ApplyTransferCommand(unresolved).execute(db_service).success
    assert db_service.get_all_events()[0].lore_date is None


def test_calendar_change_after_preview_refuses_apply(db_service):
    config = calendar(db_service)
    review = prepare_import(db_service, {"entities": [{"name": "New"}]}, {})
    config.epoch_name = "Changed"
    db_service.insert_calendar_config(config)
    assert not ApplyTransferCommand(review).execute(db_service).success
    assert not db_service.get_all_entities()


def test_native_notes_preserve_yaml_types_timing_relations_and_provenance(
    db_service,
    tmp_path,
):
    config = calendar(db_service)
    event = authored_event(db_service)
    entity = Entity(
        id=uid(),
        name="Values",
        type="person",
        created_at=0.0,
        modified_at=10.0,
        description="Original description.",
        attributes={
            "path": r"C:\temp\notes.txt",
            "values": ["yes", "001", "null"],
            "title": "user title",
            "kraken": {"source": "user"},
            "_provenance": {"source": "author"},
        },
    )
    db_service.insert_entity(entity)
    relation_id = uid()
    attributes = {
        "payload": {"attributes": {"rank": "captain"}},
        "valid_from": 1,
        "valid_to": 3,
        "sources": [{"record": event.id}],
    }
    db_service._relation_repo.insert(
        relation_id, event.id, entity.id, "changes_state", attributes, 2.0
    )
    result = ObsidianExporter(db_service).export_to_folder(tmp_path / "notes")
    assert result.success, result.errors
    data = load_sources([{"path": str(tmp_path / "notes")}])
    target = DatabaseService(":memory:")
    target.connect()
    try:
        destination = calendar(target)
        review = prepare_import(
            target, data, {"calendar_mappings": {config.id: destination.id}}
        )
        assert not review["errors"], review
        assert ApplyTransferCommand(review).execute(target).success
        stored = target.get_entity(entity.id)
        for key, value in entity.attributes.items():
            assert stored.attributes[key] == value
        assert stored.created_at == 0.0
        assert stored.modified_at == 10.0
        assert stored.description == entity.description
        relation = target.get_all_relations()[0]
        assert relation["id"] == relation_id
        assert relation["attributes"] == attributes
        assert (
            target.get_event(event.id).attributes["_temporal_v2"]["expression"][
                "qualifier"
            ]
            == "approximate"
        )
    finally:
        target.close()


def test_native_notes_reject_conflicting_readable_dates_and_links(db_service):
    calendar(db_service)
    event = authored_event(db_service)
    text = ObsidianExporter(db_service)._build_event_markdown(event, [])
    parsed = frontmatter.loads(text)
    parsed["lore_date"] = 123
    with pytest.raises(ValueError, match="conflicts"):
        ImportService.parse_markdown_file(frontmatter.dumps(parsed))
    with pytest.raises(ValueError, match="Related"):
        ImportService.parse_markdown_file(text + "\n## Related\n- caused: [[Other]]\n")


def test_native_tables_manifest_carries_context_and_hashes(db_service, tmp_path):
    config = calendar(db_service)
    event = authored_event(db_service)
    data = lore_data(snapshot(db_service.get_connection()))
    data["context"] = {"calendars": [config.to_dict()]}
    for kind in ("entities", "events", "relations"):
        (tmp_path / f"{kind}.csv").write_text(
            csv_text(kind, data[kind]), encoding="utf-8"
        )
    (tmp_path / "manifest.json").write_text(json.dumps(table_manifest(data)))
    loaded = load_sources([{"path": str(tmp_path)}])
    assert loaded["context"] == data["context"]
    assert len(loaded["source_hashes"]) == 4
    assert loaded["events"][0]["id"] == event.id


def test_direct_import_is_no_longer_a_write_api(db_service):
    result = ImportService(db_service).import_batch({"entities": [{"name": "Unsafe"}]})
    assert not result.success
    assert not db_service.get_all_entities()


def test_prepared_import_undo_redo_survives_database_reopen(tmp_path):
    from src.cli.import_review import reviewed_command
    from src.commands.event_timing_commands import ApplyEventTimingPlanCommand
    from src.commands.event_timing_intents import request_for_command
    from src.core.event_timing.definitions import (
        EndpointDefinition,
        EventTimingDefinition,
    )
    from src.services.event_timing.planning import prepare_change
    from src.services.event_timing.store import capture

    db = DatabaseService(str(tmp_path / "persistent.kraken"))
    db.connect()
    before = snapshot(db.get_connection())
    root, child, owner, relation = uid(), uid(), uid(), uid()
    data = {
        "entities": [
            {
                "id": owner,
                "name": "Values",
                "tags": ["evidence"],
                "attributes": {
                    "null": None,
                    "empty": "",
                    "list": [],
                    "zero": 0.0,
                    "false": False,
                },
            }
        ],
        "events": [
            {"id": root, "name": "Root", "lore_date": 10},
            {
                "id": child,
                "name": "Child",
                "lore_date": None,
                "attributes": EventTimingDefinition(
                    EndpointDefinition(kind="event", anchor_id=f"event:{root}")
                ).apply({}),
            },
        ],
        "relations": [
            {
                "id": relation,
                "source_id": child,
                "target_id": owner,
                "rel_type": "changes_state",
                "attributes": {"payload": {"attributes": {"rank": "captain"}}},
            }
        ],
    }
    preview = prepare_import(db, data, {})
    assert not preview["errors"]
    state = capture(db)
    plan = prepare_change(
        state, request_for_command(ApplyTransferCommand(preview), state)
    )
    command = reviewed_command(db, preview, plan)
    assert command.execute(db).success
    after = snapshot(db.get_connection())
    serialized = json.dumps(command.to_dict())
    db.close()
    db.connect()
    restored = ApplyEventTimingPlanCommand.from_dict(json.loads(serialized))
    restored.undo(db)
    assert snapshot(db.get_connection()) == before
    db.close()
    db.connect()
    assert restored.execute(db).success
    assert snapshot(db.get_connection()) == after
    saved = db.get_entity(owner)
    assert saved.attributes["null"] is None
    assert saved.attributes["false"] is False
    assert saved.tags == ["evidence"]
    assert db.get_event(child).lore_date == 10
    db.close()


def test_portable_world_preserves_all_tables_and_full_world_controls(
    db_service, tmp_path
):
    from PIL import Image

    calendar(db_service)
    owner = Entity(
        id=uid(),
        name="Gallery owner",
        type="person",
        attributes={
            "_longform": {"default": {"position": 100, "parent_id": None}},
            "_tags": ["control"],
            "baseline": None,
        },
    )
    db_service.insert_entity(owner)
    db_service.assign_tag_to_entity(owner.id, "control")
    root = tmp_path / "source"
    (root / "assets").mkdir(parents=True)
    Image.new("L", (2, 2), color=64).save(root / "assets" / "raster.png")
    Image.new("RGB", (2, 2), color=(50, 70, 90)).save(root / "assets" / "gallery.png")
    layer = MapLayerNode(
        name="Rasters",
        layer_type="group",
        children=[
            MapLayerNode(
                name="Elevation",
                layer_type="raster",
                attributes={
                    "raster_path": "assets/raster.png",
                    "raster_snapshots": [{"date": 2.0, "path": "assets/raster.png"}],
                },
            )
        ],
    )
    world_map = Map(name="Control map", image_path="assets/raster.png", layers=layer)
    db_service.insert_map(world_map)
    connection = db_service.get_connection()
    marker = uid()
    with db_service.transaction():
        connection.execute(
            "INSERT INTO markers (id,map_id,object_id,object_type,x,y,feature_type,geometry) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                marker,
                world_map.id,
                owner.id,
                "entity",
                0.2,
                0.3,
                "path",
                "[[0.2,0.3],[0.4,0.5]]",
            ),
        )
        connection.execute(
            "INSERT INTO feature_geometry_states VALUES (?,?,?,?,?,?,?,?)",
            (uid(), marker, 3.0, "[[0.1,0.2],[0.8,0.9]]", 0.1, 0.2, 1.0, 1.0),
        )
        connection.execute(
            "INSERT INTO moving_features (id,marker_id,t_start,t_end,trajectory,properties,created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (
                uid(),
                marker,
                1.0,
                2.0,
                json.dumps(
                    {
                        "type": "MovingPoint",
                        "coordinates": [[0.2, 0.3], [0.4, 0.5]],
                        "datetimes": [1.0, 2.0],
                    }
                ),
                '{"schema":1}',
                1.0,
            ),
        )
        connection.execute(
            "INSERT INTO image_attachments (id,owner_type,owner_id,image_rel_path,caption) "
            "VALUES (?,?,?,?,?)",
            (uid(), "entity", owner.id, "assets/gallery.png", "Preserved gallery"),
        )
        connection.execute(
            "INSERT INTO system_meta (key,value) VALUES (?,?)",
            ("relation_vocabulary", '{"schema":1,"custom":[]}'),
        )
    tables = [
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
    ]
    before = {
        name: sorted(
            map(tuple, connection.execute(f'SELECT * FROM "{name}"')), key=repr
        )
        for name in tables
    }
    path = tmp_path / "control.krakenworld"
    export_world(
        connection,
        {
            "path": str(root),
            "manifest": {
                "id": uid(),
                "name": "Control",
                "db_filename": "control.kraken",
            },
        },
        path,
        lambda: False,
    )
    target = import_world(path, tmp_path / "worlds", "Imported", lambda: False)
    with sqlite3.connect(target / "world.kraken") as restored:
        for name, rows in before.items():
            assert (
                sorted(restored.execute(f'SELECT * FROM "{name}"').fetchall(), key=repr)
                == rows
            ), name
    for asset in (root / "assets").iterdir():
        assert (target / "assets" / asset.name).read_bytes() == asset.read_bytes()
