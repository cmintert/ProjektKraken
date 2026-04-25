"""Phase-1 tests for the master-map nesting feature.

Covers:
* MapRepository helpers (master lookup, child query, descendant walk).
* SetMasterMapCommand execute/undo with promotion + demotion semantics.
* RegisterDetailMapCommand execute/undo, including replacement semantics.
* DeleteMapCommand child-guard.
* Phase-1 minimal validator: structural failure modes.
"""

from __future__ import annotations

import pytest

from src.app.constants import MAP_ROLE_DETAIL, MAP_ROLE_MASTER
from src.commands.map_crud_commands import (
    DeleteMapCommand,
    NestingValidationError,
    RegisterDetailMapCommand,
    SetMasterMapCommand,
    _validate_registration,
)
from src.core.map import Map
from src.services.repositories.map_repository import MapRepository


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _make_map(name: str, **attrs) -> Map:
    return Map(name=name, image_path=f"/{name}.png", attributes=dict(attrs))


def _affine(parent_id: str | None = None, scale: float = 0.25) -> dict:
    """Return a minimal valid aspect-locked-affine registration payload."""
    return {
        "mode": "aspect_locked_affine",
        "version": 1,
        "master_center_norm": {"x": 0.5, "y": 0.5},
        "scale_norm": scale,
        "rotation_deg": 0.0,
        "aspect_ratio": 1.5,
        "confidence": "user_confirmed",
    }


# ---------------------------------------------------------------------------
# Repository helpers
# ---------------------------------------------------------------------------


def test_get_master_map_returns_designated_master():
    a = _make_map("A")
    b = _make_map("B", map_role=MAP_ROLE_MASTER)
    c = _make_map("C", map_role=MAP_ROLE_DETAIL, parent_map_id=b.id)

    assert MapRepository.get_master_map([a, b, c]) is b


def test_get_master_map_returns_none_when_unset():
    a = _make_map("A")
    b = _make_map("B")
    assert MapRepository.get_master_map([a, b]) is None


def test_get_children_of_returns_only_direct_children():
    master = _make_map("Master", map_role=MAP_ROLE_MASTER)
    detail = _make_map(
        "Detail",
        map_role=MAP_ROLE_DETAIL,
        parent_map_id=master.id,
        registration=_affine(),
    )
    grand = _make_map(
        "Grand",
        map_role=MAP_ROLE_DETAIL,
        parent_map_id=detail.id,
        registration=_affine(),
    )

    children = MapRepository.get_children_of(master.id, [master, detail, grand])
    assert children == [detail]


def test_iter_descendants_walks_full_subtree():
    root = _make_map("Root", map_role=MAP_ROLE_MASTER)
    mid = _make_map(
        "Mid",
        map_role=MAP_ROLE_DETAIL,
        parent_map_id=root.id,
        registration=_affine(),
    )
    leaf = _make_map(
        "Leaf",
        map_role=MAP_ROLE_DETAIL,
        parent_map_id=mid.id,
        registration=_affine(),
    )
    sibling = _make_map(
        "Sibling",
        map_role=MAP_ROLE_DETAIL,
        parent_map_id=root.id,
        registration=_affine(),
    )

    descendants = list(
        MapRepository.iter_descendants(root.id, [root, mid, leaf, sibling])
    )
    assert {m.id for m in descendants} == {mid.id, leaf.id, sibling.id}


# ---------------------------------------------------------------------------
# SetMasterMapCommand
# ---------------------------------------------------------------------------


def test_set_master_map_promotes_target(db_service):
    map_a = _make_map("A")
    db_service.insert_map(map_a)

    cmd = SetMasterMapCommand(map_a.id)
    result = cmd.execute(db_service)

    assert result.success is True
    assert db_service.get_map(map_a.id).attributes["map_role"] == MAP_ROLE_MASTER


def test_set_master_map_demotes_previous(db_service):
    old = _make_map("Old", map_role=MAP_ROLE_MASTER)
    new = _make_map("New")
    db_service.insert_map(old)
    db_service.insert_map(new)

    cmd = SetMasterMapCommand(new.id)
    cmd.execute(db_service)

    assert db_service.get_map(new.id).attributes["map_role"] == MAP_ROLE_MASTER
    assert "map_role" not in db_service.get_map(old.id).attributes


