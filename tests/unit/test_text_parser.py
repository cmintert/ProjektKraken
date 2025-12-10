"""
Unit tests for WikiLinkParser service.
Tests the new LinkCandidate-based parser.
"""

from src.services.text_parser import WikiLinkParser, LinkCandidate


def test_extract_simple_link():
    """Test extracting a single simple link."""
    text = "Hello [[Gandalf]] there."
    links = WikiLinkParser.extract_links(text)
    
    assert len(links) == 1
    assert links[0].name == "Gandalf"
    assert links[0].modifier is None
    assert links[0].raw_text == "[[Gandalf]]"
    assert links[0].span == (6, 17)


def test_extract_link_with_label():
    """Test extracting a link with a label (pipe syntax)."""
    text = "Visit [[The Shire|Shire]] today."
    links = WikiLinkParser.extract_links(text)
    
    assert len(links) == 1
    assert links[0].name == "The Shire"
    assert links[0].modifier == "Shire"
    assert links[0].raw_text == "[[The Shire|Shire]]"
    assert links[0].span == (6, 25)


def test_extract_multiple_links():
    """Test extracting multiple links in order."""
    text = "[[Alice]] and [[Bob]] went to [[The Market]]."
    links = WikiLinkParser.extract_links(text)
    
    assert len(links) == 3
    assert links[0].name == "Alice"
    assert links[1].name == "Bob"
    assert links[2].name == "The Market"


def test_extract_duplicate_links():
    """Test that duplicate links are preserved (not deduplicated)."""
    text = "[[Echo]] [[Echo]] [[Echo]]"
    links = WikiLinkParser.extract_links(text)
    
    assert len(links) == 3
    assert all(link.name == "Echo" for link in links)
    # Verify different offsets
    assert links[0].span == (0, 8)
    assert links[1].span == (9, 17)
    assert links[2].span == (18, 26)


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
    
    assert len(links) == 1
    assert links[0].name == "Spaced Out"


def test_offset_correctness():
    """Test that offsets are accurate for extraction."""
    text = "Start [[First]] middle [[Second|2nd]] end."
    links = WikiLinkParser.extract_links(text)
    
    assert len(links) == 2
    
    # First link
    assert links[0].name == "First"
    assert links[0].span == (6, 15)
    assert text[links[0].span[0]:links[0].span[1]] == "[[First]]"
    
    # Second link
    assert links[1].name == "Second"
    assert links[1].modifier == "2nd"
    assert links[1].span == (23, 37)
    assert text[links[1].span[0]:links[1].span[1]] == "[[Second|2nd]]"


def test_pipe_with_whitespace():
    """Test pipe modifier with whitespace is trimmed."""
    text = "Link to [[Target  |  Label  ]]."
    links = WikiLinkParser.extract_links(text)
    
    assert len(links) == 1
    assert links[0].name == "Target"
    assert links[0].modifier == "Label"


def test_nested_brackets_rejected():
    """Test that nested brackets don't match."""
    text = "This [[has [[nested]] brackets]] here."
    links = WikiLinkParser.extract_links(text)
    
    # Should only match [[nested]] due to regex constraints
    assert len(links) == 1
    assert links[0].name == "nested"


def test_link_at_start():
    """Test link at the very start of text."""
    text = "[[Start]] of text."
    links = WikiLinkParser.extract_links(text)
    
    assert len(links) == 1
    assert links[0].span == (0, 9)


def test_link_at_end():
    """Test link at the very end of text."""
    text = "End of text [[End]]"
    links = WikiLinkParser.extract_links(text)
    
    assert len(links) == 1
    assert links[0].span == (12, 19)


def test_adjacent_links():
    """Test adjacent links without space."""
    text = "[[First]][[Second]]"
    links = WikiLinkParser.extract_links(text)
    
    assert len(links) == 2
    assert links[0].name == "First"
    assert links[0].span == (0, 9)
    assert links[1].name == "Second"
    assert links[1].span == (9, 19)
