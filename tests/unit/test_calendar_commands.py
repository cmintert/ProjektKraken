"""
Calendar Commands Unit Tests.

Tests for calendar-related commands following the Command pattern.
"""


import pytest

from src.commands.base_command import CommandResult
from src.commands.calendar_commands import (
    CreateCalendarConfigCommand,
    DeleteCalendarConfigCommand,
    SetActiveCalendarCommand,
    UpdateCalendarConfigCommand,
)
from src.core.calendar import (
    CalendarConfig,
    MonthDefinition,
    WeekDefinition,
)


@pytest.fixture
def sample_config() -> CalendarConfig:
    """Create a sample calendar config for testing."""
    return CalendarConfig(
        id="cmd-test-001",
        name="Command Test Calendar",
        months=[MonthDefinition(name="Month1", abbreviation="M1", days=30)],
        week=WeekDefinition(day_names=["Day1"], day_abbreviations=["D1"]),
        year_variants=[],
        epoch_name="CT",
    )


class TestCreateCalendarConfigCommand:
    """Tests for CreateCalendarConfigCommand."""

    def test_execute_creates_config(self, db_service, sample_config):
        """Test that execute creates the calendar config."""
        command = CreateCalendarConfigCommand(sample_config)

        result = command.execute(db_service)

        assert result.success
        stored = db_service.get_calendar_config(sample_config.id)
        assert stored is not None
        assert stored.name == sample_config.name

    def test_execute_returns_command_result(self, db_service, sample_config):
        """Test that execute returns a CommandResult."""
        command = CreateCalendarConfigCommand(sample_config)

        result = command.execute(db_service)

        assert isinstance(result, CommandResult)
        assert result.command_name == "CreateCalendarConfigCommand"

    def test_undo_deletes_config(self, db_service, sample_config):
        """Test that undo removes the created config."""
        command = CreateCalendarConfigCommand(sample_config)
        command.execute(db_service)

        command.undo(db_service)

        stored = db_service.get_calendar_config(sample_config.id)
        assert stored is None


class TestUpdateCalendarConfigCommand:
    """Tests for UpdateCalendarConfigCommand."""

    def test_execute_updates_config(self, db_service, sample_config):
        """Test that execute updates the calendar config."""
        # First, create the config
        db_service.insert_calendar_config(sample_config)

        # Now update it
        updated_config = CalendarConfig(
            id=sample_config.id,
            name="Updated Name",
            months=sample_config.months,
            week=sample_config.week,
            year_variants=[],
            epoch_name="UP",
        )
        command = UpdateCalendarConfigCommand(updated_config)

        result = command.execute(db_service)

        assert result.success
        stored = db_service.get_calendar_config(sample_config.id)
        assert stored.name == "Updated Name"

    def test_undo_restores_original(self, db_service, sample_config):
        """Test that undo restores the original config."""
        # Create original
        db_service.insert_calendar_config(sample_config)
        original_name = sample_config.name

        # Update it
        updated_config = CalendarConfig(
            id=sample_config.id,
            name="Updated Name",
            months=sample_config.months,
            week=sample_config.week,
            year_variants=[],
            epoch_name="UP",
        )
        command = UpdateCalendarConfigCommand(updated_config)
        command.execute(db_service)

        # Undo
        command.undo(db_service)

        stored = db_service.get_calendar_config(sample_config.id)
        assert stored.name == original_name


class TestDeleteCalendarConfigCommand:
    """Tests for DeleteCalendarConfigCommand."""

    def test_execute_deletes_config(self, db_service, sample_config):
        """Test that execute deletes the config."""
        db_service.insert_calendar_config(sample_config)

        command = DeleteCalendarConfigCommand(sample_config.id)
        result = command.execute(db_service)

        assert result.success
        stored = db_service.get_calendar_config(sample_config.id)
        assert stored is None

    def test_undo_restores_config(self, db_service, sample_config):
        """Test that undo restores the deleted config."""
        db_service.insert_calendar_config(sample_config)

        command = DeleteCalendarConfigCommand(sample_config.id)
        command.execute(db_service)
        command.undo(db_service)

        stored = db_service.get_calendar_config(sample_config.id)
        assert stored is not None
        assert stored.name == sample_config.name


class TestSetActiveCalendarCommand:
    """Tests for SetActiveCalendarCommand."""

    def test_execute_sets_active(self, db_service, sample_config):
        """Test that execute sets the calendar as active."""
        db_service.insert_calendar_config(sample_config)

        command = SetActiveCalendarCommand(sample_config.id)
        result = command.execute(db_service)

        assert result.success
        active = db_service.get_active_calendar_config()
        assert active is not None
        assert active.id == sample_config.id

    def test_undo_restores_previous_active(self, db_service, sample_config):
        """Test that undo restores the previously active calendar."""
        # Create and set first calendar as active
        first_config = CalendarConfig(
            id="first-config",
            name="First Calendar",
            months=[MonthDefinition(name="M1", abbreviation="M1", days=30)],
            week=WeekDefinition(day_names=["D1"], day_abbreviations=["D1"]),
            year_variants=[],
            epoch_name="F",
        )
        db_service.insert_calendar_config(first_config)
        db_service.set_active_calendar_config(first_config.id)

        # Create second calendar
        db_service.insert_calendar_config(sample_config)

        # Set second as active
        command = SetActiveCalendarCommand(sample_config.id)
        command.execute(db_service)

        # Undo
        command.undo(db_service)

        active = db_service.get_active_calendar_config()
        assert active is not None
        assert active.id == first_config.id
