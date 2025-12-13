"""
Calendar Database Service Unit Tests.

Tests for CalendarConfig CRUD operations in DatabaseService.
"""

import pytest
from src.core.calendar import (
    MonthDefinition,
    WeekDefinition,
    CalendarConfig,
)


@pytest.fixture
def sample_calendar() -> CalendarConfig:
    """Create a sample calendar config for testing."""
    months = [
        MonthDefinition(name="January", abbreviation="Jan", days=31),
        MonthDefinition(name="February", abbreviation="Feb", days=28),
    ]
    week = WeekDefinition(
        day_names=["Monday", "Tuesday"],
        day_abbreviations=["Mo", "Tu"],
    )
    return CalendarConfig(
        id="test-calendar-001",
        name="Test Calendar",
        months=months,
        week=week,
        year_variants=[],
        epoch_name="TC",
    )


class TestCalendarConfigCRUD:
    """Tests for calendar config database operations."""

    def test_insert_calendar_config(self, db_service, sample_calendar):
        """Test inserting a new calendar config."""
        db_service.insert_calendar_config(sample_calendar)

        result = db_service.get_calendar_config(sample_calendar.id)
        assert result is not None
        assert result.id == sample_calendar.id
        assert result.name == sample_calendar.name
        assert len(result.months) == 2

    def test_get_calendar_config_not_found(self, db_service):
        """Test that missing config returns None."""
        result = db_service.get_calendar_config("nonexistent-id")
        assert result is None

    def test_get_all_calendar_configs(self, db_service, sample_calendar):
        """Test retrieving all calendar configs."""
        # Insert two configs
        db_service.insert_calendar_config(sample_calendar)

        second = CalendarConfig(
            id="test-calendar-002",
            name="Second Calendar",
            months=[MonthDefinition(name="Month1", abbreviation="M1", days=30)],
            week=WeekDefinition(day_names=["Day1"], day_abbreviations=["D1"]),
            year_variants=[],
            epoch_name="SC",
        )
        db_service.insert_calendar_config(second)

        results = db_service.get_all_calendar_configs()
        assert len(results) == 2

    def test_update_calendar_config(self, db_service, sample_calendar):
        """Test updating an existing calendar config."""
        db_service.insert_calendar_config(sample_calendar)

        # Modify and update
        sample_calendar.name = "Updated Calendar Name"
        db_service.insert_calendar_config(sample_calendar)  # Upsert

        result = db_service.get_calendar_config(sample_calendar.id)
        assert result.name == "Updated Calendar Name"

    def test_delete_calendar_config(self, db_service, sample_calendar):
        """Test deleting a calendar config."""
        db_service.insert_calendar_config(sample_calendar)

        db_service.delete_calendar_config(sample_calendar.id)

        result = db_service.get_calendar_config(sample_calendar.id)
        assert result is None


class TestActiveCalendar:
    """Tests for active calendar management."""

    def test_get_active_calendar_when_none(self, db_service):
        """Test getting active calendar when none is set."""
        result = db_service.get_active_calendar_config()
        assert result is None

    def test_set_active_calendar(self, db_service, sample_calendar):
        """Test setting a calendar as active."""
        db_service.insert_calendar_config(sample_calendar)
        db_service.set_active_calendar_config(sample_calendar.id)

        result = db_service.get_active_calendar_config()
        assert result is not None
        assert result.id == sample_calendar.id

    def test_only_one_active_calendar(self, db_service, sample_calendar):
        """Test that setting a new active calendar deactivates the old one."""
        db_service.insert_calendar_config(sample_calendar)
        db_service.set_active_calendar_config(sample_calendar.id)

        # Create and set a second calendar as active
        second = CalendarConfig(
            id="test-calendar-002",
            name="Second Calendar",
            months=[MonthDefinition(name="Month1", abbreviation="M1", days=30)],
            week=WeekDefinition(day_names=["Day1"], day_abbreviations=["D1"]),
            year_variants=[],
            epoch_name="SC",
        )
        db_service.insert_calendar_config(second)
        db_service.set_active_calendar_config(second.id)

        # Only the second should be active
        result = db_service.get_active_calendar_config()
        assert result.id == second.id
