"""KRT-111 event-bound presence, precision, persistence and draft regressions."""

import copy
import json

import pytest

from src.commands.event_commands import DeleteEventCommand
from src.commands.layer_commands import UpdateLayerPropertiesCommand
from src.core.calendar import (
    CalendarConfig,
    CalendarConverter,
    CalendarDate,
    YearVariant,
)
from src.core.events import Event
from src.core.map import Map, MapLayerNode, resolve_layer_temporal_validity
from src.core.temporal_anchors import resolve_event_anchors
from src.core.temporal_context import TemporalResolutionContext
from src.core.temporal_expression import TemporalExpression, TemporalPrecision
from src.core.temporal_references import remap_temporal_references
from src.core.temporal_shift import calendar_shift, shift_anchor
from src.core.temporal_window import TemporalValidity, resolve_temporal_window
from src.gui.dialogs.temporal_validity_dialog import TemporalValidityDialog
from src.gui.widgets.map.map_graphics_view import MapGraphicsView
from src.gui.widgets.map.map_layer_model import MapLayerModel
from src.gui.widgets.relation_form import RelationForm

pytestmark = pytest.mark.ci_fast


def reference(identity="e", endpoint="start", value=0, unit="days", **kwargs):
    return {
        "anchor": {
            "anchor_id": f"event:{identity}",
            "endpoint": endpoint,
            "semantics": "strict_v2",
            "offset": {"unit": unit, "value": value},
            **kwargs,
        }
    }


def attributes(start=None, end=None):
    return {
        "temporal": {
            "schema": 2,
            "start": start or {"status": "open"},
            "end": end or {"status": "open"},
        }
    }


def tree(start=None, end=None):
    feature = MapLayerNode(
        "Castle", "marker", id="castle", attributes=attributes(start, end)
    )
    group = MapLayerNode("Reign", children=[feature], id="group")
    return MapLayerNode("Root", children=[group]), feature, group


def test_fractional_offset_identity_and_interval():
    anchors = resolve_event_anchors([Event("E", id="e", lore_date=0)], None)
    spec = attributes(reference(value=1.000001), reference(value=1.000002))
    window = resolve_temporal_window(spec, anchors=anchors)
    assert window.start_bounds.anchor_id != window.end_bounds.anchor_id
    assert window.status_at(1.0000015) == TemporalValidity.DEFINITE
    assert window.status_at(1.000002) == TemporalValidity.INACTIVE


def test_zero_offsets_share_identity():
    start = resolve_event_anchors([Event("E", id="e", lore_date=10)], None)["event:e"]
    for unit in ("days", "months", "years"):
        assert (
            shift_anchor(start, {"offset": {"unit": unit, "value": -0.0}}, None)
            == start
        )


@pytest.mark.parametrize(
    "authored_end,duration,expected",
    [
        (None, 10, 110),
        (None, 0, None),
        ("authored", 999, 200),
    ],
)
def test_event_end_precedence(authored_end, duration, expected):
    converter = CalendarConverter(CalendarConfig.create_default())
    event = Event("E", id="e", lore_date=100, lore_duration=duration)
    if authored_end:
        date = converter.from_float(200)
        event.attributes = {
            "_temporal_v2": {
                "schema": 1,
                "end_expression": TemporalExpression(
                    converter._config.id, date.year, date.month, date.day
                ).to_dict(),
            }
        }
    end = resolve_event_anchors([event], converter)["event:e:end"]
    assert end.hard_start == expected
    assert bool(end.error) == (expected is None)


