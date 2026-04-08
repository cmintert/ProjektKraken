"""Unit tests for event date rendering in longform content widget."""

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture
def qapp():
    """Fixture to provide QApplication instance."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def content_widget(qapp):
    """Create a LongformContentWidget for testing."""
    from src.gui.widgets.longform.content import LongformContentWidget

    widget = LongformContentWidget()
    return widget


@pytest.fixture
def mock_converter():
    """Create a mock CalendarConverter."""
    converter = MagicMock()
    converter.format_date = MagicMock(side_effect=lambda x: f"Year {int(x)}")
    return converter


class TestEventDateRendering:
    """Tests for event date display in longform content."""

    def test_event_with_date_shows_date_line(self, content_widget, mock_converter):
        """Should render date line for events with lore_date."""
        content_widget.set_calendar_converter(mock_converter)

        sequence = [
            {
                "table": "events",
                "id": "evt1",
                "name": "Battle of Dawn",
                "content": "A great battle",
                "meta": {"depth": 0},
                "heading_level": 1,
                "lore_date": 100.0,
                "lore_duration": 0.0,
            }
        ]

        content_widget.load_content(sequence)
        html = content_widget.toHtml()

        # Should contain the event date (Qt strips class attributes in HTML output)
        assert "Year 100" in html
        # Date should be italicized
        assert "font-style:italic" in html

    def test_event_with_duration_shows_range(self, content_widget, mock_converter):
        """Should render date range for events with duration."""
        content_widget.set_calendar_converter(mock_converter)

        sequence = [
            {
                "table": "events",
                "id": "evt1",
                "name": "Long Siege",
                "content": "A long siege",
                "meta": {"depth": 0},
                "heading_level": 1,
                "lore_date": 100.0,
                "lore_duration": 50.0,
            }
        ]

        content_widget.load_content(sequence)
        html = content_widget.toHtml()

        # Should contain date range with en-dash
        assert "\u2013" in html  # en-dash (or HTML entity version)
        assert "Year 100" in html
        assert "Year 150" in html  # 100 + 50

    def test_event_without_date_no_date_line(self, content_widget, mock_converter):
        """Should not render date line for events without lore_date."""
        content_widget.set_calendar_converter(mock_converter)

        sequence = [
            {
                "table": "events",
                "id": "evt1",
                "name": "Mysterious Event",
                "content": "No date known",
                "meta": {"depth": 0},
                "heading_level": 1,
                "lore_date": None,
                "lore_duration": 0.0,
            }
        ]

        content_widget.load_content(sequence)
        html = content_widget.toHtml()

        # Should not call format_date (no date to format)
        assert mock_converter.format_date.call_count == 0

    def test_entity_no_date_line(self, content_widget, mock_converter):
        """Should not render date line for entities."""
        content_widget.set_calendar_converter(mock_converter)

        sequence = [
            {
                "table": "entities",
                "id": "ent1",
                "name": "King Arthur",
                "content": "A legendary king",
                "meta": {"depth": 0},
                "heading_level": 1,
                "lore_date": 100.0,  # Entities shouldn't have dates anyway
                "lore_duration": 0.0,
            }
        ]

        content_widget.load_content(sequence)
        html = content_widget.toHtml()

        # Should not call format_date for entities
        assert mock_converter.format_date.call_count == 0

    def test_no_converter_no_date_line(self, content_widget):
        """Should not render date line if converter not set."""
        sequence = [
            {
                "table": "events",
                "id": "evt1",
                "name": "Event",
                "content": "Content",
                "meta": {"depth": 0},
                "heading_level": 1,
                "lore_date": 100.0,
                "lore_duration": 0.0,
            }
        ]

        content_widget.load_content(sequence)
        html = content_widget.toHtml()

        # Should not have formatted date (no converter to format it)
        # Event has a date but it's not rendered because converter is None
        assert "Year" not in html

    def test_converter_set_triggers_reload(self, content_widget, mock_converter):
        """Setting converter after load should re-render with dates."""
        sequence = [
            {
                "table": "events",
                "id": "evt1",
                "name": "Event",
                "content": "Content",
                "meta": {"depth": 0},
                "heading_level": 1,
                "lore_date": 100.0,
                "lore_duration": 0.0,
            }
        ]

        # Load without converter
        content_widget.load_content(sequence)
        html_before = content_widget.toHtml()
        assert "Year" not in html_before

        # Set converter and check re-render
        content_widget.set_calendar_converter(mock_converter)
        html_after = content_widget.toHtml()
        assert "Year 100" in html_after

    def test_converter_format_error_skips_date(self, content_widget, mock_converter):
        """Should gracefully skip date if format_date raises."""
        mock_converter.format_date.side_effect = ValueError("Invalid date")
        content_widget.set_calendar_converter(mock_converter)

        sequence = [
            {
                "table": "events",
                "id": "evt1",
                "name": "Event",
                "content": "Content",
                "meta": {"depth": 0},
                "heading_level": 1,
                "lore_date": 100.0,
                "lore_duration": 0.0,
            }
        ]

        content_widget.load_content(sequence)
        html = content_widget.toHtml()

        # Should not contain date text (exception was caught and suppressed)
        assert "Year" not in html