def test_set_master_map_undo_restores_previous(db_service):
    old = _make_map("Old", map_role=MAP_ROLE_MASTER)
    new = _make_map("New")
    db_service.insert_map(old)
    db_service.insert_map(new)

    cmd = SetMasterMapCommand(new.id)
    cmd.execute(db_service)
    cmd.undo(db_service)

    assert db_service.get_map(old.id).attributes["map_role"] == MAP_ROLE_MASTER
    assert "map_role" not in db_service.get_map(new.id).attributes


def test_set_master_map_promote_strips_parent_link(db_service):
    """Promoting a detail map to master must clear its parent registration."""
    master = _make_map("Master", map_role=MAP_ROLE_MASTER)
    detail = _make_map(
        "Detail",
        map_role=MAP_ROLE_DETAIL,
        parent_map_id=master.id,
        registration=_affine(),
    )
    db_service.insert_map(master)
    db_service.insert_map(detail)

    cmd = SetMasterMapCommand(detail.id)
    cmd.execute(db_service)

    promoted = db_service.get_map(detail.id)
    assert promoted.attributes["map_role"] == MAP_ROLE_MASTER
    assert "parent_map_id" not in promoted.attributes
    assert "registration" not in promoted.attributes


# ---------------------------------------------------------------------------
# RegisterDetailMapCommand
# ---------------------------------------------------------------------------


def test_register_detail_map_persists_metadata(db_service):
    master = _make_map("Master", map_role=MAP_ROLE_MASTER)
    detail = _make_map("Detail")
    db_service.insert_map(master)
    db_service.insert_map(detail)

    reg = _affine()
    cmd = RegisterDetailMapCommand(detail.id, master.id, reg)
    result = cmd.execute(db_service)

    assert result.success is True, result.message
    stored = db_service.get_map(detail.id)
    assert stored.attributes["map_role"] == MAP_ROLE_DETAIL
    assert stored.attributes["parent_map_id"] == master.id
    assert stored.attributes["registration"] == reg


def test_register_detail_map_undo_restores_attributes(db_service):
    master = _make_map("Master", map_role=MAP_ROLE_MASTER)
    detail = _make_map("Detail")
    db_service.insert_map(master)
    db_service.insert_map(detail)

    cmd = RegisterDetailMapCommand(detail.id, master.id, _affine())
    cmd.execute(db_service)
    cmd.undo(db_service)

    restored = db_service.get_map(detail.id)
    assert "map_role" not in restored.attributes
    assert "parent_map_id" not in restored.attributes
    assert "registration" not in restored.attributes


def test_register_detail_map_replace_captures_prior_state(db_service):
    """Re-registration replaces; one undo restores the prior parent."""
    master_a = _make_map("MasterA", map_role=MAP_ROLE_MASTER)
    master_b = _make_map("MasterB")  # promoted later
    detail = _make_map("Detail")
    db_service.insert_map(master_a)
    db_service.insert_map(master_b)
    db_service.insert_map(detail)

    # First registration under master_a.
    cmd1 = RegisterDetailMapCommand(detail.id, master_a.id, _affine(scale=0.2))
    cmd1.execute(db_service)

    # Promote master_b so it can act as a parent.
    SetMasterMapCommand(master_b.id).execute(db_service)

    # Re-register under master_b.
    cmd2 = RegisterDetailMapCommand(detail.id, master_b.id, _affine(scale=0.4))
    cmd2.execute(db_service)
    after_replace = db_service.get_map(detail.id)
    assert after_replace.attributes["parent_map_id"] == master_b.id
    assert after_replace.attributes["registration"]["scale_norm"] == 0.4

    # Undoing the second registration restores the first one's parent.
    cmd2.undo(db_service)
    restored = db_service.get_map(detail.id)
    assert restored.attributes["parent_map_id"] == master_a.id
    assert restored.attributes["registration"]["scale_norm"] == 0.2


def test_register_detail_map_rejects_invalid_payload(db_service):
    master = _make_map("Master", map_role=MAP_ROLE_MASTER)
    detail = _make_map("Detail")
    db_service.insert_map(master)
    db_service.insert_map(detail)

    bad = _affine()
    bad["scale_norm"] = -1.0
    cmd = RegisterDetailMapCommand(detail.id, master.id, bad)
    result = cmd.execute(db_service)
    assert result.success is False
    assert "Invalid registration" in result.message
    # Detail map must not be mutated when validation fails.
    assert "map_role" not in db_service.get_map(detail.id).attributes


