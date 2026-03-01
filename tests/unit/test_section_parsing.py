"""Tests for section parsing and coloring logic in WikiTextEdit."""


from src.gui.widgets.wiki_text_edit import WikiTextEdit


def test_section_manager_initializes(qtbot):
    """Test that SectionManager initializes on editor creation."""
    widget = WikiTextEdit()
    qtbot.addWidget(widget)

    # Editor should have a section manager instance
    assert hasattr(widget.editor, "_section_manager")
    assert widget.editor._section_manager is not None


def test_section_parsing_assigns_user_data(qtbot):
    """Test that headings and paragraphs are grouped with user data."""
    widget = WikiTextEdit()
    qtbot.addWidget(widget)

    # Set some initial text with headings
    markdown_text = (
        "# Chapter 1\n"
        "Some text for chapter 1.\n"
        "\n"
        "## Sub-section\n"
        "Text in sub-section."
    )
    widget.set_wiki_text(markdown_text)

    # Force a synchronous parse
    widget.editor._section_manager._analyze_document()

    # Verify Block User Data
    doc = widget.document()

    # Block 0: "# Chapter 1"
    block0 = doc.findBlockByNumber(0)
    data0 = block0.userData()
    assert data0 is not None
    assert hasattr(data0, "section_id")
    assert data0.section_id is not None
    assert data0.heading_level == 1

    # Block 1: "Some text for chapter 1."
    block1 = doc.findBlockByNumber(1)
    data1 = block1.userData()
    assert data1 is not None
    assert data1.section_id == data0.section_id  # Should belong to Chapter 1
    assert data1.heading_level == 0

    # ... we will add more assertions once the structure is defined
