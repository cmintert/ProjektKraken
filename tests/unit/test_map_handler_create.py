"""Tests for in-place entity/event creation from MapWidget dialogs.

These tests verify the object-selection dialog logic that was moved
from MapHandler to MapWidget.  MapHandler now receives pre-resolved
data via signals.
"""

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication

from src.gui.widgets.map_widget import MapWidget


@pytest.fixture(scope="session", autouse=True)
def qapp():
    """Ensure a QApplication exists for widget tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def map_widget_fixture(qapp):
    """Creates a MapWidget with cached entities/events."""
    widget = MapWidget()

    entity = MagicMock()
    entity.id = "ent_1"
    entity.name = "Rivendell"

    event = MagicMock()
    event.id = "evt_1"
    event.name = "Battle of Five Armies"

    widget.set_cached_items([entity], [event])
    # Pre-select a map so get_selected_map_id() returns a value
    from src.core.map import Map

    test_map = Map(id="map_1", name="Middle-earth", image_path="x.png")
    widget.set_maps([test_map])
    widget.select_map("map_1")

    yield widget
    widget.close()


class TestSelectExistingItem:
    """Tests for selecting existing entities/events."""

    def test_create_marker_existing_entity(self, map_widget_fixture):
        """Selecting an existing entity emits marker_created."""
        with patch(
            "src.gui.widgets.map_widget.QInputDialog"
        ) as MockDialog:
            MockDialog.getItem.return_value = ("Rivendell (Entity)", True)

            spy = MagicMock()
            map_widget_fixture.marker_created.connect(spy)
            map_widget_fixture._on_create_marker_requested(0.5, 0.5)

            spy.assert_called_once()
            args = spy.call_args[0]
            assert args[0] == "map_1"  # map_id
            assert args[1] == "ent_1"  # obj_id
            assert args[2] == "entity"  # obj_type

    def test_create_feature_existing_event(self, map_widget_fixture):
        """Selecting an existing event for a feature emits feature_created."""
        geometry = [{"x": 0.1, "y": 0.1}, {"x": 0.5, "y": 0.5}, {"x": 0.9, "y": 0.1}]
        with patch(
            "src.gui.widgets.map_widget.QInputDialog"
        ) as MockDialog:
            MockDialog.getItem.return_value = (
                "Battle of Five Armies (Event)",
                True,
            )

            spy = MagicMock()
            map_widget_fixture.feature_created.connect(spy)
            # Simulate drawing completion
            map_widget_fixture._on_drawing_finished("region", geometry)

            spy.assert_called_once()
            args = spy.call_args[0]
            assert args[0] == "map_1"
            assert args[1] == "evt_1"
            assert args[2] == "event"
            assert args[4] == "region"


class TestCreateNewInline:
    """Tests for the new in-place creation flow."""

    def test_create_marker_new_entity(self, map_widget_fixture):
        """Selecting '<New Entity...>' emits create_entity_requested + marker_created."""
        with patch(
            "src.gui.widgets.map_widget.QInputDialog"
        ) as MockDialog:
            MockDialog.getItem.return_value = ("<New Entity...>", True)
            MockDialog.getText.return_value = ("Mount Doom", True)

            entity_spy = MagicMock()
            marker_spy = MagicMock()
            map_widget_fixture.create_entity_requested.connect(entity_spy)
            map_widget_fixture.marker_created.connect(marker_spy)

            map_widget_fixture._on_create_marker_requested(0.3, 0.7)

            entity_spy.assert_called_once()
            marker_spy.assert_called_once()

    def test_create_marker_new_event(self, map_widget_fixture):
        """Selecting '<New Event...>' emits create_event_requested + marker_created."""
        with patch(
            "src.gui.widgets.map_widget.QInputDialog"
        ) as MockDialog:
            MockDialog.getItem.return_value = ("<New Event...>", True)
            MockDialog.getText.return_value = ("Dragon Attack", True)

            event_spy = MagicMock()
            marker_spy = MagicMock()
            map_widget_fixture.create_event_requested.connect(event_spy)
            map_widget_fixture.marker_created.connect(marker_spy)

            map_widget_fixture._on_create_marker_requested(0.6, 0.4)

            event_spy.assert_called_once()
            marker_spy.assert_called_once()

    def test_new_entity_cancel_name_emits_nothing(self, map_widget_fixture):
        """Cancelling the name dialog after choosing '<New Entity...>' emits nothing."""
        with patch(
            "src.gui.widgets.map_widget.QInputDialog"
        ) as MockDialog:
            MockDialog.getItem.return_value = ("<New Entity...>", True)
            MockDialog.getText.return_value = ("", False)

            marker_spy = MagicMock()
            map_widget_fixture.marker_created.connect(marker_spy)

            map_widget_fixture._on_create_marker_requested(0.5, 0.5)

            marker_spy.assert_not_called()

    def test_cancel_selection_emits_nothing(self, map_widget_fixture):
        """Cancelling the item selection dialog emits nothing."""
        with patch(
            "src.gui.widgets.map_widget.QInputDialog"
        ) as MockDialog:
            MockDialog.getItem.return_value = ("", False)

            marker_spy = MagicMock()
            map_widget_fixture.marker_created.connect(marker_spy)

            map_widget_fixture._on_create_marker_requested(0.5, 0.5)

            marker_spy.assert_not_called()
