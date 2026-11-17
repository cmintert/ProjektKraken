"""Geographic invariance and snapshot safety for exact hierarchy moves."""

import json
from copy import deepcopy
from dataclasses import replace

import pytest

from src.commands.map_reparent_commands import PreserveMapPlacementCommand
from src.core.map import Map
from src.services.command_transactions import command_transaction
from src.services.map_nesting_service import MapNestingService
from src.services.map_reparenting import plan_preserved_reparent, preservation_options

pytestmark = pytest.mark.ci_fast


def registration(scale=0.4, aspect=1.0, rotation=0, center=(0.4, 0.6)):
    return {
        "mode": "aspect_locked_affine",
        "version": 1,
        "scale_norm": scale,
        "aspect_ratio": aspect,
        "rotation_deg": rotation,
        "master_center_norm": {"x": center[0], "y": center[1]},
    }


def records():
    return [
        Map("Root", "root.png", id="root"),
        Map(
            "Old",
            "old.png",
            id="old",
            attributes={
                "parent_map_id": "root",
                "registration": registration(rotation=37),
            },
        ),
        Map(
            "New",
            "new.png",
            id="new",
            attributes={
                "parent_map_id": "root",
                "registration": registration(scale=0.7, rotation=-23),
            },
        ),
        Map(
            "Moved",
            "move.png",
            id="move",
            attributes={
                "parent_map_id": "old",
                "map_role": None,
                "registration": registration(aspect=1.8, rotation=19),
                "width_meters": 900,
                "authored": {"notes": "keep"},
            },
        ),
        Map(
            "Descendant",
            "leaf.png",
            id="leaf",
            attributes={
                "parent_map_id": "move",
                "registration": registration(rotation=61),
            },
        ),
    ]


def assert_invariant(before, after):
    for map_id in ("move", "leaf"):
        for u in (0, 0.17, 0.5, 1):
            for v in (0, 0.43, 1):
                original = MapNestingService.resolve_to_root(map_id, (u, v), before)
                actual = MapNestingService.resolve_to_root(map_id, (u, v), after)
                assert actual[0] == original[0]
                assert actual[1] == pytest.approx(original[1], rel=1e-10, abs=1e-12)


@pytest.mark.parametrize("parent", ["new", "root", "old"])
def test_nested_rotated_non_square_placement_and_descendants_are_invariant(parent):
    maps = records()
    snapshot = deepcopy(maps)
    plan = plan_preserved_reparent(maps, "move", parent)
    moved = maps[3]
    after = [
        replace(
            m,
            attributes={
                **m.attributes,
                "parent_map_id": parent,
                "registration": plan.registration,
            },
        )
        if m.id == "move"
        else m
        for m in maps
    ]
    assert_invariant(maps, after)
    assert maps == snapshot
    assert after[4] == maps[4]
    assert moved.attributes["authored"] == {"notes": "keep"}
    assert set(plan.expected_context) == {
        "root",
        "old",
        "move",
        *(["new"] if parent == "new" else []),
    }


def test_anisotropic_target_with_aligned_axes_is_exact():
    maps = records()
    maps[1].attributes["registration"] = registration(aspect=2)
    maps[2].attributes["registration"] = registration(aspect=3)
    maps[3].attributes["registration"] = registration(aspect=1.5)
    plan = plan_preserved_reparent(maps, "move", "new")
    after = deepcopy(maps)
    after[3].attributes.update(parent_map_id="new", registration=plan.registration)
    assert_invariant(maps, after)


def test_shear_requires_explicit_manual_fallback():
    maps = records()
    maps[2].attributes["registration"] = registration(aspect=3, rotation=8)
    with pytest.raises(ValueError, match="skewing"):
        plan_preserved_reparent(maps, "move", "new")
    assert "skewing" in preservation_options(maps, "move", [maps[2]])["new"]


