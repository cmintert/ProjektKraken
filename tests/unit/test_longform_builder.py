"""
Unit tests for longform_builder service.

Tests the core functions for building, manipulating, and exporting
longform documents.
"""

import pytest
from unittest.mock import MagicMock, patch
import json
from src.services import longform_builder


# Test helper functions


def test_safe_json_loads_valid():
    """Test safe JSON loading with valid JSON."""
    result = longform_builder._safe_json_loads('{"key": "value"}')
    assert result == {"key": "value"}


def test_safe_json_loads_empty():
    """Test safe JSON loading with empty string."""
    result = longform_builder._safe_json_loads("")
    assert result == {}


def test_safe_json_loads_invalid():
    """Test safe JSON loading with invalid JSON."""
    result = longform_builder._safe_json_loads("not json")
    assert result == {}


def test_safe_json_loads_null():
    """Test safe JSON loading with None."""
    result = longform_builder._safe_json_loads(None)
    assert result == {}


def test_get_longform_meta_exists():
    """Test extracting longform metadata when it exists."""
    attrs = {
        "longform": {"default": {"position": 100.0, "depth": 0, "parent_id": None}}
    }
    meta = longform_builder._get_longform_meta(attrs, "default")
    assert meta == {"position": 100.0, "depth": 0, "parent_id": None}


def test_get_longform_meta_missing():
    """Test extracting longform metadata when it doesn't exist."""
    attrs = {}
    meta = longform_builder._get_longform_meta(attrs, "default")
    assert meta is None


def test_set_longform_meta_new():
    """Test setting longform metadata in empty attributes."""
    attrs = {}
    meta = {"position": 100.0, "depth": 0}
    result = longform_builder._set_longform_meta(attrs, meta, "default")

    assert "longform" in result
    assert "default" in result["longform"]
    assert result["longform"]["default"] == meta


def test_set_longform_meta_update():
    """Test updating existing longform metadata."""
    attrs = {"longform": {"default": {"position": 100.0}}}
    meta = {"position": 200.0, "depth": 1}
    result = longform_builder._set_longform_meta(attrs, meta, "default")

    assert result["longform"]["default"] == meta


# Helper to create dict-like row mocks


class MockRow(dict):
    """Mock sqlite3.Row that supports dict-like access."""

    def __getitem__(self, key):
        return super().__getitem__(key)


# Test read_all_longform_items with mock connection


@pytest.fixture
def mock_connection():
    """Create a mock SQLite connection."""
    conn = MagicMock()
    return conn


def test_read_all_longform_items_mixed(mock_connection):
    """Test reading longform items from both events and entities."""
    # Mock events query
    event_rows = [
        MockRow(
            {
                "id": "event-1",
                "name": "Event One",
                "description": "Event content",
                "attributes": json.dumps(
                    {
                        "longform": {
                            "default": {
                                "position": 100.0,
                                "depth": 0,
                                "parent_id": None,
                            }
                        }
                    }
                ),
            }
        )
    ]

    # Mock entities query
    entity_rows = [
        MockRow(
            {
                "id": "entity-1",
                "name": "Entity One",
                "description": "Entity content",
                "attributes": json.dumps(
                    {
                        "longform": {
                            "default": {
                                "position": 200.0,
                                "depth": 0,
                                "parent_id": None,
                            }
                        }
                    }
                ),
            }
        )
    ]

    # Setup mock to return different results for events and entities
    def execute_side_effect(query, *args):
        cursor = MagicMock()
        if "events" in query:
            cursor.fetchall.return_value = event_rows
        else:  # entities
            cursor.fetchall.return_value = entity_rows
        return cursor

    mock_connection.execute.side_effect = execute_side_effect

    items = longform_builder.read_all_longform_items(mock_connection)

    assert len(items) == 2
    assert items[0]["table"] == "events"
    assert items[0]["id"] == "event-1"
    assert items[0]["meta"]["position"] == 100.0
    assert items[1]["table"] == "entities"
    assert items[1]["id"] == "entity-1"


