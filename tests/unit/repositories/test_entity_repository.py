"""Unit tests for EntityRepository."""

import pytest

from src.core.entities import Entity


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
@pytest.mark.smoke
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
        """Untrimmed input does not match because the repository uses exact lookup."""
        results = repository.find_named_entities("  Bilbo  ")

        assert results == []