def test_year_handover_inheritance_and_independent_events():
    converter = CalendarConverter(CalendarConfig.create_default())
    expression = TemporalExpression(
        converter._config.id, 120, precision=TemporalPrecision.YEAR
    )
    event = Event(
        "Handover",
        id="e",
        lore_date=123,
        attributes={"_temporal_v2": {"schema": 1, "expression": expression.to_dict()}},
    )
    other = copy.deepcopy(event)
    other.id = "independent"
    anchors = resolve_event_anchors([event, other], converter)
    beginning, ending = converter.start_of_year(120), converter.start_of_year(121)
    old = resolve_temporal_window(attributes(end=reference()), anchors=anchors)
    new = resolve_temporal_window(attributes(start=reference()), anchors=anchors)
    for time, old_status, new_status in (
        (beginning - 1, TemporalValidity.DEFINITE, TemporalValidity.INACTIVE),
        (beginning + 10, TemporalValidity.POSSIBLE, TemporalValidity.POSSIBLE),
        (ending, TemporalValidity.INACTIVE, TemporalValidity.DEFINITE),
    ):
        assert old.status_at(time) == old_status
        assert new.status_at(time) == new_status
    root, feature, group = tree(reference())
    group.attributes = attributes(end=reference())
    assert not resolve_layer_temporal_validity(
        root, feature.id, beginning + 10, converter, anchors=anchors
    ).valid
    group.attributes = attributes(end=reference("independent"))
    state = resolve_layer_temporal_validity(
        root, feature.id, beginning + 10, converter, anchors=anchors
    )
    assert state.valid and state.status.value == "possible"


def test_disjoint_ancestors_override_unresolved_boundary():
    root, feature, group = tree({"exact": 100}, reference("missing"))
    group.attributes = attributes(end={"exact": 50})
    assert not resolve_layer_temporal_validity(root, feature.id, 75).valid


@pytest.mark.parametrize(
    "relation,side,time,status",
    [
        ("after", "start", 100, TemporalValidity.INACTIVE),
        ("before", "end", 100, TemporalValidity.INACTIVE),
        ("after", "end", 100, TemporalValidity.DEFINITE),
    ],
)
def test_strict_constraints_at_exact_endpoint(relation, side, time, status):
    anchors = resolve_event_anchors([Event("E", id="e", lore_date=100)], None)
    data = attributes(**{side: reference(relation=relation)})
    assert resolve_temporal_window(data, anchors=anchors).status_at(time) == status


def test_legacy_after_is_not_silently_reinterpreted():
    anchors = resolve_event_anchors([Event("E", id="e", lore_date=100)], None)
    data = attributes(start={"anchor": {"anchor_id": "event:e", "relation": "after"}})
    data["temporal"]["schema"] = 1
    assert resolve_temporal_window(data, anchors=anchors).start_bounds.lower_inclusive


@pytest.mark.parametrize("unit,amount", [("months", 1), ("months", -1), ("years", 1)])
def test_calendar_shift_preserves_components(unit, amount):
    converter = CalendarConverter(CalendarConfig.create_default())
    value = converter.to_float(CalendarDate(120, 3, 15, 0.25))
    shifted = converter.from_float(calendar_shift(value, amount, unit, converter))
    assert shifted.day == 15 and shifted.time_fraction == 0.25
    assert (shifted.year, shifted.month) == (
        (121, 3) if unit == "years" else (120, 3 + amount)
    )


def test_invalid_month_and_coarse_shift_remain_unresolved():
    converter = CalendarConverter(CalendarConfig.create_default())
    for expression in (
        TemporalExpression(converter._config.id, 120, 1, 31),
        TemporalExpression(converter._config.id, 120, precision=TemporalPrecision.YEAR),
    ):
        bounds = expression.resolve_bounds(converter)
        shifted = shift_anchor(
            bounds,
            {
                "offset": {
                    "unit": "months",
                    "value": 1,
                    "calendar_id": converter._config.id,
                }
            },
            converter,
        )
        assert shifted.error and "Cannot apply" in shifted.error


def test_calendar_offsets_require_integral_value_and_matching_identity():
    converter = CalendarConverter(CalendarConfig.create_default())
    bounds = resolve_event_anchors([Event("E", id="e", lore_date=1)], converter)[
        "event:e"
    ]
    with pytest.raises(ValueError, match="whole numbers"):
        shift_anchor(bounds, {"offset": {"unit": "years", "value": 0.5}}, converter)
    assert shift_anchor(
        bounds,
        {"offset": {"unit": "months", "value": 1, "calendar_id": "missing"}},
        converter,
    ).error


