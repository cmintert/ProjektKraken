import pytest
from src.core.calendar import (
    CalendarConfig,
    CalendarConverter,
    MonthDefinition,
    WeekDefinition,
)
from src.gui.widgets.event_editor import EventEditorWidget
from src.gui.widgets.compact_duration_widget import CompactDurationWidget


@pytest.fixture
def mock_converter():
    months = [
        MonthDefinition(name="Month 1", abbreviation="M1", days=30),
        MonthDefinition(name="Month 2", abbreviation="M2", days=30),  # Regular
    ]
    # Make a variant calendar for testing overflow logic if needed
    # For now simple 30 day months

    config = CalendarConfig(
        id="test",
        name="Test",
        months=months,
        week=WeekDefinition(["D1"], ["d1"]),
        year_variants=[],
        epoch_name="Y",
    )
    return CalendarConverter(config)


class TestGranularDuration:

    def test_compact_duration_widget_simple(self, qtbot, mock_converter):
        widget = CompactDurationWidget()
        widget.set_calendar_converter(mock_converter)
        qtbot.addWidget(widget)

        # Set 1 Month 5 Days
        widget.spin_months.setValue(1)
        widget.spin_days.setValue(5)

        # With custom 30 day months, 1 Month = 30 days. + 5 = 35.
        assert widget.get_value() == 35.0

    def test_event_editor_has_duration_widget(self, qtbot):
        """EventEditorWidget should have the new  CompactDurationWidget."""
        widget = EventEditorWidget()
        qtbot.addWidget(widget)

        assert hasattr(widget, "duration_widget")
        assert isinstance(widget.duration_widget, CompactDurationWidget)

    def test_sync_duration_to_end_date(self, qtbot, mock_converter):
        widget = EventEditorWidget()
        widget.set_calendar_converter(mock_converter)
        qtbot.addWidget(widget)

        # Set Start Date: Year 1 Month 1 Day 1 (Float 0.0)
        widget.date_edit.set_value(0.0)

        # Set Duration: 30 Days (1 Month)
        # Use simple method first
        widget.duration_widget.spin_days.setValue(30)

        # Check End Date
        # Start 0.0 + 30.0 = 30.0 -> Year 1 Month 2 Day 1
        assert widget.end_date_edit.get_value() == 30.0

    def test_sync_end_date_to_duration(self, qtbot, mock_converter):
        widget = EventEditorWidget()
        widget.set_calendar_converter(mock_converter)
        qtbot.addWidget(widget)

        # Start: 0.0
        widget.date_edit.set_value(0.0)

        # Set End Date: 15.0
        widget.end_date_edit.set_value(15.0)

        # Check Duration
        assert widget.duration_widget.get_value() == 15.0
        # Check decomposition (should be 0 Y 0 M 15 D)
        assert widget.duration_widget.spin_years.value() == 0
        assert widget.duration_widget.spin_days.value() == 15
