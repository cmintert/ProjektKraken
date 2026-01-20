"""Tests for Import Service Deduplication and Modes."""

import pytest

from src.core.entities import Entity
from src.services.db_service import DatabaseService
from src.services.import_service import ImportService


@pytest.fixture
def memory_db():
    """Provides a fresh in-memory database service."""
    service = DatabaseService(":memory:")
    service.connect()
    return service


@pytest.fixture
def import_service(memory_db):
    """Provides an ImportService instance."""
    return ImportService(memory_db)


@pytest.mark.unit
class TestImportDeduplication:
    """Tests for import deduplication logic."""

    def test_import_creates_new_when_no_match(self, import_service, memory_db):
        """Should create a new entity if no match is found."""
        data = {
            "entities": [
                {"name": "New Entity", "type": "person", "description": "Fresh"}
            ]
        }

        result = import_service.import_batch(data)

        assert result.success
        assert len(result.created_entities) == 1

        entity = memory_db.get_entity(result.created_entities[0])
        assert entity.name == "New Entity"
        assert entity.description == "Fresh"

    def test_import_updates_existing_by_name(self, import_service, memory_db):
        """Should update existing entity if name matches (default mode=update)."""
        # 1. Existing entity
        existing = Entity(name="Gandalf", type="person", description="Old Desc")
        memory_db.insert_entity(existing)

        # 2. Import update
        data = {
            "entities": [
                {"name": "gandalf", "type": "person", "description": "New Desc"}
            ]
        }

        # Default mode should be 'update'
        result = import_service.import_batch(data, options={"mode": "update"})

        # Should NOT create new ID, but update existing
        assert (
            len(result.created_entities) == 1
        )  # API reports touched IDs in created currently?
        # Ideally we want separate lists or just check total count logic.
        # Current API puts updated IDs in created_entities too? Let's check implementations.
        # Actually existing created_entities tracks upserts.

        updated = memory_db.get_entity(existing.id)
        assert updated.description == "New Desc"
        # Name should likely remain as per existing (or updated if we normalize?)
        # "update" usually preserves primary keys/identity.

    def test_import_overwrites_existing_by_name(self, import_service, memory_db):
        """Should overwrite existing entity fields entirely."""
        existing = Entity(
            name="Saruman", type="person", description="White", attributes={"power": 10}
        )
        memory_db.insert_entity(existing)

        data = {
            "entities": [
                {
                    "name": "saruman",
                    "type": "person",
                    "description": "Many Colours",
                    "attributes": {"treason": True},
                }
            ]
        }

        import_service.import_batch(data, options={"mode": "overwrite"})

        updated = memory_db.get_entity(existing.id)
        assert updated.description == "Many Colours"
        # Overwrite implies replacing attributes entirely? OR merging?
        # Plan says: "Replace all fields... Update attributes"
        # Usually overwrite replaces the attributes dictionary.
        assert updated.attributes.get("treason") is True
        assert updated.attributes.get("power") is None  # Should be gone

    def test_import_skips_existing(self, import_service, memory_db):
        """Should skip update if mode is skip."""
        existing = Entity(name="Bilbo", type="person", description="Old")
        memory_db.insert_entity(existing)

        data = {"entities": [{"name": "Bilbo", "type": "person", "description": "New"}]}

        import_service.import_batch(data, options={"mode": "skip"})

        updated = memory_db.get_entity(existing.id)
        assert updated.description == "Old"

    def test_conflict_resolution_external_id_precedence(
        self, import_service, memory_db
    ):
        """External ID match should take precedence over Name match."""
        # 1. Setup: Entity A has ext_id="123" (stored in attributes), Name="Frodo"
        # 2. Import: ext_id="123", Name="Samwise"
        # 3. Should match Entity A (by ext_id) and update name to Samwise.

        attributes = {
            "_import_sources": [{"source_name": "test", "external_id": "123"}]
        }
        existing = Entity(name="Frodo", type="person", attributes=attributes)
        memory_db._entity_repo.insert(existing)  # Direct insert helper

        data = {
            "entities": [{"name": "Samwise", "type": "person", "external_id": "123"}],
        }

        import_service.import_batch(
            data, options={"source_name": "test", "mode": "update"}
        )

        updated = memory_db.get_entity(existing.id)
        assert updated.name == "Samwise"

    def test_dry_run_makes_no_changes(self, import_service, memory_db):
        """Dry run should return report but change nothing."""
        data = {"entities": [{"name": "Ghost", "type": "person"}]}

        result = import_service.import_batch(data, options={"dry_run": True})

        assert result.success
        assert len(memory_db.get_all_entities()) == 0
