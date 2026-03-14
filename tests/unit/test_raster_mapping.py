"""Tests for raster_mapping helpers.

Covers: make_empty_vem, normalize_value_entity_map, validate_no_overlaps,
lookup_entity_for_value, lookup_label_for_value, lookup_item_type_for_value,
RasterMappingEntry, RasterValueEntityMap, RasterItemRef, ProbeResult,
build_item_raster_index, and SetRasterMappingCommand overlap rejection.
"""

from src.gui.widgets.map.raster_mapping import (
    ProbeResult,
    RasterItemRef,
    RasterMappingEntry,
    RasterValueEntityMap,
    build_item_raster_index,
    lookup_entity_for_value,
    lookup_item_type_for_value,
    lookup_label_for_value,
    make_empty_vem,
    normalize_value_entity_map,
    validate_no_overlaps,
)

# ---------------------------------------------------------------------------
# make_empty_vem
# ---------------------------------------------------------------------------


def test_make_empty_vem_exact():
    vem = make_empty_vem("exact")
    assert vem["mode"] == "exact"
    assert vem["mappings"] == []


def test_make_empty_vem_range():
    vem = make_empty_vem("range")
    assert vem["mode"] == "range"
    assert vem["mappings"] == []


def test_make_empty_vem_default_is_exact():
    vem = make_empty_vem()
    assert vem["mode"] == "exact"


# ---------------------------------------------------------------------------
# normalize_value_entity_map
# ---------------------------------------------------------------------------


def test_normalize_none_returns_empty():
    assert normalize_value_entity_map(None) == {"mode": "exact", "mappings": []}


def test_normalize_empty_dict_returns_empty():
    assert normalize_value_entity_map({}) == {"mode": "exact", "mappings": []}


def test_normalize_invalid_type_returns_empty():
    assert normalize_value_entity_map([1, 2, 3]) == {
        "mode": "exact",
        "mappings": [],
    }


def test_normalize_legacy_flat_dict_converts_to_structured():
    legacy = {"1": "entity-a", "42": "entity-b"}
    result = normalize_value_entity_map(legacy)
    assert result["mode"] == "exact"
    values = {m["value"] for m in result["mappings"]}
    assert 1 in values
    assert 42 in values
    entity_ids = {m["entity_id"] for m in result["mappings"]}
    assert "entity-a" in entity_ids
    assert "entity-b" in entity_ids


def test_normalize_legacy_flat_dict_skips_non_int_keys():
    legacy = {"7": "entity-7", "not_an_int": "entity-x"}
    result = normalize_value_entity_map(legacy)
    assert len(result["mappings"]) == 1
    assert result["mappings"][0]["value"] == 7


def test_normalize_legacy_assigns_stable_ids():
    legacy = {"3": "eid"}
    result = normalize_value_entity_map(legacy)
    assert result["mappings"][0].get("id")


def test_normalize_structured_without_ids_backfills_them():
    structured = {
        "mode": "exact",
        "mappings": [
            {"value": 5, "entity_id": "eid-5", "label": "Forest"},
        ],
    }
    result = normalize_value_entity_map(structured)
    assert result["mappings"][0]["id"]  # ID was backfilled


def test_normalize_structured_preserves_existing_ids():
    structured = {
        "mode": "exact",
        "mappings": [
            {"id": "existing-id", "value": 7, "entity_id": "eid-7"},
        ],
    }
    result = normalize_value_entity_map(structured)
    assert result["mappings"][0]["id"] == "existing-id"


def test_normalize_range_mode_preserved():
    structured = {
        "mode": "range",
        "mappings": [{"id": "r1", "min": 0, "max": 100, "label": "Low"}],
    }
    result = normalize_value_entity_map(structured)
    assert result["mode"] == "range"
    assert result["mappings"][0]["min"] == 0
    assert result["mappings"][0]["max"] == 100


# ---------------------------------------------------------------------------
# validate_no_overlaps
# ---------------------------------------------------------------------------


def test_validate_empty_has_no_errors():
    assert validate_no_overlaps({"mode": "exact", "mappings": []}) == []