@pytest.mark.parametrize("value", [-1e12, -1, 0, 1, 1e12])
def test_indexed_calendar_wide_roundtrip(value):
    converter = CalendarConverter(CalendarConfig.create_default())
    assert converter.to_float(converter.from_float(value)) == value


def test_indexed_calendar_variants_and_negative_years():
    config = CalendarConfig.create_default()
    config.year_variants.append(YearVariant(year=-2, months=config.months[:3]))
    converter = CalendarConverter(config)
    for year in range(-5, 6):
        value = converter.start_of_year(year)
        assert converter.from_float(value).year == year
        assert converter.start_of_next_year(year) == converter.start_of_year(year + 1)


def test_precision_and_offset_collapse_are_diagnosed():
    converter = CalendarConverter(CalendarConfig.create_default())
    date = converter.from_float(1e12 - 100)
    expression = TemporalExpression(
        converter._config.id,
        date.year,
        date.month,
        date.day,
        0,
        0,
        0,
        precision=TemporalPrecision.SECOND,
    )
    assert "precision" in expression.resolve_bounds(converter).error
    bounds = resolve_event_anchors([Event("E", id="e", lore_date=1e12)], converter)[
        "event:e"
    ]
    assert shift_anchor(bounds, {"offset_days": 1e-6}, converter).error


def test_context_detaches_source_records():
    converter = CalendarConverter(CalendarConfig.create_default())
    event = Event("Foundation", id="e", lore_date=100)
    context = TemporalResolutionContext.build([event], converter, 7)
    event.name = "Changed"
    event.lore_date = 999
    assert context.anchors()["event:e"].hard_start == 100
    assert context.events()[0].name == "Foundation"
    assert context.revision == 7


def test_map_command_save_history_missing_event_and_undo(db_service):
    root, feature, _group = tree()
    map_obj = Map("Map", "assets/map.png", id="map", layers=root)
    db_service.map_repo.insert_map(map_obj)
    db_service.insert_event(Event("Foundation", id="e", lore_date=100))
    command = UpdateLayerPropertiesCommand(
        "map", "castle", {"temporal": attributes(reference())["temporal"]}
    )
    assert command.execute(db_service).success
    loaded = db_service.map_repo.get_map("map")
    assert (
        loaded.layers.children[0].children[0].attributes["temporal"]["start"]
        == reference()
    )
    serialized = json.loads(json.dumps(command.to_dict()))
    restored = UpdateLayerPropertiesCommand.from_dict(serialized)
    deletion = DeleteEventCommand("e").execute(db_service)
    assert not deletion.success and deletion.data["blocked_temporal_dependencies"]
    delete = DeleteEventCommand("e", deletion.data["blocked_temporal_dependencies"])
    assert not delete.execute(db_service).success
    assert (
        UpdateLayerPropertiesCommand("map", "castle", {"temporal": None})
        .execute(db_service)
        .success
    )
    assert delete.execute(db_service).success
    assert (
        UpdateLayerPropertiesCommand("map", "castle", {"notes": "Still editable"})
        .execute(db_service)
        .success
    )
    delete.undo(db_service)
    restored.undo(db_service)
    assert (
        db_service.map_repo.get_map("map").layers.children[0].children[0].attributes
        == feature.attributes
    )


def test_map_anchor_editor_roundtrip_and_live_refresh(qtbot):
    node = MapLayerNode("Castle", "marker", attributes=attributes(reference()))
    context = TemporalResolutionContext.build(
        [Event("Foundation", id="e", lore_date=100)], None
    )
    dialog = TemporalValidityDialog(node, temporal_context=context)
    qtbot.addWidget(dialog)
    assert dialog.properties()["temporal"] == node.attributes["temporal"]
    context = TemporalResolutionContext.build(
        [Event("Renamed", id="e", lore_date=200)], None, 2
    )
    dialog.set_temporal_context(context)
    assert dialog.properties()["temporal"] == node.attributes["temporal"]
    assert "Renamed" in dialog._event_controls["start"].summary.text()
    dialog._boundary_modes["end"].setCurrentIndex(1)
    assert dialog.properties()["temporal"]["start"] == reference()
    assert dialog.properties()["temporal"]["end"] == {"status": "unknown"}