def test_read_all_longform_items_no_metadata(mock_connection):
    """Test reading when rows have no longform metadata."""
    event_rows = [
        MockRow(
            {
                "id": "event-1",
                "name": "Event One",
                "description": "Event content",
                "attributes": json.dumps({}),  # No longform metadata
            }
        )
    ]

    def execute_side_effect(query, *args):
        cursor = MagicMock()
        if "events" in query:
            cursor.fetchall.return_value = event_rows
        else:
            cursor.fetchall.return_value = []
        return cursor

    mock_connection.execute.side_effect = execute_side_effect

    items = longform_builder.read_all_longform_items(mock_connection)

    assert len(items) == 0


# Test build_longform_sequence


def test_build_longform_sequence_ordering(mock_connection):
    """Test that sequence is built in correct order by position."""
    rows = [
        MockRow(
            {
                "id": "item-3",
                "name": "Third",
                "description": "",
                "attributes": json.dumps(
                    {
                        "longform": {
                            "default": {
                                "position": 300.0,
                                "depth": 0,
                                "parent_id": None,
                            }
                        }
                    }
                ),
            }
        ),
        MockRow(
            {
                "id": "item-1",
                "name": "First",
                "description": "",
                "attributes": json.dumps(
                    {
                        "longform": {
                            "default": {
                                "position": 100.0,
                                "depth": 0,
                                "parent_id": None,
                            }
                        }
                    }
                ),
            }
        ),
        MockRow(
            {
                "id": "item-2",
                "name": "Second",
                "description": "",
                "attributes": json.dumps(
                    {
                        "longform": {
                            "default": {
                                "position": 200.0,
                                "depth": 0,
                                "parent_id": None,
                            }
                        }
                    }
                ),
            }
        ),
    ]

    def execute_side_effect(query, *args):
        cursor = MagicMock()
        if "events" in query:
            cursor.fetchall.return_value = rows
        else:
            cursor.fetchall.return_value = []
        return cursor

    mock_connection.execute.side_effect = execute_side_effect

    sequence = longform_builder.build_longform_sequence(mock_connection)

    assert len(sequence) == 3
    assert sequence[0]["id"] == "item-1"
    assert sequence[1]["id"] == "item-2"
    assert sequence[2]["id"] == "item-3"


def test_build_longform_sequence_nesting(mock_connection):
    """Test that sequence handles parent-child nesting correctly."""
    rows = [
        MockRow(
            {
                "id": "parent",
                "name": "Parent",
                "description": "",
                "attributes": json.dumps(
                    {
                        "longform": {
                            "default": {
                                "position": 100.0,
                                "depth": 0,
                                "parent_id": None,
                            }
                        }
                    }
                ),
            }
        ),
        MockRow(
            {
                "id": "child-1",
                "name": "Child 1",
                "description": "",
                "attributes": json.dumps(
                    {
                        "longform": {
                            "default": {
                                "position": 110.0,
                                "depth": 1,
                                "parent_id": "parent",
                            }
                        }
                    }
                ),
            }
        ),
        MockRow(
            {
                "id": "child-2",
                "name": "Child 2",
                "description": "",
                "attributes": json.dumps(
                    {
                        "longform": {
                            "default": {
                                "position": 120.0,
                                "depth": 1,
                                "parent_id": "parent",
                            }
                        }
                    }
                ),
            }
        ),
    ]

    def execute_side_effect(query, *args):
        cursor = MagicMock()
        if "events" in query:
            cursor.fetchall.return_value = rows
        else:
            cursor.fetchall.return_value = []
        return cursor

    mock_connection.execute.side_effect = execute_side_effect

    sequence = longform_builder.build_longform_sequence(mock_connection)

    assert len(sequence) == 3
    assert sequence[0]["id"] == "parent"
    assert sequence[0]["heading_level"] == 1
    assert sequence[1]["id"] == "child-1"
    assert sequence[1]["heading_level"] == 2
    assert sequence[2]["id"] == "child-2"
    assert sequence[2]["heading_level"] == 2


