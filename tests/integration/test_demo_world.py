"""Verify the first-session sample through persisted production models."""

import json

import pytest

from scripts.create_demo_world import ARMY_ICON_ID, create_demo_world
from src.core.analysis import IssueType
from src.core.calendar import CalendarConverter
from src.core.feature_geometry_state import resolve_feature_geometry
from src.core.temporal_anchors import resolve_event_anchors
from src.core.temporal_manager import TemporalManager
from src.core.temporal_window import TemporalValidity, resolve_temporal_window
from src.core.trajectory import interpolate_position
from src.services.db_service import DatabaseService
from src.services.longform_builder import build_longform_sequence
from src.services.marker_icon_catalog import MarkerIconCatalog
from src.services.world_validator import WorldValidator

pytestmark = pytest.mark.ci_fast


@pytest.fixture
def demo(tmp_path):
    world = create_demo_world(tmp_path / "Northwatch")
    index = json.loads((world.path / "demo-index.json").read_text())
    service = DatabaseService(str(world.db_path))
    service.connect()
    try:
        yield world, index, service
    finally:
        service.close()


def test_saved_demo_changes_ruler_description_border_and_location(demo):
    world, index, db = demo
    manager = TemporalManager(db)
    realm_id = index["entities"]["Kingdom of Ashford"]
    before, change = index["before"], index["succession"]
    assert (
        manager.get_entity_state_at(realm_id, before).attributes["Ruler"]
        == "Queen Mara"
    )
    assert (
        manager.get_entity_state_at(realm_id, change - 0.001).attributes["Ruler"]
        == "Queen Mara"
    )
    state = manager.get_entity_state_at(realm_id, change)
    assert state.attributes["Ruler"] == "Captain Ilyra"
    assert "eastern coast" in state.description
    keep_id = index["entities"]["Northwatch Keep"]
    assert (
        manager.get_entity_state_at(keep_id, before).attributes["Allegiance"]
        == "Independent"
    )
    assert (
        manager.get_entity_state_at(keep_id, change).attributes["Allegiance"]
        == "Kingdom of Ashford"
    )
    markers = db.get_markers_for_map(index["map_id"])
    border = next(marker for marker in markers if marker.object_id == realm_id)
    states = db.feature_geometry_repo.get_states(border.id)
    assert (
        resolve_feature_geometry(border, states, change - 0.001).source_type == "base"
    )
    expanded = resolve_feature_geometry(border, states, change)
    assert expanded.source_type == "dated"
    assert max(p["x"] for p in expanded.geometry) > max(p["x"] for p in border.geometry)
    army = next(
        marker
        for marker in markers
        if marker.object_id == index["entities"]["Ashford Army"]
    )
    keyframes = db.get_trajectories_by_marker(army.id)[0][1]
    catalog = MarkerIconCatalog.load(world.path)
    icon = catalog.resolve_attributes(army.attributes)
    assert icon is not None and icon.id == ARMY_ICON_ID
    assert catalog.asset_file(icon).is_file()
    assert interpolate_position(keyframes, before) == (0.28, 0.72)
    assert interpolate_position(keyframes, change) == (0.72, 0.32)
    assert interpolate_position(keyframes, index["after"]) == (0.72, 0.32)
    assert (world.path / db.get_map(index["map_id"]).image_path).is_file()


def test_reigns_share_the_event_boundary_and_uncertainty_stays_partial(demo):
    _, index, db = demo
    converter = CalendarConverter(db.get_active_calendar_config())
    anchors = resolve_event_anchors(db.get_all_events(), converter)
    reigns = [r for r in db.get_all_relations() if r["rel_type"] == "rules"]
    for relation in reigns:
        window = resolve_temporal_window(
            relation["attributes"], converter=converter, anchors=anchors
        )
        is_mara = relation["source_id"] == index["entities"]["Queen Mara"]
        assert window.status_at(index["succession"] - 0.001) == (
            TemporalValidity.DEFINITE if is_mara else TemporalValidity.INACTIVE
        )
        assert window.status_at(index["succession"]) == (
            TemporalValidity.INACTIVE if is_mara else TemporalValidity.DEFINITE
        )
    event = db.get_event(index["events"]["03 - A disputed surrender report"])
    expression = event.temporal_expression
    assert expression.precision.value == "month"
    assert expression.qualifier.value == "uncertain"
    assert expression.day is None
    assert not expression.resolve_bounds(converter).has_hard_bounds


def test_validation_exercise_is_the_only_issue_and_can_be_repaired(demo):
    _, index, db = demo
    report = WorldValidator(db).validate()
    assert [(issue.issue_type, issue.object_name) for issue in report.issues] == [
        (IssueType.INCOMPLETE_ENTITY, "The unfinished coronation account")
    ]
    draft = db.get_entity(index["entities"]["The unfinished coronation account"])
    draft.description = (
        "Ilyra received the crown at Northwatch after the march from Ashford."
    )
    db.insert_entity(draft)
    assert WorldValidator(db).validate().issues == []
    sequence = build_longform_sequence(db.require_connection())
    assert len(sequence) == len(index["entities"]) + len(index["events"])


def test_generator_refuses_existing_world(tmp_path):
    target = tmp_path / "Existing"
    target.mkdir()
    sentinel = target / "keep.txt"
    sentinel.write_text("My world")
    with pytest.raises(FileExistsError):
        create_demo_world(target)
    assert sentinel.read_text() == "My world"
    assert list(target.iterdir()) == [sentinel]


def test_failed_generation_does_not_publish_partial_world(tmp_path, monkeypatch):
    def fail(*args):
        raise RuntimeError("Generation interrupted")

    monkeypatch.setattr("scripts.create_demo_world._populate", fail)
    target = tmp_path / "Northwatch"
    with pytest.raises(RuntimeError, match="Generation interrupted"):
        create_demo_world(target)
    assert not target.exists()
    assert list(tmp_path.iterdir()) == []
