"""
Unit test for RelationRepository with Temporal Attributes.

Verifies that the repository correctly handles complex JSON payloads
required for the temporal state engine (valid_from, payload dicts).
"""

import sqlite3

import pytest

from src.services.repositories.relation_repository import RelationRepository


@pytest.fixture
def db_connection():
    """Returns a fresh in-memory database connection."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    # Create schema
    conn.execute(
        """
        CREATE TABLE relations (
            id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL,
            target_id TEXT NOT NULL,
            rel_type TEXT NOT NULL,
            attributes JSON DEFAULT '{}',
            created_at REAL
        )
    """
    )
    yield conn
    conn.close()


@pytest.fixture
def repo(db_connection):
    repo = RelationRepository()
    repo.set_connection(db_connection)
    return repo


def test_insert_and_retrieve_temporal_relation(repo):
    """Test full cycle of a temporal relation with payload."""
    # Data with nested payload and time bounds
    attributes = {
        "valid_from": 100.5,
        "valid_to": None,
        "priority": "event",
        "payload": {
            "status": "Wounded",
            "location": "Battlefield",
            "stats": {"hp": 50},
        },
    }

    repo.insert(
        relation_id="rel_1",
        source_id="evt_1",
        target_id="ent_1",
        rel_type="injured_in",
        attributes=attributes,
        created_at=123456789.0,
    )

    # Retrieve
    relations = repo.get_by_source("evt_1")
    assert len(relations) == 1

    fetched_attrs = relations[0]["attributes"]

    # Verify structure matches exactly
    assert fetched_attrs["valid_from"] == 100.5
    assert fetched_attrs["valid_to"] is None
    assert fetched_attrs["payload"]["status"] == "Wounded"
    assert fetched_attrs["payload"]["stats"]["hp"] == 50


def test_update_payload(repo):
    """Test updating the JSON payload."""
    initial = {"valid_from": 100, "payload": {"a": 1}}
    repo.insert("rel_1", "src", "tgt", "type", initial, 0)

    updated = {"valid_from": 100, "payload": {"a": 2, "b": 3}}
    repo.update("rel_1", "type", updated)

    rel = repo.get_by_source("src")[0]
    assert rel["attributes"]["payload"]["a"] == 2
    assert rel["attributes"]["payload"]["b"] == 3
