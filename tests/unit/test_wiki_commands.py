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


def test_process_creates_mention_relation(db_service, source_id):
    """Test valid link creates a 'mentions' relation with metadata."""
    # Create target entity
    target_entity = Entity(name="Gandalf", type="Character")
    db_service.insert_entity(target_entity)

    text = "Speak to [[Gandalf]] and enter."
    cmd = ProcessWikiLinksCommand(source_id, text, field="description")
    result = cmd.execute(db_service)

    # Verify success
    assert result.success is True
    assert "Created 1 new mention." in result.message

    # Verify relation created
    relations = db_service.get_relations(source_id)
    assert len(relations) == 1

    rel = relations[0]
    assert rel["source_id"] == source_id
    assert rel["target_id"] == target_entity.id
    assert rel["rel_type"] == "mentions"

    # Verify attributes
    attrs = rel["attributes"]
    assert attrs["field"] == "description"
    assert "Gandalf" in attrs["snippet"]
    assert attrs["start_offset"] == 9
    assert attrs["end_offset"] == 20
    assert attrs["created_by"] == "ProcessWikiLinksCommand"
    assert "created_at" in attrs


def test_process_case_insensitive_match(db_service, source_id):
    """Test link matching is case-insensitive."""
    target_entity = Entity(name="The Shire", type="Location")
    db_service.insert_entity(target_entity)

    text = "Visit [[the shire]] today."
    cmd = ProcessWikiLinksCommand(source_id, text)
    result = cmd.execute(db_service)

    assert result.success is True
    relations = db_service.get_relations(source_id)
    assert len(relations) == 1
    assert relations[0]["target_id"] == target_entity.id


def test_process_with_aliases(db_service, source_id):
    """Test matching entity by alias."""
    # Entity with aliases in attributes
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
    relations = db_service.get_relations(source_id)
    assert len(relations) == 1
    assert relations[0]["target_id"] == target_entity.id


def test_process_skips_ambiguous(db_service, source_id):
    """Test ambiguous matches are skipped and reported."""
    # Two entities with same name
    entity1 = Entity(name="John", type="Character")
    entity2 = Entity(name="John", type="Character")
    db_service.insert_entity(entity1)
    db_service.insert_entity(entity2)

    text = "Talk to [[John]] tomorrow."
    cmd = ProcessWikiLinksCommand(source_id, text)
    result = cmd.execute(db_service)

    assert result.success is True
    assert "Skipped 1 ambiguous" in result.message

    # No relations should be created
    relations = db_service.get_relations(source_id)
    assert len(relations) == 0


def test_process_skips_missing(db_service, source_id):
    """Test unresolved links are skipped and reported."""
    text = "Find [[NonExistent]] entity."
    cmd = ProcessWikiLinksCommand(source_id, text)
    result = cmd.execute(db_service)

    assert result.success is True
    assert "Skipped 1 unresolved" in result.message

    relations = db_service.get_relations(source_id)
    assert len(relations) == 0


def test_process_multiple_links(db_service, source_id):
    """Test processing multiple links in one text."""
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
    assert "Created 3 new mentions." in result.message

    relations = db_service.get_relations(source_id)
    assert len(relations) == 3


def test_process_deduplication_by_offset(db_service, source_id):
    """Test deduplication by (target_id, start_offset)."""
    target_entity = Entity(name="Gandalf", type="Character")
    db_service.insert_entity(target_entity)

    # First processing
    text = "Meet [[Gandalf]] today."
    cmd1 = ProcessWikiLinksCommand(source_id, text)
    result1 = cmd1.execute(db_service)
    assert result1.success is True
    assert "Created 1 new mention." in result1.message

    # Second processing of same text - should detect duplicate
    cmd2 = ProcessWikiLinksCommand(source_id, text)
    result2 = cmd2.execute(db_service)
    assert result2.success is True
    assert "Created 0 new mentions." in result2.message

    # Still only one relation
    relations = db_service.get_relations(source_id)
    assert len(relations) == 1


