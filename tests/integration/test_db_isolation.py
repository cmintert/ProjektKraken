import pytest

from src.core.entities import Entity
from src.services.db_service import DatabaseService


@pytest.fixture
def db_path(tmp_path):
    """Provides a path to a temporary database file."""
    # We use a real file because in-memory DBs (:memory:) are isolated per connection usually,
    # or shared via URI but WAL behavior might be slightly different or less critical to test there.
    # To strictly test WAL isolation, a file is best.
    p = tmp_path / "isolation_test.db"
    return str(p)


def test_snapshot_isolation_and_refresh(db_path):
    """Verifies that ensure_fresh_view captures updates from other connections."""

    # 1. Setup Writer Connection
    writer_service = DatabaseService(db_path)
    writer_service.connect()
    # Ensure WAL mode
    writer_service._connection.execute("PRAGMA journal_mode=WAL;")
    writer_service._init_schema()

    # 2. Setup Reader Connection (simulating Worker)
    reader_service = DatabaseService(db_path)
    reader_service.connect()

    # 3. Reader establishes a snapshot by reading
    # Using a transaction block or just a select might trigger it depending on isolation level.
    # Python sqlite3 defaults to DEFERRED.
    # We need to ensure we are 'in a transaction'.

    # Initial state: Empty
    assert len(reader_service.get_all_entities()) == 0

    # Reader is now potentially holding a read transaction if we didn't commit?
    # correct `get_all_entities` executes a select.
    # If isolation_level is default, it might auto-commit read.
    # To simulate the persistent worker issue, we might need to manually ensure we are in a transaction.

    reader_service._connection.execute("BEGIN DEFERRED TRANSACTION")
    reader_service._connection.execute("SELECT * FROM entities")

    # 4. Writer inserts data
    entity = Entity(name="Visible One", type="test")
    writer_service.insert_entity(entity)
    # Writer commits (insert_entity does this contextually if designed so, let's double check)
    # The service methods usually commit.

    # 5. Reader checks again - WITHOUT refreshing
    # Since we manually started a transaction on reader, it should be isolated.
    cursor = reader_service._connection.execute("SELECT COUNT(*) FROM entities")
    count = cursor.fetchone()[0]

    # If snapshot isolation is working as expected (and causing the bug), count should be 0
    assert (
        count == 0
    ), "Reader should not see data committed after its transaction started"

    # 6. Apply Fix: Ensure Fresh View
    # This should commit/rollback the current read transaction
    reader_service.ensure_fresh_view()

    # 7. Reader checks again - WITH refreshing
    results = reader_service.get_all_entities()
    assert len(results) == 1, "Reader should see data after refreshing view"
    assert results[0].name == "Visible One"

    # Cleanup
    writer_service.close()
    reader_service.close()
