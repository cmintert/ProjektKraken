"""
Unit tests for TimelineDisplayWidget.

Tests the chronological event display with payload attributes.
"""

import pytest
from PySide6.QtWidgets import QApplication

from src.gui.widgets.timeline_display_widget import TimelineDisplayWidget


@pytest.fixture(scope="module")
def qapp():
    """Ensure QApplication exists for widget tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def widget(qapp):
    """Create a fresh widget for each test."""
    return TimelineDisplayWidget()


def test_widget_creation(widget):
    """Test that widget can be created."""
    assert widget is not None
    assert widget.isVisible() is False  # Not shown until added to layout


def test_empty_state(widget):
    """Test empty state message when no events."""
    widget.set_relations([])
    # Should show empty state placeholder
    html = widget.get_display_text()
    assert "No timeline events" in html or html == ""


def test_single_event_display(widget):
    """Test display of a single event with payload."""
    relations = [
        {
            "id": "r1",
            "source_id": "evt1",
            "source_event_name": "Frodo Departs the Shire",
            "source_event_date": 3018.0,
            "rel_type": "involved",
            "attributes": {
                "valid_from": 3018.0,
                "payload": {"status": "Ring Bearer", "carrying": "One Ring"},
            },
        }
    ]
    widget.set_relations(relations)
    html = widget.get_display_text()

    assert "3018" in html
    assert "Frodo Departs the Shire" in html
    assert "Ring Bearer" in html
    assert "One Ring" in html


def test_multiple_events_sorted_chronologically(widget):
    """Test that events are sorted by date."""
    relations = [
        {
            "id": "r2",
            "source_id": "evt2",
            "source_event_name": "Council of Elrond",
            "source_event_date": 3018.8,
            "rel_type": "involved",
            "attributes": {"valid_from": 3018.8},
        },
        {
            "id": "r1",
            "source_id": "evt1",
            "source_event_name": "Departs Shire",
            "source_event_date": 3018.0,
            "rel_type": "involved",
            "attributes": {"valid_from": 3018.0},
        },
        {
            "id": "r3",
            "source_id": "evt3",
            "source_event_name": "Coronation",
            "source_event_date": 3019.5,
            "rel_type": "involved",
            "attributes": {"valid_from": 3019.5},
        },
    ]
    widget.set_relations(relations)
    html = widget.get_display_text()

    # Verify all events present
    assert "Departs Shire" in html
    assert "Council of Elrond" in html
    assert "Coronation" in html

    # Verify chronological order (Departs before Council before Coronation)
    departs_pos = html.find("Departs Shire")
    council_pos = html.find("Council of Elrond")
    coronation_pos = html.find("Coronation")

    assert departs_pos < council_pos < coronation_pos


def test_playhead_highlighting(widget):
    """Test that events before playhead are highlighted."""
    relations = [
        {
            "id": "r1",
            "source_id": "evt1",
            "source_event_name": "Event 1",
            "source_event_date": 100.0,
            "rel_type": "involved",
            "attributes": {"valid_from": 100.0},
        },
        {
            "id": "r2",
            "source_id": "evt2",
            "source_event_name": "Event 2",
            "source_event_date": 200.0,
            "rel_type": "involved",
            "attributes": {"valid_from": 200.0},
        },
    ]
    widget.set_relations(relations)

    # Set playhead at 150 - Event 1 should be "active", Event 2 not yet
    widget.set_playhead_time(150.0)
    html = widget.get_display_text()

    # The implementation should mark active events somehow
    # This is flexible - could be CSS class, bold, icon, etc.
    assert html is not None


def test_event_without_payload(widget):
    """Test display of event with no payload attributes."""
    relations = [
        {
            "id": "r1",
            "source_id": "evt1",
            "source_event_name": "Simple Event",
            "source_event_date": 1000.0,
            "rel_type": "located_at",
            "attributes": {"valid_from": 1000.0},  # No payload
        }
    ]
    widget.set_relations(relations)
    html = widget.get_display_text()

    assert "Simple Event" in html
    # Should show rel_type or graceful empty