def test_validate_exact_no_overlap():
    vem = {
        "mode": "exact",
        "mappings": [
            {"id": "a", "value": 1, "label": "A"},
            {"id": "b", "value": 2, "label": "B"},
            {"id": "c", "value": 99, "label": "C"},
        ],
    }
    assert validate_no_overlaps(vem) == []


def test_validate_exact_same_value_detected():
    vem = {
        "mode": "exact",
        "mappings": [
            {"id": "a", "value": 5, "label": "A"},
            {"id": "b", "value": 5, "label": "B"},
        ],
    }
    errors = validate_no_overlaps(vem)
    assert len(errors) == 1
    assert "A" in errors[0] and "B" in errors[0]


def test_validate_range_no_overlap():
    vem = {
        "mode": "range",
        "mappings": [
            {"id": "a", "min": 0, "max": 100, "label": "Low"},
            {"id": "b", "min": 101, "max": 200, "label": "Mid"},
            {"id": "c", "min": 201, "max": 65535, "label": "High"},
        ],
    }
    assert validate_no_overlaps(vem) == []


def test_validate_range_adjacent_no_overlap():
    vem = {
        "mode": "range",
        "mappings": [
            {"id": "a", "min": 0, "max": 100, "label": "Low"},
            {"id": "b", "min": 101, "max": 200, "label": "High"},
        ],
    }
    assert validate_no_overlaps(vem) == []


def test_validate_range_overlap_detected():
    vem = {
        "mode": "range",
        "mappings": [
            {"id": "a", "min": 0, "max": 150, "label": "A"},
            {"id": "b", "min": 100, "max": 200, "label": "B"},
        ],
    }
    errors = validate_no_overlaps(vem)
    assert len(errors) >= 1


def test_validate_range_contained_overlap_detected():
    vem = {
        "mode": "range",
        "mappings": [
            {"id": "a", "min": 0, "max": 1000, "label": "A"},
            {"id": "b", "min": 100, "max": 200, "label": "B"},
        ],
    }
    assert len(validate_no_overlaps(vem)) >= 1


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------


def _meta(mappings, mode="exact"):
    """Build a minimal layer meta dict with the given mappings."""
    return {
        "value_entity_map": {
            "mode": mode,
            "mappings": [{"id": f"id-{i}", **m} for i, m in enumerate(mappings)],
        }
    }


def test_lookup_entity_exact_match():
    meta = _meta(
        [
            {
                "value": 1,
                "entity_id": "wolf-id",
                "item_type": "entity",
                "label": "Wolf",
            },
            {
                "value": 2,
                "entity_id": "bear-id",
                "item_type": "entity",
                "label": "Bear",
            },
        ]
    )
    assert lookup_entity_for_value(meta, 1) == "wolf-id"
    assert lookup_entity_for_value(meta, 2) == "bear-id"


def test_lookup_entity_no_match_returns_none():
    meta = _meta([{"value": 1, "entity_id": "wolf-id", "label": "Wolf"}])
    assert lookup_entity_for_value(meta, 99) is None


def test_lookup_entity_empty_meta_returns_none():
    assert lookup_entity_for_value({}, 1) is None
    assert lookup_entity_for_value({"value_entity_map": None}, 1) is None


def test_lookup_entity_range_mode():
    meta = _meta(
        [
            {"min": 0, "max": 100, "entity_id": "low-id", "label": "Low"},
            {"min": 101, "max": 200, "entity_id": "high-id", "label": "High"},
        ],
        mode="range",
    )
    assert lookup_entity_for_value(meta, 50) == "low-id"
    assert lookup_entity_for_value(meta, 150) == "high-id"
    assert lookup_entity_for_value(meta, 201) is None


def test_lookup_entity_boundary_values():
    meta = _meta(
        [{"min": 0, "max": 100, "entity_id": "eid", "label": "Band"}],
        mode="range",
    )
    assert lookup_entity_for_value(meta, 0) == "eid"
    assert lookup_entity_for_value(meta, 100) == "eid"
    assert lookup_entity_for_value(meta, 101) is None


