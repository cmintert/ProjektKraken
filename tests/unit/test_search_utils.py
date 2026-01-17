"""
Tests for the SearchUtils class.
"""

from dataclasses import dataclass
from typing import Any, Dict, List

from src.core.search_utils import SearchUtils


@dataclass
class MockEntity:
    """Mock entity for testing."""

    name: str
    type: str = ""
    description: str = ""
    tags: List[str] = None
    attributes: Dict[str, Any] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.attributes is None:
            self.attributes = {}


def test_matches_search_empty_search_term():
    """Test matches_search returns True for empty search term."""
    obj = MockEntity(name="Test Entity")

    assert SearchUtils.matches_search(obj, "") is True
    assert SearchUtils.matches_search(obj, "   ") is True


def test_matches_search_by_name():
    """Test matches_search finds objects by name."""
    obj = MockEntity(name="Dragon Lord")

    assert SearchUtils.matches_search(obj, "Dragon") is True
    assert SearchUtils.matches_search(obj, "Lord") is True
    assert SearchUtils.matches_search(obj, "dragon") is True  # Case insensitive
    assert SearchUtils.matches_search(obj, "DRAGON") is True


def test_matches_search_by_type():
    """Test matches_search finds objects by type."""
    obj = MockEntity(name="Entity", type="Character")

    assert SearchUtils.matches_search(obj, "character") is True
    assert SearchUtils.matches_search(obj, "Character") is True
    assert SearchUtils.matches_search(obj, "char") is True


def test_matches_search_by_description():
    """Test matches_search finds objects by description."""
    obj = MockEntity(
        name="Entity", description="A powerful wizard who controls fire magic"
    )

    assert SearchUtils.matches_search(obj, "wizard") is True
    assert SearchUtils.matches_search(obj, "fire") is True
    assert SearchUtils.matches_search(obj, "powerful") is True


def test_matches_search_by_tags():
    """Test matches_search finds objects by tags."""
    obj = MockEntity(name="Entity", tags=["hero", "warrior", "quest-giver"])

    assert SearchUtils.matches_search(obj, "hero") is True
    assert SearchUtils.matches_search(obj, "warrior") is True
    assert SearchUtils.matches_search(obj, "quest") is True


def test_matches_search_by_attributes():
    """Test matches_search finds objects by attribute values."""
    obj = MockEntity(
        name="Entity",
        attributes={"homeland": "Rivendell", "weapon": "Longbow", "skill": "Archery"},
    )

    assert SearchUtils.matches_search(obj, "Rivendell") is True
    assert SearchUtils.matches_search(obj, "longbow") is True  # Case insensitive
    assert SearchUtils.matches_search(obj, "Archery") is True


def test_matches_search_no_match():
    """Test matches_search returns False when no match found."""
    obj = MockEntity(
        name="Entity",
        type="Character",
        description="A simple merchant",
        tags=["npc"],
        attributes={"location": "Market"},
    )

    assert SearchUtils.matches_search(obj, "dragon") is False
    assert SearchUtils.matches_search(obj, "wizard") is False


def test_matches_search_with_dict():
    """Test matches_search works with dictionaries."""
    obj = {
        "name": "Test Entity",
        "type": "Location",
        "description": "A mystical forest",
        "tags": ["magic", "forest"],
        "attributes": {"biome": "temperate"},
    }

    assert SearchUtils.matches_search(obj, "Test") is True
    assert SearchUtils.matches_search(obj, "Location") is True
    assert SearchUtils.matches_search(obj, "mystical") is True
    assert SearchUtils.matches_search(obj, "magic") is True
    assert SearchUtils.matches_search(obj, "temperate") is True


def test_matches_search_case_insensitive():
    """Test matches_search is case insensitive."""
    obj = MockEntity(name="DragonBorn", type="HERO", description="LEGENDARY Warrior")

    assert SearchUtils.matches_search(obj, "dragonborn") is True
    assert SearchUtils.matches_search(obj, "hero") is True
    assert SearchUtils.matches_search(obj, "legendary") is True
    assert SearchUtils.matches_search(obj, "DRAGON") is True


def test_matches_search_partial_match():
    """Test matches_search finds partial matches."""
    obj = MockEntity(name="Swordmaster", description="Master of swordsmanship")

    assert SearchUtils.matches_search(obj, "sword") is True
    assert SearchUtils.matches_search(obj, "master") is True
    assert SearchUtils.matches_search(obj, "ship") is True  # From "swordsmanship"


def test_matches_search_whitespace_handling():
    """Test matches_search handles whitespace in search term."""
    obj = MockEntity(name="Test Entity")

    assert SearchUtils.matches_search(obj, "  Test  ") is True
    assert SearchUtils.matches_search(obj, " Entity ") is True


def test_matches_search_missing_fields():
    """Test matches_search handles missing fields gracefully."""
    obj = MockEntity(name="Entity")

    # Should not crash with missing fields
    assert SearchUtils.matches_search(obj, "Entity") is True
    assert SearchUtils.matches_search(obj, "nonexistent") is False


def test_matches_search_none_values():
    """Test matches_search handles None values gracefully."""
    obj = {
        "name": None,
        "type": None,
        "description": None,
        "tags": None,
        "attributes": None,
    }

    # Should not crash with None values
    assert SearchUtils.matches_search(obj, "test") is False


def test_matches_search_empty_tags():
    """Test matches_search handles empty tags list."""
    obj = MockEntity(name="Entity", tags=[])

    assert SearchUtils.matches_search(obj, "Entity") is True
    assert SearchUtils.matches_search(obj, "nonexistent") is False


def test_matches_search_empty_attributes():
    """Test matches_search handles empty attributes dict."""
    obj = MockEntity(name="Entity", attributes={})

    assert SearchUtils.matches_search(obj, "Entity") is True
    assert SearchUtils.matches_search(obj, "nonexistent") is False


def test_matches_search_non_string_attribute_values():
    """Test matches_search handles non-string attribute values."""
    obj = MockEntity(
        name="Entity",
        attributes={"level": 42, "health": 100.5, "active": True, "location": "Castle"},
    )

    # Should match string attribute
    assert SearchUtils.matches_search(obj, "Castle") is True
    # Should not crash on non-string attributes
    assert SearchUtils.matches_search(obj, "42") is False


def test_matches_search_multiple_fields():
    """Test that search can match across multiple fields."""
    obj = MockEntity(
        name="Dragon",
        type="Monster",
        description="Fire-breathing dragon",
        tags=["boss", "legendary"],
        attributes={"element": "fire"},
    )

    # All of these should match
    assert SearchUtils.matches_search(obj, "dragon") is True
    assert SearchUtils.matches_search(obj, "monster") is True
    assert SearchUtils.matches_search(obj, "fire") is True
    assert SearchUtils.matches_search(obj, "boss") is True
    assert SearchUtils.matches_search(obj, "legendary") is True


def test_matches_search_priority():
    """Test that matches_search checks fields in logical order."""
    # Test that name is checked (should match)
    obj = MockEntity(name="Dragon")
    assert SearchUtils.matches_search(obj, "Dragon") is True

    # Even if type would also match
    obj2 = MockEntity(name="Dragon", type="Monster")
    assert SearchUtils.matches_search(obj2, "Dragon") is True