# ---------------------------------------------------------------------------
# DeleteMapCommand child-guard
# ---------------------------------------------------------------------------


def test_delete_map_blocked_by_child(db_service):
    master = _make_map("Master", map_role=MAP_ROLE_MASTER)
    detail = _make_map(
        "Detail",
        map_role=MAP_ROLE_DETAIL,
        parent_map_id=master.id,
        registration=_affine(),
    )
    db_service.insert_map(master)
    db_service.insert_map(detail)

    cmd = DeleteMapCommand(master.id)
    result = cmd.execute(db_service)
    assert result.success is False
    assert "Detail" in result.message
    # Master must still exist.
    assert db_service.get_map(master.id) is not None


def test_delete_map_allowed_when_no_children(db_service):
    standalone = _make_map("Solo")
    db_service.insert_map(standalone)

    cmd = DeleteMapCommand(standalone.id)
    result = cmd.execute(db_service)
    assert result.success is True
    assert db_service.get_map(standalone.id) is None


def test_delete_map_undo_restores(db_service):
    standalone = _make_map("Solo")
    db_service.insert_map(standalone)

    cmd = DeleteMapCommand(standalone.id)
    cmd.execute(db_service)
    cmd.undo(db_service)
    restored = db_service.get_map(standalone.id)
    assert restored is not None
    assert restored.name == "Solo"


# ---------------------------------------------------------------------------
# Phase-1 minimal validator
# ---------------------------------------------------------------------------


def test_validate_rejects_self_parent():
    a = _make_map("A", map_role=MAP_ROLE_MASTER)
    with pytest.raises(NestingValidationError):
        _validate_registration(a.id, a.id, _affine(), [a])


def test_validate_rejects_unknown_parent():
    a = _make_map("A")
    with pytest.raises(NestingValidationError):
        _validate_registration(a.id, "nonexistent-parent", _affine(), [a])


def test_validate_rejects_parent_without_role():
    parent = _make_map("Parent")  # no map_role
    detail = _make_map("Detail")
    with pytest.raises(NestingValidationError):
        _validate_registration(detail.id, parent.id, _affine(), [parent, detail])


def test_validate_rejects_cycle():
    """A → B → A is not a depth violation but is a cycle."""
    a = _make_map("A", map_role=MAP_ROLE_MASTER)
    b = _make_map(
        "B",
        map_role=MAP_ROLE_DETAIL,
        parent_map_id=a.id,
        registration=_affine(),
    )
    # Now try to register A as a detail of B — would create A -> B -> A.
    with pytest.raises(NestingValidationError):
        _validate_registration(a.id, b.id, _affine(), [a, b])


def test_validate_rejects_depth_overflow():
    chain = [_make_map("R", map_role=MAP_ROLE_MASTER)]
    for i in range(4):  # 4 detail layers under root → depth 5 (cap)
        prev = chain[-1]
        chain.append(
            _make_map(
                f"L{i}",
                map_role=MAP_ROLE_DETAIL,
                parent_map_id=prev.id,
                registration=_affine(),
            )
        )
    new_detail = _make_map("Extra")
    with pytest.raises(NestingValidationError):
        _validate_registration(
            new_detail.id, chain[-1].id, _affine(), chain + [new_detail]
        )


@pytest.mark.parametrize(
    "mutator",
    [
        lambda r: r.update({"mode": "freeform"}),
        lambda r: r.update({"scale_norm": 0}),
        lambda r: r.update({"aspect_ratio": -2}),
        lambda r: r.update({"rotation_deg": float("nan")}),
        lambda r: r.update({"master_center_norm": {"x": "oops", "y": 0.5}}),
    ],
)
def test_validate_rejects_malformed_payload(mutator):
    parent = _make_map("Parent", map_role=MAP_ROLE_MASTER)
    detail = _make_map("Detail")
    reg = _affine()
    mutator(reg)
    with pytest.raises(NestingValidationError):
        _validate_registration(detail.id, parent.id, reg, [parent, detail])
