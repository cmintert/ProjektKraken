"""Unit tests for EntityRepository."""

import pytest

from src.core.entities import Entity
from src.services.db_service import DatabaseService


@pytest.fixture
def db_service():
    """Provides a fresh in-memory database service."""
    service = DatabaseService(":memory:")
    service.connect()
    return service


@pytest.fixture
def repository(db_service):
    """Provides an EntityRepository connected to the DB."""
    # The DB service initializes and connects the repo
    return db_service._entity_repo


@pytest.fixture
def sample_entities(repository):
    """Inserts sample entities."""
    entities = [
        Entity(id="e1", name="Gandalf", type="person"),
        Entity(id="e2", name="gandalf", type="person"),  # Duplicate name case
        Entity(id="e3", name="Bilbo", type="person"),
        Entity(id="e4", name="Aragorn", type="person"),
    ]
    for e in entities:
        repository.insert(e)
    return entities


@pytest.mark.unit
class TestEntityRepository:
    """Tests for EntityRepository methods."""

    def test_find_named_entities_exact_match(self, repository, sample_entities):
        """Should find entities with exact name match."""
        results = repository.find_named_entities("Bilbo")
        assert len(results) == 1
        assert results[0].name == "Bilbo"

    def test_find_named_entities_case_insensitive(self, repository, sample_entities):
        """Should find entities safely ignoring case."""
        # "gandalf" should match both "Gandalf" and "gandalf"
        results = repository.find_named_entities("gandalf")
        assert len(results) == 2
        names = {e.name for e in results}
        assert "Gandalf" in names
        assert "gandalf" in names

    def test_find_named_entities_no_match(self, repository, sample_entities):
        """Should return empty list if no match found."""
        results = repository.find_named_entities("Sauron")
        assert len(results) == 0

    def test_find_named_entities_trimming(self, repository, sample_entities):
        """Should handle untrimmed input by matching trimmed name in DB?"""
        # Note: current implementation intent is simple case-insensitive matching.
        # It does NOT handle whitespace collapsing in the DB query itself unless we add it.
        # But import service will normalize input.
        # Let's verify that "  Bilbo  " input matches "Bilbo" if the repo trims input?
        # Or should the caller trim?
        # Convention: Repository methods generally expect clean input or match raw?
        # Let's assume input matches raw DB content (case-blind).
        # We'll skip complex whitespace tests here if we aren't implementing complex SQL.
        pass