def test_lookup_entity_legacy_flat_dict():
    meta = {"value_entity_map": {"7": "entity-7", "13": "entity-13"}}
    assert lookup_entity_for_value(meta, 7) == "entity-7"
    assert lookup_entity_for_value(meta, 13) == "entity-13"
    assert lookup_entity_for_value(meta, 1) is None


def test_lookup_label_exact():
    meta = _meta([{"value": 3, "label": "Forest"}])
    assert lookup_label_for_value(meta, 3) == "Forest"
    assert lookup_label_for_value(meta, 4) is None


def test_lookup_label_range():
    meta = _meta(
        [{"min": 0, "max": 50, "label": "Tundra"}],
        mode="range",
    )
    assert lookup_label_for_value(meta, 25) == "Tundra"


def test_lookup_item_type_entity():
    meta = _meta(
        [{"value": 5, "entity_id": "e-id", "item_type": "entity", "label": "Wolf"}]
    )
    assert lookup_item_type_for_value(meta, 5) == "entity"


def test_lookup_item_type_event():
    meta = _meta(
        [{"value": 8, "entity_id": "ev-id", "item_type": "event", "label": "Battle"}]
    )
    assert lookup_item_type_for_value(meta, 8) == "event"


def test_lookup_item_type_unlinked_entry():
    meta = _meta([{"value": 10, "label": "Region"}])
    assert lookup_item_type_for_value(meta, 10) is None


def test_lookup_item_type_missing_vem():
    assert lookup_item_type_for_value({}, 1) is None


# ---------------------------------------------------------------------------
# RasterMappingEntry
# ---------------------------------------------------------------------------


def test_raster_mapping_entry_roundtrip_exact():
    entry = RasterMappingEntry(
        id="test-id",
        label="Forest",
        entity_id="eid-123",
        item_type="entity",
        value=42,
    )
    d = entry.to_dict()
    assert d == {
        "id": "test-id",
        "label": "Forest",
        "entity_id": "eid-123",
        "item_type": "entity",
        "value": 42,
    }
    restored = RasterMappingEntry.from_dict(d)
    assert restored.id == "test-id"
    assert restored.value == 42
    assert restored.entity_id == "eid-123"
    assert "min" not in d
    assert "max" not in d


def test_raster_mapping_entry_roundtrip_range():
    entry = RasterMappingEntry(id="range-id", label="Cold", min=0, max=100)
    d = entry.to_dict()
    assert d["min"] == 0
    assert d["max"] == 100
    assert "value" not in d
    restored = RasterMappingEntry.from_dict(d)
    assert restored.min == 0
    assert restored.max == 100


def test_raster_mapping_entry_from_dict_assigns_id_if_absent():
    entry = RasterMappingEntry.from_dict({"value": 1, "label": "X"})
    assert entry.id


def test_raster_mapping_entry_omits_none_fields():
    entry = RasterMappingEntry(id="x", label="", value=5)
    d = entry.to_dict()
    assert "entity_id" not in d
    assert "item_type" not in d
    assert "min" not in d
    assert "max" not in d


# ---------------------------------------------------------------------------
# RasterValueEntityMap
# ---------------------------------------------------------------------------


def test_raster_value_entity_map_roundtrip():
    vem = RasterValueEntityMap(
        mode="exact",
        mappings=[
            RasterMappingEntry(id="id-1", label="A", value=1),
            RasterMappingEntry(id="id-2", label="B", value=2),
        ],
    )
    d = vem.to_dict()
    assert d["mode"] == "exact"
    assert len(d["mappings"]) == 2

    restored = RasterValueEntityMap.from_dict(d)
    assert restored.mode == "exact"
    assert len(restored.mappings) == 2
    assert restored.mappings[0].id == "id-1"
    assert restored.mappings[1].label == "B"


def test_raster_value_entity_map_empty():
    vem = RasterValueEntityMap()
    d = vem.to_dict()
    assert d == {"mode": "exact", "mappings": []}


