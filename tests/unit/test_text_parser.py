"""
Unit tests for WikiLinkParser service.
"""

from src.services.text_parser import WikiLinkParser


def test_extract_simple_link():
    """Test extracting a single simple link."""
    text = "Hello [[Gandalf]] there."
    links = WikiLinkParser.extract_links(text)
    assert "Gandalf" in links
    assert len(links) == 1


def test_extract_link_with_label():
    """Test extracting a link with a label (pipe syntax)."""
    text = "Visit [[The Shire|Shire]] today."
    links = WikiLinkParser.extract_links(text)
    assert "The Shire" in links
    assert "Shire" not in links
    assert len(links) == 1


def test_extract_multiple_links():
    """Test extracting multiple links."""
    text = "[[Alice]] and [[Bob]] went to [[The Market]]."
    links = WikiLinkParser.extract_links(text)
    assert links == {"Alice", "Bob", "The Market"}


def test_extract_unique_links():
    """Test that duplicate links are deduplicated."""
    text = "[[Echo]] [[Echo]] [[Echo]]"
    links = WikiLinkParser.extract_links(text)
    assert links == {"Echo"}


def test_extract_no_links():
    """Test text with no links."""
    text = "Just plain text."
    links = WikiLinkParser.extract_links(text)
    assert len(links) == 0


def test_extract_empty_text():
    """Test empty input."""
    links = WikiLinkParser.extract_links("")
    assert len(links) == 0


def test_whitespace_handling():
    """Test trimming of whitespace inside brackets."""
    text = "[[  Spaced Out  ]]"
    links = WikiLinkParser.extract_links(text)
    assert "Spaced Out" in links
