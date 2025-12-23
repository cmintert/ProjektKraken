"""
Unit tests for LinkResolver service.

Tests ID-to-name resolution and broken link detection.
"""

from src.core.entities import Entity
from src.core.events import Event
from src.services.link_resolver import LinkResolver


def test_resolve_entity(db_service):
    """Test resolving an entity ID to its name."""
    # Create an entity
    entity = Entity(name="Gandalf the Grey", type="character")
    db_service.insert_entity(entity)

    # Resolve it
    resolver = LinkResolver(db_service)
    result = resolver.resolve(entity.id)

    assert result is not None
    assert result[0] == "Gandalf the Grey"
    assert result[1] == "entity"


def test_resolve_event(db_service):
    """Test resolving an event ID to its name."""
    # Create an event
    event = Event(name="Council of Elrond", lore_date=1000.0)
    db_service.insert_event(event)

    # Resolve it
    resolver = LinkResolver(db_service)
    result = resolver.resolve(event.id)

    assert result is not None
    assert result[0] == "Council of Elrond"
    assert result[1] == "event"


def test_resolve_broken_link(db_service):
    """Test that resolving a non-existent ID returns None."""
    resolver = LinkResolver(db_service)
    result = resolver.resolve("non-existent-id-12345")

    assert result is None


def test_cache_usage(db_service):
    """Test that the cache is used for repeated resolutions."""
    entity = Entity(name="Frodo", type="character")
    db_service.insert_entity(entity)

    resolver = LinkResolver(db_service)

    # First resolution - should hit DB
    result1 = resolver.resolve(entity.id)
    assert result1 == ("Frodo", "entity")

    # Second resolution - should use cache
    # (We can't directly verify cache usage without mocking,
    # but at least verify it works)
    result2 = resolver.resolve(entity.id)
    assert result2 == ("Frodo", "entity")


def test_invalidate_cache_specific(db_service):
    """Test invalidating a specific cache entry."""
    entity = Entity(name="Aragorn", type="character")
    db_service.insert_entity(entity)

    resolver = LinkResolver(db_service)

    # Populate cache
    resolver.resolve(entity.id)
    assert entity.id in resolver._cache

    # Invalidate specific entry
    resolver.invalidate_cache(entity.id)
    assert entity.id not in resolver._cache


def test_invalidate_cache_all(db_service):
    """Test invalidating the entire cache."""
    entity1 = Entity(name="Legolas", type="character")
    entity2 = Entity(name="Gimli", type="character")
    db_service.insert_entity(entity1)
    db_service.insert_entity(entity2)

    resolver = LinkResolver(db_service)

    # Populate cache
    resolver.resolve(entity1.id)
    resolver.resolve(entity2.id)
    assert len(resolver._cache) == 2

    # Invalidate all
    resolver.invalidate_cache()
    assert len(resolver._cache) == 0


def test_get_display_name_valid(db_service):
    """Test getting display name for valid link."""
    entity = Entity(name="Boromir", type="character")
    db_service.insert_entity(entity)

    resolver = LinkResolver(db_service)
    display_name = resolver.get_display_name(entity.id)

    assert display_name == "Boromir"


def test_get_display_name_broken_with_fallback(db_service):
    """Test getting display name for broken link with fallback."""
    resolver = LinkResolver(db_service)
    display_name = resolver.get_display_name(
        "non-existent-id-12345", fallback_name="Old Name"
    )

    assert display_name == "Old Name [BROKEN]"


def test_get_display_name_broken_without_fallback(db_service):
    """Test getting display name for broken link without fallback."""
    resolver = LinkResolver(db_service)
    display_name = resolver.get_display_name("550e8400-e29b-41d4-a716-446655440000")

    assert "[BROKEN LINK:" in display_name
    assert "550e8400" in display_name


def test_find_broken_links_none(db_service):
    """Test finding broken links when all links are valid."""
    entity = Entity(name="Saruman", type="character")
    db_service.insert_entity(entity)

    text = f"See [[id:{entity.id}|Saruman]] for details."

    resolver = LinkResolver(db_service)
    broken = resolver.find_broken_links(text)

    assert len(broken) == 0


def test_find_broken_links_some(db_service):
    """Test finding broken links when some links are broken."""
    entity = Entity(name="Galadriel", type="character")
    db_service.insert_entity(entity)

    # Use a valid UUID format for broken link
    broken_uuid = "00000000-0000-0000-0000-000000000000"
    text = (
        f"[[id:{entity.id}|Galadriel]] and [[id:{broken_uuid}|Deleted Entity]] appear."
    )

    resolver = LinkResolver(db_service)
    broken = resolver.find_broken_links(text)

    assert len(broken) == 1
    assert broken_uuid in broken


def test_name_change_propagation(db_service):
    """Test that name changes are reflected after cache invalidation."""
    entity = Entity(name="Gandalf the Grey", type="character")
    db_service.insert_entity(entity)

    resolver = LinkResolver(db_service)

    # Initial resolution
    result1 = resolver.resolve(entity.id)
    assert result1[0] == "Gandalf the Grey"

    # Update name in DB
    entity.name = "Gandalf the White"
    db_service.insert_entity(entity)  # Upsert

    # Old name still in cache
    result2 = resolver.resolve(entity.id)
    assert result2[0] == "Gandalf the Grey"  # Still cached

    # Invalidate cache
    resolver.invalidate_cache(entity.id)

    # New name should now be resolved
    result3 = resolver.resolve(entity.id)
    assert result3[0] == "Gandalf the White"
