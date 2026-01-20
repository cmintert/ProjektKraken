import pytest
from unittest.mock import MagicMock
from src.services.import_service import ImportService


def test_import_date_warning(db_service):
    """Test that failed date parsing adds a warning to the result."""
    # Setup
    import_service = ImportService(db_service)

    # Mock get_active_calendar_config to return NONE (no calendar)
    # This forces date parsing to fail
    db_service.get_active_calendar_config = MagicMock(return_value=None)

    data = {"events": [{"name": "Test Event", "lore_date": "UnknownMonth 22, 2023"}]}

    # Execute
    result = import_service.import_batch(data)

    # Verify
    assert result.success is True
    assert len(result.created_events) == 1

    # Check warnings
    # With fallback, it now attempts to parse with Gregorian default
    # Since "UnknownMonth" is invalid in Gregorian, it raises ValueError -> "Failed to parse..."
    assert len(result.warnings) > 0
    assert any("Failed to parse date string" in w for w in result.warnings)


def test_import_fallback_success(db_service):
    """Test that missing DB calendar falls back to Default Gregorian for valid dates."""
    import_service = ImportService(db_service)
    db_service.get_active_calendar_config = MagicMock(return_value=None)

    data = {"events": [{"name": "Fallback Event", "lore_date": "January 1, 2023"}]}

    result = import_service.import_batch(data)

    assert result.success is True
    assert len(result.created_events) == 1
    # Should be NO warnings because fallback handled it
    assert len(result.warnings) == 0

    # Retrieve the event to check timestamp
    event_id = result.created_events[0]
    # Check if we can retrieve it from the mocked db_service or if we need to mock retrieval
    # If db_service is a real in-memory instance (common fixture), strict retrieval works
    # However, validation logic usually implies we verify the *call* to create happened with correct data
    # OR we check the DB state.

    # Assuming db_service fixture is functional In-Memory DB:
    saved_event = db_service.get_event(event_id)
    assert saved_event is not None
    # Timestamp for Jan 1 2023 should be non-zero
    assert saved_event.lore_date != 0.0


def test_import_date_parsing_failure_warning(db_service):
    """Test that invalid date string adds a warning (when calendar exists)."""
    # Setup
    import_service = ImportService(db_service)

    # This time we let it find a calendar (mocked or real from db_service fixture if defaults exist)
    # Actually db_service fixture usually has empty DB.
    # Let's mock _get_parser to return a mock parser that raises ValueError

    mock_parser = MagicMock()
    mock_parser.parse_date.side_effect = ValueError("Invalid format")

    import_service._get_parser = MagicMock(return_value=mock_parser)

    data = {"events": [{"name": "Test Event 2", "lore_date": "BadFormat 123"}]}

    result = import_service.import_batch(data)

    assert result.success is True
    assert len(result.created_events) == 1
    assert len(result.warnings) > 0
    assert any("Failed to parse date string" in w for w in result.warnings)