def test_missing_and_future_metadata_roundtrip(qtbot):
    data = attributes(reference("missing", future={"meaning": "retained"}))
    data["temporal"]["future"] = {"keep": True}
    node = MapLayerNode("Castle", "marker", attributes=data)
    dialog = TemporalValidityDialog(node)
    qtbot.addWidget(dialog)
    assert dialog.properties()["temporal"] == data["temporal"]
    dialog._boundary_modes["end"].setCurrentIndex(1)
    assert dialog.properties()["temporal"]["start"] == data["temporal"]["start"]
    assert dialog.properties()["temporal"]["future"] == {"keep": True}


def test_relation_shared_controls_preserve_unedited_reference(qtbot):
    converter = CalendarConverter(CalendarConfig.create_default())
    context = TemporalResolutionContext.build(
        [Event("Foundation", id="e", lore_date=100)], converter
    )
    form = RelationForm(attributes=attributes(reference()), temporal_context=context)
    qtbot.addWidget(form)
    assert form.get_data()[3]["temporal"]["start"] == reference()
    controls = form._anchor_controls["start"]
    controls.endpoint.setCurrentIndex(1)
    controls.unit.setCurrentIndex(2)
    controls.offset.setValue(1)
    data = form.get_data()[3]["temporal"]
    assert data["schema"] == 2
    assert data["start"]["anchor"]["endpoint"] == "end"
    assert data["start"]["anchor"]["offset"]["unit"] == "years"


def test_remapping_changes_only_structural_supported_references():
    data = attributes(reference())
    data["prose"] = "event:e"
    result = remap_temporal_references(data, {"e": "copy"})
    assert result["temporal"]["start"]["anchor"]["anchor_id"] == "event:copy"
    assert result["prose"] == "event:e"
    assert data["temporal"]["start"]["anchor"]["anchor_id"] == "event:e"
    data["temporal"]["schema"] = 99
    assert remap_temporal_references(data, {"e": "copy"}) == data


def test_map_view_refreshes_on_reschedule_without_playhead_change(qtbot):
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QImage, QPixmap
    from PySide6.QtWidgets import QGraphicsPixmapItem

    root, feature, _group = tree(reference())
    model = MapLayerModel(root)
    view = MapGraphicsView()
    qtbot.addWidget(view)
    image = QImage(100, 100, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.white)
    view.pixmap_item = QGraphicsPixmapItem(QPixmap.fromImage(image))
    view.graphics_scene.addItem(view.pixmap_item)
    view.coord_system.set_scene_rect(QRectF(0, 0, 100, 100))
    view.set_layer_model(model)
    view.add_marker("castle", "entity", "Castle", 0.5, 0.5)
    view.set_playhead_time(150)
    model.set_temporal_context(
        TemporalResolutionContext.build(
            [Event("Foundation", id="e", lore_date=100)], None
        )
    )
    marker = view._marker_manager.markers["castle"]
    assert marker.isVisible()
    model.set_temporal_context(
        TemporalResolutionContext.build(
            [Event("Foundation", id="e", lore_date=200)], None, 2
        )
    )
    assert not marker.isVisible()
    model.set_temporal_context(
        TemporalResolutionContext.build(
            [Event("Renamed", id="e", lore_date=100)], None, 3
        )
    )
    assert marker.isVisible()
    assert "Renamed" in model._temporal_tooltip(feature)