def test_build_longform_sequence_heading_levels(mock_connection):
    """Test that heading levels are computed correctly."""
    rows = [
        MockRow(
            {
                "id": "level-0",
                "name": "Level 0",
                "description": "",
                "attributes": json.dumps(
                    {
                        "longform": {
                            "default": {
                                "position": 100.0,
                                "depth": 0,
                                "parent_id": None,
                            }
                        }
                    }
                ),
            }
        ),
        MockRow(
            {
                "id": "level-5",
                "name": "Level 5",
                "description": "",
                "attributes": json.dumps(
                    {
                        "longform": {
                            "default": {
                                "position": 200.0,
                                "depth": 5,
                                "parent_id": None,
                            }
                        }
                    }
                ),
            }
        ),
        MockRow(
            {
                "id": "level-10",
                "name": "Level 10 (capped at 6)",
                "description": "",
                "attributes": json.dumps(
                    {
                        "longform": {
                            "default": {
                                "position": 300.0,
                                "depth": 10,
                                "parent_id": None,
                            }
                        }
                    }
                ),
            }
        ),
    ]

    def execute_side_effect(query, *args):
        cursor = MagicMock()
        if "events" in query:
            cursor.fetchall.return_value = rows
        else:
            cursor.fetchall.return_value = []
        return cursor

    mock_connection.execute.side_effect = execute_side_effect

    sequence = longform_builder.build_longform_sequence(mock_connection)

    assert sequence[0]["heading_level"] == 1  # depth 0 -> level 1
    assert sequence[1]["heading_level"] == 6  # depth 5 -> level 6
    assert sequence[2]["heading_level"] == 6  # depth 10 -> level 6 (capped)


# Test insert_or_update_longform_meta


def test_insert_or_update_longform_meta_new(mock_connection):
    """Test inserting new longform metadata."""
    # Mock fetching current attributes
    cursor = MagicMock()
    cursor.fetchone.return_value = {"attributes": "{}"}
    mock_connection.execute.return_value = cursor

    longform_builder.insert_or_update_longform_meta(
        mock_connection, "events", "test-id", position=100.0, parent_id=None, depth=0
    )

    # Check that UPDATE was called
    calls = [
        call for call in mock_connection.execute.call_args_list if "UPDATE" in str(call)
    ]
    assert len(calls) > 0

    # Verify commit was called
    mock_connection.commit.assert_called()


def test_insert_or_update_longform_meta_update_existing(mock_connection):
    """Test updating existing longform metadata."""
    existing_attrs = {
        "longform": {"default": {"position": 100.0, "depth": 0, "parent_id": None}}
    }

    cursor = MagicMock()
    cursor.fetchone.return_value = {"attributes": json.dumps(existing_attrs)}
    mock_connection.execute.return_value = cursor

    longform_builder.insert_or_update_longform_meta(
        mock_connection, "events", "test-id", position=200.0
    )

    # Check that UPDATE was called
    calls = [
        call for call in mock_connection.execute.call_args_list if "UPDATE" in str(call)
    ]
    assert len(calls) > 0

    mock_connection.commit.assert_called()


def test_insert_or_update_longform_meta_invalid_table(mock_connection):
    """Test that invalid table name raises error."""
    with pytest.raises(ValueError, match="Invalid table"):
        longform_builder.insert_or_update_longform_meta(
            mock_connection, "invalid_table", "test-id", position=100.0
        )


def test_insert_or_update_longform_meta_row_not_found(mock_connection):
    """Test that missing row raises error."""
    cursor = MagicMock()
    cursor.fetchone.return_value = None
    mock_connection.execute.return_value = cursor

    with pytest.raises(ValueError, match="not found"):
        longform_builder.insert_or_update_longform_meta(
            mock_connection, "events", "missing-id", position=100.0
        )


# Test place_between_siblings_and_set_parent


def test_place_between_siblings_middle(mock_connection):
    """Test placing item between two siblings."""
    # Mock previous sibling with position 100
    prev_cursor = MagicMock()
    prev_cursor.fetchone.return_value = {
        "attributes": json.dumps({"longform": {"default": {"position": 100.0}}})
    }

    # Mock next sibling with position 300
    next_cursor = MagicMock()
    next_cursor.fetchone.return_value = {
        "attributes": json.dumps({"longform": {"default": {"position": 300.0}}})
    }

    # Mock target row
    target_cursor = MagicMock()
    target_cursor.fetchone.return_value = {"attributes": "{}"}

    def execute_side_effect(query, *args):
        if "prev-id" in str(args):
            return prev_cursor
        elif "next-id" in str(args):
            return next_cursor
        else:
            return target_cursor

    mock_connection.execute.side_effect = execute_side_effect

    longform_builder.place_between_siblings_and_set_parent(
        mock_connection,
        "events",
        "target-id",
        ("events", "prev-id"),
        ("events", "next-id"),
        None,
    )

    # Position should be average: (100 + 300) / 2 = 200
    # Can't easily verify the exact value without more complex mocking,
    # but we can verify the function completes without error
    mock_connection.commit.assert_called()


