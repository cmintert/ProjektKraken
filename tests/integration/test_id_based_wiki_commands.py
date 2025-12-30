"""
Integration tests for ID-based wiki links with commands.

Tests the complete flow of creating ID-based links and processing them.
NOTE: ProcessWikiLinksCommand is now read-only and does NOT create relations.
These tests verify detection logic and ensure NO relations are created.
"""

from src.commands.wiki_commands import ProcessWikiLinksCommand
from src.core.entities import Entity
from src.core.events import Event
from src.services.text_parser import WikiLinkParser


def test_id_based_link_processing(db_service):
    """Test that ID-based links are processed correctly (found but not created as relations)."""
    # Create entities
    gandalf = Entity(name="Gandalf", type="character")
    frodo = Entity(name="Frodo", type="character")
    db_service.insert_entity(gandalf)
    db_service.insert_entity(frodo)

    # Create event with ID-based links
    event = Event(
        name="Test Event",
        lore_date=1000.0,
        description=(f"[[id:{gandalf.id}|Gandalf]] met [[id:{frodo.id}|Frodo]]."),
    )
    db_service.insert_event(event)

    # Process wiki links
    cmd = ProcessWikiLinksCommand(event.id, event.description)
    result = cmd.execute(db_service)

    assert result.success is True
    assert "Found 2 valid links" in result.message

    # Verify NO relations were created (Command is read-only)
    relations = db_service.get_relations(event.id)
    assert len(relations) == 0


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
    assert "Found 2 valid links" in result.message

    # Verify NO relations created
    relations = db_service.get_relations(event.id)
    assert len(relations) == 0


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
    assert "Found 0 valid links" in result.message
    assert "broken link(s)" in result.message

    # Verify no relations were created
    relations = db_service.get_relations(event.id)
    assert len(relations) == 0


def test_id_link_with_display_name(db_service):
    """Test that ID-based links are correctly identified."""
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

    # Check result data
    assert result.data["valid_count"] == 1
    # Check string representation in valid_links
    assert any("Sauron the Great" in link for link in result.data["valid_links"])

    # Verify NO relations created
    relations = db_service.get_relations(event.id)
    assert len(relations) == 0


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

    # Should succeed but find no valid external links
    assert result.success is True
    # Self-reference is skipped, so 0 valid links
    assert "Found 0 valid links" in result.message

    # Verify no relations
    relations = db_service.get_relations(entity.id)
    assert len(relations) == 0


def test_id_link_undo(db_service):
    """Test that undo is a no-op for read-only command."""
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

    # Undo
    cmd.undo(db_service)

    # Verify still 0 relations (nothing changed)
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