def test_import_explicit_match_remaps_temporal_refs_without_retargeting_existing(
    db_service,
):
    import uuid

    from src.commands.transfer_commands import ApplyTransferCommand
    from src.core.entities import Entity
    from src.services.transfer_import import prepare_import

    event, castle = Event("Foundation", lore_date=10), Entity("Castle", "place")
    incoming_id = str(uuid.uuid4())
    db_service.insert_event(event)
    db_service.insert_entity(castle)
    db_service.insert_relation(
        castle.id, event.id, "built", attributes=attributes(reference(event.id))
    )
    before = copy.deepcopy(db_service.get_all_relations())
    incoming = {
        "entities": [],
        "events": [{"id": incoming_id, "name": "Foundation", "lore_date": 10}],
        "relations": [
            {
                "source_id": castle.id,
                "target_id": incoming_id,
                "rel_type": "destroyed",
                "attributes": attributes(reference(incoming_id, "end")),
            }
        ],
    }
    review = prepare_import(
        db_service, incoming, {"mode": "update", "matches": {"events:0": event.id}}
    )
    assert not review["errors"]
    assert ApplyTransferCommand(review).execute(db_service).success
    rows = db_service.get_all_relations()
    assert next(row for row in rows if row["id"] == before[0]["id"]) == before[0]
    imported = next(row for row in rows if row["rel_type"] == "destroyed")
    assert imported["target_id"] == event.id
    assert (
        imported["attributes"]["temporal"]["start"]["anchor"]["anchor_id"]
        == f"event:{event.id}"
    )


def test_portable_world_preserves_map_reference_and_precision(db_service, tmp_path):
    import sqlite3

    from src.services.world_transfer import export_world, import_world

    config = CalendarConfig.create_default()
    db_service.insert_calendar_config(config)
    event = Event(
        "Foundation",
        id="e",
        lore_date=100,
        attributes={
            "_temporal_v2": {
                "schema": 1,
                "expression": TemporalExpression(
                    config.id, 120, precision=TemporalPrecision.YEAR
                ).to_dict(),
            }
        },
    )
    db_service.insert_event(event)
    root, _feature, _group = tree(reference())
    db_service.map_repo.insert_map(Map("Map", "assets/map.png", id="map", layers=root))
    source = tmp_path / "source"
    (source / "assets").mkdir(parents=True)
    (source / "assets" / "map.png").write_bytes(b"test asset")
    world = {"path": str(source), "manifest": {"id": "original", "name": "Original"}}
    package = tmp_path / "saved.krakenworld"
    export_world(db_service.get_connection(), world, package, lambda: False)
    restored = import_world(package, tmp_path / "worlds", "Restored", lambda: False)
    with sqlite3.connect(restored / "world.kraken") as connection:
        metadata = json.loads(
            connection.execute("SELECT attributes FROM maps WHERE id='map'").fetchone()[
                0
            ]
        )
        authored = json.loads(
            connection.execute("SELECT attributes FROM events WHERE id='e'").fetchone()[
                0
            ]
        )
    assert metadata["layers"] == root.to_dict()
    assert authored == event.attributes


def test_future_expression_is_preserved_while_other_boundary_changes(qtbot):
    data = attributes({"expression": {"schema_version": 99, "calendar_id": "future"}})
    node = MapLayerNode("Castle", "marker", attributes=data)
    dialog = TemporalValidityDialog(node)
    qtbot.addWidget(dialog)
    assert dialog._boundary_modes["start"].currentData() == "preserved"
    dialog._boundary_modes["end"].setCurrentIndex(1)
    assert dialog.properties()["temporal"]["start"] == data["temporal"]["start"]


def test_coordinator_context_refresh_is_not_a_draft_edit(qtbot):
    from src.app.coordinators.map_temporal_coordinator import MapTemporalCoordinator

    event = Event("Foundation", id="e", lore_date=10)
    received = []
    coordinator = MapTemporalCoordinator(lambda: [event], [received.append])
    coordinator.set_calendar(CalendarConfig.create_default())
    first = received[-1]
    event.lore_date = 20
    coordinator.lore_changed("event", "e", "upsert")
    assert received[-1].anchors()["event:e"].hard_start == 20
    assert first.anchors()["event:e"].hard_start == 10
    assert received[-1].revision > first.revision


def test_unrepresentable_offsets_do_not_become_false_empty_intervals():
    anchors = resolve_event_anchors([Event("Far event", id="e", lore_date=1e12)], None)
    window = resolve_temporal_window(
        attributes(reference(value=1e-6), reference(value=2e-6)), anchors=anchors
    )
    assert window.error
    assert not window.is_empty
    assert window.status_at(1e12) == TemporalValidity.INDETERMINATE


