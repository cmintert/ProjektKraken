from contextlib import closing

import pytest

from src.core.entities import Entity
from src.services.db_service import DatabaseService


@pytest.fixture
def db_path(tmp_path):
    """Provide a real file so independent connections share WAL state."""
    return str(tmp_path / "isolation_test.db")


def test_snapshot_isolation_and_refresh(db_path):
    """Refresh preserves an owned snapshot until its caller ends the transaction."""
    with (
        closing(DatabaseService(db_path)) as writer,
        closing(DatabaseService(db_path)) as reader,
    ):
        writer.connect()
        reader.connect()
        writer_connection = writer.require_connection()
        reader_connection = reader.require_connection()
        assert writer_connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert reader.get_all_entities() == []

        reader_connection.execute("BEGIN DEFERRED TRANSACTION")
        assert reader.get_all_entities() == []

        entity = Entity(name="Visible One", type="test")
        writer.insert_entity(entity)
        writer_connection.commit()

        # A refresh cannot commit or roll back a transaction owned by its caller.
        reader.ensure_fresh_view()
        assert reader_connection.in_transaction
        assert reader.get_all_entities() == []

        # Ending the snapshot belongs to the caller; the next read sees WAL data.
        reader_connection.rollback()
        reader.ensure_fresh_view()
        assert not reader_connection.in_transaction
        results = reader.get_all_entities()
        assert len(results) == 1
        assert results[0].id == entity.id
        assert results[0].name == "Visible One"
