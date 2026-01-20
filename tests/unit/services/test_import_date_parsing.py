import logging
import pytest
from src.core.calendar import CalendarConfig, MonthDefinition, WeekDefinition
from src.services.db_service import DatabaseService
from src.services.import_service import ImportService


@pytest.fixture
def memory_db():
    """Provides a fresh in-memory database."""
    db = DatabaseService(":memory:")
    db.connect()
    yield db
    db.close()


@pytest.fixture
def simple_calendar() -> CalendarConfig:
    """A simple test calendar with 12 months of 30 days each."""
    months = [
        MonthDefinition(name=f"Month{i + 1}", abbreviation=f"M{i + 1}", days=30)
        for i in range(12)
    ]
    week = WeekDefinition(
        day_names=["Day1", "Day2", "Day3", "Day4", "Day5", "Day6", "Day7"],
        day_abbreviations=["D1", "D2", "D3", "D4", "D5", "D6", "D7"],
    )
    return CalendarConfig(
        id="test-calendar",
        name="Test Calendar",
        months=months,
        week=week,
        year_variants=[],
        epoch_name="SE",
    )


def test_import_parses_date_string(memory_db, simple_calendar):
    """Test importing an event with a string date works if calendar is active."""
    # 1. Setup Active Calendar
    simple_calendar.is_active = True
    memory_db.insert_calendar_config(simple_calendar)

    # Verify it is active
    active = memory_db.get_active_calendar_config()
    assert active is not None
    assert active.id == simple_calendar.id

    # 2. Prepare Import Data
    import_data = {
        "events": [
            {
                "name": "Event String Date",
                "lore_date": "Year 30",  # "Year 30" -> 30.1.1 -> (29 * 360) = 10440.0
                "type": "generic",
            }
        ]
    }

    # 3. Run Import
    importer = ImportService(memory_db)
    result = importer.import_batch(import_data)

    assert (
        result.success is True
    ), f"Import failed. Errors: {result.errors}, Warnings: {result.warnings}"
    assert (
        len(result.created_events) == 1
    ), f"No events created. Errors: {result.errors}, Warnings: {result.warnings}"

    # 4. Verify Data
    event_id = result.created_events[0]
    event = memory_db.get_event(event_id)

    assert event is not None
    # 29 full years * 360 days = 10440.0
    assert event.lore_date == 10440.0


def test_import_fallback_on_missing_calendar(memory_db):
    """Test fallback to 0.0 if no calendar is active."""
    # Ensure no active calendar
    assert memory_db.get_active_calendar_config() is None

    import_data = {
        "events": [
            {"name": "Event No Calendar", "lore_date": "Year 30", "type": "generic"}
        ]
    }

    importer = ImportService(memory_db)
    result = importer.import_batch(import_data)

    # Should succeed but defaulting date to 0.0 (and warn logs)
    assert result.success is True
    event = memory_db.get_event(result.created_events[0])
    assert event.lore_date == 0.0


def test_import_raw_float_preserved(memory_db):
    """Test that raw floats are preserved even if parser exists."""
    import_data = {
        "events": [{"name": "Event Float", "lore_date": 123.45, "type": "generic"}]
    }

    importer = ImportService(memory_db)
    result = importer.import_batch(import_data)

    event = memory_db.get_event(result.created_events[0])
    assert event.lore_date == 123.45