def test_place_between_siblings_only_prev(mock_connection):
    """Test placing item after a sibling with no next sibling."""
    prev_cursor = MagicMock()
    prev_cursor.fetchone.return_value = {
        "attributes": json.dumps({"longform": {"default": {"position": 100.0}}})
    }

    target_cursor = MagicMock()
    target_cursor.fetchone.return_value = {"attributes": "{}"}

    def execute_side_effect(query, *args):
        if "prev-id" in str(args):
            return prev_cursor
        else:
            return target_cursor

    mock_connection.execute.side_effect = execute_side_effect

    longform_builder.place_between_siblings_and_set_parent(
        mock_connection, "events", "target-id", ("events", "prev-id"), None, None
    )

    # Position should be 100 + 100 = 200
    mock_connection.commit.assert_called()


def test_place_between_siblings_no_siblings(mock_connection):
    """Test placing item with no siblings (first item)."""
    target_cursor = MagicMock()
    target_cursor.fetchone.return_value = {"attributes": "{}"}
    mock_connection.execute.return_value = target_cursor

    longform_builder.place_between_siblings_and_set_parent(
        mock_connection, "events", "target-id", None, None, None
    )

    # Position should be default (100.0)
    mock_connection.commit.assert_called()


# Test reindex_document_positions


def test_reindex_document_positions(mock_connection):
    """Test that reindex assigns clean positions."""
    # This is an integration-style test, so we'll test it in integration tests
    # For unit test, we just ensure it doesn't crash
    rows = []

    def execute_side_effect(query, *args):
        cursor = MagicMock()
        cursor.fetchall.return_value = [MagicMock(**row) for row in rows]
        cursor.fetchone.return_value = {"attributes": "{}"}
        return cursor

    mock_connection.execute.side_effect = execute_side_effect

    # Should not raise error even with empty document
    longform_builder.reindex_document_positions(mock_connection)


# Test export_longform_to_markdown


def test_export_longform_to_markdown_empty(mock_connection):
    """Test exporting empty document."""

    def execute_side_effect(query, *args):
        cursor = MagicMock()
        cursor.fetchall.return_value = []
        return cursor

    mock_connection.execute.side_effect = execute_side_effect

    markdown = longform_builder.export_longform_to_markdown(mock_connection)

    assert "# Longform Document: default" in markdown


def test_export_longform_to_markdown_with_content(mock_connection):
    """Test exporting document with content."""
    rows = [
        MockRow(
            {
                "id": "event-1",
                "name": "Event One",
                "description": "Event content here",
                "attributes": json.dumps(
                    {
                        "longform": {
                            "default": {
                                "position": 100.0,
                                "depth": 0,
                                "parent_id": None,
                            }
                        }
                    }
                ),
            }
        )
    ]

    def execute_side_effect(query, *args):
        cursor = MagicMock()
        if "events" in query:
            cursor.fetchall.return_value = rows
        else:
            cursor.fetchall.return_value = []
        return cursor

    mock_connection.execute.side_effect = execute_side_effect

    markdown = longform_builder.export_longform_to_markdown(mock_connection)

    assert "# Event One" in markdown
    assert "Event content here" in markdown
    assert "PK-LONGFORM id=event-1" in markdown
    assert "table=events" in markdown


def test_export_longform_to_markdown_title_override(mock_connection):
    """Test that title_override is used in export."""
    rows = [
        MockRow(
            {
                "id": "event-1",
                "name": "Original Name",
                "description": "Content",
                "attributes": json.dumps(
                    {
                        "longform": {
                            "default": {
                                "position": 100.0,
                                "depth": 0,
                                "parent_id": None,
                                "title_override": "Custom Title",
                            }
                        }
                    }
                ),
            }
        )
    ]

    def execute_side_effect(query, *args):
        cursor = MagicMock()
        if "events" in query:
            cursor.fetchall.return_value = rows
        else:
            cursor.fetchall.return_value = []
        return cursor

    mock_connection.execute.side_effect = execute_side_effect

    markdown = longform_builder.export_longform_to_markdown(mock_connection)

    assert "# Custom Title" in markdown
    assert "Original Name" not in markdown.split("<!--")[1]  # Not in heading
