"""
Tests for the BaseRepository class.
"""

import json
import sqlite3

import pytest

from src.services.repositories.base_repository import BaseRepository


@pytest.fixture
def in_memory_db():
    """Creates an in-memory SQLite database."""
    conn = sqlite3.connect(":memory:")
    yield conn
    conn.close()


@pytest.fixture
def repository(in_memory_db):
    """Creates a BaseRepository instance with in-memory database."""
    return BaseRepository(connection=in_memory_db)


def test_base_repository_initialization_with_connection(in_memory_db):
    """Test BaseRepository can be initialized with a connection."""
    repo = BaseRepository(connection=in_memory_db)

    assert repo._connection is in_memory_db


def test_base_repository_initialization_without_connection():
    """Test BaseRepository can be initialized without a connection."""
    repo = BaseRepository()

    assert repo._connection is None


def test_set_connection(in_memory_db):
    """Test set_connection sets the database connection."""
    repo = BaseRepository()
    assert repo._connection is None

    repo.set_connection(in_memory_db)

    assert repo._connection is in_memory_db


def test_transaction_success(repository):
    """Test transaction context manager commits on success."""
    # Create a test table
    repository._connection.execute("CREATE TABLE test (id INTEGER, value TEXT)")

    with repository.transaction() as conn:
        conn.execute("INSERT INTO test (id, value) VALUES (?, ?)", (1, "test"))

    # Verify data was committed
    cursor = repository._connection.execute("SELECT * FROM test WHERE id = 1")
    row = cursor.fetchone()
    assert row == (1, "test")


def test_transaction_rollback_on_error(repository):
    """Test transaction context manager rolls back on error."""
    # Create a test table
    repository._connection.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")

    try:
        with repository.transaction() as conn:
            conn.execute("INSERT INTO test (id) VALUES (?)", (1,))
            # This should cause an error (duplicate primary key)
            conn.execute("INSERT INTO test (id) VALUES (?)", (1,))
    except sqlite3.IntegrityError:
        pass  # Expected error

    # Verify rollback - no rows should be present
    cursor = repository._connection.execute("SELECT COUNT(*) FROM test")
    count = cursor.fetchone()[0]
    assert count == 0


def test_transaction_without_connection():
    """Test transaction raises error when connection not initialized."""
    repo = BaseRepository()

    with pytest.raises(RuntimeError, match="Database connection not initialized"):
        with repo.transaction():
            pass


def test_serialize_json():
    """Test _serialize_json converts dict to JSON string."""
    data = {"key": "value", "number": 42, "nested": {"inner": "data"}}

    result = BaseRepository._serialize_json(data)

    assert isinstance(result, str)
    parsed = json.loads(result)
    assert parsed == data


def test_serialize_json_empty_dict():
    """Test _serialize_json handles empty dict."""
    result = BaseRepository._serialize_json({})

    assert result == "{}"


def test_serialize_json_complex_types():
    """Test _serialize_json handles various Python types."""
    data = {
        "string": "text",
        "integer": 123,
        "float": 45.67,
        "boolean": True,
        "null": None,
        "list": [1, 2, 3],
        "nested": {"a": "b"},
    }

    result = BaseRepository._serialize_json(data)
    parsed = json.loads(result)

    assert parsed == data


def test_deserialize_json():
    """Test _deserialize_json converts JSON string to dict."""
    json_str = '{"key": "value", "number": 42}'

    result = BaseRepository._deserialize_json(json_str)

    assert result == {"key": "value", "number": 42}


def test_deserialize_json_empty_string():
    """Test _deserialize_json returns empty dict for empty string."""
    result = BaseRepository._deserialize_json("")

    assert result == {}


def test_deserialize_json_invalid_json():
    """Test _deserialize_json returns empty dict for invalid JSON."""
    result = BaseRepository._deserialize_json("not valid json {")

    assert result == {}


def test_deserialize_json_non_dict():
    """Test _deserialize_json returns empty dict for non-dict JSON."""
    result = BaseRepository._deserialize_json('["array", "values"]')

    assert result == {}


def test_deserialize_json_null():
    """Test _deserialize_json handles None input."""
    result = BaseRepository._deserialize_json(None)

    assert result == {}


def test_deserialize_json_complex():
    """Test _deserialize_json handles complex nested structures."""
    json_str = json.dumps(
        {"level1": {"level2": {"level3": ["a", "b", "c"]}}, "data": [1, 2, 3]}
    )

    result = BaseRepository._deserialize_json(json_str)

    assert result["level1"]["level2"]["level3"] == ["a", "b", "c"]
    assert result["data"] == [1, 2, 3]


def test_transaction_propagates_exceptions(repository):
    """Test transaction propagates exceptions to caller."""
    repository._connection.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")

    with pytest.raises(sqlite3.IntegrityError):
        with repository.transaction() as conn:
            conn.execute("INSERT INTO test (id) VALUES (?)", (1,))
            conn.execute("INSERT INTO test (id) VALUES (?)", (1,))


def test_transaction_multiple_operations(repository):
    """Test transaction can handle multiple database operations."""
    repository._connection.execute("CREATE TABLE test (id INTEGER, value TEXT)")

    with repository.transaction() as conn:
        conn.execute("INSERT INTO test (id, value) VALUES (?, ?)", (1, "first"))
        conn.execute("INSERT INTO test (id, value) VALUES (?, ?)", (2, "second"))
        conn.execute("INSERT INTO test (id, value) VALUES (?, ?)", (3, "third"))

    # Verify all operations were committed
    cursor = repository._connection.execute("SELECT COUNT(*) FROM test")
    count = cursor.fetchone()[0]
    assert count == 3


def test_roundtrip_json_serialization():
    """Test serialization and deserialization are inverse operations."""
    original = {
        "string": "value",
        "number": 42,
        "float": 3.14,
        "boolean": True,
        "null": None,
        "list": [1, 2, 3],
        "nested": {"key": "value"},
    }

    serialized = BaseRepository._serialize_json(original)
    deserialized = BaseRepository._deserialize_json(serialized)

    assert deserialized == original