# ---------------------------------------------------------------------------
# ProbeResult
# ---------------------------------------------------------------------------


def test_probe_result_has_item_type_field():
    result = ProbeResult(
        node_id="node-1",
        value=42,
        entity_id="eid",
        item_type="entity",
        label="Wolf",
    )
    assert result.item_type == "entity"
    assert result.entity_id == "eid"
    assert result.label == "Wolf"


def test_probe_result_item_type_defaults_none():
    result = ProbeResult(node_id="node-1", value=0)
    assert result.item_type is None
    assert result.entity_id is None
    assert result.label is None


# ---------------------------------------------------------------------------
# RasterItemRef
# ---------------------------------------------------------------------------


def test_raster_item_ref_exact():
    ref = RasterItemRef(
        map_id="map-1",
        node_id="node-1",
        mapping_id="m-id",
        label="Wolf territory",
        mode="exact",
        value=7,
    )
    assert ref.map_id == "map-1"
    assert ref.value == 7
    assert ref.min is None


def test_raster_item_ref_range():
    ref = RasterItemRef(
        map_id="map-2",
        node_id="node-2",
        mapping_id="m-id-2",
        label="Cold zone",
        mode="range",
        min=0,
        max=100,
    )
    assert ref.min == 0
    assert ref.max == 100
    assert ref.value is None


# ---------------------------------------------------------------------------
# build_item_raster_index
# ---------------------------------------------------------------------------


def test_build_item_raster_index_basic():
    maps_data = [
        {
            "id": "map-1",
            "attributes": {
                "raster_layers": [
                    {
                        "node_id": "layer-1",
                        "value_entity_map": {
                            "mode": "exact",
                            "mappings": [
                                {
                                    "id": "m1",
                                    "value": 1,
                                    "entity_id": "wolf-id",
                                    "item_type": "entity",
                                    "label": "Wolf",
                                },
                                {
                                    "id": "m2",
                                    "value": 2,
                                    "entity_id": "bear-id",
                                    "item_type": "entity",
                                    "label": "Bear",
                                },
                            ],
                        },
                    }
                ]
            },
        }
    ]
    index = build_item_raster_index(maps_data)
    assert "wolf-id" in index
    assert "bear-id" in index
    wolf_refs = index["wolf-id"]
    assert len(wolf_refs) == 1
    assert wolf_refs[0].map_id == "map-1"
    assert wolf_refs[0].node_id == "layer-1"
    assert wolf_refs[0].label == "Wolf"
    assert wolf_refs[0].value == 1


def test_build_item_raster_index_skips_unlinked_entries():
    maps_data = [
        {
            "id": "map-1",
            "attributes": {
                "raster_layers": [
                    {
                        "node_id": "layer-1",
                        "value_entity_map": {
                            "mode": "exact",
                            "mappings": [
                                {"id": "m1", "value": 5, "label": "Unlabeled"},
                            ],
                        },
                    }
                ]
            },
        }
    ]
    index = build_item_raster_index(maps_data)
    assert index == {}


def test_build_item_raster_index_multiple_maps():
    maps_data = [
        {
            "id": "map-1",
            "attributes": {
                "raster_layers": [
                    {
                        "node_id": "layer-A",
                        "value_entity_map": {
                            "mode": "exact",
                            "mappings": [
                                {
                                    "id": "m1",
                                    "value": 1,
                                    "entity_id": "eid-1",
                                    "label": "A",
                                },
                            ],
                        },
                    }
                ]
            },
        },
        {
            "id": "map-2",
            "attributes": {
                "raster_layers": [
                    {
                        "node_id": "layer-B",
                        "value_entity_map": {
                            "mode": "exact",
                            "mappings": [
                                {
                                    "id": "m2",
                                    "value": 3,
                                    "entity_id": "eid-1",
                                    "label": "A again",
                                },
                            ],
                        },
                    }
                ]
            },
        },
    ]
    index = build_item_raster_index(maps_data)
    assert len(index["eid-1"]) == 2
    map_ids = {r.map_id for r in index["eid-1"]}
    assert map_ids == {"map-1", "map-2"}


