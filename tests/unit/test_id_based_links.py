"""
Unit tests for ID-based wiki links.

Tests the new ID-based linking format: [[id:UUID|DisplayName]]
"""

import pytest
from src.services.text_parser import WikiLinkParser, LinkCandidate


def test_parse_id_based_link():
    """Test parsing ID-based link format."""
    text = "See [[id:550e8400-e29b-41d4-a716-446655440000|Gandalf]] for details."
    links = WikiLinkParser.extract_links(text)

    assert len(links) == 1
    link = links[0]
    assert link.is_id_based is True
    assert link.target_id == "550e8400-e29b-41d4-a716-446655440000"
    assert link.modifier == "Gandalf"
    assert link.name is None
    assert link.span == (4, 55)  # Corrected end position


def test_parse_legacy_name_link():
    """Test parsing legacy name-based link format."""
    text = "See [[Gandalf]] for details."
    links = WikiLinkParser.extract_links(text)

    assert len(links) == 1
    link = links[0]
    assert link.is_id_based is False
    assert link.target_id is None
    assert link.name == "Gandalf"
    assert link.modifier is None


def test_parse_legacy_name_with_label():
    """Test parsing legacy name-based link with label."""
    text = "See [[Gandalf|the Grey Wizard]] for details."
    links = WikiLinkParser.extract_links(text)

    assert len(links) == 1
    link = links[0]
    assert link.is_id_based is False
    assert link.target_id is None
    assert link.name == "Gandalf"
    assert link.modifier == "the Grey Wizard"


def test_parse_mixed_links():
    """Test parsing both ID-based and name-based links in same text."""
    text = (
        "[[Frodo]] met [[id:550e8400-e29b-41d4-a716-446655440000|Gandalf]] "
        "and went to [[id:a1b2c3d4-e5f6-4789-0abc-def123456789|Rivendell]]."
    )
    links = WikiLinkParser.extract_links(text)

    assert len(links) == 3

    # First: legacy name
    assert links[0].is_id_based is False
    assert links[0].name == "Frodo"

    # Second: ID-based
    assert links[1].is_id_based is True
    assert links[1].target_id == "550e8400-e29b-41d4-a716-446655440000"
    assert links[1].modifier == "Gandalf"

    # Third: ID-based
    assert links[2].is_id_based is True
    assert links[2].target_id == "a1b2c3d4-e5f6-4789-0abc-def123456789"
    assert links[2].modifier == "Rivendell"


def test_format_id_link():
    """Test creating ID-based link string."""
    result = WikiLinkParser.format_id_link(
        "550e8400-e29b-41d4-a716-446655440000", "Gandalf the Grey"
    )
    assert result == "[[id:550e8400-e29b-41d4-a716-446655440000|Gandalf the Grey]]"


def test_format_name_link():
    """Test creating name-based link string."""
    result = WikiLinkParser.format_name_link("Gandalf")
    assert result == "[[Gandalf]]"


def test_format_name_link_with_label():
    """Test creating name-based link with label."""
    result = WikiLinkParser.format_name_link("Gandalf", "the Grey")
    assert result == "[[Gandalf|the Grey]]"


def test_id_case_insensitive():
    """Test that ID matching is case-insensitive (UUIDs can be uppercase)."""
    text = "See [[id:550E8400-E29B-41D4-A716-446655440000|Test]] here."
    links = WikiLinkParser.extract_links(text)

    assert len(links) == 1
    assert links[0].is_id_based is True
    # UUID should be extracted as-is
    assert links[0].target_id == "550E8400-E29B-41D4-A716-446655440000"


def test_id_without_display_name():
    """Test ID-based link without display name (edge case)."""
    text = "See [[id:550e8400-e29b-41d4-a716-446655440000]] here."
    links = WikiLinkParser.extract_links(text)

    assert len(links) == 1
    link = links[0]
    assert link.is_id_based is True
    assert link.target_id == "550e8400-e29b-41d4-a716-446655440000"
    assert link.modifier is None  # No display name provided


def test_invalid_id_format_treated_as_name():
    """Test that invalid ID format is treated as name-based link."""
    # Not a valid UUID
    text = "See [[id:not-a-uuid|Test]] here."
    links = WikiLinkParser.extract_links(text)

    assert len(links) == 1
    link = links[0]
    # Should be treated as name-based since UUID format is invalid
    assert link.is_id_based is False
    assert link.name == "id:not-a-uuid"
    assert link.modifier == "Test"


def test_span_correctness_id_based():
    """Test that span offsets are correct for ID-based links."""
    text = "Start [[id:550e8400-e29b-41d4-a716-446655440000|Gandalf]] end."
    links = WikiLinkParser.extract_links(text)

    assert len(links) == 1
    start, end = links[0].span

    # Extract the matched text and verify
    matched_text = text[start:end]
    assert matched_text == "[[id:550e8400-e29b-41d4-a716-446655440000|Gandalf]]"


def test_adjacent_id_links():
    """Test parsing adjacent ID-based links."""
    text = (
        "[[id:550e8400-e29b-41d4-a716-446655440000|A]]"
        "[[id:a1b2c3d4-e5f6-4789-0abc-def123456789|B]]"
    )
    links = WikiLinkParser.extract_links(text)

    assert len(links) == 2
    assert links[0].target_id == "550e8400-e29b-41d4-a716-446655440000"
    assert links[1].target_id == "a1b2c3d4-e5f6-4789-0abc-def123456789"


def test_whitespace_in_id_link():
    """Test that whitespace in ID-based links is handled correctly."""
    text = "[[id:550e8400-e29b-41d4-a716-446655440000 | Gandalf the Grey ]]"
    links = WikiLinkParser.extract_links(text)

    assert len(links) == 1
    # Name should have leading "id:" but trailing whitespace stripped
    # This is because the regex captures before pipe, then strips
    link = links[0]
    # The regex should capture "id:550e8400-e29b-41d4-a716-446655440000 "
    # Then we strip, so: "id:550e8400-e29b-41d4-a716-446655440000"
    # But the ID regex requires no trailing space, so this should still work
    assert link.is_id_based is True
    assert link.modifier.strip() == "Gandalf the Grey"