def test_strict_occurrence_cannot_equal_after_endpoint():
    anchors = resolve_event_anchors([Event("E", id="e", lore_date=100)], None)
    spec = {"temporal": {"schema": 2, "at": reference(relation="after")}}
    assert (
        resolve_temporal_window(spec, anchors=anchors).status_at(100)
        == TemporalValidity.INACTIVE
    )


def test_schema_two_defaults_to_strict_but_legacy_before_is_preserved():
    anchors = resolve_event_anchors([Event("E", id="e", lore_date=100)], None)
    boundary = {"anchor": {"anchor_id": "event:e", "relation": "after"}}
    assert not resolve_temporal_window(
        attributes(boundary), anchors=anchors
    ).start_bounds.lower_inclusive
    legacy = attributes(end={"anchor": {"anchor_id": "event:e", "relation": "before"}})
    legacy["temporal"]["schema"] = 1
    assert (
        resolve_temporal_window(legacy, anchors=anchors).status_at(100)
        == TemporalValidity.INACTIVE
    )


def test_calendar_period_shift_handles_a_large_uncertainty_span_without_day_iteration():
    from src.core.temporal_expression import ResolvedTemporalBounds

    converter = CalendarConverter(CalendarConfig.create_default())
    bounds = ResolvedTemporalBounds(0, 1e10, anchor_id="event:e")
    shifted = shift_anchor(
        bounds,
        {
            "offset": {
                "unit": "years",
                "value": 400,
                "calendar_id": converter._config.id,
            }
        },
        converter,
    )
    assert shifted.error is None
    assert shifted.hard_end - shifted.hard_start == 1e10


def test_unknown_calendar_transform_ids_include_the_bound_calendar():
    bounds = resolve_event_anchors([Event("E", id="e", lore_date=100)], None)["event:e"]

    def shifted(calendar):
        return shift_anchor(
            bounds,
            {"offset": {"unit": "months", "value": 1, "calendar_id": calendar}},
            None,
        )

    assert shifted("a").anchor_id != shifted("b").anchor_id
    assert shifted("a").hard_start is None


def test_relation_future_expression_stays_lossless_when_meaning_changes(qtbot):
    data = attributes({"expression": {"schema_version": 99, "calendar_id": "future"}})
    form = RelationForm(attributes=data)
    qtbot.addWidget(form)
    assert form._boundary_choices["start"].currentData() == "preserved"
    form.temporal_behavior.setCurrentIndex(1)
    assert form.get_data()[3]["temporal"]["start"] == data["temporal"]["start"]


def test_future_window_schema_requires_both_modes_to_be_replaced(qtbot):
    data = attributes(reference())
    data["temporal"]["schema"] = 99
    dialog = TemporalValidityDialog(MapLayerNode("Castle", "marker", attributes=data))
    qtbot.addWidget(dialog)
    assert dialog.properties()["temporal"] == data["temporal"]
    dialog._boundary_modes["start"].setCurrentIndex(1)
    assert dialog.properties()["temporal"]["schema"] == 99
    dialog._boundary_modes["end"].setCurrentIndex(1)
    assert dialog.properties()["temporal"]["schema"] in {1, 2}


def test_inherited_summary_shows_impossible_joint_presence(qtbot):
    context = TemporalResolutionContext.build(
        [Event("Handover", id="e", lore_date=100)], None
    )
    dialog = TemporalValidityDialog(
        MapLayerNode("Castle", "marker", attributes=attributes(reference())),
        temporal_context=context,
        playhead_time=100,
        ancestor_windows=(("Old reign", attributes(end=reference())),),
    )
    qtbot.addWidget(dialog)
    assert (
        "With group dates (Old reign): not present" in dialog._temporal_summary.text()
    )


