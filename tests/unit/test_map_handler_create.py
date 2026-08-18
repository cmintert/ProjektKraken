"""Tests for point-marker selection and lightweight map creation requests."""

from unittest.mock import MagicMock, patch

import pytest

from src.core.map import Map
from src.gui.dialogs.map_object_picker_dialog import MapObjectChoice
from src.gui.widgets.map_widget import MapWidget


@pytest.fixture
def map_widget_fixture(qapp):
    """Create a MapWidget with a selected map and cached objects."""
    widget = MapWidget()
    entity = MagicMock(id="ent_1", name="Rivendell", type="Location")
    event = MagicMock(id="evt_1", name="Battle of Five Armies")
    widget.set_cached_items([entity], [event])
    widget.set_maps([Map(id="map_1", name="Middle-earth", image_path="x.png")])
    widget.select_map("map_1")
    yield widget
    widget.close()


def test_existing_entity_emits_marker_created(map_widget_fixture):
    choice = MapObjectChoice(
        action="existing",
        object_id="ent_1",
        object_type="entity",
        name="Rivendell",
    )
    with patch.object(map_widget_fixture, "_choose_map_object", return_value=choice):
        spy = MagicMock()
        map_widget_fixture.marker_created.connect(spy)
        map_widget_fixture._on_create_marker_requested(0.5, 0.5)

    spy.assert_called_once_with(
        "map_1", "ent_1", "entity", "Rivendell", 0.5, 0.5
    )


@pytest.mark.parametrize(
    ("choice", "expected_type"),
    [
        (
            MapObjectChoice(
                action="create",
                object_type="entity",
                name="Grey Ford",
                entity_type="Location",
            ),
            "entity",
        ),
        (
            MapObjectChoice(
                action="create",
                object_type="entity",
                name="Edda Voss",
                entity_type="Character",
            ),
            "entity",
        ),
        (
            MapObjectChoice(
                action="create", object_type="event", name="The Crossing"
            ),
            "event",
        ),
    ],
)
def test_new_object_requests_atomic_creation(
    map_widget_fixture, choice, expected_type
):
    with patch.object(map_widget_fixture, "_choose_map_object", return_value=choice):
        atomic_spy = MagicMock()
        marker_spy = MagicMock()
        map_widget_fixture.marker_object_creation_requested.connect(atomic_spy)
        map_widget_fixture.marker_created.connect(marker_spy)
        map_widget_fixture._on_create_marker_requested(0.3, 0.7)

    atomic_spy.assert_called_once()
    args = atomic_spy.call_args.args
    assert args[0] == "map_1"
    assert args[2] == expected_type
    assert args[3] == choice.name
    assert args[4] == choice.entity_type
    assert args[5:] == (0.3, 0.7)
    marker_spy.assert_not_called()


def test_cancel_emits_nothing(map_widget_fixture):
    with patch.object(map_widget_fixture, "_choose_map_object", return_value=None):
        marker_spy = MagicMock()
        atomic_spy = MagicMock()
        map_widget_fixture.marker_created.connect(marker_spy)
        map_widget_fixture.marker_object_creation_requested.connect(atomic_spy)
        map_widget_fixture._on_create_marker_requested(0.5, 0.5)

    marker_spy.assert_not_called()
    atomic_spy.assert_not_called()


def test_feature_creation_preserves_chosen_entity_type(map_widget_fixture):
    choice = MapObjectChoice(
        action="create",
        object_type="entity",
        name="Northern League",
        entity_type="Faction",
    )
    with patch.object(map_widget_fixture, "_choose_map_object", return_value=choice):
        entity_spy = MagicMock()
        feature_spy = MagicMock()
        map_widget_fixture.create_entity_requested.connect(entity_spy)
        map_widget_fixture.feature_created.connect(feature_spy)
        geometry = [{"x": 0.1, "y": 0.1}, {"x": 0.5, "y": 0.5}]
        map_widget_fixture._on_drawing_finished("path", geometry)

    entity_spy.assert_called_once()
    assert entity_spy.call_args.args[1:] == ("Northern League", "Faction")
    feature_spy.assert_called_once()
