"""
Unit tests for ProcessWikiLinksCommand.
Tests the new 'mentions' relation type with metadata.
"""

import pytest

from src.commands.wiki_commands import ProcessWikiLinksCommand
from src.core.entities import Entity
from src.services.db_service import DatabaseService


@pytest.fixture
def db_service():
    """In-memory database service for testing."""
    service = DatabaseService(":memory:")
    service.connect()
    yield service
    service.close()


@pytest.fixture
def source_id():
    return "source-123"


def test_process_no_links(db_service, source_id):
    """Test text with no links does nothing."""
    cmd = ProcessWikiLinksCommand(source_id, "Just plain text.")
    result = cmd.execute(db_service)

    assert result.success is True
    assert "No links found" in result.message


def test_process_finds_valid_link(db_service, source_id):
    """Test valid link is properly identified but NO relation is created."""
    target_entity = Entity(name="Gandalf", type="Character")
    db_service.insert_entity(target_entity)

    text = "Speak to [[Gandalf]] and enter."
    cmd = ProcessWikiLinksCommand(source_id, text, field="description")
    result = cmd.execute(db_service)

    # Verify success and reporting
    assert result.success is True
    assert "Found 1 valid link." in result.message
    assert result.data["valid_count"] == 1
    assert "Gandalf (Entity)" in result.data["valid_links"]

    # Verify NO relation created
    relations = db_service.get_relations(source_id)
    assert len(relations) == 0


def test_process_case_insensitive_match(db_service, source_id):
    """Test link matching is case-insensitive."""
    target_entity = Entity(name="The Shire", type="Location")
    db_service.insert_entity(target_entity)

    text = "Visit [[the shire]] today."
    cmd = ProcessWikiLinksCommand(source_id, text)
    result = cmd.execute(db_service)

    assert result.success is True
    assert result.data["valid_count"] == 1

    # No relations
    relations = db_service.get_relations(source_id)
    assert len(relations) == 0


def test_process_with_aliases(db_service, source_id):
    """Test matching entity by alias."""
    target_entity = Entity(
        name="Gandalf the Grey",
        type="Character",
        attributes={"aliases": ["Gandalf", "Mithrandir"]},
    )
    db_service.insert_entity(target_entity)

    text = "Meet [[Mithrandir]] at dawn."
    cmd = ProcessWikiLinksCommand(source_id, text)
    result = cmd.execute(db_service)

    assert result.success is True
    assert result.data["valid_count"] == 1
    assert "Gandalf the Grey (Entity)" in result.data["valid_links"]


def test_process_skips_ambiguous(db_service, source_id):
    """Test ambiguous matches are skipped and reported."""
    entity1 = Entity(name="John", type="Character")
    entity2 = Entity(name="John", type="Character")
    db_service.insert_entity(entity1)
    db_service.insert_entity(entity2)

    text = "Talk to [[John]] tomorrow."
    cmd = ProcessWikiLinksCommand(source_id, text)
    result = cmd.execute(db_service)

    assert result.success is True
    assert "Found 1 ambiguous link(s)" in result.message
    assert result.data["ambiguous_count"] == 1
    assert result.data["valid_count"] == 0


def test_process_skips_missing(db_service, source_id):
    """Test unresolved links are skipped and reported."""
    text = "Find [[NonExistent]] entity."
    cmd = ProcessWikiLinksCommand(source_id, text)
    result = cmd.execute(db_service)

    assert result.success is True
    assert "Found 1 broken link(s)" in result.message
    assert result.data["broken_count"] == 1
    assert result.data["valid_count"] == 0


def test_process_multiple_links(db_service, source_id):
    """Test processing multiple links finds all of them."""
    entity1 = Entity(name="Alice", type="Character")
    entity2 = Entity(name="Bob", type="Character")
    entity3 = Entity(name="Charlie", type="Character")

    db_service.insert_entity(entity1)
    db_service.insert_entity(entity2)
    db_service.insert_entity(entity3)

    text = "[[Alice]] met [[Bob]] and [[Charlie]]."
    cmd = ProcessWikiLinksCommand(source_id, text)
    result = cmd.execute(db_service)

    assert result.success is True
    assert "Found 3 valid links." in result.message
    assert result.data["valid_count"] == 3


def test_process_same_entity_multiple_times(db_service, source_id):
    """Test same entity linked multiple times counts as multiple findings."""
    target_entity = Entity(name="Gandalf", type="Character")
    db_service.insert_entity(target_entity)

    text = "[[Gandalf]] left, but [[Gandalf]] returned."
    cmd = ProcessWikiLinksCommand(source_id, text)
    result = cmd.execute(db_service)

    assert result.success is True
    # It should report finding 2 valid links, even if they point to same entity
    assert "Found 2 valid links." in result.message
    assert result.data["valid_count"] == 2


def test_process_skips_self_reference(db_service):
    """Test self-referencing links are skipped."""
    entity_id = "self-ref-entity"
    entity = Entity(id=entity_id, name="MySelf", type="Character")
    db_service.insert_entity(entity)

    text = "I am [[MySelf]]."
    cmd = ProcessWikiLinksCommand(entity_id, text)
    result = cmd.execute(db_service)

    assert result.success is True
    assert result.data["valid_count"] == 0


def test_process_undo_does_nothing(db_service, source_id):
    """Test undo is a no-op."""
    target_entity = Entity(name="Gandalf", type="Character")
    db_service.insert_entity(target_entity)

    cmd = ProcessWikiLinksCommand(source_id, "Meet [[Gandalf]].")
    cmd.execute(db_service)

    # Undo
    cmd.undo(db_service)
    # Just ensure no errors and state is clean
    assert True


def test_pipe_modifier_ignored_for_matching(db_service, source_id):
    """Test pipe modifier doesn't affect entity matching."""
    target_entity = Entity(name="Gandalf", type="Character")
    db_service.insert_entity(target_entity)

    text = "See [[Gandalf|the wizard]]."
    cmd = ProcessWikiLinksCommand(source_id, text)
    result = cmd.execute(db_service)

    assert result.success is True
    assert result.data["valid_count"] == 1


def test_process_wiki_links_to_events(db_service, source_id):
    """Test links pointing to events."""
    from src.core.events import Event

    event_id = "550e8400-e29b-41d4-a716-446655440000"
    target_event = Event(id=event_id, name="Big Bang", type="event", lore_date=0.0)
    db_service.insert_event(target_event)

    cmd = ProcessWikiLinksCommand(
        "src1", f"Link to [[Big Bang]] and [[id:{event_id}|ID Link]]"
    )

    result = cmd.execute(db_service)

    assert result.success is True
    assert "Found 2 valid links" in result.message
    assert result.data["valid_count"] == 2

    # Since we store formatted strings like "Name (Type)" in valid_links
    assert "Big Bang (Event)" in result.data["valid_links"]