def test_build_item_raster_index_legacy_vem():
    """build_item_raster_index should handle legacy flat-dict VEM transparently."""
    maps_data = [
        {
            "id": "map-1",
            "attributes": {
                "raster_layers": [
                    {
                        "node_id": "layer-1",
                        "value_entity_map": {"7": "wolf-id"},
                    }
                ]
            },
        }
    ]
    index = build_item_raster_index(maps_data)
    assert "wolf-id" in index
    assert index["wolf-id"][0].value == 7


def test_build_item_raster_index_empty_maps():
    assert build_item_raster_index([]) == {}


def test_build_item_raster_index_no_raster_layers():
    maps_data = [{"id": "map-1", "attributes": {}}]
    assert build_item_raster_index(maps_data) == {}


# ---------------------------------------------------------------------------
# SetRasterMappingCommand overlap rejection (integration)
# ---------------------------------------------------------------------------


def test_set_raster_mapping_command_rejects_overlapping_exact(db_service):
    """SetRasterMappingCommand.execute() must fail for overlapping exact entries."""

    # Create a map and raster layer
    import tempfile

    from src.commands.map_commands import CreateMapCommand
    from src.commands.raster_commands import (
        CreateRasterLayerCommand,
        SetRasterMappingCommand,
    )

    world_root = tempfile.mkdtemp()
    map_cmd = CreateMapCommand({"name": "Test Map", "image_path": ""})
    result = map_cmd.execute(db_service)
    assert result.success
    map_id = result.data["id"]

    layer_cmd = CreateRasterLayerCommand(
        map_id=map_id,
        name="Biome",
        width=64,
        height=64,
        mode="discrete",
        world_root=world_root,
    )
    layer_result = layer_cmd.execute(db_service)
    assert layer_result.success
    node_id = layer_result.data["node_id"]

    # Build an overlapping mapping (both entries claim value 5)
    bad_mapping = {
        "mode": "exact",
        "mappings": [
            {"id": "m1", "value": 5, "label": "Forest", "entity_id": "eid-1"},
            {"id": "m2", "value": 5, "label": "Desert", "entity_id": "eid-2"},
        ],
    }
    cmd = SetRasterMappingCommand(
        map_id=map_id,
        node_id=node_id,
        new_mapping=bad_mapping,
        old_mapping={},
    )
    cmd_result = cmd.execute(db_service)
    assert not cmd_result.success
    assert "overlap" in cmd_result.message.lower()

    # Clean up
    import shutil

    shutil.rmtree(world_root, ignore_errors=True)


def test_set_raster_mapping_command_accepts_valid_mapping(db_service):
    """SetRasterMappingCommand.execute() must succeed for non-overlapping entries."""
    import tempfile

    from src.commands.map_commands import CreateMapCommand
    from src.commands.raster_commands import (
        CreateRasterLayerCommand,
        SetRasterMappingCommand,
    )

    world_root = tempfile.mkdtemp()
    map_cmd = CreateMapCommand({"name": "Test Map 2", "image_path": ""})
    result = map_cmd.execute(db_service)
    assert result.success
    map_id = result.data["id"]

    layer_cmd = CreateRasterLayerCommand(
        map_id=map_id,
        name="Biome",
        width=64,
        height=64,
        mode="discrete",
        world_root=world_root,
    )
    layer_result = layer_cmd.execute(db_service)
    assert layer_result.success
    node_id = layer_result.data["node_id"]

    good_mapping = {
        "mode": "exact",
        "mappings": [
            {"id": "m1", "value": 1, "label": "Forest", "entity_id": "eid-1"},
            {"id": "m2", "value": 2, "label": "Desert", "entity_id": "eid-2"},
        ],
    }
    cmd = SetRasterMappingCommand(
        map_id=map_id,
        node_id=node_id,
        new_mapping=good_mapping,
        old_mapping={},
    )
    cmd_result = cmd.execute(db_service)
    assert cmd_result.success

    import shutil

    shutil.rmtree(world_root, ignore_errors=True)
