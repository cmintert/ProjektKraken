"""
Integration tests for ID-based wiki links with commands.

Tests the complete flow of creating ID-based links and processing them.
"""

import pytest
from src.services.db_service import DatabaseService
from src.core.entities import Entity
from src.core.events import Event
from src.commands.wiki_commands import ProcessWikiLinksCommand
from src.services.text_parser import WikiLinkParser


def test_id_based_link_processing(db_service):
    """Test that ID-based links are processed correctly."""
    # Create entities
    gandalf = Entity(name="Gandalf", type="character")
    frodo = Entity(name="Frodo", type="character")
    db_service.insert_entity(gandalf)
    db_service.insert_entity(frodo)

    # Create event with ID-based links
    event = Event(
        name="Test Event",
        lore_date=1000.0,
        description=f"[[id:{gandalf.id}|Gandalf]] met [[id:{frodo.id}|Frodo]].",
    )
    db_service.insert_event(event)

    # Process wiki links
    cmd = ProcessWikiLinksCommand(event.id, event.description)
    result = cmd.execute(db_service)

    assert result.success is True
    assert "2 new mentions" in result.message

    # Verify relations were created
    relations = db_service.get_relations(event.id)
    assert len(relations) == 2

    # Check that relations have correct targets
    target_ids = {rel["target_id"] for rel in relations}
    assert gandalf.id in target_ids
    assert frodo.id in target_ids

    # Verify is_id_based flag is set
    for rel in relations:
        attrs = rel.get("attributes", {})
        assert attrs.get("is_id_based") is True


def test_mixed_links_processing(db_service):
    """Test processing a mix of ID-based and name-based links."""
    # Create entities
    aragorn = Entity(name="Aragorn", type="character")
    legolas = Entity(name="Legolas", type="character")
    db_service.insert_entity(aragorn)
    db_service.insert_entity(legolas)

    # Create event with mixed links
    event = Event(
        name="Test Event",
        lore_date=1000.0,
        description=f"[[id:{aragorn.id}|Aragorn]] and [[Legolas]] traveled together.",
    )
    db_service.insert_event(event)

    # Process wiki links
    cmd = ProcessWikiLinksCommand(event.id, event.description)
    result = cmd.execute(db_service)

    assert result.success is True
    assert "2 new mentions" in result.message

    # Verify both relations were created
    relations = db_service.get_relations(event.id)
    assert len(relations) == 2

    # Check is_id_based flag
    for rel in relations:
        attrs = rel.get("attributes", {})
        if rel["target_id"] == aragorn.id:
            assert attrs.get("is_id_based") is True
        elif rel["target_id"] == legolas.id:
            assert attrs.get("is_id_based") is False


def test_broken_id_link_skipped(db_service):
    """Test that broken ID-based links are skipped with warning."""
    fake_uuid = "00000000-0000-0000-0000-000000000000"

    event = Event(
        name="Test Event",
        lore_date=1000.0,
        description=f"[[id:{fake_uuid}|Deleted Character]] was here.",
    )
    db_service.insert_event(event)

    # Process wiki links
    cmd = ProcessWikiLinksCommand(event.id, event.description)
    result = cmd.execute(db_service)

    assert result.success is True
    assert "0 new mentions" in result.message
    assert "1 unresolved" in result.message

    # Verify no relations were created
    relations = db_service.get_relations(event.id)
    assert len(relations) == 0


def test_id_link_with_display_name(db_service):
    """Test that ID-based links preserve display names in relations."""
    sauron = Entity(name="Sauron the Great", type="character")
    db_service.insert_entity(sauron)

    event = Event(
        name="Test Event",
        lore_date=1000.0,
        description=f"[[id:{sauron.id}|Dark Lord]] rose to power.",
    )
    db_service.insert_event(event)

    # Process wiki links
    cmd = ProcessWikiLinksCommand(event.id, event.description)
    result = cmd.execute(db_service)

    assert result.success is True

    # Verify relation was created
    relations = db_service.get_relations(event.id)
    assert len(relations) == 1

    # Check snippet contains display name
    attrs = relations[0].get("attributes", {})
    snippet = attrs.get("snippet", "")
    assert "Dark Lord" in snippet  # Display name should be in snippet


def test_id_link_self_reference_skipped(db_service):
    """Test that self-referencing ID-based links are skipped."""
    entity = Entity(name="Test Entity", type="character")
    db_service.insert_entity(entity)

    # Update entity description with self-reference
    entity.description = f"I am [[id:{entity.id}|myself]]."
    db_service.insert_entity(entity)  # Upsert

    # Process wiki links
    cmd = ProcessWikiLinksCommand(entity.id, entity.description)
    result = cmd.execute(db_service)

    # Should succeed but create no relations
    assert result.success is True
    assert "0 new mentions" in result.message

    # Verify no relations
    relations = db_service.get_relations(entity.id)
    assert len(relations) == 0


def test_id_link_undo(db_service):
    """Test that ID-based link processing can be undone."""
    gandalf = Entity(name="Gandalf", type="character")
    db_service.insert_entity(gandalf)

    event = Event(
        name="Test Event",
        lore_date=1000.0,
        description=f"[[id:{gandalf.id}|Gandalf]] appeared.",
    )
    db_service.insert_event(event)

    # Process wiki links
    cmd = ProcessWikiLinksCommand(event.id, event.description)
    result = cmd.execute(db_service)
    assert result.success is True

    # Verify relation created
    relations = db_service.get_relations(event.id)
    assert len(relations) == 1

    # Undo
    cmd.undo(db_service)

    # Verify relation removed
    relations = db_service.get_relations(event.id)
    assert len(relations) == 0


def test_format_helpers():
    """Test the WikiLinkParser format helper methods."""
    # Test ID-based link formatting
    id_link = WikiLinkParser.format_id_link(
        "550e8400-e29b-41d4-a716-446655440000", "Gandalf"
    )
    assert id_link == "[[id:550e8400-e29b-41d4-a716-446655440000|Gandalf]]"

    # Parse it back
    links = WikiLinkParser.extract_links(id_link)
    assert len(links) == 1
    assert links[0].is_id_based is True
    assert links[0].target_id == "550e8400-e29b-41d4-a716-446655440000"
    assert links[0].modifier == "Gandalf"

    # Test name-based link formatting
    name_link = WikiLinkParser.format_name_link("Frodo", "Ring Bearer")
    assert name_link == "[[Frodo|Ring Bearer]]"

    # Parse it back
    links = WikiLinkParser.extract_links(name_link)
    assert len(links) == 1
    assert links[0].is_id_based is False
    assert links[0].name == "Frodo"
    assert links[0].modifier == "Ring Bearer"
