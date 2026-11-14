"""Parity and source integrity of the sole temporal rendering pipeline."""

from copy import deepcopy
from dataclasses import replace
from fractions import Fraction

import pytest
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QStyleOptionGraphicsItem

from src.core.calendar import CalendarConfig, CalendarConverter
from src.core.date_parser import DateParser
from src.core.event_timing.constraints import Interval
from src.core.event_timing.definitions import EndpointDefinition, EventTimingDefinition
from src.core.event_timing.presentation import event_navigation_context, present_event
from src.core.event_timing.projection import project_event
from src.core.event_timing.resolution import TemporalWorldResolution
from src.core.event_timing.solver import resolve_world
from src.core.events import Event
from src.core.temporal_context import TemporalResolutionContext
from src.gui.widgets.timeline.event_item import EventItem
from src.gui.widgets.timeline.temporal_geometry import project_temporal_geometry
from src.services.recurrence_presentation_service import project_recurrence
from src.services.timeline_event_preparation_service import (
    TimelineEventPreparationService,
)

pytestmark = pytest.mark.ci_fast


@pytest.fixture
def converter():
    return CalendarConverter(CalendarConfig.create_default())


def authored(converter, text, schema):
    expression = DateParser(converter._config).parse_expression(text)
    definition = EventTimingDefinition(
        EndpointDefinition(expression=expression.to_dict())
    )
    attributes = (
        {"_temporal_v2": {"schema": 1, "expression": expression.to_dict()}}
        if schema == 1
        else definition.apply({})
    )
    return Event(name="Coastal Race", lore_date=0, attributes=attributes)


@pytest.mark.parametrize("schema", [1, 2])
@pytest.mark.parametrize(
    "text,mode",
    [
        ("1 April 561", "exact"),
        ("1 April 561 12:00", "exact"),
        ("1 April 561 12:00:00", "exact"),
        ("calculated 1 April 561", "exact"),
        ("April 561", "window"),
        ("561", "window"),
        ("c. 561", "soft"),
        ("1 April 561?", "soft"),
        ("before 561", "one_sided"),
        ("after 561", "one_sided"),
        ("between 560 and 561", "window"),
    ],
)
def test_schema_and_resolution_paths_have_identical_meaning(
    converter, schema, text, mode
):
    event = authored(converter, text, schema)
    before = deepcopy(event.to_dict())
    resolution = resolve_world([event], converter)
    restored = TemporalWorldResolution.from_dict(resolution.to_dict())
    direct = present_event(event, converter)
    for model in (resolution, restored):
        projected = project_event(event, model)
        assert present_event(projected, converter) == direct
        for scale in (0.001, 1, 1000):
            assert project_temporal_geometry(direct.start, scale).mode == mode
        assert event_navigation_context(projected, converter)["uncertain"] == (
            mode != "exact"
        )
    assert event.to_dict() == before


@pytest.mark.parametrize(
    "text,mode", [("1 April 561 12:00", "exact"), ("561", "window"), ("c. 561", "soft")]
)
def test_followed_dates_inherit_source_meaning(converter, text, mode):
    parent = authored(converter, text, 2)
    definition = EventTimingDefinition(
        EndpointDefinition(
            "event",
            anchor_id=f"event:{parent.id}",
            offset={"unit": "days", "value": 3},
        )
    )
    child = Event(name="Following", lore_date=0, attributes=definition.apply({}))
    context = TemporalResolutionContext.build([parent, child], converter)
    projected = context.view_events()
    source, target = [present_event(value, converter).start for value in projected]
    assert source.occurrence == target.occurrence == mode
    assert source.precision == target.precision
    assert source.qualifier == target.qualifier
    if source.possible_start is not None:
        assert target.possible_start == pytest.approx(source.possible_start + 3)