def test_chronology_aliases_preserve_inherited_transition_correlation():
    from src.core.temporal_constraints import TemporalConstraint, TemporalConstraintKind

    config = CalendarConfig.create_default()
    converter = CalendarConverter(config)
    expression = TemporalExpression(config.id, 120, precision=TemporalPrecision.YEAR)
    events = [
        Event(
            "First",
            id="a",
            lore_date=100,
            attributes={
                "_temporal_v2": {"schema": 1, "expression": expression.to_dict()}
            },
        ),
        Event(
            "Second",
            id="b",
            lore_date=100,
            attributes={
                "_temporal_v2": {"schema": 1, "expression": expression.to_dict()}
            },
        ),
    ]
    root, feature, group = tree(reference("a"))
    group.attributes = attributes(end=reference("b"))
    rules = (TemporalConstraint("event:a", TemporalConstraintKind.SAME_AS, "event:b"),)
    state = resolve_layer_temporal_validity(
        root,
        feature.id,
        converter.start_of_year(120) + 10,
        converter,
        anchors=resolve_event_anchors(events, converter),
        constraints=rules,
    )
    assert not state.valid and state.valid_time is None


@pytest.mark.parametrize("text", ["1.000001", "1e-20", "5e-324", "-1.000002"])
def test_offset_keyboard_input_is_lossless_and_enter_stays_local(qtbot, text):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    dialog = TemporalValidityDialog(
        MapLayerNode("Castle", "marker", attributes=attributes(reference()))
    )
    qtbot.addWidget(dialog)
    controls = dialog._event_controls["start"]
    controls.disclosure.setChecked(True)
    dialog.show()
    field = controls.offset
    field.setFocus()
    field.selectAll()
    QTest.keyClicks(field, text)
    QTest.keyClick(field, Qt.Key.Key_Return)
    assert field.value() == float(text)
    assert dialog.isVisible()
    controls.endpoint.setCurrentIndex(1)
    assert dialog.properties()["temporal"]["start"]["anchor"]["offset"][
        "value"
    ] == float(text)


def test_manual_date_draft_survives_calendar_and_event_context_refresh(qtbot):
    from PySide6.QtTest import QTest

    converter = CalendarConverter(CalendarConfig.create_default())
    expression = TemporalExpression(
        converter._config.id, 120, precision=TemporalPrecision.YEAR
    )
    node = MapLayerNode(
        "Castle", "marker", attributes=attributes({"expression": expression.to_dict()})
    )
    dialog = TemporalValidityDialog(node, calendar_converter=converter)
    qtbot.addWidget(dialog)
    dialog.show()
    dialog._start.txt_date.setFocus()
    dialog._start.txt_date.selectAll()
    QTest.keyClicks(dialog._start.txt_date, "120-")
    before = dialog._start.txt_date.text()
    replacement = CalendarConverter(CalendarConfig.create_default())
    dialog.set_temporal_context(TemporalResolutionContext.build([], replacement, 2))
    assert dialog._start.txt_date.text() == before
    assert dialog._start.has_pending_draft()
    assert (
        dialog.properties()["temporal"]["start"] == node.attributes["temporal"]["start"]
    )


def test_calendar_image_gaps_retain_occurrence_and_window_correlation():
    from src.core.temporal_expression import ResolvedTemporalBounds

    converter = CalendarConverter(CalendarConfig.create_default())
    source = ResolvedTemporalBounds(
        converter.start_of_day(123, 2, 1),
        converter.start_of_day(123, 4, 1),
        anchor_id="event:e",
        base_anchor="event:e",
    )
    shifted = shift_anchor(
        source,
        {"offset": {"unit": "years", "value": 1, "calendar_id": converter._config.id}},
        converter,
    )
    assert shifted.error is None
    gap = converter.start_of_day(124, 2, 29) + 0.5
    anchors = {"event:e": shifted}
    instant = resolve_temporal_window(
        {"temporal": {"schema": 2, "at": reference()}}, anchors=anchors
    )
    assert instant.status_at(gap) == TemporalValidity.INACTIVE
    window = resolve_temporal_window(
        attributes(reference(), reference(value=0.1)), anchors=anchors
    )
    assert window.status_at(gap) == TemporalValidity.INACTIVE
    assert window.status_at(gap - 1) == TemporalValidity.POSSIBLE
    independent = resolve_temporal_window(
        {"temporal": {"schema": 2, "at": reference(relation="after")}},
        anchors=anchors,
    )
    assert (
        independent.status_at(converter.start_of_year(125)) != TemporalValidity.INACTIVE
    )


