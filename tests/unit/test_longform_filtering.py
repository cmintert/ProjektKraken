import json
from unittest.mock import MagicMock, patch

import pytest

from src.services import longform_builder
from src.services.worker import DatabaseWorker


@pytest.fixture
def mock_conn():
    conn = MagicMock()
    # Mock cursors for read_all_longform_items

    # Events data
    ROW_EVENT_1 = {
        "id": "e1",
        "name": "Event 1",
        "description": "Desc 1",
        "attributes": '{"_longform": {"default": {"position": 100}}}',
    }
    ROW_EVENT_2 = {
        "id": "e2",
        "name": "Filtered Event",
        "description": "Desc 2",
        "attributes": '{"_longform": {"default": {"position": 200}}}',
    }

    # Entities data
    ROW_ENTITY_1 = {
        "id": "ent1",
        "name": "Entity 1",
        "description": "Desc Ent 1",
        "attributes": '{"_longform": {"default": {"position": 300}}}',
    }

    # Setup cursor behavior
    cursor = MagicMock()

    # We need to handle multiple execute calls differently
    def side_effect(query, params=()):
        mock_cursor = MagicMock()
        if "FROM events" in query:
            mock_cursor.fetchall.return_value = [dict(ROW_EVENT_1), dict(ROW_EVENT_2)]
        elif "FROM entities" in query:
            mock_cursor.fetchall.return_value = [dict(ROW_ENTITY_1)]
        return mock_cursor

    conn.execute.side_effect = side_effect
    return conn


def test_read_all_longform_items_no_filter(mock_conn):
    """Test reading all items without any filter."""
    items = longform_builder.read_all_longform_items(mock_conn, "default")
    ids = {item["id"] for item in items}
    assert ids == {"e1", "e2", "ent1"}


def test_read_all_longform_items_with_allowed_ids(mock_conn):
    """Test reading items with a restricted set of allowed IDs."""
    allowed = {"e1", "ent1"}
    items = longform_builder.read_all_longform_items(
        mock_conn, "default", allowed_ids=allowed
    )
    ids = {item["id"] for item in items}
    assert "e1" in ids
    assert "ent1" in ids
    assert "e2" not in ids


def test_build_longform_sequence_skips_ensure_indexed_when_filtered(mock_conn):
    """Test that build_longform_sequence skips ensure_all_items_indexed when allowed_ids is set."""
    with patch("src.services.longform_builder.ensure_all_items_indexed") as mock_ensure:
        with patch(
            "src.services.longform_builder.read_all_longform_items"
        ) as mock_read:
            mock_read.return_value = []

            # Case 1: No filter -> Should call ensure
            longform_builder.build_longform_sequence(
                mock_conn, "default", allowed_ids=None
            )
            mock_ensure.assert_called_once()

            mock_ensure.reset_mock()

            # Case 2: Filter -> Should NOT call ensure
            longform_builder.build_longform_sequence(
                mock_conn, "default", allowed_ids={"x"}
            )
            mock_ensure.assert_not_called()


def test_worker_load_longform_sequence_pass_through_filter():
    """Test that worker.load_longform_sequence handles filter config correctly."""
    worker = DatabaseWorker("dummy.db")
    worker.db_service = MagicMock()

    # Mock db_service methods
    worker.db_service._connection = MagicMock()
    # filter_ids_by_tags returns List[tuple[str, str]] not a set
    worker.db_service.filter_ids_by_tags.return_value = [
        ("event", "id1"),
        ("entity", "id2"),
    ]

    with patch("src.services.longform_builder.build_longform_sequence") as mock_build:
        # Call with filter - using JSON string as per new signature
        filter_config = {"include": ["TagA"]}
        filter_json = json.dumps(filter_config)
        worker.load_longform_sequence("default", filter_json)

        # Verify db_service filter called
        worker.db_service.filter_ids_by_tags.assert_called_with(
            object_type=None,
            include=["TagA"],
            include_mode="any",  # default
            exclude=None,
            exclude_mode="any",  # default
            case_sensitive=False,  # default
        )

        # Verify builder called with allowed_ids (as a set of just IDs)
        mock_build.assert_called_with(
            worker.db_service._connection, doc_id="default", allowed_ids={"id1", "id2"}
        )