def test_disjoint_solutions_never_render_a_precise_layout_anchor(converter):
    event = authored(converter, "1 April 561 12:00", 2)
    resolution = resolve_world([event], converter)
    endpoint = resolution.endpoints[f"event:{event.id}"]
    resolution.endpoints[endpoint.identity] = replace(
        endpoint,
        ranges=(
            Interval(Fraction(1), Fraction(1), True, True),
            Interval(Fraction(3), Fraction(3), True, True),
        ),
    )
    display = present_event(project_event(event, resolution), converter).start
    assert display.occurrence == "window"
    assert len(display.ranges) == 2


def test_actual_timeline_preparation_preserves_coastal_race_precision(converter):
    event = authored(converter, "1 April 561 12:00", 2)
    context = TemporalResolutionContext.build([event], converter)
    prepared = TimelineEventPreparationService.replace([event], set(), context)
    display = present_event(prepared.events[0], converter).start
    assert display.occurrence == "exact"
    assert display.possible_end - display.possible_start == pytest.approx(1 / 1440)
    assert not display.explicit_window


def test_numeric_and_calendar_records_share_marker_grammar(converter):
    calendar = present_event(authored(converter, "1 April 561", 2), converter)
    numeric = present_event(
        Event(name="Landfall", lore_date=calendar.start.anchor), converter
    )
    assert project_temporal_geometry(calendar.start, 1) == project_temporal_geometry(
        numeric.start, 1
    )


def test_source_edits_calendar_changes_and_undo_invalidate_snapshots(converter):
    event = authored(converter, "1 April 561 12:00", 2)
    projected = project_event(event, resolve_world([event], converter))
    original = present_event(projected, converter)
    # Editing an assertion must not retain an older calculated projection.
    changed = authored(converter, "561", 2)
    changed.attributes["_temporal_v2"]["projection"] = projected.attributes[
        "_temporal_v2"
    ]["projection"]
    assert present_event(changed, converter).start.occurrence == "window"
    assert present_event(projected, None).start.occurrence == "unresolved"
    assert present_event(projected, converter) == original
    assert present_event(changed, converter).start.occurrence == "window"


def test_repeats_use_the_same_precise_start_model(converter):
    event = authored(converter, "1 April 561", 2)
    event.attributes["_recurrence"] = {
        "frequency": "years",
        "interval": 3,
        "calendar_id": converter._config.id,
    }
    display = present_event(event, converter).start
    page = project_recurrence(
        event, converter, display.possible_start, display.possible_start + 1500, 365
    )
    assert page.occurrences
    assert page.presentation == display


def test_painting_and_zoom_only_consume_prepared_presentation(
    qapp, monkeypatch, converter
):
    import src.gui.widgets.timeline.event_item as item_module

    EventItem.set_calendar_converter(converter)
    item = EventItem(authored(converter, "1 April 561", 2))

    def unexpected(*args):
        pytest.fail("Painting or zoom rebuilt temporal meaning")

    monkeypatch.setattr(item_module, "present_event", unexpected)
    image = QImage(200, 100, QImage.Format.Format_ARGB32_Premultiplied)
    painter = QPainter(image)
    try:
        for zoom in (0.1, 1, 10):
            item.set_zoom(zoom)
            item.paint(painter, QStyleOptionGraphicsItem())
            item.shape()
            item.boundingRect()
    finally:
        painter.end()
        monkeypatch.undo()
        EventItem.set_calendar_converter(None)


@pytest.mark.parametrize("bulk", [False, True])
def test_render_snapshots_are_not_written_into_saved_assertions(
    db_service, converter, bulk
):
    source = authored(converter, "1 April 561 12:00", 2)
    projected = project_event(source, resolve_world([source], converter))
    before = deepcopy(projected.to_dict())
    if bulk:
        db_service._event_repo.insert_bulk([projected])
    else:
        db_service._event_repo.insert(projected)
    stored = db_service.get_event(source.id)
    assert stored.attributes == source.attributes
    assert projected.to_dict() == before


@pytest.mark.parametrize("metadata", [None, "unsupported", {"schema": 999}])
def test_unsupported_timing_is_unresolved_not_an_alternate_rendering(metadata):
    event = Event(
        name="Unsupported", lore_date=4, attributes={"_temporal_v2": metadata}
    )
    assert present_event(event, None).start.occurrence == "unresolved"