def test_process_same_entity_different_offsets(db_service, source_id):
    """Test same entity mentioned at different positions."""
    target_entity = Entity(name="Gandalf", type="Character")
    db_service.insert_entity(target_entity)

    text = "[[Gandalf]] left, but [[Gandalf]] returned."
    cmd = ProcessWikiLinksCommand(source_id, text)
    result = cmd.execute(db_service)

    assert result.success is True
    assert "Created 2 new mentions." in result.message

    relations = db_service.get_relations(source_id)
    assert len(relations) == 2

    # Verify different offsets
    offsets = [rel["attributes"]["start_offset"] for rel in relations]
    assert 0 in offsets
    assert 22 in offsets


def test_process_skips_self_reference(db_service):
    """Test self-referencing links are skipped."""
    entity_id = "self-ref-entity"
    entity = Entity(id=entity_id, name="MySelf", type="Character")
    db_service.insert_entity(entity)

    text = "I am [[MySelf]]."
    cmd = ProcessWikiLinksCommand(entity_id, text)
    result = cmd.execute(db_service)

    assert result.success is True

    # No relations should be created for self-reference
    relations = db_service.get_relations(entity_id)
    assert len(relations) == 0


def test_process_undo(db_service, source_id):
    """Test undo deletes created relations."""
    target_entity = Entity(name="Gandalf", type="Character")
    db_service.insert_entity(target_entity)

    cmd = ProcessWikiLinksCommand(source_id, "Meet [[Gandalf]].")
    result = cmd.execute(db_service)

    assert result.success is True
    assert len(cmd._created_relations) == 1

    # Verify relation exists
    relations_before = db_service.get_relations(source_id)
    assert len(relations_before) == 1

    # Undo
    cmd.undo(db_service)

    # Verify relation deleted
    relations_after = db_service.get_relations(source_id)
    assert len(relations_after) == 0
    assert len(cmd._created_relations) == 0


def test_snippet_generation(db_service, source_id):
    """Test snippet extraction includes context."""
    target_entity = Entity(name="X", type="Character")
    db_service.insert_entity(target_entity)

    text = "This is a longer text with [[X]] in the middle for testing."
    cmd = ProcessWikiLinksCommand(source_id, text)
    result = cmd.execute(db_service)

    assert result.success is True

    relations = db_service.get_relations(source_id)
    snippet = relations[0]["attributes"]["snippet"]

    # Snippet should contain the link and some context
    assert "[[X]]" in snippet
    assert len(snippet) <= 50  # Should be roughly 40 chars + ellipsis


def test_snippet_with_ellipsis(db_service, source_id):
    """Test snippet adds ellipsis when text is truncated."""
    target_entity = Entity(name="Target", type="Character")
    db_service.insert_entity(target_entity)

    text = "A" * 100 + "[[Target]]" + "B" * 100
    cmd = ProcessWikiLinksCommand(source_id, text)
    result = cmd.execute(db_service)

    assert result.success is True

    relations = db_service.get_relations(source_id)
    snippet = relations[0]["attributes"]["snippet"]

    # Should have ellipsis on both sides
    assert snippet.startswith("...")
    assert snippet.endswith("...")


def test_field_parameter(db_service, source_id):
    """Test field parameter is stored in relation attributes."""
    target_entity = Entity(name="Test", type="Character")
    db_service.insert_entity(target_entity)

    text = "[[Test]] content."
    cmd = ProcessWikiLinksCommand(source_id, text, field="notes")
    result = cmd.execute(db_service)

    assert result.success is True

    relations = db_service.get_relations(source_id)
    assert relations[0]["attributes"]["field"] == "notes"


def test_pipe_modifier_ignored_for_matching(db_service, source_id):
    """Test pipe modifier doesn't affect entity matching."""
    target_entity = Entity(name="Gandalf", type="Character")
    db_service.insert_entity(target_entity)

    # Link with label should still match by name
    text = "See [[Gandalf|the wizard]]."
    cmd = ProcessWikiLinksCommand(source_id, text)
    result = cmd.execute(db_service)

    assert result.success is True

    relations = db_service.get_relations(source_id)
    assert len(relations) == 1
    assert relations[0]["target_id"] == target_entity.id