@pytest.mark.parametrize(
    "damage", ["unrelated", "missing", "invalid", "cycle", "descendant"]
)
def test_invalid_or_unconnected_chains_are_not_guessed(damage):
    maps = records()
    target = "new"
    if damage == "unrelated":
        maps[2].attributes = {}
    elif damage == "missing":
        del maps[1].attributes["registration"]
    elif damage == "invalid":
        maps[1].attributes["registration"]["scale_norm"] = float("nan")
    elif damage == "cycle":
        maps[1].attributes["parent_map_id"] = "move"
    else:
        target = "leaf"
    before = json.dumps([m.to_dict() for m in maps], sort_keys=True)
    with pytest.raises(ValueError):
        plan_preserved_reparent(maps, "move", target)
    assert json.dumps([m.to_dict() for m in maps], sort_keys=True) == before


@pytest.mark.parametrize(
    "scale,aspect", [(1e-300, 1e300), (1e300, 1e-300), (1e-300, 1)]
)
def test_numerically_unusable_registration_is_rejected(scale, aspect):
    maps = records()
    maps[2].attributes["registration"] = registration(scale=scale, aspect=aspect)
    with pytest.raises(ValueError):
        plan_preserved_reparent(maps, "move", "new")


@pytest.mark.parametrize("changed", ["move", "old", "new", "root"])
def test_worker_rejects_stale_source_or_either_ancestry(db_service, changed):
    maps = records()
    plan = plan_preserved_reparent(maps, "move", "new")
    command = PreserveMapPlacementCommand("move", "new", plan.expected_context)
    for m in maps:
        db_service.insert_map(m)
    stale = db_service.get_map(changed)
    stale.attributes["map_role"] = "changed"
    db_service.insert_map(stale)
    before = [m.to_dict() for m in db_service.get_all_maps()]
    assert not command.execute(db_service).success
    assert before == [m.to_dict() for m in db_service.get_all_maps()]


def test_serialized_worker_command_preserves_content_and_exact_history(db_service):
    maps = records()
    for m in maps:
        db_service.insert_map(m)
    plan = plan_preserved_reparent(maps, "move", "new")
    command = PreserveMapPlacementCommand("move", "new", plan.expected_context)
    # Mutating caller snapshots cannot alter the dispatched intent.
    plan.expected_context.clear()
    assert command.execute(db_service).success
    after = db_service.get_all_maps()
    assert_invariant(maps, after)
    first_saved = db_service.get_map("move").to_dict()
    command = PreserveMapPlacementCommand.from_dict(
        json.loads(json.dumps(command.to_dict()))
    )
    current = db_service.get_map("move")
    current.attributes["extra"] = "authored after move"
    db_service.insert_map(current)
    assert command.undo(db_service).success
    restored = db_service.get_map("move")
    assert restored.attributes == {**maps[3].attributes, "extra": "authored after move"}
    assert command.execute(db_service).success
    assert db_service.get_map("move").attributes == {
        **first_saved["attributes"],
        "extra": "authored after move",
    }
    for key in ("root", "old", "new", "leaf"):
        assert db_service.get_map(key).to_dict() == next(
            m.to_dict() for m in maps if m.id == key
        )


def test_failed_write_rolls_back_proposal_and_map(db_service, monkeypatch):
    maps = records()
    for record in maps:
        db_service.insert_map(record)
    plan = plan_preserved_reparent(maps, "move", "new")
    command = PreserveMapPlacementCommand("move", "new", plan.expected_context)
    before = command.to_dict()
    insert = db_service.insert_map

    def fail_after_write(record):
        insert(record)
        raise RuntimeError("Injected write failure")

    monkeypatch.setattr(db_service, "insert_map", fail_after_write)
    with pytest.raises(RuntimeError, match="Injected"):
        # The worker's outer history transaction opts into complete retry state.
        with command_transaction(db_service, restore_retry_state=True):
            command.execute(db_service)
    assert db_service.get_map("move").to_dict() == maps[3].to_dict()
    assert command.to_dict() == before
    monkeypatch.setattr(db_service, "insert_map", insert)
    assert command.execute(db_service).success
    assert_invariant(maps, db_service.get_all_maps())
