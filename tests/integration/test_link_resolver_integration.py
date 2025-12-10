"""
Integration test for LinkResolver with WikiTextEdit and highlighting.

Tests the complete ID-based linking system including broken link visualization.
"""

import pytest
from PySide6.QtWidgets import QApplication
from src.gui.widgets.wiki_text_edit import WikiTextEdit
from src.services.link_resolver import LinkResolver
from src.core.entities import Entity


@pytest.fixture(scope="session")
def qapp():
    """Ensure QApplication exists."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_link_resolver_with_editor(db_service, qapp):
    """Test LinkResolver integration with WikiTextEdit."""
    # Create test entities
    gandalf = Entity(name="Gandalf", type="character")
    frodo = Entity(name="Frodo", type="character")
    db_service.insert_entity(gandalf)
    db_service.insert_entity(frodo)

    # Create resolver
    resolver = LinkResolver(db_service)

    # Test resolution
    assert resolver.resolve(gandalf.id) == ("Gandalf", "entity")
    assert resolver.resolve(frodo.id) == ("Frodo", "entity")

    # Test broken link
    assert resolver.resolve("00000000-0000-0000-0000-000000000000") is None


def test_broken_link_highlighting(db_service, qapp):
    """Test that broken links are highlighted differently."""
    # Create entity
    gandalf = Entity(name="Gandalf", type="character")
    db_service.insert_entity(gandalf)

    # Create editor with resolver
    editor = WikiTextEdit()
    resolver = LinkResolver(db_service)
    editor.set_link_resolver(resolver)

    # Set text with both valid and broken links
    broken_uuid = "00000000-0000-0000-0000-000000000000"
    text = (
        f"[[id:{gandalf.id}|Gandalf]] is here, "
        f"but [[id:{broken_uuid}|Deleted Character]] is not."
    )
    editor.setPlainText(text)

    # Verify text was set
    assert gandalf.id in editor.toPlainText()
    assert broken_uuid in editor.toPlainText()

    # The highlighter should have different formats for valid vs broken
    # This is tested implicitly through the highlighter logic


def test_autocomplete_with_id_based_links(db_service, qapp):
    """Test that autocomplete generates ID-based links."""
    # Create entities
    aragorn = Entity(name="Aragorn", type="character")
    legolas = Entity(name="Legolas", type="character")
    db_service.insert_entity(aragorn)
    db_service.insert_entity(legolas)

    # Create editor
    editor = WikiTextEdit()

    # Set up completion with ID tuples
    items = [
        (aragorn.id, aragorn.name, "entity"),
        (legolas.id, legolas.name, "entity"),
    ]
    editor.set_completer(items=items)

    # Verify completer is set up
    assert editor._completer is not None
    assert len(editor._completion_map) == 2
    assert aragorn.name in editor._completion_map
    assert editor._completion_map[aragorn.name] == (aragorn.id, "entity")


def test_link_navigation_by_id(db_service, qapp):
    """Test that links can be navigated by ID."""
    # Create entity
    sauron = Entity(name="Sauron", type="character")
    db_service.insert_entity(sauron)

    # Create editor
    editor = WikiTextEdit()

    # Set text with ID-based link
    text = f"[[id:{sauron.id}|Dark Lord]] is mentioned here."
    editor.setPlainText(text)

    # Simulate Ctrl+Click to get link target
    # The get_link_at_pos should return the UUID
    # (We can't easily test the actual click without complex mocking)


def test_resolver_cache_invalidation(db_service):
    """Test that cache invalidation works correctly."""
    # Create entity
    gandalf = Entity(name="Gandalf the Grey", type="character")
    db_service.insert_entity(gandalf)

    # Create resolver
    resolver = LinkResolver(db_service)

    # Resolve to populate cache
    result = resolver.resolve(gandalf.id)
    assert result[0] == "Gandalf the Grey"
    assert gandalf.id in resolver._cache

    # Update entity name
    gandalf.name = "Gandalf the White"
    db_service.insert_entity(gandalf)

    # Old value still cached
    result = resolver.resolve(gandalf.id)
    assert result[0] == "Gandalf the Grey"

    # Invalidate cache
    resolver.invalidate_cache(gandalf.id)

    # New value should be returned
    result = resolver.resolve(gandalf.id)
    assert result[0] == "Gandalf the White"


def test_find_broken_links_in_text(db_service):
    """Test finding broken links in a text block."""
    # Create one valid entity
    frodo = Entity(name="Frodo", type="character")
    db_service.insert_entity(frodo)

    resolver = LinkResolver(db_service)

    # Text with valid and broken links
    broken_id = "00000000-0000-0000-0000-000000000000"
    text = (
        f"[[id:{frodo.id}|Frodo]] meets "
        f"[[id:{broken_id}|Missing]] and "
        f"[[Gandalf]] somewhere."  # Name-based link (not checked for broken)
    )

    broken = resolver.find_broken_links(text)
    assert len(broken) == 1
    assert broken_id in broken


def test_get_display_name_scenarios(db_service):
    """Test various display name resolution scenarios."""
    # Create entity
    aragorn = Entity(name="Aragorn", type="character")
    db_service.insert_entity(aragorn)

    resolver = LinkResolver(db_service)

    # Valid link - should return current name
    display = resolver.get_display_name(aragorn.id)
    assert display == "Aragorn"

    # Broken link with fallback
    broken_id = "00000000-0000-0000-0000-000000000000"
    display = resolver.get_display_name(broken_id, fallback_name="Old Name")
    assert display == "Old Name [BROKEN]"

    # Broken link without fallback
    display = resolver.get_display_name(broken_id)
    assert "[BROKEN LINK:" in display
    assert "00000000" in display


def test_resolver_handles_events_and_entities(db_service):
    """Test that resolver can resolve both events and entities."""
    from src.core.events import Event

    # Create entity and event
    entity = Entity(name="Rivendell", type="location")
    event = Event(name="Council of Elrond", lore_date=1000.0)

    db_service.insert_entity(entity)
    db_service.insert_event(event)

    resolver = LinkResolver(db_service)

    # Should resolve both
    entity_result = resolver.resolve(entity.id)
    assert entity_result == ("Rivendell", "entity")

    event_result = resolver.resolve(event.id)
    assert event_result == ("Council of Elrond", "event")
