"""
Security tests for longform_builder module.

Tests table name validation to ensure SQL injection protection.
"""

import pytest

from src.services import longform_builder


def test_validate_table_name_valid_events():
    """Test that 'events' table name is valid."""
    # Should not raise
    longform_builder._validate_table_name("events")


def test_validate_table_name_valid_entities():
    """Test that 'entities' table name is valid."""
    # Should not raise
    longform_builder._validate_table_name("entities")


def test_validate_table_name_invalid():
    """Test that invalid table names are rejected."""
    with pytest.raises(ValueError, match="Invalid table name"):
        longform_builder._validate_table_name("users")


def test_validate_table_name_sql_injection_attempt():
    """Test that SQL injection attempts are blocked."""
    # Attempt to inject SQL via table name
    with pytest.raises(ValueError, match="Invalid table name"):
        longform_builder._validate_table_name("events; DROP TABLE users--")


def test_validate_table_name_case_sensitive():
    """Test that table name validation is case-sensitive."""
    # Uppercase should fail
    with pytest.raises(ValueError, match="Invalid table name"):
        longform_builder._validate_table_name("EVENTS")


def test_insert_or_update_invalid_table(db_service):
    """Test that insert_or_update_longform_meta rejects invalid tables."""
    with pytest.raises(ValueError, match="Invalid table name"):
        longform_builder.insert_or_update_longform_meta(
            db_service._connection,
            "invalid_table",
            "some-id",
            position=100.0,
        )


def test_promote_item_invalid_table(db_service):
    """Test that promote_item rejects invalid tables."""
    with pytest.raises(ValueError, match="Invalid table name"):
        longform_builder.promote_item(
            db_service._connection,
            "invalid_table",
            "some-id",
        )


def test_demote_item_invalid_table(db_service):
    """Test that demote_item rejects invalid tables."""
    with pytest.raises(ValueError, match="Invalid table name"):
        longform_builder.demote_item(
            db_service._connection,
            "invalid_table",
            "some-id",
        )


def test_remove_from_longform_invalid_table(db_service):
    """Test that remove_from_longform rejects invalid tables."""
    with pytest.raises(ValueError, match="Invalid table name"):
        longform_builder.remove_from_longform(
            db_service._connection,
            "invalid_table",
            "some-id",
        )


def test_place_between_siblings_invalid_target_table(db_service):
    """Test that place_between_siblings rejects invalid target tables."""
    with pytest.raises(ValueError, match="Invalid table name"):
        longform_builder.place_between_siblings_and_set_parent(
            db_service._connection,
            "invalid_table",
            "some-id",
            None,
            None,
            None,
        )


def test_place_between_siblings_invalid_prev_table(db_service):
    """Test that place_between_siblings rejects invalid prev sibling tables."""
    with pytest.raises(ValueError, match="Invalid table name"):
        longform_builder.place_between_siblings_and_set_parent(
            db_service._connection,
            "events",
            "some-id",
            ("invalid_table", "prev-id"),
            None,
            None,
        )


def test_place_between_siblings_invalid_next_table(db_service):
    """Test that place_between_siblings rejects invalid next sibling tables."""
    with pytest.raises(ValueError, match="Invalid table name"):
        longform_builder.place_between_siblings_and_set_parent(
            db_service._connection,
            "events",
            "some-id",
            None,
            ("invalid_table", "next-id"),
            None,
        )
