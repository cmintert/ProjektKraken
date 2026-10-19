"""Pure reconciliation regression cases for KRT-41."""

from copy import deepcopy

import pytest

from src.core.events import Event
from src.services.timeline_event_preparation_service import (
    TimelineEventPreparationService as Preparation,
)

pytestmark = pytest.mark.ci_fast


def effect(event=None, *, delete=None):
    return {
        "object_type": "event",
        "object_id": delete if delete is not None else event.id,
        "operation": "delete" if delete is not None else "upsert",
        "snapshot": None if delete is not None else event.to_dict(),
        "relations_changed": False,
    }


def test_replacement_keeps_identity_and_equal_date_order():
    a = Event(id="a", name="A", lore_date=0.125)
    b = Event(id="b", name="B", lore_date=0.125)
    earlier = Event(id="early", name="Earlier", lore_date=-1.5)
    result = Preparation.replace([a, b, earlier], {"a", "gone"})
    assert result.events == (earlier, a, b)
    assert result.events[1] is a
    assert result.upserts == result.events
    assert result.removed_ids == {"gone"}
    assert result.layout_changed


def test_ordered_effects_preserve_untouched_identity_and_last_update():
    a = Event(id="a", name="A", lore_date=0)
    b = Event(id="b", name="B", lore_date=0)
    renamed = Event(id="a", name="Latest", lore_date=0)
    result = Preparation.apply_effects(
        [a, b], [effect(delete="a"), effect(a), effect(renamed)]
    )
    assert result.events[0] is b
    assert result.events[1].name == "Latest"
    assert len(result.upserts) == 1
    assert not result.removed_ids
    assert result.layout_changed
    assert a.name == "A"


@pytest.mark.parametrize("operation", ["move", "delete"])
def test_absent_delete_cannot_erase_prior_geometry_change(operation):
    event = Event(id="a", name="A", lore_date=1)
    changed = Event(id="a", name="A", lore_date=2)
    first = effect(changed) if operation == "move" else effect(delete="a")
    result = Preparation.apply_effects([event], [first, effect(delete="absent")])
    assert result.layout_changed
    assert len(result.events) == (1 if operation == "move" else 0)


def test_absent_deletion_is_not_a_geometry_change():
    assert not Preparation.apply_effects([], [effect(delete="absent")]).layout_changed


def test_metadata_refresh_does_not_repack():
    a = Event(id="a", name="A", lore_date=0)
    changed = Event.from_dict(deepcopy(a.to_dict()))
    changed.description = "New prose"
    result = Preparation.apply_effects([a], [effect(changed)])
    assert not result.layout_changed
    assert result.upserts[0].description == "New prose"
    assert a.description != "New prose"


@pytest.mark.parametrize(
    "field,value",
    [
        ("name", "Longer name"),
        ("lore_date", -0.125),
        ("lore_duration", 0.25),
        ("type", "combat"),
        ("tags", ["War"]),
        ("attributes", {"_temporal_v2": {"kind": "approximate"}}),
    ],
)
def test_geometry_and_grouping_fields_invalidate(field, value):
    a = Event(id="a", name="A", lore_date=0)
    changed = Event.from_dict(deepcopy(a.to_dict()))
    setattr(changed, field, value)
    assert Preparation.apply_effects([a], [effect(changed)]).layout_changed


def test_upsert_then_delete_leaves_no_upsert():
    event = Event(id="a", name="A", lore_date=0)
    result = Preparation.apply_effects([], [effect(event), effect(delete="a")])
    assert result.events == result.upserts == ()
    assert result.removed_ids == {"a"}