def test_sparse_calendar_variants_do_not_enumerate_large_ordinary_spans():
    from src.core.temporal_expression import ResolvedTemporalBounds

    config = CalendarConfig.create_default()
    config.year_variants.append(
        YearVariant(year=20, months=copy.deepcopy(config.months))
    )
    converter = CalendarConverter(config)
    result = shift_anchor(
        ResolvedTemporalBounds(0, 1e10, anchor_id="event:e"),
        {"offset": {"unit": "years", "value": 400, "calendar_id": config.id}},
        converter,
    )
    assert result.error is None
    assert result.hard_start == calendar_shift(0, 400, "years", converter)
    assert result.hard_end == calendar_shift(1e10, 400, "years", converter)
    # The variant overrides year 20's leap day; its image has a one-day gap.
    assert len(result.possible_ranges) == 2


def test_calendar_transform_identity_keeps_duration_before_transform():
    from src.core.temporal_expression import ResolvedTemporalBounds

    converter = CalendarConverter(CalendarConfig.create_default())
    start = ResolvedTemporalBounds(0, 0, anchor_id="event:e", base_anchor="event:e")
    end = shift_anchor(start, {"offset_days": 1}, converter)
    ref = {"offset": {"unit": "years", "value": 1, "calendar_id": converter._config.id}}
    assert (
        shift_anchor(start, ref, converter).anchor_id
        != shift_anchor(end, ref, converter).anchor_id
    )


def test_after_start_and_before_end_of_same_event_is_provably_empty():
    converter = CalendarConverter(CalendarConfig.create_default())
    expression = TemporalExpression(
        converter._config.id, 120, precision=TemporalPrecision.YEAR
    )
    event = Event(
        "E",
        id="e",
        lore_date=0,
        attributes={"_temporal_v2": {"schema": 1, "expression": expression.to_dict()}},
    )
    window = resolve_temporal_window(
        attributes(reference(relation="after"), reference(relation="before")),
        anchors=resolve_event_anchors([event], converter),
    )
    assert window.is_empty
    assert not window.is_valid
    assert (
        window.status_at(converter.start_of_year(120) + 10) == TemporalValidity.INACTIVE
    )


@pytest.mark.parametrize("theme", ["dark_mode", "light_mode"])
@pytest.mark.parametrize("width", [360, 800])
def test_relation_expansion_keeps_controls_inside_their_layout(
    qtbot, qapp, theme, width
):
    from pathlib import Path

    from PySide6.QtGui import QFont, QFontDatabase

    from src.core.theme_manager import ThemeManager

    manager = ThemeManager()
    previous = manager.current_theme_name, qapp.styleSheet(), qapp.font()
    font = Path("C:/Windows/Fonts/segoeui.ttf")
    if font.exists():
        QFontDatabase.addApplicationFont(str(font))
        qapp.setFont(QFont("Segoe UI", 10))
    try:
        manager.apply_theme(qapp, Path("src/resources/main.qss").read_text("utf-8"))
        manager.set_theme(theme, qapp, persist=False)
        form = RelationForm(attributes=attributes(reference(), reference()))
        qtbot.addWidget(form)
        form.resize(width, 640)
        form.show()
        for controls in form._anchor_controls.values():
            controls.disclosure.setChecked(True)
        qapp.processEvents()
        for controls in form._anchor_controls.values():
            form.form_scroll_area.ensureWidgetVisible(controls.unit)
            qapp.processEvents()
            advanced = controls.unit.parentWidget()
            assert advanced.rect().contains(controls.unit.geometry())
            assert controls.rect().contains(advanced.geometry())
            group = controls.parentWidget()
            assert group.rect().contains(controls.geometry())
    finally:
        manager.set_theme(previous[0], qapp, persist=False)
        qapp.setStyleSheet(previous[1])
        qapp.setFont(previous[2])
